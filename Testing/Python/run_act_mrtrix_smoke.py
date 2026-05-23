#!/usr/bin/env python3
"""Check ACT MRtrix command planning against explicit inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from tractography import ACTTrackingConfig, run_act_tracking


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--parcellation-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dwi-path", type=Path, default=None)
    parser.add_argument("--bval-path", type=Path, default=None)
    parser.add_argument("--bvec-path", type=Path, default=None)
    parser.add_argument("--mask-path", type=Path, default=None)
    parser.add_argument("--five-tt-path", type=Path, default=None)
    parser.add_argument("--gmwmi-path", type=Path, default=None)
    parser.add_argument("--seed-count", type=int, default=1_000_000)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_act_tracking(
        ACTTrackingConfig(
            subject_id=args.subject_id,
            parcellation_path=args.parcellation_path,
            output_dir=args.output_dir,
            dwi_path=args.dwi_path,
            bval_path=args.bval_path,
            bvec_path=args.bvec_path,
            mask_path=args.mask_path,
            five_tt_path=args.five_tt_path,
            gmwmi_path=args.gmwmi_path,
            seed_count=args.seed_count,
            execute=args.execute,
        )
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    print(f"executed={result.executed}")
    print(f"standard_act_ready={result.standard_act_ready}")
    print(f"commands={len(result.commands)}")
    print(f"manifest={result.manifest_path}")
    print(f"qc={result.qc_path}")
    print("backend=" + json.dumps(result.backend_status, sort_keys=True))
    print("outputs=" + json.dumps(manifest["outputs"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
