#!/usr/bin/env python3
"""Summarize real completed WMA and TractCloud bundle-backend closure evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _summarize_wma(output_dir: Path, input_tractography: Path) -> dict[str, Any]:
    from tractography.wma import summarize_wma_outputs

    qc_path = output_dir / "wma_org_atlas_qc.json"
    manifest_path = output_dir / "wma_org_atlas_manifest.json"
    qc = _read_json(qc_path)
    summary = summarize_wma_outputs(output_dir, input_tractography)
    return {
        "backend": "wma_org_atlas",
        "status": qc.get("status"),
        "executed": qc.get("executed"),
        "qc_path": qc_path.as_posix(),
        "manifest_path": manifest_path.as_posix() if manifest_path.is_file() else None,
        "input_tractography": input_tractography.as_posix(),
        "core_counts": {
            "initial_cluster_count": summary.get("initial_cluster_count"),
            "outlier_removed_cluster_count": summary.get("outlier_removed_cluster_count"),
            "transformed_cluster_count": summary.get("transformed_cluster_count"),
            "anatomical_tract_count": summary.get("anatomical_tract_count"),
        },
        "completed": qc.get("status") == "completed" and int(summary.get("anatomical_tract_count") or 0) > 0,
    }


def _summarize_tractcloud(output_dir: Path) -> dict[str, Any]:
    from tractography.tractcloud import summarize_tractcloud_outputs

    qc_path = output_dir / "tractcloud_qc.json"
    manifest_path = output_dir / "tractcloud_manifest.json"
    qc = _read_json(qc_path)
    summary = summarize_tractcloud_outputs(output_dir)
    return {
        "backend": "tractcloud",
        "status": qc.get("status"),
        "executed": qc.get("executed"),
        "qc_path": qc_path.as_posix(),
        "manifest_path": manifest_path.as_posix() if manifest_path.is_file() else None,
        "core_counts": {
            "bundle_count": summary.get("bundle_count"),
            "category_count": len(summary.get("category_dirs") or []),
        },
        "completed": qc.get("status") == "completed" and int(summary.get("bundle_count") or 0) > 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wma-output-dir", required=True, type=Path)
    parser.add_argument("--wma-input-tractography", required=True, type=Path)
    parser.add_argument("--tractcloud-output-dir", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    args = parser.parse_args(argv)

    wma = _summarize_wma(args.wma_output_dir.expanduser().resolve(), args.wma_input_tractography.expanduser().resolve())
    tractcloud = _summarize_tractcloud(args.tractcloud_output_dir.expanduser().resolve())
    report = {
        "kind": "slicerddsurfer_bundle_backend_closure",
        "version": 1,
        "completed": bool(wma["completed"] and tractcloud["completed"]),
        "backends": {
            "wma": wma,
            "tractcloud": tractcloud,
        },
    }
    output_json = args.output_json.expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output_json)
    print(json.dumps({"completed": report["completed"], "wma": wma["core_counts"], "tractcloud": tractcloud["core_counts"]}, indent=2, sort_keys=True))
    return 0 if report["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
