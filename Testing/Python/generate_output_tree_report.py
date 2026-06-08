#!/usr/bin/env python3
"""Generate an annotated HTML tree for a SlicerDDSurfer outputs directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared import write_output_tree_report


DEFAULT_OUTPUT_ROOT = Path("/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs")
DEFAULT_DEST = REPO_ROOT / "SlicerDDSurfer_100307_release_candidate_output_tree.html"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a static annotated SlicerDDSurfer output-tree HTML report.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="outputs directory to scan.")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="HTML report destination.")
    parser.add_argument("--latest-dest", type=Path, help="Optional latest-report destination to write the same HTML.")
    parser.add_argument("--subject-id", default="100307-release-candidate", help="Subject id shown in the report.")
    parser.add_argument("--run-name", default="rc_csd_act", help="Run name shown in the report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = write_output_tree_report(
        output_root=args.output_root,
        destination=args.dest,
        latest_destination=args.latest_dest,
        subject_id=args.subject_id,
        run_name=args.run_name,
    )
    print(f"wrote {paths.report_html}")
    if paths.report_html_latest:
        print(f"wrote latest {paths.report_html_latest}")
    print(
        f"regular_files={paths.regular_file_count} "
        f"symlinks={paths.symlink_count} "
        f"total={paths.total_nodes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
