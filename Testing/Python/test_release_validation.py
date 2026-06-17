#!/usr/bin/env python3
"""Tests for the release validation runner."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


class ReleaseValidationTest(unittest.TestCase):
    def test_build_validation_steps_cover_release_evidence_chain(self) -> None:
        from scripts.release_validation import build_validation_steps

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject_root = root / "subject"
            batch_root = root / "batch"
            subject_root.mkdir()
            batch_root.mkdir()
            args = SimpleNamespace(
                subject_root=subject_root,
                subject_id="sub-01",
                output_root=root / "outputs",
                batch_root=batch_root,
                report_dir=root / "report",
                run_name="Test1",
                execute=False,
                dependency_config=root / "deps.json",
                jobs=2,
                arrange_inputs="symlink",
                tractography_backend="csd_act",
                connectome_backend="python",
                skip_slicer_smoke=True,
                slicer_launcher=Path("/missing/Slicer"),
                xvfb_run=Path("/missing/xvfb-run"),
            )

            steps = build_validation_steps(args, ["--skip-environment-check"])

            names = [step.name for step in steps]
            self.assertIn("single_subject_all_backends", names)
            self.assertIn("batch_validation", names)
            self.assertIn("bundle_backend_wmql", names)
            self.assertIn("bundle_backend_wma", names)
            self.assertIn("bundle_backend_tractcloud", names)
            self.assertIn("output_tree_html", names)
            self.assertIn("repository_release_audit", names)
            self.assertIn("slicer_smoke", names)
            single_command = next(step.command for step in steps if step.name == "single_subject_all_backends")
            self.assertIn("--bundle-backend", single_command)
            self.assertIn("all", single_command)
            self.assertIn("--plan", single_command)
            batch_command = next(step.command for step in steps if step.name == "batch_validation")
            self.assertIn("--jobs", batch_command)
            self.assertIn("2", batch_command)
            self.assertIn("--dependency-config", batch_command)
            slicer_smoke = next(step for step in steps if step.name == "slicer_smoke")
            self.assertTrue(slicer_smoke.skipped)


if __name__ == "__main__":
    unittest.main()
