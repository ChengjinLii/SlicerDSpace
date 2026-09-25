#!/usr/bin/env python3
"""Tests for run_postprocess_docker.py's staging directory validation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import run_postprocess_docker


class StageSubjectInputsTest(unittest.TestCase):
    def _make_inputs(self, root: Path) -> tuple[Path, Path]:
        native_dir = root / "native"
        mri_dir = root / "mri"
        native_dir.mkdir()
        mri_dir.mkdir()
        for name in run_postprocess_docker.REQUIRED_MRI_FILES:
            (mri_dir / name).write_text(name, encoding="utf-8")
        (native_dir / "100307_predicted_wm_lh_orig.stl").write_text("stl", encoding="utf-8")
        return native_dir, mri_dir

    def test_rejects_traversal_subject_id_without_touching_the_filesystem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native_dir, mri_dir = self._make_inputs(root)
            inputs_dir = root / "inputs"
            sibling = root / "sibling_should_survive"
            sibling.mkdir()
            (sibling / "keepme.txt").write_text("keep", encoding="utf-8")

            with self.assertRaises(ValueError):
                run_postprocess_docker.stage_subject_inputs(
                    subject_id="../sibling_should_survive",
                    native_dir=native_dir,
                    mri_dir=mri_dir,
                    inputs_dir=inputs_dir,
                    clobber=True,
                )

            self.assertTrue((sibling / "keepme.txt").is_file())

    def test_clobber_only_removes_the_resolved_subject_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native_dir, mri_dir = self._make_inputs(root)
            inputs_dir = root / "inputs"
            stale_subject_dir = inputs_dir / "100307"
            stale_subject_dir.mkdir(parents=True)
            (stale_subject_dir / "stale.txt").write_text("stale", encoding="utf-8")

            staged = run_postprocess_docker.stage_subject_inputs(
                subject_id="100307",
                native_dir=native_dir,
                mri_dir=mri_dir,
                inputs_dir=inputs_dir,
                clobber=True,
            )

            self.assertFalse((staged / "stale.txt").exists())
            self.assertTrue((staged / "mri" / "brain.mgz").is_file())
            self.assertTrue((staged / "surf" / "100307_predicted_wm_lh_orig.stl").is_file())


if __name__ == "__main__":
    unittest.main()
