#!/usr/bin/env python3
"""Tests for optional DWI preprocessing wrapper."""

from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _write_subject(root: Path, subject_id: str = "100307") -> Path:
    subject = root / subject_id
    input_dir = subject / "input"
    input_dir.mkdir(parents=True)
    (input_dir / "data.nii.gz").write_text("dwi", encoding="utf-8")
    (input_dir / "bvals").write_text("0 1000 1000\n", encoding="utf-8")
    (input_dir / "bvecs").write_text("0 1 0\n0 0 1\n0 0 0\n", encoding="utf-8")
    (input_dir / "nodif_brain_mask.nii.gz").write_text("mask", encoding="utf-8")
    return subject


def _write_nifti_subject(root: Path, subject_id: str = "100307") -> Path:
    import nibabel as nib
    import numpy as np

    subject = root / subject_id
    input_dir = subject / "input"
    input_dir.mkdir(parents=True)
    data = np.zeros((5, 5, 5, 3), dtype=np.float32)
    data[..., 0] = 1.0
    data[2, 2, 2, 1] = 2.0
    data[2, 2, 3, 2] = 3.0
    mask = np.ones((5, 5, 5), dtype=np.uint8)
    nib.save(nib.Nifti1Image(data, np.eye(4)), str(input_dir / "data.nii.gz"))
    nib.save(nib.Nifti1Image(mask, np.eye(4)), str(input_dir / "nodif_brain_mask.nii.gz"))
    (input_dir / "bvals").write_text("0 1000 1000\n", encoding="utf-8")
    (input_dir / "bvecs").write_text("0 1 0\n0 0 1\n0 0 0\n", encoding="utf-8")
    return subject


def _write_fake_command(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_fake_backend(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True)
    _write_fake_command(
        bin_dir / "dwidenoise",
        """
import pathlib, sys
pathlib.Path(sys.argv[2]).write_text('denoised')
if '-noise' in sys.argv:
    pathlib.Path(sys.argv[sys.argv.index('-noise') + 1]).write_text('noise')
""",
    )
    _write_fake_command(
        bin_dir / "mrdegibbs",
        """
import pathlib, sys
pathlib.Path(sys.argv[2]).write_text('degibbs')
""",
    )
    _write_fake_command(
        bin_dir / "dwifslpreproc",
        """
import pathlib, sys
pathlib.Path(sys.argv[2]).write_text('preprocessed')
if '-export_grad_fsl' in sys.argv:
    idx = sys.argv.index('-export_grad_fsl')
    pathlib.Path(sys.argv[idx + 1]).write_text('0 1 0\\n0 0 1\\n0 0 0\\n')
    pathlib.Path(sys.argv[idx + 2]).write_text('0 1000 1000\\n')
""",
    )


class DwiPreprocessingPipelineTest(unittest.TestCase):
    def test_skip_writes_optional_skipped_manifest(self) -> None:
        from preprocessing import DwiPreprocessingConfig, run_dwi_preprocessing

        with tempfile.TemporaryDirectory() as tmp:
            subject = _write_subject(Path(tmp))
            result = run_dwi_preprocessing(
                DwiPreprocessingConfig(subject_id="100307", input_root=subject, skip=True)
            )

            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(result.status, "skipped")
            self.assertTrue(manifest["optional"])
            self.assertTrue(manifest["skip"])

    def test_dry_run_writes_plan_without_requiring_commands(self) -> None:
        from preprocessing import DwiPreprocessingConfig, run_dwi_preprocessing

        with tempfile.TemporaryDirectory() as tmp:
            subject = _write_subject(Path(tmp))
            result = run_dwi_preprocessing(
                DwiPreprocessingConfig(subject_id="100307", input_root=subject, execute=False)
            )

            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(result.status, "planned")
            self.assertEqual(manifest["status"], "planned")
            self.assertEqual(manifest["backend"]["backend"], "dipy")
            self.assertIn("motion_correction", " ".join(manifest["commands"][2]["argv"]))

    def test_execute_with_fake_backend_generates_final_outputs(self) -> None:
        from preprocessing import DwiPreprocessingConfig, inspect_preprocessing_backend, run_dwi_preprocessing

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            subject = _write_subject(tmp_path)
            bin_dir = tmp_path / "bin"
            _write_fake_backend(bin_dir)

            config = DwiPreprocessingConfig(
                subject_id="100307",
                input_root=subject,
                backend="mrtrix_fsl",
                execute=True,
                mrtrix_bin_dir=bin_dir,
                fsl_bin_dir=bin_dir,
            )
            backend = inspect_preprocessing_backend(config)
            self.assertTrue(backend["available"])

            result = run_dwi_preprocessing(config)

            self.assertEqual(result.status, "completed")
            self.assertTrue(result.final_dwi_path.is_file())
            self.assertTrue(result.final_bval_path.is_file())
            self.assertTrue(result.final_bvec_path.is_file())
            self.assertTrue(result.final_mask_path.is_file())

    def test_execute_dipy_basic_generates_final_outputs(self) -> None:
        from preprocessing import DwiPreprocessingConfig, run_dwi_preprocessing

        with tempfile.TemporaryDirectory() as tmp:
            subject = _write_nifti_subject(Path(tmp))
            result = run_dwi_preprocessing(
                DwiPreprocessingConfig(
                    subject_id="100307",
                    input_root=subject,
                    backend="dipy",
                    execute=True,
                    dipy_denoise_method="none",
                    dipy_run_gibbs=False,
                    dipy_run_motion_correction=False,
                )
            )

            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(result.status, "completed")
            self.assertTrue(result.final_dwi_path.is_file())
            self.assertEqual(qc["backend_details"]["denoise"]["status"], "skipped")
            self.assertEqual(qc["backend_details"]["motion"]["status"], "skipped")

    def test_execute_dipy_fast_path_links_raw_outputs(self) -> None:
        from preprocessing import DwiPreprocessingConfig, run_dwi_preprocessing

        with tempfile.TemporaryDirectory() as tmp:
            subject = _write_subject(Path(tmp))
            result = run_dwi_preprocessing(
                DwiPreprocessingConfig(
                    subject_id="100307",
                    input_root=subject,
                    backend="dipy",
                    execute=True,
                    dipy_denoise_method="none",
                    dipy_run_gibbs=False,
                    dipy_run_motion_correction=False,
                    force=True,
                )
            )

            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(result.status, "completed")
            self.assertTrue(result.final_dwi_path.exists())
            self.assertEqual(manifest["status"], "completed")
            self.assertTrue(qc["backend_details"]["fast_path"])


if __name__ == "__main__":
    unittest.main()
