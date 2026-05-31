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


if __name__ == "__main__":
    unittest.main()
