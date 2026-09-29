#!/usr/bin/env python3
"""World-space DDSeg vs DDParcel QC gate and the shared world-space resampler."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import nibabel as nib
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from segmentation.world_qc import (  # noqa: E402
    DEFAULT_MIN_WM_DICE,
    compute_world_agreement,
    evaluate_ddseg_world_qc,
    write_ddseg_world_qc,
)
from shared.world_space import resample_nearest_to_grid  # noqa: E402

SHAPE = (10, 12, 8)


def _ras() -> np.ndarray:
    affine = np.diag([1.5, 1.5, 1.5, 1.0])
    affine[:3, 3] = (-7.0, -8.0, -5.0)
    return affine


def _las(shape=SHAPE) -> np.ndarray:
    affine = _ras()
    affine[0, 0] = -1.5
    affine[0, 3] = _ras()[0, 3] + 1.5 * (shape[0] - 1)
    return affine


def _anatomy():
    """RAS-order toy brain: WM core in the anterior half, GM elsewhere, a 'ventricle'."""

    ddseg = np.zeros(SHAPE, dtype=np.int16)
    ddseg[1:-1, 1:-1, 1:-1] = 2
    ddseg[2:-2, 6:-2, 2:-2] = 1  # WM anterior
    ddseg[4:6, 3:5, 3:5] = 3  # CSF
    wmparc = np.zeros(SHAPE, dtype=np.int32)
    wmparc[ddseg == 2] = 1030  # cortex
    wmparc[ddseg == 1] = 3030  # WM parcel
    wmparc[ddseg == 3] = 4  # lateral ventricle
    return ddseg, wmparc


class WorldResampleTest(unittest.TestCase):
    def test_identical_world_grid_in_other_storage_is_recovered(self) -> None:
        rng = np.random.default_rng(3)
        data = rng.integers(0, 100, size=SHAPE)
        las = data[::-1, :, :]
        out = resample_nearest_to_grid(las, _las(), SHAPE, _ras())
        np.testing.assert_array_equal(out, data)

    def test_outside_voxels_get_fill_value(self) -> None:
        data = np.ones((2, 2, 2), dtype=np.int32)
        out = resample_nearest_to_grid(data, np.eye(4), (4, 2, 2), np.eye(4), fill_value=-1)
        np.testing.assert_array_equal(out[2:], -1)


class WorldAgreementTest(unittest.TestCase):
    def test_aligned_segmentation_passes_even_when_storage_differs(self) -> None:
        ddseg, wmparc = _anatomy()
        metrics = compute_world_agreement(ddseg, _ras(), wmparc[::-1, :, :], _las())
        self.assertAlmostEqual(metrics["wm_dice"], 1.0)
        self.assertAlmostEqual(metrics["gm_dice"], 1.0)
        self.assertAlmostEqual(metrics["lateral_ventricle_csf_fraction"], 1.0)

    def test_anterior_posterior_mirror_is_detected(self) -> None:
        ddseg, wmparc = _anatomy()
        mirrored = ddseg[:, ::-1, :]
        metrics = compute_world_agreement(mirrored, _ras(), wmparc, _ras())
        self.assertLess(metrics["wm_dice"], DEFAULT_MIN_WM_DICE)

    def test_raw_index_pairing_would_be_wrong_but_world_pairing_is_right(self) -> None:
        ddseg, wmparc = _anatomy()
        ddseg_lr_asym = ddseg.copy()
        ddseg_lr_asym[2:4, 6:-2, 2:-2] = 2  # make WM left-right asymmetric
        wmparc_asym = wmparc.copy()
        wmparc_asym[2:4, 6:-2, 2:-2] = 1030
        world = compute_world_agreement(ddseg_lr_asym, _ras(), wmparc_asym[::-1], _las())
        raw_dice = 2 * np.sum((ddseg_lr_asym == 1) & (wmparc_asym[::-1] >= 3000)) / (
            np.sum(ddseg_lr_asym == 1) + np.sum(wmparc_asym >= 3000)
        )
        self.assertAlmostEqual(world["wm_dice"], 1.0)
        self.assertLess(raw_dice, 0.9)


class WorldQCRecordTest(unittest.TestCase):
    def _write(self, root: Path, ddseg: np.ndarray, wmparc: np.ndarray):
        seg = root / "SegmentationMap_GMWMCSF.nii.gz"
        parc = root / "wmparc.nii.gz"
        nib.save(nib.Nifti1Image(ddseg.astype(np.float32), _ras()), str(seg))
        nib.save(nib.Nifti1Image(wmparc[::-1].astype(np.int32), _las()), str(parc))
        return seg, parc

    def test_record_passes_and_fails_with_threshold(self) -> None:
        ddseg, wmparc = _anatomy()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seg, parc = self._write(root, ddseg, wmparc)
            record = write_ddseg_world_qc(seg, parc, root / "ddseg_world_qc.json")
            self.assertEqual(record["status"], "passed")
            self.assertTrue(record["meets_acceptance_target"])
            on_disk = json.loads((root / "ddseg_world_qc.json").read_text(encoding="utf-8"))
            self.assertEqual(on_disk["thresholds"]["min_wm_dice"], DEFAULT_MIN_WM_DICE)
            seg_m, parc_m = self._write(root, ddseg[:, ::-1, :], wmparc)
            failed = evaluate_ddseg_world_qc(seg_m, parc_m)
            self.assertEqual(failed["status"], "failed")

    def test_invalid_threshold_is_rejected(self) -> None:
        ddseg, wmparc = _anatomy()
        with tempfile.TemporaryDirectory() as tmp:
            seg, parc = self._write(Path(tmp), ddseg, wmparc)
            with self.assertRaises(ValueError):
                evaluate_ddseg_world_qc(seg, parc, min_wm_dice=1.5)


@unittest.skipUnless(
    os.environ.get("SLICERDDSURFER_HEAVY_DDSEG_QC"),
    "heavy: set SLICERDDSURFER_HEAVY_DDSEG_QC=<ddseg_dir>:<wmparc> to check a real DDSeg run",
)
class RealSubjectWorldQCTest(unittest.TestCase):
    def test_real_ddseg_meets_acceptance_target(self) -> None:
        ddseg_dir, wmparc = os.environ["SLICERDDSURFER_HEAVY_DDSEG_QC"].split(":", 1)
        record = evaluate_ddseg_world_qc(Path(ddseg_dir) / "SegmentationMap_GMWMCSF.nii.gz", Path(wmparc))
        self.assertGreaterEqual(record["metrics"]["wm_dice"], 0.80)


if __name__ == "__main__":
    unittest.main()
