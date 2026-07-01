#!/usr/bin/env python3
"""Validate local release evidence files before publishing a release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object in {path}")
    return payload


def validate_fresh_clone_report(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    errors: list[str] = []
    if payload.get("kind") != "slicerdsurfer_fresh_clone_smoke_report":
        errors.append("unexpected kind")
    if payload.get("status") != "passed":
        errors.append(f"status is {payload.get('status')!r}, expected 'passed'")
    code_checkout = payload.get("code_checkout")
    if not isinstance(code_checkout, dict) or not code_checkout.get("separate_from_model_assets"):
        errors.append("missing code_checkout.separate_from_model_assets=true")
    model_asset_download = payload.get("model_asset_download")
    if not isinstance(model_asset_download, dict) or not model_asset_download.get("separate_from_code_checkout"):
        errors.append("missing model_asset_download.separate_from_code_checkout=true")
    step_names = {str(step.get("name")) for step in payload.get("steps", []) if isinstance(step, dict)}
    for required in ("git_clone", "git_checkout", "make_test_fast"):
        if required not in step_names:
            errors.append(f"missing step {required}")
    asset_profile = str(payload.get("asset_profile") or "core")
    for required in (f"download_model_assets_{asset_profile}", f"verify_model_assets_{asset_profile}"):
        if required not in step_names:
            errors.append(f"missing step {required}")
    if errors:
        raise RuntimeError(f"Fresh-clone smoke report is not release-ready: {', '.join(errors)}")
    return {
        "path": path.expanduser().resolve().as_posix(),
        "status": "passed",
        "asset_profile": asset_profile,
        "step_count": len(step_names),
    }


def validate_asset_mirror_manifest(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    errors: list[str] = []
    if payload.get("kind") != "slicerdsurfer_model_asset_mirror":
        errors.append("unexpected kind")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        errors.append("records must be a non-empty list")
        records = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"record {index} is not an object")
            continue
        if not record.get("path"):
            errors.append(f"record {index} missing path")
        if not isinstance(record.get("size_bytes"), int) or int(record.get("size_bytes") or 0) <= 0:
            errors.append(f"record {index} missing positive size_bytes")
        sha = str(record.get("sha256") or "")
        if len(sha) != 64:
            errors.append(f"record {index} missing sha256")
        expected_sha = str(record.get("expected_sha256") or "")
        if expected_sha and expected_sha != sha:
            errors.append(f"record {index} sha256 does not match expected_sha256")
        expected_size = record.get("expected_size_bytes")
        if expected_size is not None and int(expected_size) != int(record.get("size_bytes") or -1):
            errors.append(f"record {index} size_bytes does not match expected_size_bytes")
    if errors:
        raise RuntimeError(f"Asset mirror manifest is not release-ready: {', '.join(errors)}")
    return {
        "path": path.expanduser().resolve().as_posix(),
        "profile": payload.get("profile"),
        "record_count": len(records),
        "git_commit": payload.get("git_commit"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh-clone-report", type=Path, help="fresh_clone_smoke_report.json to validate.")
    parser.add_argument("--asset-mirror-manifest", action="append", type=Path, help="asset_mirror_manifest.json to validate. Can be repeated.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        results: dict[str, Any] = {
            "kind": "slicerdsurfer_release_evidence_validation",
            "version": 1,
            "fresh_clone_report": None,
            "asset_mirror_manifests": [],
        }
        if args.fresh_clone_report:
            results["fresh_clone_report"] = validate_fresh_clone_report(args.fresh_clone_report)
        for manifest in args.asset_mirror_manifest or []:
            results["asset_mirror_manifests"].append(validate_asset_mirror_manifest(manifest))
        if not args.fresh_clone_report and not args.asset_mirror_manifest:
            raise RuntimeError("Provide --fresh-clone-report or --asset-mirror-manifest.")
        print(json.dumps(results, indent=2, sort_keys=True))
        return 0
    except RuntimeError as exc:
        print(f"[release-evidence] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
