#!/usr/bin/env python3
"""Tests for Python SAF integration facade."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class SAFIntegrationTest(unittest.TestCase):
    def _make_subject(self, root: Path, subject_id: str = "100307") -> Path:
        subject = root / subject_id
        input_dir = subject / "input"
        input_dir.mkdir(parents=True)
        for name in ["data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"]:
            (input_dir / name).write_text("stub", encoding="utf-8")
        return subject

    def _make_fs_dir(self, root: Path) -> Path:
        fs_dir = root / "freesurfer"
        (fs_dir / "surf").mkdir(parents=True)
        (fs_dir / "mri").mkdir()
        for name in ["rh.pial", "lh.pial", "rh.white", "lh.white", "rh.inflated", "lh.inflated", "rh.sphere", "lh.sphere", "rh.curv", "lh.curv"]:
            (fs_dir / "surf" / name).write_text("stub", encoding="utf-8")
        (fs_dir / "mri" / "brain.mgz").write_text("stub", encoding="utf-8")
        return fs_dir

    def test_saf_backend_is_bundled(self) -> None:
        from tractography import bundled_saf_backend_dir, inspect_saf_backend

        backend_dir = bundled_saf_backend_dir()
        self.assertTrue((backend_dir / "SAF_pipeline.py").is_file())
        status = inspect_saf_backend(noregister=True)
        self.assertTrue(status["backend_dir_exists"])
        self.assertIn("numpy", status["packages"])

    def test_saf_dry_run_writes_manifest_and_qc(self) -> None:
        from shared import subject_layout
        from tractography import SAFConfig, run_saf

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject = self._make_subject(root)
            fs_dir = self._make_fs_dir(root)
            fod = root / "wmfod.nii.gz"
            fod.write_text("stub", encoding="utf-8")
            tractogram = root / "input.tck"
            tractogram.write_text("stub", encoding="utf-8")

            result = run_saf(
                SAFConfig(
                    subject_id=subject.name,
                    input_root=subject,
                    fs_dir=fs_dir,
                    fod_path=fod,
                    pregenerated_tractogram=tractogram,
                    noregister=True,
                    maxlen=None,
                    execute=False,
                )
            )
            layout = subject_layout(subject)
            self.assertEqual(result.output_dir, layout.saf)
            self.assertTrue(result.manifest_path.is_file())
            self.assertTrue(result.qc_path.is_file())
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "saf_short_association_fibres")
            self.assertNotIn("mrtrix:tckgen", manifest["backend"]["missing_required"])
            self.assertEqual(qc["status"], "planned")
            self.assertFalse(result.executed)

    def test_mrtrix_bin_dir_is_used_for_backend_discovery(self) -> None:
        from tractography import inspect_saf_backend

        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "mrtrix-bin"
            bin_dir.mkdir()
            for command in ["mrconvert", "tckgen", "tckstats", "tcksample"]:
                path = bin_dir / command
                path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                path.chmod(0o755)

            status = inspect_saf_backend(
                mrtrix_bin_dir=bin_dir,
                noregister=True,
                require_mrconvert=True,
                require_tckgen=True,
                require_tckstats=True,
                require_tcksample=True,
            )
            self.assertEqual(status["mrtrix"]["bin_dir"], bin_dir.resolve().as_posix())
            self.assertEqual(status["missing_required"], [])
            self.assertTrue(status["available"])

    def test_mrtrix_env_bin_dir_is_used_for_backend_discovery(self) -> None:
        from tractography import inspect_saf_backend

        old_value = os.environ.get("SLICERDDSURFER_MRTRIX_BIN")
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "mrtrix-env-bin"
            bin_dir.mkdir()
            mrconvert = bin_dir / "mrconvert"
            mrconvert.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            mrconvert.chmod(0o755)
            os.environ["SLICERDDSURFER_MRTRIX_BIN"] = bin_dir.as_posix()
            try:
                status = inspect_saf_backend(
                    noregister=True,
                    require_mrconvert=True,
                    require_tckgen=False,
                    require_tckstats=False,
                )
            finally:
                if old_value is None:
                    os.environ.pop("SLICERDDSURFER_MRTRIX_BIN", None)
                else:
                    os.environ["SLICERDDSURFER_MRTRIX_BIN"] = old_value
            self.assertEqual(status["mrtrix_required"]["mrconvert"], mrconvert.resolve().as_posix())
            self.assertEqual(status["missing_required"], [])

    def test_mrtrix_prefix_mode_is_recorded_without_path_lookup(self) -> None:
        from tractography import inspect_saf_backend

        status = inspect_saf_backend(
            mrtrix_prefix="singularity exec mrtrix.sif ",
            noregister=True,
            require_mrconvert=True,
            require_tckgen=True,
            require_tckstats=False,
        )
        self.assertEqual(status["mrtrix"]["discovery"], "prefix_unchecked")
        self.assertEqual(status["mrtrix_required"]["tckgen"], "singularity exec mrtrix.sif tckgen")
        self.assertEqual(status["missing_required"], [])


if __name__ == "__main__":
    unittest.main()
