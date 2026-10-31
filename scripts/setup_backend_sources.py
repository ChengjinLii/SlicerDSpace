#!/usr/bin/env python3
"""Prepare pinned optional algorithm sources without Git, compilers or environment changes."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from shared.backend_sources import SOURCES, prepare_sources
    from shared.managed_runtimes import write_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", nargs="+", choices=tuple(SOURCES), required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--accept-terms", action="store_true")
    parser.add_argument("--offline-root", type=Path)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare_sources(args.profiles, root=args.root, execute=args.execute,
                                 accept_terms=args.accept_terms, offline_root=args.offline_root)
    except Exception as exc:
        result = dict(kind="slicerdspace_backend_setup", status="failed", error=str(exc))
    write_json(args.result, result)
    print(json.dumps(result, indent=2), flush=True)
    return int(result["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
