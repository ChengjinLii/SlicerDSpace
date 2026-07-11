"""Tests for the private-data-free beginner demo subject."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import nibabel as nib
import numpy as np

from shared.demo_data import DEMO_SUBJECT_ID, create_synthetic_demo_subject


class DemoDataTest(unittest.TestCase):
    def test_synthetic_demo_is_valid_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject_root = create_synthetic_demo_subject(root)
            repeated = create_synthetic_demo_subject(root)
            input_dir = subject_root / "input"
            dwi = np.asarray(nib.load(input_dir / "data.nii.gz").dataobj)
            mask = np.asarray(nib.load(input_dir / "nodif_brain_mask.nii.gz").dataobj)
            bvals = np.loadtxt(input_dir / "bvals")
            bvecs = np.loadtxt(input_dir / "bvecs")

        self.assertEqual(subject_root.name, DEMO_SUBJECT_ID)
        self.assertEqual(repeated, subject_root)
        self.assertEqual(dwi.shape, (4, 4, 4, 7))
        self.assertEqual(mask.shape, (4, 4, 4))
        self.assertEqual(bvals.shape, (7,))
        self.assertEqual(bvecs.shape, (3, 7))
        self.assertTrue(np.all(np.isfinite(dwi)))
        self.assertTrue(np.all(mask == 1))


if __name__ == "__main__":
    unittest.main()
