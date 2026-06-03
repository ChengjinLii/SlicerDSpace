#!/usr/bin/env python3
"""Tests for the canonical subject I/O layout."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class IOLayoutTest(unittest.TestCase):
    def test_default_task_dirs_match_product_tree(self) -> None:
        from shared import default_task_output_dir, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            layout = subject_layout(subject_root)

            self.assertEqual(default_task_output_dir(subject_root, "microstructure"), layout.outputs / "02_microstructure")
            self.assertEqual(default_task_output_dir(subject_root, "ddseg"), layout.outputs / "03_structural" / "ddseg")
            self.assertEqual(default_task_output_dir(subject_root, "ddsurfer"), layout.outputs / "03_structural" / "ddsurfer")
            self.assertEqual(default_task_output_dir(subject_root, "ddparcel"), layout.outputs / "03_structural" / "ddparcel")
            self.assertEqual(
                default_task_output_dir(subject_root, "tractography_dti"),
                layout.outputs / "04_tractography" / "tractograms" / "dti_det",
            )
            self.assertEqual(default_task_output_dir(subject_root, "saf"), layout.outputs / "04_tractography" / "saf")
            self.assertEqual(default_task_output_dir(subject_root, "connectome"), layout.outputs / "04_tractography" / "connectome")
            self.assertEqual(
                default_task_output_dir(subject_root, "regional_microstructure"),
                layout.outputs / "05_statistics" / "regional_microstructure",
            )

    def test_dependency_path_can_infer_same_subject_output_tree(self) -> None:
        from shared import default_task_output_dir_for_dependency

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            tractogram = subject_root / "outputs" / "04_tractography" / "tractograms" / "dti_det" / "wholebrain.vtk"

            self.assertEqual(
                default_task_output_dir_for_dependency(tractogram, "connectome"),
                subject_root.resolve() / "outputs" / "04_tractography" / "connectome",
            )
            self.assertEqual(
                default_task_output_dir_for_dependency(tractogram, "tractcloud"),
                subject_root.resolve() / "outputs" / "04_tractography" / "bundles" / "tract_cloud_dl",
            )
            self.assertEqual(
                default_task_output_dir_for_dependency(tractogram, "wmql"),
                subject_root.resolve() / "outputs" / "04_tractography" / "bundles" / "wmql",
            )

    def test_legacy_outputs_can_be_materialized_under_canonical_tree(self) -> None:
        from shared import materialize_canonical_output_tree, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            legacy_micro = subject_root / "outputs" / "microstructure"
            legacy_ddparcel = subject_root / "outputs" / "ddparcel"
            legacy_validation = subject_root / "outputs" / "validation"
            legacy_tractography_out = subject_root / "outputs" / "tractography"
            legacy_tractcloud = subject_root / "AnatomicalTracts"
            legacy_micro.mkdir(parents=True)
            legacy_ddparcel.mkdir(parents=True)
            legacy_validation.mkdir(parents=True)
            legacy_tractography_out.mkdir(parents=True)
            legacy_tractcloud.mkdir(parents=True)
            (legacy_micro / "100307-dti-FractionalAnisotropy.nii.gz").write_text("fa", encoding="utf-8")
            (legacy_ddparcel / "100307-DDSurfer-wmparc.nii.gz").write_text("wmparc", encoding="utf-8")
            (legacy_validation / "100307_input_validation.json").write_text("{}", encoding="utf-8")
            (legacy_tractography_out / "100307-dti-deterministic_manifest.json").write_text("{}", encoding="utf-8")
            (legacy_tractcloud / "AF_left.vtp").write_text("tract", encoding="utf-8")

            created = materialize_canonical_output_tree(subject_root, mode="copy", archive_legacy=True)
            layout = subject_layout(subject_root)

            self.assertTrue((layout.microstructure_dti / "100307_dti_FA.nii.gz").is_file())
            self.assertTrue((layout.ddparcel / "100307-DDSurfer-wmparc.nii.gz").is_file())
            self.assertTrue((layout.run_metadata / "validation" / "100307_input_validation.json").is_file())
            self.assertTrue((layout.tractograms_dti_det / "100307-dti-deterministic_manifest.json").is_file())
            self.assertTrue((layout.bundles_tractcloud / "AnatomicalTracts" / "AF_left.vtp").is_file())
            self.assertTrue((subject_root / ".legacy_flat_outputs" / "microstructure").is_dir())
            self.assertTrue((subject_root / ".legacy_flat_outputs" / "tractography").is_dir())
            self.assertTrue((subject_root / ".legacy_flat_outputs" / "AnatomicalTracts").is_dir())
            self.assertIn("100307-dti-FractionalAnisotropy.nii.gz", created)

    def test_development_outputs_can_be_archived_outside_canonical_tree(self) -> None:
        from shared import archive_development_outputs, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            layout = subject_layout(subject_root)
            probe_dir = layout.bundles / "wmql_probe_af_cst"
            check_dir = layout.connectome / "csd_act_mean_fa_check"
            saf_dir = layout.tractography / "saf_python_execute_fastsurfer"
            smoke_dir = layout.outputs / "connectome_execute_smoke"
            for path in (probe_dir, check_dir, saf_dir, smoke_dir):
                path.mkdir(parents=True)
                (path / "marker.txt").write_text("x", encoding="utf-8")

            moved = archive_development_outputs(subject_root)

            self.assertFalse(probe_dir.exists())
            self.assertFalse(check_dir.exists())
            self.assertFalse(saf_dir.exists())
            self.assertFalse(smoke_dir.exists())
            self.assertTrue((subject_root / ".debug_outputs" / "04_tractography" / "bundles" / "wmql_probe_af_cst").is_dir())
            self.assertTrue((subject_root / ".debug_outputs" / "04_tractography" / "connectome" / "csd_act_mean_fa_check").is_dir())
            self.assertTrue((subject_root / ".debug_outputs" / "04_tractography" / "saf_python_execute_fastsurfer").is_dir())
            self.assertTrue((subject_root / ".debug_outputs" / "legacy_outputs_root" / "connectome_execute_smoke").is_dir())
            self.assertGreaterEqual(len(moved), 4)

    def test_legacy_wma_runs_can_be_materialized_under_canonical_bundles_tree(self) -> None:
        from shared import materialize_canonical_output_tree, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "149741"
            legacy_wma = subject_root / ".debug_outputs" / "legacy_outputs_root" / "wma_org_execute_20260531_ldfix"
            case_dir = legacy_wma / "149741_ukf_pp_downsampled" / "FiberClustering"
            case_dir.mkdir(parents=True)
            (legacy_wma / "wma_org_atlas_qc.json").write_text("{}", encoding="utf-8")

            created = materialize_canonical_output_tree(subject_root, mode="copy", archive_legacy=False)
            layout = subject_layout(subject_root)

            self.assertTrue((layout.bundles_wma / "wma_org_execute_20260531_ldfix").is_dir())
            self.assertTrue((layout.bundles_wma / "wma_org_execute_20260531_ldfix" / "wma_org_atlas_qc.json").is_file())
            self.assertIn("wma_org_execute_20260531_ldfix", created)

    def test_legacy_csd_run_dirs_can_be_materialized_under_canonical_csd_tree(self) -> None:
        from shared import archive_development_outputs, materialize_canonical_output_tree, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            legacy_csd = subject_root / "outputs" / "04_tractography" / "csd_act_100k"
            legacy_csd.mkdir(parents=True)
            (legacy_csd / "csd_act_qc.json").write_text("{}", encoding="utf-8")

            created = materialize_canonical_output_tree(subject_root, mode="copy", archive_legacy=False)
            layout = subject_layout(subject_root)
            self.assertTrue((layout.csd / "csd_act_100k" / "csd_act_qc.json").is_file())
            self.assertIn("csd_act_100k", created)

            moved = archive_development_outputs(subject_root)
            self.assertFalse(legacy_csd.exists())
            self.assertTrue((subject_root / ".debug_outputs" / "04_tractography" / "legacy_csd_runs" / "csd_act_100k").is_dir())
            self.assertIn(legacy_csd.as_posix(), moved)

    def test_legacy_connectome_metric_dirs_can_be_materialized_under_run_metric_tree(self) -> None:
        from shared import archive_development_outputs, materialize_canonical_output_tree, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            legacy_metric_dir = subject_root / "outputs" / "04_tractography" / "connectome" / "csd_act_100k_mean_fa"
            legacy_metric_dir.mkdir(parents=True)
            (legacy_metric_dir / "100307-connectome-mean_fa_qc.json").write_text("{}", encoding="utf-8")

            created = materialize_canonical_output_tree(subject_root, mode="copy", archive_legacy=False)
            layout = subject_layout(subject_root)
            target = layout.connectome / "csd_act_100k" / "mean_fa" / "100307-connectome-mean_fa_qc.json"
            self.assertTrue(target.is_file())
            self.assertIn("csd_act_100k_mean_fa", created)

            moved = archive_development_outputs(subject_root)
            self.assertFalse(legacy_metric_dir.exists())
            self.assertTrue((subject_root / ".debug_outputs" / "04_tractography" / "connectome_legacy_layout" / "csd_act_100k_mean_fa").is_dir())
            self.assertIn(legacy_metric_dir.as_posix(), moved)


if __name__ == "__main__":
    unittest.main()
