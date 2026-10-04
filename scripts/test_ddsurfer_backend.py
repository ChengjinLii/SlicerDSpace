#!/usr/bin/env python3
"""Run upstream tests in an isolated snapshot with external model assets."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-root', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='ddsurfer-upstream-tests-') as temp:
        snapshot = Path(temp) / 'backend'
        shutil.copytree(ROOT / 'surface/ddsurfer_backend', snapshot,
                        ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('weights', 'template'):
            (snapshot / name).mkdir()
        assets = json.loads((ROOT / 'models/assets_manifest.json').read_text())
        for relative in assets['profiles']['surface']['required_paths']:
            path = Path(relative)
            (snapshot / path.relative_to('surface')).symlink_to(args.asset_root.resolve() / path)
        return subprocess.call([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=snapshot)


if __name__ == '__main__':
    raise SystemExit(main())
