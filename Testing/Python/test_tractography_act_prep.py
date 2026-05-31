#!/usr/bin/env python3
"""Tests for ACT 5TT/GMWMI preparation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ACTPrepTest(unittest.TestCase):
    def test_execute_true_generates_5tt_and_gmwmi(self) -> None:
        import nibabel as nib
        import numpy as np
        from tractography import ACTPrepConfig, run_act_prep

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            labels = np.zeros((5, 5, 5), dtype=np.int16)
            labels[1:4, 1:4, 1:2] = 1
            labels[1:4, 1:4, 2:4] = 2
            labels[0, 0, 0] = 3
            segmentation = root / "SegmentationMap_GMWMCSF.nii.gz"
            nib.save(nib.Nifti1Image(labels, np.eye(4)), segmentation.as_posix())

            result = run_act_prep(
                ACTPrepConfig(
                    subject_id="100307",
                    segmentation_path=segmentation,
                    output_dir=root / "act_prep",
                    execute=True,
                )
            )

            self.assertTrue(result.executed)
            self.assertTrue(result.five_tt_path.is_file())
            self.assertTrue(result.gmwmi_path.is_file())
            five_tt = nib.load(result.five_tt_path.as_posix()).shape
            self.assertEqual(five_tt, (5, 5, 5, 5))
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(qc["status"], "completed")
            self.assertGreater(qc["gmwmi_voxels"], 0)


if __name__ == "__main__":
    unittest.main()
