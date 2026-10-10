"""Anatomical orientation handling for DDSeg inference.

The DDSeg CNNs were trained on 2D slices of volumes whose array axes run
left->right, posterior->anterior and inferior->superior (RAS array order).
This was established empirically on two subjects with different storage
orientations (HCP 100307, LAS-stored; PPMI 3124, LPS-stored):

* the mean image stored inside each TorchScript model (MATLAB zerocenter mean
  of the training slices) correlates best with the subject's slice-averaged
  input when the input is in RAS/LAS order, and clearly worse for A-P or S-I
  flipped inputs; and
* world-space WM Dice against DDParcel is highest for RAS input on both
  subjects (RAS > RPS > LAS > LPS; RAI collapses the ventricles).

Earlier code applied fixed ``flipud``/``fliplr`` calls to the on-disk arrays.
Those flips are storage-order dependent (a LAS and an LPS file end up in
different anatomical orientations) and, because the features and the mask were
flipped differently, the prediction was written mirrored anterior-posterior.

This module instead reorients every input to the model orientation using the
image affine and maps predictions back with the exact inverse permutation/flip,
so the output shares the mask's on-disk voxel grid and affine.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
from nibabel.orientations import (
    aff2axcodes,
    apply_orientation,
    axcodes2ornt,
    io_orientation,
    ornt_transform,
)

MODEL_INPUT_AXCODES: tuple[str, str, str] = ("R", "A", "S")
ORIENTATION_CONVENTION = "affine_reoriented_ras_model_input_v2"

_SPACE_TO_RAS_SIGNS = {
    "right-anterior-superior": (1.0, 1.0, 1.0),
    "ras": (1.0, 1.0, 1.0),
    "left-posterior-superior": (-1.0, -1.0, 1.0),
    "lps": (-1.0, -1.0, 1.0),
    "left-anterior-superior": (-1.0, 1.0, 1.0),
    "las": (-1.0, 1.0, 1.0),
}


def axcodes(affine: np.ndarray) -> str:
    return "".join(str(code) for code in aff2axcodes(np.asarray(affine, dtype=np.float64)))


def nrrd_header_affine(header: Mapping[str, Any]) -> np.ndarray:
    """Return the RAS+ voxel-to-world affine described by a pynrrd header.

    ``space directions`` rows are the world vectors of the array axes in the
    header's ``space``; they are converted to RAS+ like ``space origin``.
    """

    space = str(header.get("space", "")).strip().lower()
    if space not in _SPACE_TO_RAS_SIGNS:
        raise ValueError(f"Unsupported or missing NRRD space '{header.get('space')}'; cannot determine orientation.")
    directions = header.get("space directions")
    if directions is None:
        raise ValueError("NRRD header has no 'space directions'; cannot determine orientation.")
    rows = [np.asarray(row, dtype=np.float64) for row in directions if row is not None and not np.all(np.isnan(np.asarray(row, dtype=np.float64)))]
    if len(rows) != 3 or any(row.shape != (3,) for row in rows):
        raise ValueError(f"Expected three spatial 'space directions' rows, got {directions!r}")
    origin = np.asarray(header.get("space origin", (0.0, 0.0, 0.0)), dtype=np.float64)
    signs = np.asarray(_SPACE_TO_RAS_SIGNS[space], dtype=np.float64)
    affine = np.eye(4, dtype=np.float64)
    affine[:3, :3] = (np.stack(rows, axis=0) * signs).T
    affine[:3, 3] = origin * signs
    return affine


def _to_model_transform(affine: np.ndarray) -> np.ndarray:
    return ornt_transform(io_orientation(np.asarray(affine, dtype=np.float64)), axcodes2ornt(MODEL_INPUT_AXCODES))


def _from_model_transform(affine: np.ndarray) -> np.ndarray:
    return ornt_transform(axcodes2ornt(MODEL_INPUT_AXCODES), io_orientation(np.asarray(affine, dtype=np.float64)))


def to_model_orientation(array: np.ndarray, affine: np.ndarray) -> np.ndarray:
    """Reorient an on-disk array (first three axes spatial) to the model's RAS order."""

    return np.ascontiguousarray(apply_orientation(np.asarray(array), _to_model_transform(affine)))


def from_model_orientation(array: np.ndarray, affine: np.ndarray) -> np.ndarray:
    """Exact inverse of :func:`to_model_orientation` for an image stored with ``affine``."""

    return np.ascontiguousarray(apply_orientation(np.asarray(array), _from_model_transform(affine)))


def require_same_orientation(reference_affine: np.ndarray, reference_shape, other_affine: np.ndarray, other_shape, label: str) -> float:
    """Fail loudly unless ``other`` is stored on the reference voxel grid orientation.

    Returns the maximum absolute affine difference (mm) for the QC record.
    """

    if tuple(int(v) for v in reference_shape[:3]) != tuple(int(v) for v in other_shape[:3]):
        raise ValueError(
            f"DDSeg input '{label}' has shape {tuple(other_shape[:3])}, expected the mask shape {tuple(reference_shape[:3])}."
        )
    if axcodes(reference_affine) != axcodes(other_affine):
        raise ValueError(
            f"DDSeg input '{label}' is stored as {axcodes(other_affine)} but the brain mask is {axcodes(reference_affine)}; "
            "features and mask must share one voxel grid."
        )
    return float(np.max(np.abs(np.asarray(reference_affine, dtype=np.float64) - np.asarray(other_affine, dtype=np.float64))))
