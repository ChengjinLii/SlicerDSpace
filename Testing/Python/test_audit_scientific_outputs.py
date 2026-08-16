#!/usr/bin/env python3
"""Tests for the multi-subject scientific output audit."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ScientificOutputAuditTest(unittest.TestCase):
    def _fixture(
        self,
        root: Path,
        *,
        invalid_fa: bool = False,
        ddseg_only: bool = False,
        full_routes: bool = False,
    ) -> Path:
        import nibabel as nib
        import numpy as np

        subject_root = root / "input-subject"
        input_dir = subject_root / "input"
        input_dir.mkdir(parents=True)
        affine = np.eye(4)
        dwi = np.ones((3, 3, 3, 7), dtype=np.float32)
        mask = np.ones((3, 3, 3), dtype=np.uint8)
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
        tasks = [
            {"name": "microstructure.dti", "status": "completed", "outputs": outputs},
            {
                "name": "tractography.dti_det",
                "status": "completed",
                "outputs": {"tractogram_trk": tract_path.as_posix()},
            },
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
            for key, value in (("fwf", 0.2), ("fw_fa", 0.4), ("fw_md", 0.001)):
                path = freewater_dir / f"sub-01_{key}.nii.gz"
                nib.save(nib.Nifti1Image(np.full(mask.shape, value, dtype=np.float32), affine), path)
                freewater_outputs[key] = path.as_posix()
            noddi_outputs = {}
            for key, value in (("ndi", 0.6), ("odi", 0.3), ("isovf", 0.1)):
                path = noddi_dir / f"sub-01_{key}.nii.gz"
                nib.save(nib.Nifti1Image(np.full(mask.shape, value, dtype=np.float32), affine), path)
                noddi_outputs[key] = path.as_posix()
            tasks.extend(
                [
                    {"name": "microstructure.freewater", "status": "completed", "outputs": freewater_outputs},
                    {"name": "microstructure.noddi", "status": "completed", "outputs": noddi_outputs},
                ]
            )

            csd_dir = subject_output / "04_tractography" / "tractograms" / "Test1"
            csd_dir.mkdir(parents=True)
            csd_tck = csd_dir / "sub-01_csd_act_ifod2.tck"
            nib.streamlines.save(tractogram, csd_tck.as_posix())
            tasks.append(
                {
                    "name": "tractography.csd_act",
                    "status": "completed",
                    "outputs": {"tractogram": csd_tck.as_posix()},
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
            wmql_bundle = wmql_dir / "af.left.trk"
            nib.streamlines.save(tractogram, wmql_bundle.as_posix())
            wmql_qc = wmql_dir / "wmql_qc.json"
            wmql_qc.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "output_summary": {"bundle_count": 1, "bundle_files": [wmql_bundle.as_posix()]},
                    }
                ),
                encoding="utf-8",
            )
            tasks.append({"name": "bundles.wmql", "status": "completed", "qc_path": wmql_qc.as_posix()})

            wma_dir = subject_output / "04_tractography" / "bundles" / "wma" / "Test1"
            anatomy_dir = wma_dir / "AnatomicalTracts"
            anatomy_dir.mkdir(parents=True)
            for index in range(73):
                (anatomy_dir / f"tract-{index:02d}.vtp").write_text("vtp\n", encoding="utf-8")
            wma_qc = wma_dir / "wma_qc.json"
            wma_manifest = wma_dir / "wma_manifest.json"
            wma_qc.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "output_summary": {
                            "anatomical_tract_count": 73,
                            "anatomical_tracts_dir": anatomy_dir.as_posix(),
                        },
                    }
                ),
                encoding="utf-8",
            )
            wma_manifest.write_text(json.dumps({"input_tractography": csd_tck.as_posix()}), encoding="utf-8")
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
            tractcloud_bundle.write_text("vtp\n", encoding="utf-8")
            tractcloud_qc = tractcloud_dir / "tractcloud_qc.json"
            tractcloud_manifest = tractcloud_dir / "tractcloud_manifest.json"
            tractcloud_qc.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "output_summary": {"bundle_count": 1, "bundle_files": [tractcloud_bundle.as_posix()]},
                    }
                ),
                encoding="utf-8",
            )
            tractcloud_manifest.write_text(
                json.dumps({"input_tractography": saf_vtk.as_posix()}),
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
        self.assertTrue(checks["tractcloud.input_matches_same_run_saf"]["passed"])
        self.assertTrue(checks["connectome_streamline_count.assigned_streamlines"]["passed"])


if __name__ == "__main__":
    unittest.main()
