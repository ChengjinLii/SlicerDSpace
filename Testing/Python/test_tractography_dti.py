#!/usr/bin/env python3
"""Lightweight tests for the DTI tractography scaffold."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from tractography import DTITrackingConfig, run_dti_tracking
from tractography.dti import _eudx_length_limits


SUBJECT_ID = "100307"


def _touch(path: Path, content: str = "placeholder") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_subject_root(root: Path) -> Path:
    subject_root = root / SUBJECT_ID
    input_dir = subject_root / "input"
    _touch(input_dir / "data.nii.gz")
    _touch(input_dir / "bvals")
    _touch(input_dir / "bvecs")
    _touch(input_dir / "nodif_brain_mask.nii.gz")
    return subject_root


def _make_nifti_subject_root(root: Path) -> Path:
    import nibabel as nib
    import numpy as np

    subject_root = root / SUBJECT_ID
    input_dir = subject_root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    bvals = np.array([0, 1000, 1000, 1000, 1000, 1000, 1000], dtype=float)
    bvecs = np.array(
        [
            [0, 1, 0, 0, 1 / np.sqrt(2), 1 / np.sqrt(2), 0],
            [0, 0, 1, 0, 1 / np.sqrt(2), 0, 1 / np.sqrt(2)],
            [0, 0, 0, 1, 0, 1 / np.sqrt(2), 1 / np.sqrt(2)],
        ],
        dtype=float,
    )
    tensor = np.diag([0.0015, 0.0003, 0.0003])
    data = np.zeros((4, 4, 4, len(bvals)), dtype=np.float32)
    data[..., 0] = 1000.0
    for index, (bval, gradient) in enumerate(zip(bvals[1:], bvecs.T[1:]), start=1):
        attenuation = np.exp(-bval * float(gradient @ tensor @ gradient))
        data[..., index] = 1000.0 * attenuation
    mask = np.ones((4, 4, 4), dtype=np.uint8)
    nib.save(nib.Nifti1Image(data, np.eye(4)), str(input_dir / "data.nii.gz"))
    nib.save(nib.Nifti1Image(mask, np.eye(4)), str(input_dir / "nodif_brain_mask.nii.gz"))
    (input_dir / "bvals").write_text(" ".join(f"{value:g}" for value in bvals) + "\n", encoding="utf-8")
    (input_dir / "bvecs").write_text(
        "\n".join(" ".join(f"{value:.10g}" for value in row) for row in bvecs) + "\n",
        encoding="utf-8",
    )
    return subject_root


def _make_native_cache(subject_root: Path, fit_method: str = "wls") -> Path:
    cache_dir = subject_root / "cache" / "native_dti" / fit_method
    _touch(cache_dir / "manifest.json", '{"kind": "native_dti"}')
    _touch(cache_dir / "DTI.nrrd")
    _touch(cache_dir / f"{SUBJECT_ID}-dti-FractionalAnisotropy.nii.gz")
    _touch(cache_dir / f"{SUBJECT_ID}-dti-MeanDiffusivity.nii.gz")
    return cache_dir


class DTITractographyScaffoldTest(unittest.TestCase):
    def test_eudx_length_limits_cover_dipy_unit_change(self) -> None:
        self.assertEqual(_eudx_length_limits("1.11.0", 0.5), (2, 500))
        self.assertEqual(_eudx_length_limits("1.12.1", 0.5), (0, 250))

    def test_writes_manifest_and_qc_when_native_cache_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = _make_subject_root(Path(tmp))
            cache_dir = _make_native_cache(subject_root)
            output_dir = subject_root / "outputs" / "tractography"

            result = run_dti_tracking(
                DTITrackingConfig(
                    subject_id=SUBJECT_ID,
                    input_root=subject_root,
                    output_dir=output_dir,
                    tracking_method="deterministic",
                    output_format="trk",
                )
            )

            self.assertFalse(result.executed)
            self.assertTrue(result.native_cache_available)
            self.assertEqual(result.native_bundle_dir, cache_dir)
            self.assertEqual(result.streamlines_path.name, f"{SUBJECT_ID}-dti-deterministic.trk")
            self.assertTrue(result.manifest_path.is_file())
            self.assertTrue(result.qc_path.is_file())

            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "planned")
            self.assertEqual(manifest["backend"], "dipy")
            self.assertFalse(manifest["executed"])
            self.assertTrue(manifest["native_dti_cache"]["available"])
            self.assertEqual(manifest["parameters"]["fit_method"], "wls")
            self.assertEqual(manifest["outputs"]["streamlines"], result.streamlines_path.as_posix())
            self.assertEqual(qc["status"], "planned")
            self.assertIsNone(qc["streamline_count"])

    def test_missing_native_cache_is_recorded_without_failing_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = _make_subject_root(Path(tmp))

            result = run_dti_tracking(
                DTITrackingConfig(
                    subject_id=SUBJECT_ID,
                    input_root=subject_root.parent,
                    output_format="tck",
                )
            )

            self.assertFalse(result.native_cache_available)
            self.assertEqual(result.streamlines_path.name, f"{SUBJECT_ID}-dti-deterministic.tck")
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertFalse(manifest["native_dti_cache"]["available"])
            self.assertFalse(Path(manifest["outputs"]["streamlines"]).exists())

    def test_execute_true_generates_streamlines_with_dipy_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = _make_nifti_subject_root(Path(tmp))
            output_dir = subject_root / "outputs" / "tractography"

            result = run_dti_tracking(
                DTITrackingConfig(
                    subject_id=SUBJECT_ID,
                    input_root=subject_root,
                    output_dir=output_dir,
                    output_format="trk",
                    min_fa=0.05,
                    seed_density=1,
                    max_seed_voxels=4,
                    execute=True,
                )
            )

            self.assertTrue(result.executed)
            self.assertTrue(result.streamlines_path.is_file())
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(qc["status"], "completed")
            self.assertGreaterEqual(qc["streamline_count"], 1)
            self.assertEqual(qc["seed_voxel_count"], 4)
            self.assertGreater(qc["tracking_mask_voxels"], qc["seed_voxel_count"])


if __name__ == "__main__":
    unittest.main()
