#!/usr/bin/env python3
"""Run real MRtrix ACT preparation without changing archived subject outputs."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import nibabel as nib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.orchestrator import _resolve_parcellation, _resolve_segmentation
from tractography.act_prep import ACTPrepConfig, run_act_prep


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", required=True, type=Path)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--mrtrix-bin-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Use a new output directory to retain independent validation evidence.")
    segmentation = _resolve_segmentation(args.subject_root)
    parcellation = _resolve_parcellation(args.subject_root, args.subject_id)
    if segmentation is None or parcellation is None:
        parser.error("Both DDSeg and DDParcel outputs are required.")
    started = time.perf_counter()
    result = run_act_prep(ACTPrepConfig(args.subject_id, segmentation, args.output_dir,
        execute=True, parcellation_path=parcellation, mrtrix_bin_dir=args.mrtrix_bin_dir), log=print)
    elapsed = time.perf_counter() - started
    image = nib.load(result.five_tt_path)
    data = np.asarray(image.dataobj)
    source = nib.load(segmentation)
    foreground = np.asarray(source.dataobj) > 0
    qc = json.loads(result.qc_path.read_text())
    checks = {
        "finite": bool(np.isfinite(data).all()),
        "nonnegative": bool((data >= 0).all()),
        "shape": image.shape == (*source.shape, 5),
        "float32": image.get_data_dtype() == np.dtype("float32"),
        "affine": bool(np.array_equal(image.affine, source.affine)),
        "foreground_sum": bool(np.allclose(data[foreground].sum(axis=-1), 1, rtol=0, atol=1e-6)),
        "background_zero": not bool(data[~foreground].any()),
        "sgm_present": bool(data[..., 1].sum() > 0),
        "pathology_zero": not bool(data[..., 4].any()),
        "gmwmi_present": qc["gmwmi_voxels"] > 0,
        "mrtrix_format_check": qc["5ttcheck"]["returncode"] == 0,
    }
    record = {"status": "passed" if all(checks.values()) else "failed",
        "scope": "ACT preparation with real 5ttcheck and 5tt2gmwmi",
        "elapsed_seconds": elapsed, "checks": checks,
        "five_tt_stats": qc["five_tt_stats"],
        "source_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (segmentation, parcellation)}}
    (args.output_dir / "acceptance.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    if record["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
