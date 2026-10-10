#!/usr/bin/env python3
"""Tests for parcellation/conversion/nifti_write.py's error handling.

nifti_write() used to silently swallow every read/write error (printing a
message and returning None) and used a bare ``except: pass`` around its
DWI bval/bvec extraction. Both are unsafe: callers such as
parcellation/pipeline.py cannot tell a failed conversion happened, and a
bare except also hides real bugs behind the "this must be fMRI, not DWI"
fallback. This module stubs the (unavailable in this environment) nrrd and
nibabel packages so the pure control-flow can be exercised headlessly.
"""

from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _make_4d_header(*, num_gradients: int = 2) -> dict:
    return {
        "space": "left-posterior-superior",
        "space origin": np.array([0.0, 0.0, 0.0]),
        "dimension": 4,
        "kinds": ["domain", "domain", "domain", "list"],
        "space directions": np.eye(4, 3),
        "sizes": [2, 2, 2, num_gradients],
        "DWMRI_b-value": "1000",
        "measurement frame": np.eye(3),
        **{f"DWMRI_gradient_{i:04}": "1 0 0" for i in range(num_gradients)},
    }


class NiftiWriteErrorHandlingTest(unittest.TestCase):
    def setUp(self) -> None:
        self._nrrd_module = types.ModuleType("nrrd")
        self._nrrd_module.read = mock.Mock()
        nifti1_module = types.SimpleNamespace(Nifti1Image=mock.MagicMock(return_value=mock.MagicMock()))
        self._nib_module = types.ModuleType("nibabel")
        self._nib_module.nifti1 = nifti1_module
        self._nib_module.save = mock.Mock()
        self._modules_patch = mock.patch.dict(
            sys.modules, {"nrrd": self._nrrd_module, "nibabel": self._nib_module}
        )
        self._modules_patch.start()
        self.addCleanup(self._modules_patch.stop)
        # Re-import fresh each test so the stubbed nrrd/nibabel are bound.
        sys.modules.pop("anatomy.parcellation.conversion.nifti_write", None)
        import anatomy.parcellation.conversion.nifti_write as nifti_write_module

        self.nifti_write_module = nifti_write_module
        self.nifti_write = nifti_write_module.nifti_write

    def test_raises_file_not_found_for_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does_not_exist.nrrd"
            with self.assertRaises(FileNotFoundError):
                self.nifti_write(str(missing))
            self._nrrd_module.read.assert_not_called()

    def test_wraps_nrrd_read_failure_as_runtime_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.nrrd"
            path.write_text("stub", encoding="utf-8")
            self._nrrd_module.read.side_effect = ValueError("corrupt header")

            with self.assertRaises(RuntimeError) as ctx:
                self.nifti_write(str(path))
            self.assertIn("corrupt header", str(ctx.exception))
            self.assertIsInstance(ctx.exception.__cause__, ValueError)

    def test_missing_dwi_gradient_metadata_is_treated_as_non_diffusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.nrrd"
            path.write_text("stub", encoding="utf-8")
            hdr = _make_4d_header()
            del hdr["DWMRI_b-value"]  # Missing DWI metadata -> KeyError branch.
            data = np.zeros((2, 2, 2, 2))
            self._nrrd_module.read.return_value = (data, hdr)
            prefix = str(Path(tmp) / "out")

            # Must not raise, and must still write the NIfTI output.
            self.nifti_write(str(path), prefix)

            self._nib_module.save.assert_called_once()
            self.assertFalse(Path(prefix + ".bval").exists())
            self.assertFalse(Path(prefix + ".bvec").exists())

    def test_missing_dwi_gradient_metadata_cleans_up_partial_bval_bvec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.nrrd"
            path.write_text("stub", encoding="utf-8")
            # 3 gradients declared in sizes, but only 1 gradient key present,
            # so the second loop iteration raises KeyError after some bytes
            # were already written to .bval/.bvec.
            hdr = _make_4d_header(num_gradients=1)
            hdr["sizes"] = [2, 2, 2, 3]
            data = np.zeros((2, 2, 2, 3))
            self._nrrd_module.read.return_value = (data, hdr)
            prefix = str(Path(tmp) / "out")

            self.nifti_write(str(path), prefix)

            self.assertFalse(Path(prefix + ".bval").exists())
            self.assertFalse(Path(prefix + ".bvec").exists())

    def test_malformed_gradient_value_is_not_hidden_as_non_diffusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.nrrd"
            path.write_text("stub", encoding="utf-8")
            hdr = _make_4d_header(num_gradients=1)
            hdr["DWMRI_gradient_0000"] = "not-a-number 0 0"
            data = np.zeros((2, 2, 2, 1))
            self._nrrd_module.read.return_value = (data, hdr)
            prefix = str(Path(tmp) / "out")

            with self.assertRaises(ValueError):
                self.nifti_write(str(path), prefix)

    def test_successful_dwi_extraction_writes_bval_and_bvec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.nrrd"
            path.write_text("stub", encoding="utf-8")
            hdr = _make_4d_header(num_gradients=2)
            data = np.zeros((2, 2, 2, 2))
            self._nrrd_module.read.return_value = (data, hdr)
            prefix = str(Path(tmp) / "out")

            self.nifti_write(str(path), prefix)

            self.assertTrue(Path(prefix + ".bval").is_file())
            self.assertTrue(Path(prefix + ".bvec").is_file())
            self._nib_module.save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
