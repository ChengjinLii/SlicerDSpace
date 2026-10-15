#!/usr/bin/env python3
"""Tests for DTI scalar map materialization in the microstructure workflow."""

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


class MicrostructureDTIScalarsTest(unittest.TestCase):
    def test_free_water_qc_validates_saved_maps(self) -> None:
        from microstructure.pipeline import _output_paths, _write_free_water_qc

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _output_paths("100307", root / "outputs" / "02_microstructure")
            for path in paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
            affine = np.eye(4)
            mask = np.asarray([1, 1, 0], dtype=np.uint8).reshape(3, 1, 1)
            valid = np.asarray([1, 0, 0], dtype=np.uint8).reshape(3, 1, 1)
            arrays = {
                "fwf": np.asarray([0.2, 0.8, 0.0], dtype=np.float32).reshape(3, 1, 1),
                "fw_tissue_fa": np.asarray([0.4, 0.0, 0.0], dtype=np.float32).reshape(3, 1, 1),
                "fw_tissue_md": np.asarray([0.0008, 0.0, 0.0], dtype=np.float32).reshape(3, 1, 1),
                "fw_tissue_valid_mask": valid,
            }
            input_paths = {name: root / name for name in ("dwi", "bval", "bvec")}
            input_paths["mask"] = root / "mask.nii.gz"
            nib.save(nib.Nifti1Image(mask, affine), input_paths["mask"])
            for name in ("dwi", "bval", "bvec"):
                input_paths[name].write_text("x", encoding="utf-8")
            for key, array in arrays.items():
                nib.save(nib.Nifti1Image(array, affine), paths[key])
            raw = type(
                "Raw",
                (),
                {
                    "dwi_path": input_paths["dwi"],
                    "bval_path": input_paths["bval"],
                    "bvec_path": input_paths["bvec"],
                    "mask_path": input_paths["mask"],
                },
            )()
            config = type(
                "Config",
                (),
                {
                    "subject_id": "100307",
                    "raw_input_bundle": raw,
                    "free_water_max_fraction_for_tissue": 0.7,
                },
            )()

            payload = _write_free_water_qc(config, paths)

            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["validity"]["brain_mask_voxels"], 2)
            self.assertEqual(payload["validity"]["valid_tissue_voxels"], 1)
            self.assertTrue(paths["free_water_qc"].is_file())

    def test_free_water_scalar_sanitizer_rejects_unreliable_tissue_fits(self) -> None:
        from microstructure.pipeline import _sanitize_free_water_scalars

        fwf, tissue_fa, tissue_md, valid, invalid_count = _sanitize_free_water_scalars(
            np.asarray([0.25, np.nan, 0.8, 0.4, 0.3], dtype=np.float32),
            np.asarray([0.4, 0.7, 0.5, 1.0, 0.5], dtype=np.float32),
            np.asarray([7.0e-4, 8.0e-4, 9.0e-4, 3.3e-4, 4.0e-3], dtype=np.float32),
            np.asarray(
                [
                    [1.2e-3, 7.0e-4, 2.0e-4],
                    [1.2e-3, 7.0e-4, 2.0e-4],
                    [1.2e-3, 7.0e-4, 2.0e-4],
                    [1.0e-3, 0.0, 0.0],
                    [6.0e-3, 4.0e-3, 2.0e-3],
                ],
                dtype=np.float32,
            ),
        )

        np.testing.assert_allclose(fwf, [0.25, 0.0, 0.8, 0.4, 0.3])
        np.testing.assert_allclose(tissue_fa, [0.4, 0.0, 0.0, 0.0, 0.0])
        np.testing.assert_allclose(tissue_md, [7.0e-4, 0.0, 0.0, 0.0, 0.0])
        np.testing.assert_array_equal(valid, [True, False, False, False, False])
        self.assertEqual(invalid_count, 4)

    def test_expected_manifest_distinguishes_selected_and_available_optional_maps(self) -> None:
        from microstructure.pipeline import (
            MicrostructureConfig,
            _expected_free_water_manifest,
            _expected_manifest,
            _expected_noddi_manifest,
            _free_water_outputs_current,
            _noddi_outputs_current,
            _output_paths,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {name: root / name for name in ("dwi", "bval", "bvec", "mask")}
            for path in inputs.values():
                path.write_text("x", encoding="utf-8")
            native_dir = root / "native"
            native_dir.mkdir()
            config = object.__new__(MicrostructureConfig)
            object.__setattr__(config, "run_free_water", True)
            object.__setattr__(config, "run_noddi", False)
            object.__setattr__(config, "subject_id", "100307")
            object.__setattr__(config, "native_bundle", type("Native", (), {"fit_method": "wls", "bundle_dir": native_dir, "manifest_path": native_dir / "manifest.json"})())
            raw = type(
                "Raw",
                (),
                {
                    "dwi_path": inputs["dwi"],
                    "bval_path": inputs["bval"],
                    "bvec_path": inputs["bvec"],
                    "mask_path": inputs["mask"],
                },
            )()
            object.__setattr__(config, "raw_input_bundle", raw)
            object.__setattr__(config, "free_water_fit_method", "WLS")
            object.__setattr__(config, "free_water_chunk_size", 2)
            object.__setattr__(config, "free_water_engine", "serial")
            object.__setattr__(config, "free_water_n_jobs", None)
            object.__setattr__(config, "free_water_vox_per_chunk", None)
            object.__setattr__(config, "free_water_max_fraction_for_tissue", 0.7)
            object.__setattr__(config, "noddi_directional_average", False)
            object.__setattr__(config, "noddi_b0_threshold", 50)
            object.__setattr__(config, "noddi_lmax", 12)
            object.__setattr__(config, "noddi_ndirs", 500)
            object.__setattr__(config, "noddi_nthreads", 1)
            object.__setattr__(config, "noddi_solver_lambda1", 0.5)
            object.__setattr__(config, "noddi_solver_lambda2", 0.001)
            object.__setattr__(config, "noddi_max_isotropic_fraction_for_tissue", 0.7)

            manifest = _expected_manifest(
                config,
                None,
                free_water_available=True,
                noddi_available=True,
            )
            paths = _output_paths("100307", root / "outputs" / "02_microstructure")
            for key in (
                "fwf",
                "fw_tissue_fa",
                "fw_tissue_md",
                "fw_tissue_valid_mask",
                "free_water_qc",
                "noddi_ndi",
                "noddi_odi",
                "noddi_fwf",
                "noddi_tissue_valid_mask",
                "noddi_rmse",
                "noddi_nrmse",
                "noddi_qc",
            ):
                paths[key].parent.mkdir(parents=True, exist_ok=True)
                paths[key].write_text("map", encoding="utf-8")
            from microstructure.pipeline import _file_signature, FREE_WATER_KEYS, NODDI_KEYS

            for qc_key, keys in (("free_water_qc", FREE_WATER_KEYS), ("noddi_qc", NODDI_KEYS)):
                paths[qc_key].write_text(json.dumps({
                    "status": "completed", "automatic_qc_passed": True, "checks": {"fixture": True},
                    "output_artifacts": {str(paths[key].resolve()): _file_signature(paths[key]) for key in keys},
                }), encoding="utf-8")
            paths["free_water_manifest"].write_text(
                json.dumps(_expected_free_water_manifest(config)),
                encoding="utf-8",
            )
            paths["noddi_manifest"].write_text(
                json.dumps(_expected_noddi_manifest(config)),
                encoding="utf-8",
            )

            self.assertTrue(_free_water_outputs_current(config, paths))
            self.assertTrue(_noddi_outputs_current(config, paths))
            inputs["dwi"].write_text("different input", encoding="utf-8")
            self.assertFalse(_free_water_outputs_current(config, paths))
            self.assertFalse(_noddi_outputs_current(config, paths))

        self.assertTrue(manifest["free_water_model"]["run_enabled"])
        self.assertFalse(manifest["noddi_model"]["run_enabled"])
        self.assertTrue(manifest["noddi_model"]["outputs_available"])
        self.assertIn("NODDI_NDI", manifest["roi_metrics"])

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
            self.assertEqual(paths["fw_tissue_valid_mask"].name, "100307_fw_tissue_valid_mask.nii.gz")
            self.assertEqual(paths["free_water_qc"].name, "freewater_qc.json")
            self.assertEqual(paths["noddi_tissue_valid_mask"].name, "100307_noddi_tissue_valid_mask.nii.gz")
            self.assertEqual(paths["noddi_rmse"].name, "100307_noddi_RMSE.nii.gz")
            self.assertEqual(paths["noddi_nrmse"].name, "100307_noddi_NRMSE.nii.gz")
            self.assertEqual(paths["noddi_qc"].name, "noddi_qc.json")
            self.assertEqual(paths["free_water_progress"].name, "freewater_progress.json")
            self.assertEqual(paths["noddi_progress"].name, "noddi_progress.json")

    def test_noddi_sanitizer_preserves_display_map_but_masks_tissue_statistics(self) -> None:
        from microstructure.pipeline import _sanitize_noddi_maps

        ndi, odi, isovf, valid, qc = _sanitize_noddi_maps(
            np.asarray([0.2, 0.99, 0.99, np.nan], dtype=np.float32),
            np.asarray([0.4, 0.7, 0.6, 0.2], dtype=np.float32),
            np.asarray([0.2, 0.8, 0.7, 0.1], dtype=np.float32),
            np.asarray([True, True, True, True]),
            max_isotropic_fraction=0.7,
        )

        np.testing.assert_array_equal(valid, [True, False, True, False])
        np.testing.assert_allclose(ndi, [0.2, 0.99, 0.99, 0.0])
        np.testing.assert_allclose(odi, [0.4, 0.7, 0.6, 0.0])
        np.testing.assert_allclose(isovf, [0.2, 0.8, 0.7, 0.1])
        self.assertEqual(qc["excluded_high_isotropic_voxels"], 1)
        self.assertEqual(qc["excluded_nonfinite_or_out_of_range_voxels"], 1)

    def test_roi_stats_exclude_zero_pair_used_for_invalid_free_water_tissue_fit(self) -> None:
        from microstructure.pipeline import _compute_roi_stats

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            affine = np.eye(4)
            roi_path = root / "roi.nii.gz"
            fa_path = root / "fw_fa.nii.gz"
            md_path = root / "fw_md.nii.gz"
            nib.save(nib.Nifti1Image(np.ones((3, 1, 1), dtype=np.int16), affine), str(roi_path))
            nib.save(
                nib.Nifti1Image(np.asarray([0.4, 0.0, 0.6], dtype=np.float32).reshape(3, 1, 1), affine),
                str(fa_path),
            )
            nib.save(
                nib.Nifti1Image(np.asarray([7.0e-4, 0.0, 9.0e-4], dtype=np.float32).reshape(3, 1, 1), affine),
                str(md_path),
            )
            json_path = root / "stats.json"

            count = _compute_roi_stats(
                metric_paths={"fw_tissue_fa": fa_path, "fw_tissue_md": md_path},
                roi_label_map=roi_path,
                lut_path=None,
                csv_path=root / "stats.csv",
                json_path=json_path,
            )
            row = json.loads(json_path.read_text(encoding="utf-8"))["rows"][0]

            self.assertEqual(count, 1)
            self.assertEqual(row["voxel_count"], 2)
            self.assertAlmostEqual(row["fw_tissue_fa_mean"], 0.5)
            self.assertAlmostEqual(row["fw_tissue_md_mean"], 8.0e-4)
            self.assertGreater(row["fw_tissue_md_min"], 0.0)

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
