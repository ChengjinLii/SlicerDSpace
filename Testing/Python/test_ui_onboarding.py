"""Tests for beginner onboarding helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from shared.demo_data import create_synthetic_demo_subject
from shared.ui_onboarding import (
    capability_dashboard_text,
    diagnostic_report_text,
    normalized_language,
    platform_path_examples,
)


@dataclass
class FakeItem:
    key: str
    label: str
    status: str
    targets: tuple[str, ...]


@dataclass
class FakeResult:
    runnable_targets: tuple[str, ...]
    blocked_targets: tuple[str, ...]
    statuses: tuple[FakeItem, ...]


class FakeOwner:
    _parameterNode = None
    _lastEnvironmentResult = None
    ui = None

    def _read_environment_path_setting(self, key: str) -> str:
        return {"model_assets_dir": "/tmp/models"}.get(key, "")


class OnboardingHelpersTest(unittest.TestCase):
    def test_normalized_language_defaults_to_english(self) -> None:
        self.assertEqual(normalized_language(""), "en")
        self.assertEqual(normalized_language("zh-CN"), "zh")

    def test_path_examples_match_the_selected_platform(self) -> None:
        windows = platform_path_examples("en", system="Windows")
        macos = platform_path_examples("en", system="Darwin")
        linux = platform_path_examples("zh", system="Linux")

        self.assertIn(r"C:\Users\name\data\sub-01", windows)
        self.assertIn("/Users/name/data/sub-01", macos)
        self.assertIn("/opt/homebrew/bin", macos)
        self.assertIn("本机路径示例", linux)
        self.assertIn("/home/name/data/sub-01", linux)

    def test_capability_dashboard_explains_runnable_and_blocked_targets(self) -> None:
        result = FakeResult(
            runnable_targets=("validation", "microstructure"),
            blocked_targets=("tractography",),
            statuses=(FakeItem("command:tckgen", "tckgen", "missing", ("tractography",)),),
        )

        english = capability_dashboard_text(result, language="en")
        chinese = capability_dashboard_text(result, language="zh")

        self.assertIn("Runnable now: validation, microstructure", english)
        self.assertIn("tractography: tckgen", english)
        self.assertIn("你现在可以运行：validation, microstructure", chinese)
        self.assertIn("tractography: tckgen", chinese)

    def test_diagnostic_report_is_json(self) -> None:
        report = json.loads(diagnostic_report_text(FakeOwner()))

        self.assertEqual(report["external_paths"]["model_assets_dir"], "/tmp/models")
        self.assertIn("python", report)

    def test_create_synthetic_demo_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = create_synthetic_demo_subject(Path(tmp))

            self.assertTrue((subject_root / "input" / "data.nii.gz").is_file())
            self.assertTrue((subject_root / "input" / "bvals").is_file())
            self.assertTrue((subject_root / "input" / "bvecs").is_file())
            self.assertTrue((subject_root / "input" / "nodif_brain_mask.nii.gz").is_file())


if __name__ == "__main__":
    unittest.main()
