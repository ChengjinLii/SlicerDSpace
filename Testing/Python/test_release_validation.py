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

    def test_slicer_smoke_step_uses_staged_module_env_and_disable_cli(self) -> None:
        from scripts.release_validation import build_validation_steps

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject_root = root / "subject"
            subject_root.mkdir()
            launcher = root / "Slicer"
            xvfb_run = root / "xvfb-run"
            launcher.write_text("#!/usr/bin/env sh\n", encoding="utf-8")
            xvfb_run.write_text("#!/usr/bin/env sh\n", encoding="utf-8")
            args = SimpleNamespace(
                subject_root=subject_root,
                subject_id="sub-01",
                output_root=root / "outputs",
                batch_root=None,
                report_dir=root / "report",
                run_name="Test1",
                execute=False,
                dependency_config=None,
                jobs=1,
                arrange_inputs="none",
                tractography_backend="csd_act",
                connectome_backend="python",
                skip_slicer_smoke=False,
                slicer_launcher=launcher,
                xvfb_run=xvfb_run,
            )

            steps = build_validation_steps(args, [])

            stage = next(step for step in steps if step.name == "stage_slicer_extension")
            self.assertIn("--link-mode", stage.command)
            self.assertIn("copy", stage.command)
            slicer_smoke = next(step for step in steps if step.name == "slicer_smoke")
            self.assertFalse(slicer_smoke.skipped)
            self.assertEqual(slicer_smoke.command[0], "env")
            self.assertTrue(
                any(part.startswith("SLICERDDSURFER_EXTENSION_MODULE_DIR=") for part in slicer_smoke.command)
            )
            self.assertTrue(any(part.startswith("PATH=") for part in slicer_smoke.command))
            self.assertIn("--disable-cli-modules", slicer_smoke.command)


if __name__ == "__main__":
    unittest.main()
