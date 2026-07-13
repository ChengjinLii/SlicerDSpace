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
import os, pathlib, sys
pathlib.Path(sys.argv[2]).write_text('preprocessed')
pathlib.Path(sys.argv[2]).with_name('fsl_environment.txt').write_text(
    os.environ.get('FSLDIR', '') + '\\n' + os.environ.get('FSLOUTPUTTYPE', '') + '\\n'
)
scratch = pathlib.Path(sys.argv[sys.argv.index('-scratch') + 1])
scratch.mkdir(parents=True, exist_ok=True)
prefix = scratch / 'dwi_post_eddy'
for suffix in (
    '.eddy_parameters', '.eddy_movement_rms', '.eddy_outlier_map',
    '.eddy_outlier_report', '.eddy_cnr_maps.nii.gz', '.eddy_residuals.nii.gz',
):
    pathlib.Path(str(prefix) + suffix).write_text('eddy artifact: ' + suffix)
if '-export_grad_fsl' in sys.argv:
    idx = sys.argv.index('-export_grad_fsl')
    pathlib.Path(sys.argv[idx + 1]).write_text('0 1 0\\n0 0 1\\n0 0 0\\n')
    pathlib.Path(sys.argv[idx + 2]).write_text('0 1000 1000\\n')
""",
    )


class DwiPreprocessingPipelineTest(unittest.TestCase):
    def test_rotate_bvecs_accepts_n_by_4_by_4_affines(self) -> None:
        import numpy as np

        from preprocessing.pipeline import _rotate_bvecs_best_effort

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bvec"
            output = root / "rotated.bvec"
            source.write_text("1 0 0\n0 1 0\n0 0 1\n", encoding="utf-8")
            rotation = np.array(
                [
                    [0.0, -1.0, 0.0, 0.0],
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ]
            )
            affines = np.repeat(np.eye(4)[None, ...], 3, axis=0)
            affines[1] = rotation

            status = _rotate_bvecs_best_effort(source, output, affines)

            rotated = np.loadtxt(output)
            self.assertEqual(status["status"], "rotated")
            self.assertEqual(status["affine_layout"], "Nx4x4")
            np.testing.assert_allclose(rotated[:, 0], [1.0, 0.0, 0.0], atol=1e-8)
            np.testing.assert_allclose(rotated[:, 1], [-1.0, 0.0, 0.0], atol=1e-8)

    def test_rotate_bvecs_accepts_dipy_4_by_4_by_n_affines(self) -> None:
        import numpy as np

        from preprocessing.pipeline import _rotate_bvecs_best_effort

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bvec"
            output = root / "rotated.bvec"
            source.write_text("1 0 0\n0 1 0\n0 0 1\n", encoding="utf-8")
            rotation = np.array(
                [
                    [0.0, -1.0, 0.0, 0.0],
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ]
            )
            affines = np.repeat(np.eye(4)[None, ...], 3, axis=0)
            affines[1] = rotation

            status = _rotate_bvecs_best_effort(source, output, np.moveaxis(affines, 0, -1))

            rotated = np.loadtxt(output)
            self.assertEqual(status["status"], "rotated")
            self.assertEqual(status["affine_layout"], "4x4xN")
            np.testing.assert_allclose(rotated[:, 0], [1.0, 0.0, 0.0], atol=1e-8)
            np.testing.assert_allclose(rotated[:, 1], [-1.0, 0.0, 0.0], atol=1e-8)

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
            fsl_environment = (result.final_dwi_path.parent / "fsl_environment.txt").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(fsl_environment, [bin_dir.parent.resolve().as_posix(), "NIFTI_GZ"])
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            expected_suffixes = {
                "eddy_parameters": "_eddy_parameters.txt",
                "eddy_movement_rms": "_eddy_movement_rms.txt",
                "eddy_outlier_map": "_eddy_outlier_map.txt",
                "eddy_outlier_report": "_eddy_outlier_report.txt",
                "eddy_cnr_maps": "_eddy_cnr_maps.nii.gz",
                "eddy_residuals": "_eddy_residuals.nii.gz",
            }
            for key, suffix in expected_suffixes.items():
                self.assertTrue(qc["files"][key]["exists"], key)
                self.assertTrue(qc["files"][key]["path"].endswith(suffix), key)
                self.assertEqual(
                    qc["backend_details"]["eddy_qc_collection"]["artifacts"][key]["status"],
                    "copied",
                )

    def test_mrtrix_rpe_none_forwards_phase_encoding_and_readout(self) -> None:
        from preprocessing import DwiPreprocessingConfig, run_dwi_preprocessing

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            subject = _write_subject(tmp_path)
            bin_dir = tmp_path / "fsl" / "bin"
            _write_fake_backend(bin_dir)

            result = run_dwi_preprocessing(
                DwiPreprocessingConfig(
                    subject_id="100307",
                    input_root=subject,
                    backend="mrtrix_fsl",
                    execute=False,
                    mrtrix_bin_dir=bin_dir,
                    fsl_bin_dir=bin_dir,
                    phase_encoding_direction="AP",
                    readout_time=0.1,
                )
            )

            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            command = manifest["commands"][2]["argv"]
            self.assertIn("-rpe_none", command)
            self.assertEqual(command[command.index("-pe_dir") + 1], "AP")
            self.assertEqual(command[command.index("-readout_time") + 1], "0.1")

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
