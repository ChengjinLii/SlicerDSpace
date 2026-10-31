#!/usr/bin/env python3
"""Run synthetic installation checks without loading patient data or changing packages."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from shared.setup_selftest import run_checks
    from shared.managed_runtimes import write_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_checks(json.loads(args.request.read_text()))
    except Exception as exc:
        result = dict(kind='slicerdspace_setup_selftest', status='failed', error=f'{type(exc).__name__}: {exc}')
    write_json(args.result, result)
    print(json.dumps(result, indent=2), flush=True)
    return int(result['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
