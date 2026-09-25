#!/usr/bin/env python3
"""Tests for shared/run_cancellation.py's SIGTERM manifest-cancellation helpers."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.run_cancellation import (
    cancelled_manifest_payload,
    orchestration_manifest_path,
    write_cancelled_manifest,
)


class CancelledManifestPayloadTest(unittest.TestCase):
    def test_builds_minimal_payload_when_no_manifest_exists_yet(self) -> None:
        payload = cancelled_manifest_payload(
            None, subject_id="100307", run_name="Test1", cancelled_at="2026-01-01T00:00:00Z"
        )
        self.assertEqual(payload["status"], "cancelled")
        self.assertEqual(payload["subject_id"], "100307")
        self.assertEqual(payload["run_name"], "Test1")
        self.assertEqual(payload["cancelled_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(payload["tasks"], [])

    def test_preserves_completed_tasks_and_cancels_unfinished_ones(self) -> None:
        existing = {
            "kind": "slicerdsurfer_orchestration",
            "subject_id": "100307",
            "run_name": "Test1",
            "status": "running",
            "tasks": [
                {"name": "validation", "status": "completed"},
                {"name": "preprocessing", "status": "running"},
                {"name": "tractography", "status": "pending"},
                {"name": "connectome", "status": "skipped", "reason": "not selected"},
            ],
        }
        payload = cancelled_manifest_payload(
            existing, subject_id="100307", run_name="Test1", cancelled_at="2026-01-01T00:00:05Z"
        )
        self.assertEqual(payload["status"], "cancelled")
        self.assertEqual(payload["cancelled_at"], "2026-01-01T00:00:05Z")
        statuses = {task["name"]: task["status"] for task in payload["tasks"]}
        self.assertEqual(
            statuses,
            {
                "validation": "completed",
                "preprocessing": "cancelled",
                "tractography": "cancelled",
                "connectome": "skipped",
            },
        )

    def test_does_not_mutate_the_existing_payload_in_place(self) -> None:
        existing = {"tasks": [{"name": "a", "status": "running"}]}
        cancelled_manifest_payload(existing, subject_id="s", run_name="r", cancelled_at="t")
        self.assertEqual(existing["tasks"][0]["status"], "running")
        self.assertNotIn("status", existing)


class WriteCancelledManifestTest(unittest.TestCase):
    def test_writes_a_fresh_manifest_when_none_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "00_run_metadata" / "Test1_orchestration_manifest.json"

            payload = write_cancelled_manifest(
                manifest_path,
                subject_id="100307",
                run_name="Test1",
                cancelled_at="2026-01-01T00:00:00Z",
            )

            self.assertTrue(manifest_path.is_file())
            on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk, payload)
            self.assertEqual(on_disk["status"], "cancelled")

    def test_updates_an_existing_checkpoint_manifest_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "Test1_orchestration_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "subject_id": "100307",
                        "run_name": "Test1",
                        "status": "running",
                        "tasks": [{"name": "validation", "status": "completed"}],
                    }
                ),
                encoding="utf-8",
            )

            write_cancelled_manifest(
                manifest_path,
                subject_id="100307",
                run_name="Test1",
                cancelled_at="2026-01-01T00:05:00Z",
            )

            on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["status"], "cancelled")
            self.assertEqual(on_disk["tasks"][0]["status"], "completed")

    def test_corrupted_existing_manifest_falls_back_to_a_fresh_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "Test1_orchestration_manifest.json"
            manifest_path.write_text("{not valid json", encoding="utf-8")

            write_cancelled_manifest(
                manifest_path,
                subject_id="100307",
                run_name="Test1",
                cancelled_at="2026-01-01T00:05:00Z",
            )

            on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["status"], "cancelled")
            self.assertEqual(on_disk["subject_id"], "100307")


class OrchestrationManifestPathTest(unittest.TestCase):
    def test_matches_the_orchestrator_own_naming_convention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            subject_root.mkdir()

            manifest_path = orchestration_manifest_path(subject_root, run_name="Test1")

            self.assertEqual(manifest_path.name, "Test1_orchestration_manifest.json")
            self.assertEqual(manifest_path.parent.name, "00_run_metadata")

    def test_normalizes_run_name_the_same_way_the_orchestrator_does(self) -> None:
        # normalize_run_name() strips whitespace and replaces "/" with "_"
        # (it does not otherwise sanitize the name); this must match exactly
        # so a cancelled-manifest write lands on the same path the
        # orchestrator itself would use.
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            subject_root.mkdir()

            manifest_path = orchestration_manifest_path(subject_root, run_name="  2026/Q1 ")

            self.assertEqual(manifest_path.name, "2026_Q1_orchestration_manifest.json")


if __name__ == "__main__":
    unittest.main()
