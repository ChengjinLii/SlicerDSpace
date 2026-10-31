#!/usr/bin/env python3
"""Tests for the multi-subject scientific output audit."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from vtp_fixture import vtp_lines


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ScientificOutputAuditTest(unittest.TestCase):
    def test_preprocessing_independently_rejects_invalid_numerical_outputs(self):
        import nibabel as nib
        import numpy as np
        from scripts.audit_scientific_outputs import _audit_preprocessing

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = {key: root / name for key, name in {
                "dwi": "dwi.nii.gz", "mask": "mask.nii.gz",
                "bval": "bvals", "bvec": "bvecs",
            }.items()}
            nib.save(nib.Nifti1Image(np.ones((2, 2, 2), dtype=np.uint8), np.eye(4)), paths["mask"])
            paths["bvec"].write_text("0 1 1\n0 0 0\n0 0 0\n")
            native = root / "preprocessing.json"
            native.write_text(json.dumps({"cache_key": "fixture"}))
            qc = root / "qc.json"
            qc.write_text(json.dumps({"status": "completed"}))
            manifest = {"tasks": [{"name": "preprocessing.dwi", "status": "completed",
                                   "manifest_path": str(native), "qc_path": str(qc),
                                   "outputs": {key: str(path) for key, path in paths.items()}}]}
            for condition, bad_check in (("valid", None), ("nan", "preprocessing.dwi_finite"),
                                         ("inf", "preprocessing.dwi_finite"),
                                         ("zero", "preprocessing.brain_signal"),
                                         ("negative_bval", "preprocessing.bvals_nonnegative")):
                with self.subTest(condition=condition):
                    data = np.ones((2, 2, 2, 3), dtype=np.float32)
                    if condition in {"nan", "inf"}:
                        data[0, 0, 0, 1] = np.nan if condition == "nan" else np.inf
                    elif condition == "zero":
                        data.fill(0)
                    nib.save(nib.Nifti1Image(data, np.eye(4)), paths["dwi"])
                    paths["bval"].write_text("0 -1000 1000\n" if condition == "negative_bval" else "0 1000 1000\n")
                    checks = []
                    self.assertTrue(_audit_preprocessing(manifest, checks))
                    failures = {check["name"] for check in checks if not check["passed"]}
                    self.assertEqual(failures, {bad_check} if bad_check else set())

    def _fixture(
        self,
        root: Path,
        *,
        invalid_fa: bool = False,
        ddseg_only: bool = False,
        full_routes: bool = False,
        tractography_qc_length_offset_mm: float | None = None,
        legacy_wma_qc: bool = False,
    ) -> Path:
        import nibabel as nib
        import numpy as np

        subject_root = root / "input-subject"
        input_dir = subject_root / "input"
        input_dir.mkdir(parents=True)
        affine = np.eye(4)
        dwi = np.ones((3, 3, 3, 7), dtype=np.float32)
        mask = np.ones((3, 3, 3), dtype=np.uint8)
        mask[0, 0, 0] = 0
        nib.save(nib.Nifti1Image(dwi, affine), input_dir / "data.nii.gz")
        nib.save(nib.Nifti1Image(mask, affine), input_dir / "nodif_brain_mask.nii.gz")

        output_root = root / "outputs"
        subject_output = output_root / "sub-01"
        dti_dir = subject_output / "02_microstructure" / "dti"
        tract_dir = subject_output / "04_tractography" / "tractograms" / "dti_det" / "Test1"
        metadata_dir = subject_output / "00_run_metadata"
        dti_dir.mkdir(parents=True)
        tract_dir.mkdir(parents=True)
        metadata_dir.mkdir(parents=True)

        l1 = np.full(mask.shape, 0.0015, dtype=np.float32)
        l2 = np.full(mask.shape, 0.0006, dtype=np.float32)
        l3 = np.full(mask.shape, 0.0003, dtype=np.float32)
        arrays = {
            "fa": np.full(mask.shape, 1.2 if invalid_fa else 0.5, dtype=np.float32),
            "md": (l1 + l2 + l3) / 3.0,
            "ad": l1,
            "rd": (l2 + l3) / 2.0,
            "l1": l1,
            "l2": l2,
            "l3": l3,
            "trace": l1 + l2 + l3,
        }
        outputs: dict[str, str] = {}
        for key, array in arrays.items():
            path = dti_dir / f"sub-01_dti_{key.upper()}.nii.gz"
            nib.save(nib.Nifti1Image(array, affine), path)
            outputs[key] = path.as_posix()

        tract_path = tract_dir / "sub-01-dti-deterministic.trk"
        tractogram = nib.streamlines.Tractogram(
            [np.asarray([[0.25, 0.25, 0.25], [1.25, 1.25, 1.25]], dtype=np.float32)],
            affine_to_rasmm=np.eye(4),
        )
        nib.streamlines.save(tractogram, tract_path.as_posix())
        tractography_task = {
            "name": "tractography.dti_det",
            "status": "completed",
            "outputs": {"tractogram_trk": tract_path.as_posix()},
        }
        if tractography_qc_length_offset_mm is not None:
            saved_streamline = next(iter(nib.streamlines.load(tract_path.as_posix()).streamlines))
            saved_length = float(
                np.linalg.norm(np.diff(saved_streamline, axis=0), axis=1).sum()
            )
            tractography_qc = tract_dir / "tractography_qc.json"
            tractography_qc.write_text(
                json.dumps(
                    {
                        "streamline_count": 1,
                        "length_min_mm": saved_length + tractography_qc_length_offset_mm,
                        "length_max_mm": saved_length + tractography_qc_length_offset_mm,
                    }
                ),
                encoding="utf-8",
            )
            tractography_task["qc_path"] = tractography_qc.as_posix()
        tasks = [
            {"name": "microstructure.dti", "status": "completed", "outputs": outputs},
            tractography_task,
        ]
        if ddseg_only:
            ddseg_dir = subject_output / "03_structural" / "ddseg"
            ddseg_dir.mkdir(parents=True)
            segmentation = np.ones(mask.shape, dtype=np.uint8)
            segmentation[:, :, 1] = 2
            segmentation[:, :, 2] = 3
            segmentation_path = ddseg_dir / "SegmentationMap_GMWMCSF.nii.gz"
            nib.save(nib.Nifti1Image(segmentation, affine), segmentation_path)
            ddseg_outputs = {"segmentation": segmentation_path.as_posix()}
            # DDSeg labels are background=0, WM=1, GM=2, and CSF=3. The
            # omitted background probability means the three saved tissue
            # maps may legitimately sum to less than one.
            for label, key in ((2, "gm"), (1, "wm"), (3, "csf")):
                path = ddseg_dir / f"ProbabilisticMap_{key.upper()}.nii.gz"
                nib.save(
                    nib.Nifti1Image(0.9 * (segmentation == label).astype(np.float32), affine),
                    path,
                )
                ddseg_outputs[f"{key}_probability"] = path.as_posix()
            tasks.append(
                {
                    "name": "segmentation.ddseg",
                    "status": "completed",
                    "outputs": ddseg_outputs,
                }
            )

        if full_routes:
            freewater_dir = subject_output / "02_microstructure" / "freewater"
            noddi_dir = subject_output / "02_microstructure" / "noddi"
            freewater_dir.mkdir(parents=True)
            noddi_dir.mkdir(parents=True)
            freewater_outputs = {}
            for key, value in (("fwf", 0.2), ("fw_fa", 0.4), ("fw_md", 0.001), ("valid_mask", 1.0)):
                path = freewater_dir / f"sub-01_{key}.nii.gz"
                nib.save(nib.Nifti1Image(np.full(mask.shape, value, dtype=np.float32), affine), path)
                freewater_outputs[key] = path.as_posix()
            freewater_qc = freewater_dir / "freewater_qc.json"
            freewater_qc.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "input": {"mask": (input_dir / "nodif_brain_mask.nii.gz").as_posix()},
                        "checks": {"synthetic_contract": True},
                        "validity": {"valid_tissue_fraction": 1.0},
                    }
                ),
                encoding="utf-8",
            )
            freewater_outputs["qc"] = freewater_qc.as_posix()
            noddi_outputs = {}
            for key, value in (
                ("ndi", 0.6),
                ("odi", 0.3),
                ("isovf", 0.1),
                ("rmse", 0.01),
                ("nrmse", 0.01),
                ("valid_mask", 1.0),
            ):
                path = noddi_dir / f"sub-01_{key}.nii.gz"
                array = np.full(mask.shape, value, dtype=np.float32)
                if key in {"ndi", "odi"}:
                    array[mask == 0] = 0.0
                nib.save(nib.Nifti1Image(array, affine), path)
                output_key = {
                    "ndi": "noddi_ndi",
                    "odi": "noddi_odi",
                    "isovf": "noddi_fwf",
                    "rmse": "noddi_rmse",
                    "nrmse": "noddi_nrmse",
                    "valid_mask": "noddi_tissue_valid_mask",
                }[key]
                noddi_outputs[output_key] = path.as_posix()
            noddi_qc = noddi_dir / "noddi_qc.json"
            noddi_qc.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "input": {"mask": (input_dir / "nodif_brain_mask.nii.gz").as_posix()},
                        "validity": {"valid_tissue_fraction": 1.0},
                        "summary": {"nrmse_valid_tissue": {"p95": 0.01}},
                    }
                ),
                encoding="utf-8",
            )
            noddi_outputs["qc"] = noddi_qc.as_posix()
            tasks.extend(
                [
                    {"name": "microstructure.freewater", "status": "completed", "outputs": freewater_outputs},
                    {"name": "microstructure.noddi", "status": "completed", "outputs": noddi_outputs},
                ]
            )

            csd_dir = subject_output / "04_tractography" / "tractograms" / "Test1"
            csd_dir.mkdir(parents=True)
            csd_tck = csd_dir / "sub-01_csd_act_ifod2.tck"
            csd_vtk = csd_dir / "sub-01_csd_act_ifod2.vtk"
            nib.streamlines.save(tractogram, csd_tck.as_posix())
            csd_vtk.write_text(
                "# vtk DataFile Version 3.0\nASCII\nDATASET POLYDATA\n"
                "POINTS 2 float\n0 0 0 1 0 0\nLINES 1 3\n2 0 1\n",
                encoding="utf-8",
            )
            csd_manifest = csd_dir / "csd_act_manifest.json"
            csd_qc = csd_dir / "csd_act_qc.json"
            from tractography.act_prep import ACT_PREP_VERSION
            act_dependencies = {}
            for key in ("five_tt", "gmwmi"):
                path = csd_dir / (key + ".nii.gz")
                nib.save(nib.Nifti1Image(np.ones((3, 3, 3), dtype=np.float32), np.eye(4)), path)
                stat = path.stat()
                act_dependencies[key] = dict(path=str(path), size=stat.st_size, mtime_ns=stat.st_mtime_ns)
            prior = csd_dir / "source_parcellation.nii.gz"
            nib.save(nib.Nifti1Image(np.full((3, 3, 3), 10, dtype=np.int16), np.eye(4)), prior)
            prior_stat = prior.stat()
            (csd_dir / "act_prep_qc.json").write_text(json.dumps(dict(status="completed", version=ACT_PREP_VERSION,
                sgm_from_ddparcel=True, five_tt_stats={"channel_volume_voxel_units": {"sgm": 27.0}})))
            (csd_dir / "act_prep_manifest.json").write_text(json.dumps(dict(inputs={"parcellation": {
                "path": str(prior), "exists": True, "size": prior_stat.st_size, "mtime_ns": prior_stat.st_mtime_ns}})))
            csd_manifest.write_text(
                json.dumps({"parameters": {"min_length_mm": 1.0, "max_length_mm": 250.0}, "dependencies": act_dependencies}),
                encoding="utf-8",
            )
            csd_qc.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "scientific_output_summary": {
                            "tck": {"streamline_count": 1, "all_points_finite": True}
                        },
                    }
                ),
                encoding="utf-8",
            )
            tasks.append(
                {
                    "name": "tractography.csd_act",
                    "status": "completed",
                    "qc_path": csd_qc.as_posix(),
                    "manifest_path": csd_manifest.as_posix(),
                    "outputs": {
                        "tractogram": csd_tck.as_posix(),
                        "tractogram_vtk": csd_vtk.as_posix(),
                    },
                }
            )

            saf_dir = subject_output / "04_tractography" / "saf" / "Test1"
            saf_dir.mkdir(parents=True)
            saf_tck = saf_dir / "SAF.tck"
            saf_vtk = saf_dir / "SAF.vtk"
            nib.streamlines.save(tractogram, saf_tck.as_posix())
            saf_vtk.write_text("vtk\n", encoding="utf-8")
            saf_qc = saf_dir / "saf_qc.json"
            saf_manifest = saf_dir / "saf_manifest.json"
            saf_qc.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "streamline_count": 1,
                        "output_summary": {
                            "saf_tractogram": {"path": saf_tck.as_posix()},
                            "saf_vtk": {"path": saf_vtk.as_posix()},
                        },
                        "scientific_output_summary": {
                            "streamline_count": 1,
                            "all_points_finite": True,
                            "length_mm": {"min": 1.0, "max": 2.0},
                        },
                    }
                ),
                encoding="utf-8",
            )
            saf_manifest.write_text(json.dumps({"status": "completed"}), encoding="utf-8")
            tasks.append(
                {
                    "name": "tractography.saf",
                    "status": "completed",
                    "qc_path": saf_qc.as_posix(),
                    "manifest_path": saf_manifest.as_posix(),
                    "outputs": {"tractogram": saf_tck.as_posix(), "tractogram_vtk": saf_vtk.as_posix()},
                }
            )

            wmql_dir = subject_output / "04_tractography" / "bundles" / "wmql" / "Test1"
            wmql_dir.mkdir(parents=True)
            wmql_bundle = wmql_dir / "sub-01_desc-wmql_af.left.trk"
            sampled = nib.streamlines.Tractogram(list(tractogram.streamlines) * 20, affine_to_rasmm=np.eye(4))
            nib.streamlines.save(sampled, wmql_bundle.as_posix())
            wmql_qc = wmql_dir / "wmql_qc.json"
            wmql_qc.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "output_summary": {
                            "bundle_count": 1,
                            "bundle_readable_count": 1,
                            "bundle_nonempty_count": 1,
                            "bundle_files": [wmql_bundle.as_posix()],
                        },
                    }
                ),
                encoding="utf-8",
            )
            tasks.append({"name": "bundles.wmql", "status": "completed", "qc_path": wmql_qc.as_posix()})

            wma_dir = subject_output / "04_tractography" / "bundles" / "wma" / "Test1"
            wma_input = subject_output / "04_tractography" / "subject_ukf_whole_brain.vtk"
            wma_input.write_text("vtk\n", encoding="utf-8")
            anatomy_dir = (
                wma_dir / wma_input.stem / "AnatomicalTracts"
                if legacy_wma_qc
                else wma_dir / "AnatomicalTracts"
            )
            anatomy_dir.mkdir(parents=True)
            from tractography.wma import REQUIRED_MAJOR_TRACTS

            names = list(REQUIRED_MAJOR_TRACTS) + [f"tract-{index:02d}.vtp" for index in range(68)]
            for name in names:
                (anatomy_dir / name).write_text(
                    vtp_lines(20),
                    encoding="utf-8",
                )
            wma_qc = wma_dir / "wma_qc.json"
            wma_manifest = wma_dir / "wma_manifest.json"
            wma_summary = {
                "anatomical_tract_count": 73,
                "anatomical_tract_readable_count": 73,
                "anatomical_tract_nonempty_count": 73,
                "anatomical_tracts_dir": anatomy_dir.as_posix(),
            }
            if legacy_wma_qc:
                wma_summary = {"anatomical_tract_count": 73}
            wma_qc.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "output_summary": wma_summary,
                    }
                ),
                encoding="utf-8",
            )
            wma_manifest.write_text(
                json.dumps(
                    {
                        "input_tractography": wma_input.as_posix(),
                        "output_dir": wma_dir.as_posix(),
                    }
                ),
                encoding="utf-8",
            )
            tasks.append(
                {
                    "name": "bundles.wma",
                    "status": "completed",
                    "qc_path": wma_qc.as_posix(),
                    "manifest_path": wma_manifest.as_posix(),
                }
            )

            tractcloud_dir = subject_output / "04_tractography" / "bundles" / "tractcloud" / "Test1"
            tractcloud_dir.mkdir(parents=True)
            tractcloud_bundle = tractcloud_dir / "bundle.vtp"
            tractcloud_bundle.write_text(vtp_lines(1), encoding="utf-8")
            tractcloud_qc = tractcloud_dir / "tractcloud_qc.json"
            tractcloud_manifest = tractcloud_dir / "tractcloud_manifest.json"
            tractcloud_qc.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "output_summary": {
                            "bundle_count": 1,
                            "bundle_readable_count": 1,
                            "bundle_nonempty_count": 1,
                            "assigned_streamline_count": 1,
                            "bundle_files": [tractcloud_bundle.as_posix()],
                        },
                    }
                ),
                encoding="utf-8",
            )
            tractcloud_manifest.write_text(
                json.dumps({"input_tractography": csd_vtk.as_posix()}),
                encoding="utf-8",
            )
            tasks.append(
                {
                    "name": "bundles.tractcloud",
                    "status": "completed",
                    "qc_path": tractcloud_qc.as_posix(),
                    "manifest_path": tractcloud_manifest.as_posix(),
                }
            )

            connectome_dir = subject_output / "04_tractography" / "connectome" / "Test1"
            connectome_dir.mkdir(parents=True)
            matrix_path = connectome_dir / "connectome.csv"
            nodes_path = connectome_dir / "nodes.tsv"
            matrix_path.write_text("source_node,target_node,streamline_count\n2,4,3\n", encoding="utf-8")
            nodes_path.write_text("node_id\tlabel\tname\n1\t2\tA\n2\t4\tB\n", encoding="utf-8")
            connectome_qc = connectome_dir / "connectome_qc.json"
            connectome_manifest = connectome_dir / "connectome_manifest.json"
            connectome_qc.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "metric": "streamline_count",
                        "edge_count": 1,
                        "node_count": 2,
                        "streamline_count_assigned": 3,
                    }
                ),
                encoding="utf-8",
            )
            connectome_manifest.write_text(
                json.dumps(
                    {
                        "metric": "streamline_count",
                        "outputs": {"matrix": matrix_path.as_posix(), "nodes": nodes_path.as_posix()},
                    }
                ),
                encoding="utf-8",
            )
            tasks.append(
                {
                    "name": "connectome.streamline_count",
                    "status": "completed",
                    "qc_path": connectome_qc.as_posix(),
                    "manifest_path": connectome_manifest.as_posix(),
                }
            )

        manifest = {
            "subject_id": "sub-01",
            "subject_root": subject_root.as_posix(),
            "output_root": subject_output.as_posix(),
            "tasks": tasks,
        }
        (metadata_dir / "Test1_orchestration_manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        return output_root

    def test_valid_dti_and_tractography_batch_passes(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(Path(tmp))
            report = audit_output_root(
                output_root,
                require_dti=True,
                require_tractography=True,
                min_subjects=1,
            )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["summary"]["passed_subjects"], 1)

    def test_single_subject_output_root_is_supported(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(Path(tmp))
            report = audit_output_root(
                output_root / "sub-01",
                require_dti=True,
                require_tractography=True,
            )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["summary"]["subject_count"], 1)

    def test_failed_validation_run_cannot_pass_scientific_audit(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            subject_output = Path(tmp) / "outputs" / "sub-01"
            metadata_dir = subject_output / "00_run_metadata"
            validation_dir = metadata_dir / "validation"
            validation_dir.mkdir(parents=True)
            report_path = validation_dir / "sub-01_input_validation.json"
            report_path.write_text(
                json.dumps(
                    {
                        "status": "failed",
                        "passed": False,
                        "error_count": 1,
                        "warning_count": 0,
                        "metrics": {
                            "files": {
                                "dwi": {"exists": False, "is_file": False},
                                "bval": {"exists": True, "is_file": True},
                                "bvec": {"exists": True, "is_file": True},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            manifest = {
                "status": "failed",
                "subject_id": "sub-01",
                "subject_root": (Path(tmp) / "input-subject").as_posix(),
                "output_root": subject_output.as_posix(),
                "tasks": [
                    {
                        "name": "validation",
                        "status": "failed",
                        "qc_path": report_path.as_posix(),
                    }
                ],
            }
            (metadata_dir / "validation_orchestration_manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            report = audit_output_root(subject_output)

        self.assertEqual(report["status"], "failed")
        failed_names = {
            check["name"]
            for check in report["subjects"][0]["checks"]
            if not check["passed"]
        }
        self.assertIn("orchestration.status", failed_names)
        self.assertIn("orchestration.task_statuses", failed_names)
        self.assertIn("validation.task_status", failed_names)
        self.assertIn("validation.report_status", failed_names)
        self.assertIn("validation.required_files", failed_names)

    def test_out_of_range_fa_fails(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(Path(tmp), invalid_fa=True)
            report = audit_output_root(output_root, require_dti=True)

        self.assertEqual(report["status"], "failed")
        failed_names = {
            check["name"]
            for check in report["subjects"][0]["checks"]
            if not check["passed"]
        }
        self.assertIn("dti.fa.range", failed_names)

    def test_tractography_qc_length_summary_allows_only_storage_quantization(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(
                Path(tmp) / "quantized",
                tractography_qc_length_offset_mm=2e-5,
            )
            quantized_report = audit_output_root(output_root, require_tractography=True)
            mismatch_root = self._fixture(
                Path(tmp) / "mismatch",
                tractography_qc_length_offset_mm=1e-2,
            )
            mismatch_report = audit_output_root(mismatch_root, require_tractography=True)

        quantized_check = next(
            check
            for check in quantized_report["subjects"][0]["checks"]
            if check["name"] == "tractography.qc_length_summary"
        )
        mismatch_check = next(
            check
            for check in mismatch_report["subjects"][0]["checks"]
            if check["name"] == "tractography.qc_length_summary"
        )
        self.assertTrue(quantized_check["passed"])
        self.assertFalse(mismatch_check["passed"])

    def test_explicit_run_name_is_stable_after_partial_rerun(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(Path(tmp))
            metadata_dir = output_root / "sub-01" / "00_run_metadata"
            (metadata_dir / "partial_orchestration_manifest.json").write_text(
                json.dumps(
                    {
                        "subject_id": "sub-01",
                        "subject_root": (Path(tmp) / "input-subject").as_posix(),
                        "output_root": (output_root / "sub-01").as_posix(),
                        "tasks": [{"name": "segmentation.ddseg", "status": "completed"}],
                    }
                ),
                encoding="utf-8",
            )
            report = audit_output_root(
                output_root,
                require_dti=True,
                require_tractography=True,
                run_name="Test1",
            )

        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["subjects"][0]["manifest_path"].endswith("Test1_orchestration_manifest.json"))

    def test_partial_structural_route_ignores_unselected_routes(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(Path(tmp), ddseg_only=True)
            report = audit_output_root(output_root, require_dti=True)
            full_structural_report = audit_output_root(output_root, require_structural=True)

        self.assertEqual(report["status"], "passed")
        check_names = {check["name"] for check in report["subjects"][0]["checks"]}
        self.assertIn("structural.ddseg.segmentation_exists", check_names)
        self.assertIn("structural.ddseg.probability_mass", check_names)
        self.assertIn("structural.ddseg.probability_label_agreement", check_names)
        self.assertFalse(any(name.startswith("structural.ddparcel") for name in check_names))
        self.assertFalse(any(name.startswith("structural.ddsurfer") for name in check_names))
        self.assertEqual(full_structural_report["status"], "failed")
        required_check = next(
            check
            for check in full_structural_report["subjects"][0]["checks"]
            if check["name"] == "required.structural"
        )
        self.assertFalse(required_check["passed"])

    def test_full_route_outputs_receive_scientific_checks(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(Path(tmp), full_routes=True)
            report = audit_output_root(
                output_root,
                require_dti=True,
                require_tractography=True,
                require_full_routes=True,
            )

        self.assertEqual(report["status"], "passed")
        checks = {check["name"]: check for check in report["subjects"][0]["checks"]}
        self.assertTrue(checks["required.full_routes"]["passed"])
        self.assertTrue(checks["freewater.fwf.range"]["passed"])
        self.assertTrue(checks["noddi.ndi.zero_outside_brain_mask"]["passed"])
        self.assertTrue(checks["noddi.odi.zero_outside_brain_mask"]["passed"])
        self.assertTrue(checks["tractcloud.input_matches_same_run_tractography"]["passed"])
        self.assertTrue(checks["wma.input_tractography_exists"]["passed"])
        self.assertTrue(checks["connectome_streamline_count.assigned_streamlines"]["passed"])

    def test_legacy_wma_qc_is_redecoded_from_real_vtp_content(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(Path(tmp), full_routes=True, legacy_wma_qc=True)
            report = audit_output_root(output_root, require_full_routes=True)

        self.assertEqual(report["status"], "passed")
        checks = {check["name"]: check for check in report["subjects"][0]["checks"]}
        self.assertEqual(checks["wma.anatomical_tracts_readable"]["value"], 73)
        self.assertEqual(checks["wma.anatomical_tracts_nonempty"]["value"]["nonempty"], 73)

    def test_raw_mrtrix_matrix_uses_anatomical_nodes_not_label_extent(self) -> None:
        import numpy as np
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(Path(tmp), full_routes=True)
            matrix = np.zeros((4, 4))
            matrix[1, 3] = matrix[3, 1] = 3
            np.savetxt(next(output_root.rglob("connectome.csv")), matrix, delimiter=",")
            qc_path = next(output_root.rglob("connectome_qc.json"))
            qc = json.loads(qc_path.read_text())
            qc["dense_node_count"] = 4
            qc_path.write_text(json.dumps(qc))
            report = audit_output_root(output_root, require_full_routes=True)
            self.assertEqual(report["status"], "passed")
            checks = {check["name"]: check for check in report["subjects"][0]["checks"]}
            self.assertTrue(checks["connectome_streamline_count.node_count"]["passed"])
            matrix[1, 3] = np.nan
            np.savetxt(next(output_root.rglob("connectome.csv")), matrix, delimiter=",")
            report = audit_output_root(output_root, require_full_routes=True)
            self.assertEqual(report["status"], "failed")
            checks = {check["name"]: check for check in report["subjects"][0]["checks"]}
            self.assertFalse(checks["connectome_streamline_count.dense_values"]["passed"])

    def test_old_completed_qc_does_not_hide_corrupted_bundle_geometry(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(Path(tmp), full_routes=True)
            next(root.rglob("tract-00.vtp")).write_text("truncated")
            next(root.rglob("bundle.vtp")).write_text("truncated")
            report = audit_output_root(root, require_full_routes=True)
            checks = {item["name"]: item for item in report["subjects"][0]["checks"]}
            self.assertFalse(checks["wma.anatomical_tracts_readable"]["passed"])
            self.assertFalse(checks["tractcloud.bundles_decoded_nonempty"]["passed"])


if __name__ == "__main__":
    unittest.main()
