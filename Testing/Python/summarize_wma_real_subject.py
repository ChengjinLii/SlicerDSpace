#!/usr/bin/env python3
"""Summarize a real WMA ORG atlas run from its existing QC/output tree."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="WMA run output root containing manifest/qc.")
    parser.add_argument("--input-tractography", required=True, help="Original input tractography used for the run.")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--output-json", default=None)
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from tractography.wma import summarize_wma_outputs

    output_dir = Path(args.output_dir).expanduser().resolve()
    input_tractography = Path(args.input_tractography).expanduser().resolve()
    manifest_path = output_dir / "wma_org_atlas_manifest.json"
    qc_path = output_dir / "wma_org_atlas_qc.json"
    manifest = _read_json(manifest_path) if manifest_path.is_file() else None
    qc = _read_json(qc_path) if qc_path.is_file() else None
    summary = summarize_wma_outputs(output_dir, input_tractography)

    report = {
        "kind": "wma_real_subject_summary",
        "subject_id": args.subject_id,
        "output_dir": output_dir.as_posix(),
        "input_tractography": input_tractography.as_posix(),
        "manifest_path": manifest_path.as_posix() if manifest_path.is_file() else None,
        "qc_path": qc_path.as_posix() if qc_path.is_file() else None,
        "manifest_status": manifest.get("status") if manifest else None,
        "qc_status": qc.get("status") if qc else None,
        "qc_error": qc.get("error") if qc else None,
        "summary": summary,
    }
    output_json = (
        Path(args.output_json).expanduser().resolve()
        if args.output_json
        else output_dir / f"{args.subject_id}_wma_real_subject_summary.json"
    )
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
