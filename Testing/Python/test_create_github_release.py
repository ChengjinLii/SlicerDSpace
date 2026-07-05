#!/usr/bin/env python3
"""Tests for the GitHub Release creation helper."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


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
        self.assertIn(smoke_report, plan.assets)


if __name__ == "__main__":
    unittest.main()
