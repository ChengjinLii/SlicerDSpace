#!/usr/bin/env python3
"""Compare a real isolated NODDI refit to saved parameters, without modifying maps."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(original, refit, subject_id, mask, report):
    import nibabel as nib
    import numpy as np

    mask_data = np.asarray(nib.load(mask).dataobj) > 0
    rows = []
    for suffix in ("NDI", "ODI", "IsoVF", "RMSE", "NRMSE", "tissue_valid_mask"):
        name = f"{subject_id}_noddi_{suffix}.nii.gz"
        paths = [original / name, refit / name]
        images = [nib.load(path) for path in paths]
        arrays = [image.get_fdata(dtype=np.float32) for image in images]
        error = np.abs(arrays[0][mask_data] - arrays[1][mask_data])
        rows.append({"metric": suffix, "paths": [str(path.resolve()) for path in paths],
                     "file_sha256": [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths],
                     "exact_voxel_values": bool(np.array_equal(arrays[0], arrays[1], equal_nan=True)),
                     "max_absolute_difference_in_brain": float(np.max(error)),
                     "mean_absolute_difference_in_brain": float(np.mean(error)),
                     "same_grid": images[0].shape == images[1].shape and bool(np.array_equal(images[0].affine, images[1].affine))})
    payload = {"kind": "real_noddi_refit_output_comparison", "subject_id": subject_id, "metrics": rows,
               "scope": "Implementation/numerical repeatability, NOT independent anatomical accuracy."}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("original", "refit", "mask", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--subject-id", required=True)
    args = parser.parse_args()
    run(args.original, args.refit, args.subject_id, args.mask, args.report)
