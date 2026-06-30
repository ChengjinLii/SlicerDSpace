#!/usr/bin/env python3
"""Tests for check_github_ci_status.py."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_github_ci_status.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_github_ci_status", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CheckGithubCiStatusTest(unittest.TestCase):
    def test_summarize_check_runs_accepts_success_neutral_and_skipped(self) -> None:
        module = _load_module()

        summary = module.summarize_check_runs(
            [
                {"name": "fast-checks", "status": "completed", "conclusion": "success"},
                {"name": "docs", "status": "completed", "conclusion": "neutral"},
                {"name": "manual-release-step", "status": "completed", "conclusion": "skipped"},
            ]
        )

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["unsuccessful_runs"], [])

    def test_summarize_check_runs_reports_failed_or_in_progress_runs(self) -> None:
        module = _load_module()

        summary = module.summarize_check_runs(
            [
                {"name": "fast-checks", "status": "completed", "conclusion": "failure"},
                {"name": "lint", "status": "in_progress", "conclusion": None},
            ]
        )

        self.assertFalse(summary["ok"])
        self.assertEqual([run["name"] for run in summary["unsuccessful_runs"]], ["fast-checks", "lint"])

    def test_required_check_assessment_flags_old_release_jobs(self) -> None:
        module = _load_module()

        assessment = module.required_check_assessment(
            ["CI / fast-checks", "fresh-clone-smoke", "create-github-release"]
        )

        self.assertFalse(assessment["ok"])
        self.assertTrue(assessment["expected_present"])
        self.assertEqual(assessment["stale_required_checks"], ["create-github-release", "fresh-clone-smoke"])

    def test_required_check_assessment_accepts_fast_checks_only(self) -> None:
        module = _load_module()

        assessment = module.required_check_assessment(["CI / fast-checks"])

        self.assertTrue(assessment["ok"])
        self.assertTrue(assessment["expected_present"])
        self.assertEqual(assessment["stale_required_checks"], [])


if __name__ == "__main__":
    unittest.main()
