#!/usr/bin/env python3
"""Tests for DTI scalar map materialization in the microstructure workflow."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import nibabel as nib
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class MicrostructureDTIScalarsTest(unittest.TestCase):
    def test_output_paths_include_full_dti_scalar_set(self) -> None:
        from microstructure.pipeline import _output_paths

        with tempfile.TemporaryDirectory() as tmp:
            paths = _output_paths("100307", Path(tmp) / "outputs" / "02_microstructure")
            self.assertEqual(paths["fa"].name, "100307_dti_FA.nii.gz")
            self.assertEqual(paths["md"].name, "100307_dti_MD.nii.gz")
            self.assertEqual(paths["ad"].name, "100307_dti_AD.nii.gz")
            self.assertEqual(paths["rd"].name, "100307_dti_RD.nii.gz")
            self.assertEqual(paths["l1"].name, "100307_dti_L1.nii.gz")
            self.assertEqual(paths["l2"].name, "100307_dti_L2.nii.gz")
            self.assertEqual(paths["l3"].name, "100307_dti_L3.nii.gz")
            self.assertEqual(paths["trace"].name, "100307_dti_Trace.nii.gz")

    def test_rd_is_computed_from_l2_l3_average(self) -> None:
        from microstructure.pipeline import _compute_rd_map

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            affine = np.eye(4)
            l2 = np.asarray([[2.0, 4.0], [6.0, 8.0]], dtype=np.float32)
            l3 = np.asarray([[1.0, 3.0], [5.0, 7.0]], dtype=np.float32)
            l2_path = root / "l2.nii.gz"
            l3_path = root / "l3.nii.gz"
            rd_path = root / "rd.nii.gz"
            nib.save(nib.Nifti1Image(l2, affine), str(l2_path))
            nib.save(nib.Nifti1Image(l3, affine), str(l3_path))

            _compute_rd_map(l2_path, l3_path, rd_path)

            actual = nib.load(str(rd_path)).get_fdata(dtype=np.float32)
            np.testing.assert_allclose(actual, (l2 + l3) / 2.0)


if __name__ == "__main__":
    unittest.main()
