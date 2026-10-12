#!/usr/bin/env python3
"""Read-only HCP ROI backend acceptance, NOT a full-brain/clinical validation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import dipy
import nibabel as nib
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_INPUT = Path("/data/chengjin/SlicerDDSurfer-test/100307/input")
DEFAULT_EVIDENCE = REPO_ROOT / "ignore/validation/brain_mask_backends_20261012/dki"
DIPY_SOURCE = "https://docs.dipy.org/stable/examples_built/reconstruction/reconst_dki.html"
LIMITATION = (
    "Small spatial ROI acceptance only, using supplied mask and unsmoothed observations. "
    "Agreement with the same upstream library is not independent algorithm validation, "
    "an anatomical-quality assessment, a full-brain fit, or clinical evidence."
)


def fingerprint(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    stat = path.stat()
    return {"path": str(path.resolve()), "sha256": digest.hexdigest(), "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns}


def stream_roi(image: nib.Nifti1Image, source: Path, start: np.ndarray, side: int) -> np.ndarray:
    """Read each on-disk volume once; never materialize the full 4D HCP image."""
    if len(image.shape) != 4 or image.dataobj.order != "F":
        raise ValueError("ROI extractor requires a 4D Fortran-order NIfTI source")
    spatial = image.shape[:3]
    roi = tuple(slice(int(value), int(value) + side) for value in start)
    output = np.empty((side, side, side, image.shape[3]), dtype=np.float32)
    count = int(np.prod(spatial))
    dtype = image.dataobj.dtype
    volume_bytes = count * dtype.itemsize
    opener = gzip.open if source.name.endswith(".gz") else open
    with opener(source, "rb") as stream:
        stream.seek(image.dataobj.offset)
        for index in range(image.shape[3]):
            block = stream.read(volume_bytes)
            if len(block) != volume_bytes:
                raise ValueError(f"Truncated NIfTI source at volume {index}")
            volume = np.frombuffer(block, dtype=dtype).reshape(spatial, order="F")
            output[..., index] = volume[roi] * image.dataobj.slope + image.dataobj.inter
    return output


def prepare_roi(input_root: Path, evidence_dir: Path, *, side: int = 4, center=None) -> dict:
    input_root, evidence_dir = input_root.resolve(), evidence_dir.resolve()
    if evidence_dir == input_root or input_root in evidence_dir.parents or evidence_dir in input_root.parents:
        raise ValueError("Evidence directory must be separate from source inputs")
    paths = {"dwi": input_root / "data.nii.gz", "bval": input_root / "bvals", "bvec": input_root / "bvecs",
             "mask": input_root / "nodif_brain_mask.nii.gz"}
    before = {name: fingerprint(path) for name, path in paths.items()}
    image = nib.load(paths["dwi"])
    mask_image = nib.load(paths["mask"])
    mask = np.asarray(mask_image.dataobj)
    if mask.shape != image.shape[:3] or not np.allclose(mask_image.affine, image.affine, rtol=0, atol=1e-4):
        raise ValueError("Supplied mask does not match the source image grid")
    if not np.isfinite(mask).all() or not np.all((mask == 0) | (mask == 1)) or not mask.any():
        raise ValueError("Supplied mask must be finite, binary and nonempty")
    if side < 2:
        raise ValueError("ROI side must be at least two voxels")
    center = np.asarray(center if center is not None else np.median(np.argwhere(mask), axis=0), dtype=int)
    start = center - side // 2
    if center.shape != (3,) or np.any(start < 0) or np.any(start + side > image.shape[:3]):
        raise ValueError("Requested ROI is outside the source grid")
    slices = tuple(slice(int(value), int(value) + side) for value in start)
    cropped_mask = mask[slices].astype(np.uint8)
    if not cropped_mask.any():
        raise ValueError("Requested ROI contains no supplied-mask voxels")
    print(f"Streaming {image.shape[3]} volumes into a {side}^3 voxel ROI", flush=True)
    data = stream_roi(image, paths["dwi"], start, side)
    affine = image.affine.copy()
    affine[:3, 3] = (image.affine @ np.r_[start, 1])[:3]
    subject = evidence_dir / "hcp100307_roi"
    inputs = subject / "input"
    inputs.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(data, affine), inputs / "data.nii.gz")
    nib.save(nib.Nifti1Image(cropped_mask, affine), inputs / "nodif_brain_mask.nii.gz")
    for key, name in (("bval", "bvals"), ("bvec", "bvecs")):
        (inputs / name).write_bytes(paths[key].read_bytes())
    after = {name: fingerprint(path) for name, path in paths.items()}
    if before != after:
        raise RuntimeError("Source fingerprints changed during read-only ROI extraction")
    payload = {
        "kind": "dki_real_roi_preparation", "status": "prepared_backend_not_yet_checked",
        "created_at": datetime.now(timezone.utc).isoformat(), "source_subject": "HCP100307",
        "scope": "small_spatial_roi_only", "limitation": LIMITATION,
        "source_inputs": before, "source_inputs_unchanged": True, "subject_root": str(subject),
        "source_shape": list(image.shape), "roi_start": start.tolist(),
        "roi_stop_exclusive": (start + side).tolist(), "roi_shape": list(data.shape),
        "roi_affine": affine.tolist(), "supplied_mask_voxels": int(cropped_mask.sum()),
        "smoothing": "none", "denoising": "none", "resampling": "none",
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "nibabel": nib.__version__, "dipy": dipy.__version__},
        "reference_documentation": DIPY_SOURCE,
    }
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "roi_preparation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="ascii")
    return payload


def verify_backend(evidence_dir: Path) -> dict:
    """Verify a previously prepared real ROI against direct upstream DIPY."""
    from dipy.core.gradients import gradient_table
    from dipy.reconst.dki import DiffusionKurtosisModel
    from microstructure.dki import DkiConfig, DKI_METRICS, inspect_dki_inputs, run_dki
    from shared.pipeline import RawInputBundle

    evidence_dir = evidence_dir.resolve()
    preparation = json.loads((evidence_dir / "roi_preparation.json").read_text())
    subject = Path(preparation["subject_root"])
    inputs = subject / "input"
    bundle = RawInputBundle(subject, "100307", inputs, inputs / "data.nii.gz", inputs / "bvals",
                            inputs / "bvecs", inputs / "nodif_brain_mask.nii.gz")
    config = DkiConfig("100307", bundle, subject / "outputs/02_microstructure/dki")
    before = {name: fingerprint(path) for name, path in {
        "dwi": bundle.dwi_path, "bval": bundle.bval_path, "bvec": bundle.bvec_path, "mask": bundle.mask_path}.items()}
    info = inspect_dki_inputs(config)
    if not info["eligible"]:
        raise ValueError(info["reasons"])
    started = time.perf_counter()
    result = run_dki(config)
    mask = np.asarray(nib.load(bundle.mask_path).dataobj) > 0
    data = nib.load(bundle.dwi_path).get_fdata()[mask][:, info["selected_volumes"]]
    bvals = np.loadtxt(bundle.bval_path).reshape(-1)[info["selected_volumes"]]
    bvecs = np.loadtxt(bundle.bvec_path).T[info["selected_volumes"]].copy()
    bvecs[bvals <= config.b0_threshold] = 0
    gtab = gradient_table(bvals, bvecs=bvecs, b0_threshold=config.b0_threshold, atol=0.01)
    fit = DiffusionKurtosisModel(gtab, fit_method="WLS", return_S0_hat=True, min_signal=1e-6).fit(data)
    differences = {}
    for key in DKI_METRICS:
        direct = np.asarray(fit.kfa if key == "kfa" else getattr(fit, key)(min_kurtosis=None, max_kurtosis=None))
        backend = nib.load(result.outputs[f"{key}_raw"]).get_fdata()[mask]
        np.testing.assert_allclose(backend, direct, rtol=1e-5, atol=2e-6)
        differences[key] = float(np.max(np.abs(backend - direct)))
    direct_rmse = np.sqrt(np.mean((fit.predict(gtab, S0=fit.model_S0) - data) ** 2, axis=1))
    np.testing.assert_allclose(nib.load(result.rmse_path).get_fdata()[mask], direct_rmse, rtol=1e-5, atol=2e-6)
    reused = run_dki(config)
    assert reused.status == "cached"
    after = {name: fingerprint(Path(record["path"])) for name, record in before.items()}
    assert before == after, "Prepared real ROI inputs changed"
    qc = json.loads(result.qc_path.read_text())
    payload = {
        "kind": "dki_real_roi_backend_acceptance", "status": "PASS", "scope": "small_spatial_roi_only",
        "limitation": LIMITATION, "source_subject": "HCP100307", "roi_inputs_unchanged": True,
        "eligibility": info, "map_max_abs_difference_vs_direct_dipy": differences,
        "fit_voxels": qc["fitted_voxels"], "valid_voxels": qc["valid_voxels"],
        "median_nrmse": float(np.median(nib.load(result.nrmse_path).get_fdata()[mask])),
        "cached_rerun": reused.status, "elapsed_seconds": time.perf_counter() - started,
        "qc_path": str(result.qc_path), "human_review": "pending",
        "mkcurve_scientific_run": "NOT_RUN: no MATLAB runtime", "original_source_inputs": preparation["source_inputs"],
    }
    (evidence_dir / "backend_acceptance.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--roi-side", type=int, default=4)
    parser.add_argument("--roi-center", type=int, nargs=3)
    parser.add_argument("--prepare-only", action="store_true",
                        help="Prepare a real unsmoothed ROI; do not claim backend acceptance")
    parser.add_argument("--verify-backend", action="store_true", help="Verify the previously prepared real ROI against direct DIPY")
    args = parser.parse_args(argv)
    started = time.perf_counter()
    if args.verify_backend:
        print(json.dumps(verify_backend(args.evidence_dir), indent=2))
        return 0
    if not args.prepare_only:
        parser.error("Specify --prepare-only or --verify-backend")
    payload = prepare_roi(args.input_root, args.evidence_dir, side=args.roi_side, center=args.roi_center)
    print(json.dumps({"status": payload["status"], "roi_shape": payload["roi_shape"],
                      "elapsed_seconds": time.perf_counter() - started, "limitation": LIMITATION}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
