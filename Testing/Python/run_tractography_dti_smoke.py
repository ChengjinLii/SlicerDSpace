#!/usr/bin/env python3
"""Run the DTI tractography scaffold on a subject root without tractography execution."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from tractography import DTITrackingConfig, run_dti_tracking


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", type=Path, default=Path("/data/chengjin/SlicerDDSurfer-test/100307"))
    parser.add_argument("--subject-id", default="100307")
    parser.add_argument("--fit-method", choices=("ls", "wls"), default="wls")
    parser.add_argument("--tracking-method", choices=("deterministic", "probabilistic"), default="deterministic")
    parser.add_argument("--output-format", choices=("trk", "tck"), default="trk")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--require-native-cache", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_dti_tracking(
        DTITrackingConfig(
            subject_id=args.subject_id,
            input_root=args.subject_root,
            output_dir=args.output_dir,
            fit_method=args.fit_method,
            tracking_method=args.tracking_method,
            output_format=args.output_format,
            execute=False,
        )
    )
    if args.require_native_cache and not result.native_cache_available:
        raise RuntimeError(f"Native DTI cache is missing or incomplete: {result.native_bundle_dir}")

    print(f"subject_id={result.subject_id}")
    print(f"native_cache_available={result.native_cache_available}")
    print(f"manifest={result.manifest_path}")
    print(f"qc={result.qc_path}")
    print(f"planned_streamlines={result.streamlines_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
