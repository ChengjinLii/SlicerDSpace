#!/usr/bin/env python3
"""Tests for the GitHub Release creation helper."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock
from dataclasses import replace


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "create_github_release.py"


def _load_release_module():
    spec = importlib.util.spec_from_file_location("create_github_release", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CreateGithubReleaseTest(unittest.TestCase):
    def test_default_assets_use_new_location_with_legacy_fallback(self) -> None:
        module = _load_release_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = root / "ignore/releases/v1.0"
            legacy = root / "release_artifacts/v1.0"
            self.assertEqual(module.default_assets(root, "v1.0")[0].parent, current)
            legacy.mkdir(parents=True)
            self.assertEqual(module.default_assets(root, "v1.0")[0].parent, legacy)
            current.mkdir(parents=True)
            self.assertEqual(module.default_assets(root, "v1.0")[0].parent, current)

    def _validated_plan(self, module, root):
        notes = root / "notes.md"
        notes.write_text("Release notes")
        evidence = root / "fresh_clone_smoke_report.json"
        evidence.write_text(json.dumps({
            "kind": "slicerdsurfer_fresh_clone_smoke_report", "status": "passed",
            "asset_profile": "core", "asset_mode": "download", "resolved_commit": "a" * 40,
            "code_checkout": {"separate_from_model_assets": True},
            "model_asset_check": {"separate_from_code_checkout": True},
            "steps": [{"name": name, "status": "passed", "exit_code": 0} for name in
                      ("git_clone", "git_checkout", "make_test_fast", "model_assets_download_core", "verify_model_assets_core")],
        }))
        return module.ReleasePlan("owner/repo", "v1.0", "Test", notes, (evidence,),
                                  True, True, True, True, evidence, "a" * 40)

    def test_release_requires_real_evidence_before_any_network_write(self):
        module = _load_release_module()
        with tempfile.TemporaryDirectory() as tmp:
            plan = self._validated_plan(module, Path(tmp))
            module.validate_plan(plan)
            self.assertEqual(module.release_payload(plan)["target_commitish"], "a" * 40)
            for invalid in (replace(plan, fresh_clone_report=None),
                            replace(plan, expected_commit="b" * 40),
                            replace(plan, assets=plan.assets * 2)):
                with self.subTest(plan=invalid), mock.patch.object(module, "_api_request") as api:
                    with self.assertRaises((ValueError, RuntimeError)):
                        module.create_release(invalid, token="test")
                    api.assert_not_called()
            plan.fresh_clone_report.write_text("{}")
            with self.assertRaises(RuntimeError):
                module.validate_plan(plan)

    def test_existing_tag_and_public_release_are_protected(self):
        module = _load_release_module()
        with tempfile.TemporaryDirectory() as tmp:
            plan = self._validated_plan(module, Path(tmp))
            with mock.patch.object(module, "_api_request", return_value={"sha": "b" * 40}) as api:
                with self.assertRaisesRegex(RuntimeError, "different commit"):
                    module.create_release(plan, token="test")
                self.assertEqual(api.call_count, 1)
            with mock.patch.object(module, "_api_request", return_value={"sha": "a" * 40}), \
                 mock.patch.object(module, "get_existing_release", return_value={"draft": False}):
                with self.assertRaisesRegex(RuntimeError, "already published"):
                    module.create_release(plan, token="test")

    def test_release_payload_defaults_to_draft_prerelease(self) -> None:
        module = _load_release_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "notes.md"
            asset = root / "artifact.json"
            notes.write_text("# Notes\n", encoding="utf-8")
            asset.write_text("{}", encoding="utf-8")
            plan = module.ReleasePlan(
                repository="owner/repo",
                tag="v1.2.3",
                title="Release v1.2.3",
                notes_file=notes,
                assets=(asset,),
                draft=True,
                prerelease=True,
                reuse_existing=False,
                replace_existing_assets=False,
            )

            payload = module.release_payload(plan)

        self.assertEqual(payload["tag_name"], "v1.2.3")
        self.assertEqual(payload["name"], "Release v1.2.3")
        self.assertEqual(payload["body"], "# Notes\n")
        self.assertTrue(payload["draft"])
        self.assertTrue(payload["prerelease"])

    def test_validate_plan_reports_missing_artifacts(self) -> None:
        module = _load_release_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "notes.md"
            notes.write_text("# Notes\n", encoding="utf-8")
            plan = module.ReleasePlan(
                repository="owner/repo",
                tag="v1.2.3",
                title="Release v1.2.3",
                notes_file=notes,
                assets=(root / "missing.json",),
                draft=True,
                prerelease=True,
                reuse_existing=False,
                replace_existing_assets=False,
            )

            with self.assertRaises(FileNotFoundError):
                module.validate_plan(plan)

    def test_build_release_plan_accepts_additional_smoke_report_asset(self) -> None:
        module = _load_release_module()

        smoke_report = Path("/tmp/fresh_clone_smoke_report.json")
        args = Namespace(
            repository="owner/repo",
            tag="v0.1.0",
            title="Title",
            notes_file=REPO_ROOT / "docs" / "release" / "GITHUB_RELEASE_DRAFT_v0.1.0.md",
            asset=[],
            fresh_clone_report=smoke_report,
            publish=False,
            final=False,
            reuse_existing=True,
            replace_existing_assets=True,
        )

        plan = module.build_release_plan(args)

        self.assertEqual(plan.repository, "owner/repo")
        self.assertEqual(plan.tag, "v0.1.0")
        self.assertTrue(plan.draft)
        self.assertTrue(plan.prerelease)
        self.assertTrue(plan.reuse_existing)
        self.assertTrue(plan.replace_existing_assets)
        # build_release_plan() resolves asset paths; resolve here too so the
        # comparison holds under macOS's /tmp -> /private/tmp symlink.
        self.assertIn(smoke_report.resolve(), plan.assets)


if __name__ == "__main__":
    unittest.main()
