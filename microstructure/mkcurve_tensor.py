# Python translation of lib/DKI/{dki_fit,dki_mk_only,dki_parameters}.m
# Copyright (c) 2017 New York University and University of Antwerp.
# Modifications: Python translation for SlicerDDSurfer, 2026.
# This file and mkcurve_directions.json are covered by MPL-2.0.
# See licenses/MK-Curve-DKI-MPL-2.0.txt. Not an official upstream Python release.
"""Unconstrained author-style WLLS and numerical kurtosis integration."""

from functools import lru_cache
from itertools import combinations_with_replacement
import json
from math import factorial
from pathlib import Path

import numpy as np
from scipy.linalg import lstsq


def tensor_basis(directions, order):
    directions = np.asarray(directions, dtype=np.float64)
    indices = list(combinations_with_replacement(range(3), order))
    counts = [factorial(order) / np.prod([factorial(index.count(j)) for j in range(3)]) for index in indices]
    return np.stack([np.prod(directions[..., index], axis=-1) * count
                     for index, count in zip(indices, counts)], axis=-1)


@lru_cache(maxsize=1)
def integration_directions():
    directions = np.asarray(json.loads(Path(__file__).with_name("mkcurve_directions.json").read_text()), dtype=float)
    if directions.shape != (256, 3) or not np.isfinite(directions).all():
        raise ValueError("Invalid author MK-Curve integration directions")
    directions.setflags(write=False)
    return directions


def design_matrix(bvals, bvecs):
    bvals = np.asarray(bvals, dtype=float).reshape(-1)
    directions = np.asarray(bvecs, dtype=float).copy()
    if directions.shape != (len(bvals), 3) or not np.isfinite(directions).all() or not np.isfinite(bvals).all():
        raise ValueError("MK-Curve gradient dimensions/values are invalid")
    norms = np.linalg.norm(directions, axis=1, keepdims=True)
    directions /= np.where(norms > 0, norms, 1)
    return np.column_stack((np.ones(len(bvals)), -bvals[:, None] * tensor_basis(directions, 2),
                            bvals[:, None] ** 2 / 6 * tensor_basis(directions, 4)))


def fit_wlls(signals, design, *, solver="reference"):
    """Return log(S0), six D and fifteen unnormalised fourth-order coefficients.

    As upstream: OLS initialization, predicted-signal weights, one WLLS solve.
    Column equilibration changes the solver conditioning, not its objective.
    No eigenvalue/kurtosis clipping, constraints, or iterative reweighting.
    """
    if solver not in {"reference", "batched"}:
        raise ValueError("MK-Curve solver must be reference or batched")
    signals = np.asarray(signals, dtype=np.float64)
    if signals.ndim != 2 or signals.shape[1] != len(design):
        raise ValueError("MK-Curve signals must be voxels x measurements")
    output = np.full((len(signals), 22), np.nan)
    scale = np.linalg.norm(design, axis=0)
    if np.any(scale == 0) or np.linalg.cond(design) > 1e15:
        return output
    scaled = design / scale
    if np.linalg.matrix_rank(scaled) < 22:
        return output
    valid = np.isfinite(signals).all(axis=1)
    logs = np.log(np.maximum(signals[valid], np.finfo(float).eps))
    if not len(logs):
        return output
    initial = lstsq(scaled, logs.T, lapack_driver="gelsy")[0]
    with np.errstate(over="ignore", invalid="ignore"):
        weights = np.exp(scaled @ initial).T
    pending = np.ones(len(logs), dtype=bool)
    if solver == "batched":
        candidates = np.flatnonzero(np.isfinite(weights).all(axis=1) & (weights.max(axis=1) > 0))
        # Equilibrated normal systems are used only when well conditioned.
        # Ill-conditioned or rank-deficient rows retain the pivoted QR solve.
        for start in range(0, len(candidates), 256):
            ids = candidates[start:start + 256]
            w = weights[ids] / weights[ids].max(axis=1, keepdims=True)
            weighted = scaled * w[:, :, None]
            gram = weighted.transpose(0, 2, 1) @ weighted
            eigenvalues = np.linalg.eigvalsh(gram)
            safe = (eigenvalues[:, 0] > 0) & (eigenvalues[:, -1] < 1e6 * eigenvalues[:, 0])
            if not safe.any():
                continue
            rhs = weighted[safe].transpose(0, 2, 1) @ (logs[ids[safe]] * w[safe])[:, :, None]
            try:
                beta = np.linalg.solve(gram[safe], rhs)[:, :, 0] / scale
            except np.linalg.LinAlgError:
                continue
            good = np.isfinite(beta).all(axis=1)
            accepted = ids[safe][good]
            output[np.flatnonzero(valid)[accepted]] = beta[good]
            pending[accepted] = False
    for index, observed, weight in zip(np.flatnonzero(valid)[pending], logs[pending], weights[pending]):
        if not np.isfinite(weight).all() or not np.any(weight > 0):
            continue
        # Dividing all weights by a common factor leaves WLLS unchanged.
        weight = weight / weight.max()
        fit, _, rank, _ = lstsq(scaled * weight[:, None], observed * weight, lapack_driver="gelsy")
        if rank == 22:
            output[index] = fit / scale
    return output


def mean_kurtosis(coefficients):
    directions = integration_directions()
    adc = coefficients[:, 1:7] @ tensor_basis(directions, 2).T
    fourth = coefficients[:, 7:22] @ tensor_basis(directions, 4).T
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        result = np.mean(fourth / adc ** 2, axis=1)
        md_squared = np.mean(coefficients[:, [1, 4, 6]], axis=1) ** 2
    # Upstream W is normalized by MD^2: the algebraic cancellation is not
    # defined at zero MD, even if a direct numerator/ADC computation is finite.
    result[(md_squared == 0) | ~np.isfinite(md_squared)] = np.nan
    return result


def parameter_maps(coefficients):
    n = len(coefficients)
    maps = {key: np.full(n, np.nan) for key in ("fa", "md", "ad", "rd", "mk", "ak", "rk", "e1", "e2", "e3")}
    maps["mk"] = mean_kurtosis(coefficients)
    angles = np.arange(256) * (2 * np.pi / 256)
    equator = np.column_stack((np.cos(angles), np.sin(angles), np.zeros(256)))
    for index, beta in enumerate(coefficients):
        if not np.isfinite(beta).all():
            continue
        xx, xy, xz, yy, yz, zz = beta[1:7]
        matrix = np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])
        values, vectors = np.linalg.eigh(matrix)
        values, direction = values[::-1], vectors[:, -1]
        md = values.mean()
        with np.errstate(divide="ignore", invalid="ignore"):
            fa = np.sqrt(1.5 * np.sum((values - md) ** 2) / np.sum(values ** 2))
        maps["fa"][index], maps["md"][index] = fa, md
        maps["ad"][index], maps["rd"][index] = values[0], values[1:].mean()
        for key, value in zip(("e1", "e2", "e3"), values):
            maps[key][index] = value
        if md == 0:
            continue
        v = np.array([-direction[1], direction[0], 0.])
        s2, c = np.dot(v, v), direction[2]
        if s2 < 1e-24:
            radial = equator  # Well-defined equatorial plane at either pole.
        else:
            vx, vy, vz = v
            cross = np.array([[0, -vz, vy], [vz, 0, -vx], [-vy, vx, 0]])
            rotation = np.eye(3) + cross + cross @ cross * ((1 - c) / s2)
            radial = equator @ rotation.T
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            ak = (tensor_basis(direction[None, :], 4) @ beta[7:22])[0] / values[0] ** 2
            rk = np.mean((tensor_basis(radial, 4) @ beta[7:22]) / (tensor_basis(radial, 2) @ beta[1:7]) ** 2)
        maps["ak"][index], maps["rk"][index] = ak, rk
    return maps
