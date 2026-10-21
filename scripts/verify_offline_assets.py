#!/usr/bin/env python3
"""Verify selected model profiles in an existing offline resource directory."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def verify_offline_assets(root, profiles):
    from scripts.download_model_assets import load_manifest, resolve_asset_plan, verify_asset_plan
    manifest = load_manifest(Path(__file__).resolve().parents[1] / "models/assets_manifest.json")
    checks = {profile: verify_asset_plan(root, resolve_asset_plan(manifest, profile), check_hashes=True)
              for profile in profiles}
    return {"kind": "slicerdsurfer_offline_assets", "status": "completed" if checks and all(
            record["ok"] for record in checks.values()) else "failed", "root": str(root.resolve()), "checks": checks,
            "scope": "Trusted bundled manifest checksum validation; no downloads or scientific QC"}


def main():
    from shared.managed_runtimes import write_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--profiles", required=True, nargs="+")
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify_offline_assets(args.root, args.profiles)
    except Exception as exc:
        result = {"kind": "slicerdsurfer_offline_assets", "status": "failed", "error": str(exc)}
    write_json(args.result, result)
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
