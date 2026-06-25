#!/usr/bin/env python3
"""Tests for background-process helper state."""

from __future__ import annotations

import unittest
from pathlib import Path

from shared.ui_background_process import build_background_run_context, qprocess_is_running


class UIBackgroundProcessTest(unittest.TestCase):
    def test_missing_process_is_not_running(self) -> None:
        self.assertFalse(qprocess_is_running(None))

    def test_build_single_subject_background_context(self) -> None:
        context = build_background_run_context(
            {
                "subject_id": "sub-01",
                "subject_root": Path("/data/sub-01"),
                "output_root": Path("/out"),
                "run_name": "Test1",
                "targets": ("validation",),
            },
            ["validation"],
        )

        self.assertEqual(context["subject_id"], "sub-01")
        self.assertEqual(context["subject_root"], Path("/data/sub-01"))
        self.assertEqual(context["selected_workflows"], ["validation"])
        self.assertIn("started_at", context)

    def test_build_batch_background_context(self) -> None:
        context = build_background_run_context(
            {
                "subject_id": "sub-01",
                "subject_root": Path("/data/sub-01"),
                "output_root": Path("/out"),
                "run_name": "Test1",
                "targets": ("validation",),
            },
            ["validation"],
            batch_root=Path("/data/batch"),
            batch_size=4,
        )

        self.assertEqual(context["subject_id"], "batch")
        self.assertEqual(context["subject_root"], Path("/data/batch"))
        self.assertEqual(context["batch_size"], 4)


if __name__ == "__main__":
    unittest.main()
