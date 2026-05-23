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


def _make_native_cache(subject_root: Path, fit_method: str = "wls") -> Path:
    cache_dir = subject_root / "cache" / "native_dti" / fit_method
    _touch(cache_dir / "manifest.json", '{"kind": "native_dti"}')
    _touch(cache_dir / "DTI.nrrd")
    _touch(cache_dir / f"{SUBJECT_ID}-dti-FractionalAnisotropy.nii.gz")
    _touch(cache_dir / f"{SUBJECT_ID}-dti-MeanDiffusivity.nii.gz")
    return cache_dir


class DTITractographyScaffoldTest(unittest.TestCase):
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

    def test_execute_true_is_not_enabled_yet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = _make_subject_root(Path(tmp))

            with self.assertRaises(NotImplementedError):
                run_dti_tracking(
                    DTITrackingConfig(
                        subject_id=SUBJECT_ID,
                        input_root=subject_root,
                        execute=True,
                    )
                )


if __name__ == "__main__":
    unittest.main()
