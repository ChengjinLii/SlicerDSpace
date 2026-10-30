"""Synthetic DDParcel acceptance failures; no anatomical accuracy claims."""

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import nibabel as nib
import numpy as np

from anatomy.parcellation.qc import validate_outputs, label_semantics
from anatomy.parcellation.pipeline import DDParcelRegisteredConfig, run_ddparcel_from_registered_bundle
from microstructure.pipeline import scalar_qc_current


class DDParcelQcTest(unittest.TestCase):
    def test_legacy_filename_cannot_establish_regional_white_matter_content(self):
        values = np.array([0, 2, 41, 1001, 1024, 2001, 2024]).reshape(1, 1, -1)
        record = label_semantics(values)
        self.assertTrue(record['cortical_labels_without_regional_wm'])
        self.assertEqual(record['regional_white_matter_voxels'], 0)
        self.assertEqual(record['generic_cerebral_white_matter_voxels'], 2)
        self.assertTrue(record['warnings'])
        regional = label_semantics(np.array([1001, 2001, 3001, 4001]))
        self.assertFalse(regional['cortical_labels_without_regional_wm'])
        self.assertEqual(regional['regional_white_matter_label_ids'], [3001, 4001])
        self.assertEqual(regional['left_regional_white_matter_voxels'], 1)
        self.assertEqual(regional['right_regional_white_matter_voxels'], 1)

    def test_callosal_anatomy_is_reported_separately_from_wmql_aliases(self):
        values = np.array([0, 2, 41, 192, 192, 251, 255, 1004, 2004, 3004, 4004, 1001])
        before = values.copy()
        record = label_semantics(values)
        self.assertEqual(record['corpus_callosum_label_ids'], [192, 251, 255, 1004, 2004, 3004, 4004])
        self.assertEqual(record['corpus_callosum_voxels'], 8)
        self.assertEqual(record['corpus_callosum_192_voxels'], 2)
        np.testing.assert_array_equal(values, before)
        self.assertEqual(label_semantics(np.array([0, 2, 41]))['corpus_callosum_voxels'], 0)

    def test_native_export_missing_corrupt_or_wrong_grid_cannot_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mask = root / "mask.nii.gz"
            nib.save(nib.Nifti1Image(np.ones((3, 3, 3), np.float32), np.eye(4)), mask)
            paths = [root / "test-DDSurfer-wmparc.nii.gz", root / "test-DDSurfer-wmparc-Reg.mgz"]
            paths.extend(root / f"test-dti-{metric}-Reg-NormMasked.nii.gz" for metric in (
                "FractionalAnisotropy", "Trace", "MinEigenvalue", "MidEigenvalue"))
            for path in paths:
                image_cls = nib.MGHImage if path.suffix == ".mgz" else nib.Nifti1Image
                nib.save(image_cls(np.ones((3, 3, 3), np.float32), np.eye(4)), path)
            validate_outputs("test", root, mask)
            self.assertTrue(scalar_qc_current(root / "ddparcel_qc.json", paths))
            paths[0].unlink()
            with self.assertRaises(FileNotFoundError):
                validate_outputs("test", root, mask)
            self.assertFalse(scalar_qc_current(root / "ddparcel_qc.json", paths))
            nib.save(nib.Nifti1Image(np.ones((3, 3, 3), np.float32), np.diag([2, 1, 1, 1])), paths[0])
            with self.assertRaises(ValueError):
                validate_outputs("test", root, mask)

    def test_missing_inverse_transform_is_failure_not_skipped_native_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mask = root / "mask.nii.gz"
            mask.touch()
            (root / "test-dti-MidEigenvalue-Reg-NormMasked.nii.gz").touch()
            (root / "test-DDSurfer-wmparc-Reg.mgz").touch()
            bundle = SimpleNamespace(subject_id="test", bundle_dir=root, inverse_transform_path=root / "missing.h5")
            with patch("anatomy.parcellation.pipeline.resolve_cli_executable", return_value="test-cli"):
                with self.assertRaises(FileNotFoundError):
                    run_ddparcel_from_registered_bundle(DDParcelRegisteredConfig("test", bundle, root, mask))


if __name__ == "__main__":
    unittest.main()
