"""Chunk I/O parity with real NIfTI compression/scaling, no fitting changes."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import nibabel as nib
import numpy as np

from shared.diffusion_io import diffusion_image


class DiffusionChunkIoTest(unittest.TestCase):
    def test_compressed_slabs_equal_original_scaled_values_and_clean_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "data.nii.gz"
            data = np.arange(3 * 4 * 5 * 6, dtype=np.int16).reshape(3, 4, 5, 6)
            image = nib.Nifti1Image(data, np.diag([2, 2, 2, 1]))
            image.header.set_slope_inter(2, 3)
            nib.save(image, source)
            before = source.read_bytes()
            expected = nib.load(source).get_fdata(dtype=np.float32)
            with diffusion_image(source, root / "work") as opened:
                for index in range(5):
                    np.testing.assert_array_equal(np.asarray(opened.dataobj[:, :, index:index+1, :]), expected[:, :, index:index+1, :])
                np.testing.assert_array_equal(opened.affine, image.affine)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(list((root / "work").iterdir()), [])

    def test_disk_space_failure_is_actionable_and_plain_nifti_needs_no_copy(self):
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = nib.Nifti1Image(np.ones((2, 2, 2, 4), np.float32), np.eye(4))
            nib.save(image, root / "data.nii.gz")
            with patch("shared.diffusion_io.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
                with self.assertRaises(RuntimeError):
                    with diffusion_image(root / "data.nii.gz", root / "work"):
                        pass
            nib.save(image, root / "data.nii")
            with patch("shared.diffusion_io.shutil.copyfileobj", side_effect=AssertionError("uncompressed input must not copy")):
                with diffusion_image(root / "data.nii", root / "work") as opened:
                    self.assertEqual(opened.shape, (2, 2, 2, 4))


if __name__ == "__main__":
    unittest.main()
