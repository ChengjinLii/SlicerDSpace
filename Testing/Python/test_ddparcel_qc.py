"""Synthetic DDParcel acceptance failures; no anatomical accuracy claims."""

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import nibabel as nib
import numpy as np

from anatomy.parcellation.qc import validate_outputs
from anatomy.parcellation.pipeline import DDParcelRegisteredConfig, run_ddparcel_from_registered_bundle
from microstructure.pipeline import scalar_qc_current


class DDParcelQcTest(unittest.TestCase):
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
