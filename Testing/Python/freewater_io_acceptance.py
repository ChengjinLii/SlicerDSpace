#!/usr/bin/env python3
"""Real HCP ROI parity for changed Free Water I/O, NOT full-brain fitting QC."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def run(subject, report_dir):
    import nibabel as nib
    import numpy as np
    from dipy.core.gradients import gradient_table
    from dipy.reconst.fwdti import FreeWaterTensorModel
    from shared.pipeline import RawInputBundle
    from microstructure.pipeline import (MicrostructureConfig, _output_paths, _compute_free_water_maps,
                                         _sanitize_free_water_scalars, _load_bvals_bvecs)

    inputs = subject / "input"
    raw = RawInputBundle(subject, "100307", inputs, inputs / "data.nii.gz", inputs / "bvals",
                         inputs / "bvecs", inputs / "nodif_brain_mask.nii.gz")
    source_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (
        raw.dwi_path, raw.bval_path, raw.bvec_path, raw.mask_path)}
    config = MicrostructureConfig("100307", raw, None, report_dir)
    paths = _output_paths("100307", report_dir)
    start = time.perf_counter()
    _compute_free_water_maps(config=config, paths=paths)
    elapsed = time.perf_counter() - start
    mask = np.asarray(nib.load(raw.mask_path).dataobj) > 0
    data = nib.load(raw.dwi_path).get_fdata(dtype=np.float32)[mask]
    bvals, bvecs = _load_bvals_bvecs(raw)
    fitted = FreeWaterTensorModel(gradient_table(bvals, bvecs=bvecs, b0_threshold=50), fit_method="WLS").fit(data)
    expected = _sanitize_free_water_scalars(fitted.f, fitted.fa, fitted.md, fitted.evals, max_free_water_fraction=.7)
    checks = {}
    for key, reference in zip(("fwf", "fw_tissue_fa", "fw_tissue_md", "fw_tissue_valid_mask"), expected[:4]):
        actual = nib.load(paths[key]).get_fdata(dtype=np.float32)[mask]
        checks[key] = {"max_abs_error": float(np.max(np.abs(actual - reference))),
                       "equal": bool(np.allclose(actual, reference, rtol=1e-6, atol=1e-8))}
    payload = {"kind": "real_roi_freewater_io_parity", "scope": "64-voxel real HCP spatial ROI; not full-brain runtime or anatomical accuracy",
               "runtime_seconds": elapsed, "mask_voxels": int(mask.sum()), "checks": checks,
               "inputs_unchanged": all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == value for path, value in source_hashes.items()),
               "source_sha256": source_hashes}
    payload["passed"] = payload["inputs_unchanged"] and all(check["equal"] for check in checks.values())
    (report_dir / "acceptance.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2), flush=True)
    if not payload["passed"]:
        raise RuntimeError("Free Water I/O changed real ROI fitting results")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.subject.resolve(), args.report_dir.resolve())
