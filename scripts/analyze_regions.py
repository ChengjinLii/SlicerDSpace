#!/usr/bin/env python3
"""Inspect a completed run or postprocess explicitly selected anatomical regions."""

import argparse
from pathlib import Path
import sys
import signal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.region_analysis import inspect_run, read_json, run_analysis, write_json


def main():
    def cancelled(*_):
        raise KeyboardInterrupt("Regional job cancelled")

    signal.signal(signal.SIGTERM, cancelled)
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", type=Path, help="One single-subject orchestration manifest")
    mode.add_argument("--request", type=Path, help="Regional analysis JSON request")
    mode.add_argument("--batch", type=Path, help="Shared regional request and completed subject manifests")
    parser.add_argument("--atlas", type=Path)
    parser.add_argument("--lut", type=Path)
    parser.add_argument("--catalog", type=Path)
    args = parser.parse_args()
    if args.inspect:
        if not args.catalog:
            parser.error("--inspect requires --catalog")
        write_json(
            args.catalog,
            inspect_run(
                args.inspect.expanduser().resolve(),
                atlas_override=args.atlas.expanduser().resolve() if args.atlas else None,
                lut_path=args.lut.expanduser().resolve() if args.lut else None,
            ),
        )
        print("[Regions] Available regions and QC-eligible inputs: " + str(args.catalog), flush=True)
    elif args.batch:
        from shared.region_batch import run_region_batch

        path = run_region_batch(read_json(args.batch))
        print("[Regions] Cohort summaries: " + str(path), flush=True)
        if read_json(path)["status"] != "completed":
            raise SystemExit(1)
    else:
        run_analysis(read_json(args.request))


if __name__ == "__main__":
    main()
