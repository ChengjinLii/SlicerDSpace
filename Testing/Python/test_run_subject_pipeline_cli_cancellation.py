#!/usr/bin/env python3
"""Tests for run_subject_pipeline_cli.py's SIGTERM cancellation handler.

The actual `signal.signal(signal.SIGTERM, ...)` registration and delivery
cannot be meaningfully unit-tested headlessly (it requires a real process
to receive a real signal). What is testable, and what actually contains the
logic, is the handler function itself: _make_sigterm_handler() returns a
plain callable that write_cancelled_manifest()s to a given path and then
calls sys.exit(). This module calls that handler directly, the way a real
SIGTERM delivery would, without sending any signal.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import shared.run_subject_pipeline_cli as cli_module


class MakeSigtermHandlerTest(unittest.TestCase):
    def test_handler_writes_cancelled_manifest_and_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "00_run_metadata" / "Test1_orchestration_manifest.json"
            handler = cli_module._make_sigterm_handler(
                manifest_path, subject_id="100307", run_name="Test1"
            )

            with self.assertRaises(SystemExit) as ctx:
                handler(15, None)

            self.assertEqual(ctx.exception.code, 143)
            self.assertTrue(manifest_path.is_file())
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "cancelled")
            self.assertEqual(payload["subject_id"], "100307")
            self.assertEqual(payload["run_name"], "Test1")
            self.assertIn("cancelled_at", payload)

    def test_handler_preserves_an_existing_checkpoint_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "Test1_orchestration_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "subject_id": "100307",
                        "run_name": "Test1",
                        "status": "running",
                        "tasks": [
                            {"name": "validation", "status": "completed"},
                            {"name": "preprocessing", "status": "running"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            handler = cli_module._make_sigterm_handler(
                manifest_path, subject_id="100307", run_name="Test1"
            )

            with self.assertRaises(SystemExit):
                handler(15, None)

            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "cancelled")
            statuses = {task["name"]: task["status"] for task in payload["tasks"]}
            self.assertEqual(statuses["validation"], "completed")
            self.assertEqual(statuses["preprocessing"], "cancelled")

    def test_orchestration_manifest_path_is_computed_before_the_signal_fires(self) -> None:
        # The manifest path must be resolvable from config alone -- without
        # needing run_subject_products() to have started or finished --
        # since a SIGTERM could arrive before any task has been checkpointed.
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            subject_root.mkdir()

            manifest_path = cli_module.orchestration_manifest_path(subject_root, run_name="Test1")

            self.assertFalse(manifest_path.exists())
            handler = cli_module._make_sigterm_handler(
                manifest_path, subject_id="100307", run_name="Test1"
            )
            with self.assertRaises(SystemExit):
                handler(15, None)
            self.assertTrue(manifest_path.is_file())


if __name__ == "__main__":
    unittest.main()
