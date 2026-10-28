#!/usr/bin/env python3
"""Run the shared SlicerDSpace input validation/QC layer on a subject root."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from shared import InputValidationConfig, validate_subject_inputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", type=Path, default=Path("/data/chengjin/SlicerDDSurfer-test/100307"))
    parser.add_argument("--subject-id", default="100307")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--t1w", type=Path, default=None)
    parser.add_argument("--bids-metadata", type=Path, default=None)
    parser.add_argument(
        "--dependency-group",
        action="append",
        default=[],
        help="Dependency group to check. May be repeated. Examples: core, microstructure, preprocessing, registration, tractography, all.",
    )
    parser.add_argument("--require-phase-encoding", action="store_true")
    parser.add_argument("--fail-on-warning", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dependency_groups = tuple(args.dependency_group) if args.dependency_group else ("core",)
    result = validate_subject_inputs(
        InputValidationConfig(
            subject_id=args.subject_id,
            input_root=args.subject_root,
            output_dir=args.output_dir,
            t1w_path=args.t1w,
            bids_metadata_path=args.bids_metadata,
            dependency_groups=dependency_groups,
            require_phase_encoding=args.require_phase_encoding,
        )
    )
    print(f"subject_id={result.subject_id}")
    print(f"status={result.status}")
    print(f"errors={result.error_count}")
    print(f"warnings={result.warning_count}")
    print(f"report={result.report_path}")
    for issue in result.messages:
        suffix = f" {issue.details}" if issue.details else ""
        print(f"{issue.level.upper()} [{issue.category}] {issue.message}{suffix}")
    if not result.passed:
        return 1
    if args.fail_on_warning and result.warning_count:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
