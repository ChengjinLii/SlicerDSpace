#!/usr/bin/env python3
"""Generate SlicerDDSurfer subject report artifacts from a run manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared import subject_layout, write_subject_reports


def _infer_manifest(subject_root: Path, output_root: Path | None, run_name: str) -> Path:
    layout = subject_layout(subject_root, output_root=output_root)
    return layout.run_metadata / f"{run_name}_orchestration_manifest.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", required=True, type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--run-name", default="csd_act")
    parser.add_argument("--manifest", type=Path, help="Optional explicit orchestration manifest path.")
    args = parser.parse_args(argv)

    subject_root = args.subject_root.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve() if args.output_root else None
    manifest = args.manifest.expanduser().resolve() if args.manifest else _infer_manifest(subject_root, output_root, args.run_name)
    if not manifest.is_file():
        raise FileNotFoundError(f"Orchestration manifest not found: {manifest}")
    paths = write_subject_reports(
        subject_root=subject_root,
        output_root=output_root,
        manifest_path=manifest,
        run_name=args.run_name,
    )
    print(paths.report_html.as_posix())
    print(paths.provenance_json.as_posix())
    print(paths.qc_summary_json.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
