#!/usr/bin/env python3
"""Tests for shared UI stylesheet helpers."""

from __future__ import annotations

import unittest

from shared.ui_styles import (
    ENVIRONMENT_READY_LABEL_STYLE,
    ENVIRONMENT_RESULTS_DIALOG_STYLE,
    RUN_STATUS_TABLE_STYLE,
    SLICERDDSURFER_UI_STYLE,
    run_summary_label_style,
)


class UIStylesTest(unittest.TestCase):
    def test_main_stylesheet_contains_key_panels(self) -> None:
        self.assertIn("QFrame#headerFrame", SLICERDDSURFER_UI_STYLE)
        self.assertIn("QWidget#externalBackendsGroup", SLICERDDSURFER_UI_STYLE)
        self.assertIn("QPushButton#runSelectedButton", SLICERDDSURFER_UI_STYLE)
        self.assertIn("QPlainTextEdit#logPlainTextEdit", SLICERDDSURFER_UI_STYLE)
        self.assertNotIn("border-left", SLICERDDSURFER_UI_STYLE)

    def test_run_status_table_style_contains_header_and_selection_rules(self) -> None:
        self.assertIn("QTableWidget", RUN_STATUS_TABLE_STYLE)
        self.assertIn("QHeaderView::section", RUN_STATUS_TABLE_STYLE)
        self.assertIn("selection-background-color", RUN_STATUS_TABLE_STYLE)

    def test_environment_dialog_style_contains_summary_and_item_rules(self) -> None:
        self.assertIn("QLabel#environmentSummaryLabel", ENVIRONMENT_RESULTS_DIALOG_STYLE)
        self.assertIn("QFrame#environmentItemFrame", ENVIRONMENT_RESULTS_DIALOG_STYLE)
        self.assertIn("QScrollArea", ENVIRONMENT_RESULTS_DIALOG_STYLE)
        self.assertIn("#2E7D32", ENVIRONMENT_READY_LABEL_STYLE)

    def test_run_summary_label_style_uses_state_palette_and_unknown_fallback(self) -> None:
        failed = run_summary_label_style("failed")
        unknown = run_summary_label_style("not-a-state")

        self.assertIn("#FDECEC", failed)
        self.assertIn("#6B1A1A", failed)
        self.assertIn("#F3F7F4", unknown)
        self.assertIn("QLabel#runSummaryLabel", unknown)
        self.assertNotIn("border-left", failed)


if __name__ == "__main__":
    unittest.main()
