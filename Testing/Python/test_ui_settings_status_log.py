#!/usr/bin/env python3
"""Tests for widget settings/status helper modules."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from shared.ui_settings import coerce_user_setting_value, common_user_setting_specs
from shared.ui_status_log import set_existing_report_path


class UISettingsStatusLogTest(unittest.TestCase):
    def test_common_user_setting_specs_include_run_and_target_state(self) -> None:
        names = [name for name, _value_type in common_user_setting_specs()]

        self.assertIn("orchestrationRunName", names)
        self.assertIn("batchMode", names)
        self.assertIn("targetTractography", names)

    def test_coerce_user_setting_values(self) -> None:
        self.assertTrue(coerce_user_setting_value("true", bool))
        self.assertFalse(coerce_user_setting_value("0", bool))
        self.assertEqual(coerce_user_setting_value("7", int), 7)
        self.assertEqual(coerce_user_setting_value(None, str), "")

    def test_set_existing_report_path_updates_button_state(self) -> None:
        owner = SimpleNamespace(_button=SimpleNamespace(enabled=False))
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.html"
            report.write_text("report", encoding="utf-8")

            set_existing_report_path(owner, "_report", "_button", report)

        self.assertEqual(owner._report, report)
        self.assertTrue(owner._button.enabled)

    def test_set_existing_report_path_clears_missing_path(self) -> None:
        owner = SimpleNamespace(_button=SimpleNamespace(enabled=True))

        set_existing_report_path(owner, "_report", "_button", "/missing/report.html")

        self.assertIsNone(owner._report)
        self.assertFalse(owner._button.enabled)


if __name__ == "__main__":
    unittest.main()
