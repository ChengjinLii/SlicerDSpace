#!/usr/bin/env python3
"""Tests for the external MRtrix CSD/FOD/ACT backend planning layer."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import nibabel as nib
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from tractography.csd import CSDActConfig, inspect_mrtrix_csd_backend, run_csd_act


class CSDActBackendTest(unittest.TestCase):
    def test_dry_run_writes_manifest_qc_and_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dwi = root / "data.nii.gz"
            mask = root / "mask.nii.gz"
            five_tt = root / "5tt.nii.gz"
            gmwmi = root / "gmwmi.nii.gz"
            bval = root / "bvals"
            bvec = root / "bvecs"
            nib.save(nib.Nifti1Image(np.ones((2, 2, 2, 2), dtype=np.float32), np.eye(4)), str(dwi))
            nib.save(nib.Nifti1Image(np.ones((2, 2, 2), dtype=np.uint8), np.eye(4)), str(mask))
            nib.save(nib.Nifti1Image(np.ones((2, 2, 2, 5), dtype=np.float32), np.eye(4)), str(five_tt))
            nib.save(nib.Nifti1Image(np.ones((2, 2, 2), dtype=np.uint8), np.eye(4)), str(gmwmi))
            bval.write_text("0 1000\n", encoding="utf-8")
            bvec.write_text("0 1\n0 0\n0 0\n", encoding="utf-8")

            result = run_csd_act(
                CSDActConfig(
                    subject_id="100307",
                    dwi_path=dwi,
                    bval_path=bval,
                    bvec_path=bvec,
                    mask_path=mask,
                    five_tt_path=five_tt,
                    gmwmi_path=gmwmi,
                    output_dir=root / "outputs" / "04_tractography" / "csd",
                    tractogram_dir=root / "outputs" / "04_tractography" / "tractograms" / "csd_act_test",
                    select_streamlines=10,
                    export_trk=True,
                    mrtrix_bin_dir=root / "fake_mrtrix_bin",
                )
            )

            self.assertFalse(result.executed)
            self.assertTrue(result.manifest_path.is_file())
            self.assertTrue(result.qc_path.is_file())
            self.assertGreaterEqual(len(result.commands), 6)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "mrtrix_csd_act")
            self.assertEqual(qc["status"], "planned")
            self.assertEqual(manifest["parameters"]["mrtrix_bin_dir"], (root / "fake_mrtrix_bin").as_posix())
            self.assertEqual(
                manifest["parameters"]["tractogram_dir"],
                (root / "outputs" / "04_tractography" / "tractograms" / "csd_act_test").as_posix(),
            )
            self.assertTrue(manifest["parameters"]["export_trk"])
            self.assertIsNotNone(manifest["outputs"]["tractogram_trk"])
            self.assertFalse(qc["tractogram_trk_exists"])
            self.assertIsNotNone(result.tractogram_trk_path)
            self.assertIn("dwi2response", " ".join(" ".join(command) for command in result.commands))
            self.assertIn("tckgen", " ".join(" ".join(command) for command in result.commands))

    def test_backend_inspection_honors_explicit_bin_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            for command in ("mrconvert", "dwi2response", "dwi2fod", "mtnormalise", "tckgen", "tcksift2"):
                path = bin_dir / command
                path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                path.chmod(0o755)

            status = inspect_mrtrix_csd_backend(bin_dir)

            self.assertTrue(status["available"])
            self.assertEqual(status["missing_commands"], [])
            self.assertEqual(status["commands"]["tckgen"], (bin_dir / "tckgen").resolve().as_posix())


if __name__ == "__main__":
    unittest.main()
