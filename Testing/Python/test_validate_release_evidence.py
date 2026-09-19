#!/usr/bin/env python3
"""Tests for validate_release_evidence.py."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_release_evidence.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_release_evidence", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ValidateReleaseEvidenceTest(unittest.TestCase):
    def test_fresh_clone_report_requires_passed_boundary_steps(self) -> None:
        module = _load_module()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fresh_clone_smoke_report.json"
            path.write_text(
                json.dumps(
                    {
                        "kind": "slicerdsurfer_fresh_clone_smoke_report",
                        "status": "passed",
                        "asset_profile": "core",
                        "asset_mode": "download",
                        "resolved_commit": "a" * 40,
                        "code_checkout": {"separate_from_model_assets": True},
                        "model_asset_check": {"separate_from_code_checkout": True},
                        "steps": [
                            {"name": name, "status": "passed", "exit_code": 0}
                            for name in ("git_clone", "git_checkout", "model_assets_download_core",
                                         "make_test_fast", "verify_model_assets_core")
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = module.validate_fresh_clone_report(path)
            original = json.loads(path.read_text())
            for status, code in (("failed", 1), ("skipped", 0), ("passed", 1), ("passed", None)):
                broken = json.loads(json.dumps(original))
                broken["steps"][2].update(status=status, exit_code=code)
                path.write_text(json.dumps(broken))
                with self.subTest(status=status, code=code), self.assertRaises(RuntimeError):
                    module.validate_fresh_clone_report(path)
            for key, value in (("asset_mode", "plan"), ("asset_profile", "sentinel"),
                               ("resolved_commit", "main"), ("steps", None)):
                broken = dict(original, **{key: value})
                path.write_text(json.dumps(broken))
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    module.validate_fresh_clone_report(path)
            path.write_text(json.dumps(original))
            with self.assertRaises(RuntimeError):
                module.validate_fresh_clone_report(path, expected_commit="b" * 40)
            module.validate_fresh_clone_report(path, expected_commit="a" * 40)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["asset_profile"], "core")

    def test_fresh_clone_report_rejects_missing_boundary(self) -> None:
        module = _load_module()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fresh_clone_smoke_report.json"
            path.write_text(json.dumps({"kind": "slicerdsurfer_fresh_clone_smoke_report", "status": "passed"}), encoding="utf-8")

            with self.assertRaises(RuntimeError):
                module.validate_fresh_clone_report(path)

    def test_asset_mirror_manifest_requires_matching_hash_and_size(self) -> None:
        module = _load_module()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "asset_mirror_manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "kind": "slicerdsurfer_model_asset_mirror",
                        "profile": "core",
                        "git_commit": "abc",
                        "records": [
                            {
                                "path": "weights/model.pt",
                                "size_bytes": 10,
                                "expected_size_bytes": 10,
                                "sha256": "a" * 64,
                                "expected_sha256": "a" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = module.validate_asset_mirror_manifest(path)

        self.assertEqual(result["profile"], "core")
        self.assertEqual(result["record_count"], 1)

    def test_asset_mirror_manifest_rejects_mismatches(self) -> None:
        module = _load_module()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "asset_mirror_manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "kind": "slicerdsurfer_model_asset_mirror",
                        "records": [
                            {
                                "path": "weights/model.pt",
                                "size_bytes": 10,
                                "expected_size_bytes": 11,
                                "sha256": "a" * 64,
                                "expected_sha256": "b" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                module.validate_asset_mirror_manifest(path)


if __name__ == "__main__":
    unittest.main()
