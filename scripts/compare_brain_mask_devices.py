#!/usr/bin/env python3
"""Compare real same-input mask acceptances without claiming ground-truth accuracy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import nibabel as nib
import numpy as np


def load(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("status") != "pass":
        raise ValueError(f"Acceptance did not pass: {path}")
    result = record["result"]
    image_path = path.parent / Path(result["mask_path"]).name
    image = nib.load(str(image_path))
    values = np.asarray(image.dataobj)
    if not np.isfinite(values).all() or not np.all((values == 0) | (values == 1)) or not np.any(values):
        raise ValueError(f"Invalid mask: {image_path}")
    log_path = path.parent.parent / (path.parent.name + ".log")
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else result.get("stdout_tail", "")
    phases = {}
    for name, key in (("Pre-Processing", "preprocessing"), ("Masking", "cnn_models"), ("Total", "pnl_internal_total")):
        match = re.search(re.escape(name) + r" Time Taken\s*:\s*([\d.]+)\s*min", log)
        phases[key] = float(match.group(1)) * 60 if match else None
    summary = {
        "source": str(path.resolve()), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "mask": str(image_path.resolve()), "mask_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "acceptance_seconds": record["seconds"], "device": result.get("device_execution"),
        "brain_voxels": int(np.count_nonzero(values)), "rounded_log_phase_seconds": phases,
        "supplied_mask_unchanged": record.get("supplied_mask_unchanged"),
    }
    return record, image, values.astype(bool), summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runs = [load(path) for path in args.reports]
    comparisons = []
    for index, (record, image, mask, summary) in enumerate(runs[1:], 1):
        reference, reference_image, reference_mask, reference_summary = runs[0]
        inputs = lambda r: [item["sha256"] for item in r["result"]["signature"]["inputs"]]
        if inputs(record) != inputs(reference):
            raise ValueError("Cannot compare timings/masks as paired evidence: input hashes differ")
        if mask.shape != reference_mask.shape or not np.allclose(image.affine, reference_image.affine, rtol=0, atol=1e-4):
            raise ValueError("Native mask geometry differs")
        intersection = int(np.count_nonzero(mask & reference_mask))
        comparisons.append({
            "reference": reference_summary["source"], "comparison": summary["source"],
            "same_input_hashes": True, "same_native_geometry": True,
            "dice": 2 * intersection / (int(np.count_nonzero(mask)) + int(np.count_nonzero(reference_mask))),
            "different_voxels": int(np.count_nonzero(mask != reference_mask)),
            "reference_seconds": reference_summary["acceptance_seconds"], "comparison_seconds": summary["acceptance_seconds"],
        })
    output = {"kind": "brain_mask_device_comparison", "status": "integrity_pass",
              "runs": [run[3] for run in runs], "comparisons": comparisons,
              "scope": "Same-input repeated real inference; Dice is agreement, not anatomical accuracy. Full wall time includes hashing/b0/registration/QC, not Docker startup or installation. Log phases are rounded.",
              "anatomical_review": "pending"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
