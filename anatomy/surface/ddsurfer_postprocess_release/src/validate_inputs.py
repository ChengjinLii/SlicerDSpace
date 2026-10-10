#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate optimized DDSurfer postprocess inputs.")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--mode", required=True, choices=["left", "right", "whole"])
    parser.add_argument("--input-subject-dir", required=True)
    parser.add_argument("--output-json", required=True)
    return parser.parse_args()


def file_record(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def required_inputs(subject_id: str, subject_dir: Path, mode: str) -> list[tuple[str, Path]]:
    records: list[tuple[str, Path]] = [
        ("wmparc", subject_dir / "mri" / "DDSurfer-wmparc.nii.gz"),
        ("brain_mgz", subject_dir / "mri" / "brain.mgz"),
    ]
    hemi_map = {
        "left": ["lh"],
        "right": ["rh"],
        "whole": ["lh", "rh"],
    }
    for hemi in hemi_map[mode]:
        records.append((f"{hemi}_wm_stl", subject_dir / "surf" / f"{subject_id}_predicted_wm_{hemi}_orig.stl"))
        records.append((f"{hemi}_pial_stl", subject_dir / "surf" / f"{subject_id}_predicted_pial_{hemi}_orig.stl"))
    return records


def main() -> int:
    args = parse_args()
    subject_dir = Path(args.input_subject_dir).expanduser().resolve()
    issues: list[dict[str, object]] = []
    checks: dict[str, dict[str, object]] = {}

    for key, path in required_inputs(args.subject_id, subject_dir, args.mode):
        record = file_record(path)
        checks[key] = record
        if not record["exists"]:
            issues.append({"severity": "error", "field": key, "message": f"Missing required input: {path}"})

    payload = {
        "kind": "ddsurfer_postprocess_validation",
        "subject_id": args.subject_id,
        "mode": args.mode,
        "input_subject_dir": str(subject_dir),
        "checks": checks,
        "issue_count": len(issues),
        "issues": issues,
        "status": "ok" if not issues else "failed",
    }
    output = Path(args.output_json).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if issues:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
