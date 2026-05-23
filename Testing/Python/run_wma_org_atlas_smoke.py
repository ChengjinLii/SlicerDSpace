#!/usr/bin/env python3
"""Check or run the WMA ORG atlas adapter with explicit external paths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from tractography import WMAOrgAtlasConfig, inspect_wma_backend, inspect_wma_org_atlas, run_wma_org_atlas


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--input-tractography", type=Path, required=True)
    parser.add_argument("--atlas-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--slicer-executable", type=Path, required=True)
    parser.add_argument("--wma-root", type=Path, default=None)
    parser.add_argument("--transform-path", type=Path, default=None)
    parser.add_argument("--registration-mode", choices=("rig", "nonrig"), default="rig")
    parser.add_argument("--num-threads", type=int, default=1)
    parser.add_argument("--use-virtual-x", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backend = inspect_wma_backend(args.wma_root, require_virtual_x=args.use_virtual_x)
    atlas = inspect_wma_org_atlas(args.atlas_dir)
    print("backend=" + json.dumps(backend, sort_keys=True))
    print("atlas=" + json.dumps(atlas, sort_keys=True))

    result = run_wma_org_atlas(
        WMAOrgAtlasConfig(
            subject_id=args.subject_id,
            input_tractography=args.input_tractography,
            atlas_dir=args.atlas_dir,
            output_dir=args.output_dir,
            slicer_executable=args.slicer_executable,
            wma_root=args.wma_root,
            transform_path=args.transform_path,
            registration_mode=args.registration_mode,
            num_threads=args.num_threads,
            use_virtual_x=args.use_virtual_x,
            execute=args.execute,
        )
    )
    print(f"executed={result.executed}")
    print(f"return_code={result.return_code}")
    print(f"manifest={result.manifest_path}")
    print(f"qc={result.qc_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
