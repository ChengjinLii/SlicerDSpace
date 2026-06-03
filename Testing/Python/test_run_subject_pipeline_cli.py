#!/usr/bin/env python3
"""Tests for the unified run_subject_pipeline CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "run_subject_pipeline.py"


class RunSubjectPipelineCliTest(unittest.TestCase):
    def test_dry_run_all_writes_manifest_and_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--subject-root",
                    str(subject_root),
                    "--all",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["subject_id"], "100307")
            self.assertTrue(payload["run_manifest_path"].endswith("_orchestration_manifest.json"))
            task_names = [task["name"] for task in payload["tasks"]]
            self.assertIn("preprocessing.dwi", task_names)
            self.assertIn("segmentation.ddseg", task_names)
            self.assertIn("parcellation.ddparcel", task_names)
            self.assertIn("surface.ddsurfer", task_names)
            self.assertIn("microstructure.dti", task_names)
            self.assertIn("tractography.csd_act", task_names)
            self.assertIn("bundles.wmql", task_names)
            self.assertIn("connectome.streamline_count", task_names)

    def test_targets_and_skip_targets_override_default_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "subjectA"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--subject-root",
                    str(subject_root),
                    "--targets",
                    "validation,microstructure,tractography,connectome",
                    "--skip-targets",
                    "connectome",
                    "--tractography-backend",
                    "dti_det",
                    "--print-manifest-only",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            manifest_path = Path(completed.stdout.strip())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["subject_id"], "subjectA")
            self.assertEqual(manifest["targets"], ["validation", "microstructure", "tractography"])
            self.assertEqual(manifest["tractography_backend"], "dti_det")

    def test_cli_accepts_optional_algorithm_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "149741"
            input_dir = subject_root / "input"
            tractography_dir = subject_root / "tractography"
            input_dir.mkdir(parents=True)
            tractography_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")
            (tractography_dir / "149741_ukf_pp_downsampled.vtk").write_text("vtk", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--subject-root",
                    str(subject_root),
                    "--targets",
                    "saf,wma,tractcloud",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(completed.stdout)
            task_names = [task["name"] for task in payload["tasks"]]
            self.assertEqual(task_names, ["tractography.saf", "bundles.wma", "bundles.tractcloud"])


if __name__ == "__main__":
    unittest.main()
