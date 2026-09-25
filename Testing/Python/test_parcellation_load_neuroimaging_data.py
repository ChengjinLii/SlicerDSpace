#!/usr/bin/env python3
"""Tests that load_neuroimaging_data.py raises instead of silently continuing.

Several code paths in this module used to either call sys.exit()/exit()
(which raises SystemExit, escaping ordinary ``except Exception`` handlers
and terminating the whole interpreter if uncaught) or catch every exception
in a Dataset.__init__ and only print it, leaving the object half
constructed instead of failing the construction. This module stubs the
several heavy, optional dependencies (nibabel, h5py, scipy, skimage, torch)
that load_neuroimaging_data.py imports at module scope but that this
environment does not have installed, so the pure control-flow fixes can be
exercised headlessly.
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


def _stub_modules_for_import() -> dict[str, types.ModuleType]:
    """Build fake modules for every heavy dependency this file imports.

    Only used as a scoped ``mock.patch.dict(sys.modules, ...)`` override for
    the single import below -- never installed permanently -- so this test
    file cannot leak fake nibabel/scipy/skimage/torch modules into
    unrelated tests that run in the same process and need the real thing
    (or a real ModuleNotFoundError) when it is actually installed.
    """

    stubs: dict[str, types.ModuleType] = {}
    stubs["nibabel"] = types.ModuleType("nibabel")
    stubs["h5py"] = types.ModuleType("h5py")

    scipy_module = types.ModuleType("scipy")
    ndimage_module = types.ModuleType("scipy.ndimage")
    morphology_module = types.ModuleType("scipy.ndimage.morphology")
    filters_module = types.ModuleType("scipy.ndimage.filters")
    ndimage_module.morphology = morphology_module
    ndimage_module.filters = filters_module
    scipy_module.ndimage = ndimage_module
    stubs["scipy"] = scipy_module
    stubs["scipy.ndimage"] = ndimage_module
    stubs["scipy.ndimage.morphology"] = morphology_module
    stubs["scipy.ndimage.filters"] = filters_module

    skimage_module = types.ModuleType("skimage")
    measure_module = types.ModuleType("skimage.measure")
    measure_module.label = mock.Mock()
    skimage_module.measure = measure_module
    stubs["skimage"] = skimage_module
    stubs["skimage.measure"] = measure_module

    torch_module = types.ModuleType("torch")
    utils_module = types.ModuleType("torch.utils")
    data_module = types.ModuleType("torch.utils.data")
    dataset_module = types.ModuleType("torch.utils.data.dataset")

    class _FakeDataset:
        """Stand-in for torch.utils.data.dataset.Dataset (base class only)."""

    dataset_module.Dataset = _FakeDataset
    data_module.dataset = dataset_module
    utils_module.data = data_module
    torch_module.utils = utils_module
    stubs["torch"] = torch_module
    stubs["torch.utils"] = utils_module
    stubs["torch.utils.data"] = data_module
    stubs["torch.utils.data.dataset"] = dataset_module
    return stubs


# Stub only for the duration of this one import: load_neuroimaging_data.py
# keeps its own bound references (e.g. its module-level `nib` name) after
# import, so the module remains usable once sys.modules is restored below.
with mock.patch.dict(sys.modules, _stub_modules_for_import()):
    import parcellation.data_loader.load_neuroimaging_data as load_neuroimaging_data


class FakeHeader:
    def get_zooms(self):
        return (1.0, 1.0, 1.0)


class FakeOrig:
    """Minimal stand-in for a nibabel image, as load_and_conform_image() uses it."""

    def __init__(self, shape):
        self.shape = shape
        self.header = FakeHeader()
        self.affine = np.eye(4)

    def get_fdata(self):
        return np.zeros(self.shape)


class LoadAndConformImageRaisesInsteadOfExitingTest(unittest.TestCase):
    def test_multiple_frames_raises_value_error_not_system_exit(self) -> None:
        orig = FakeOrig(shape=(256, 256, 256, 2))
        with mock.patch.object(load_neuroimaging_data.nib, "load", return_value=orig, create=True), \
             mock.patch.object(load_neuroimaging_data, "is_conform", return_value=False):
            with self.assertRaises(ValueError) as ctx:
                load_neuroimaging_data.load_and_conform_image("scan.nii.gz")
        self.assertNotIsInstance(ctx.exception, SystemExit)
        self.assertIn("Multiple input frames", str(ctx.exception))

    def test_inconsistent_nifti_header_raises_value_error_not_system_exit(self) -> None:
        orig = FakeOrig(shape=(200, 200, 200))
        with mock.patch.object(load_neuroimaging_data.nib, "load", return_value=orig, create=True), \
             mock.patch.object(load_neuroimaging_data, "is_conform", return_value=False), \
             mock.patch.object(load_neuroimaging_data, "check_affine_in_nifti", return_value=False):
            with self.assertRaises(ValueError) as ctx:
                load_neuroimaging_data.load_and_conform_image("scan.nii.gz")
        self.assertNotIsInstance(ctx.exception, SystemExit)
        self.assertIn("Inconsistency", str(ctx.exception))


class OrigDataThickSlicesReraisesTest(unittest.TestCase):
    def test_internal_failure_propagates_instead_of_leaving_a_half_built_object(self) -> None:
        # A 2D volume makes get_thick_slices() fail with a real ValueError
        # ("not enough values to unpack"); the old code printed this and
        # returned, leaving self.count/self.images unset.
        bad_orig = np.zeros((10, 10))

        with self.assertRaises(ValueError):
            load_neuroimaging_data.OrigDataThickSlices("scan.nii.gz", bad_orig, plane="Coronal")


class HdfDatasetRaisesInsteadOfExitingTest(unittest.TestCase):
    def test_mismatched_hdf5_file_counts_raise_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_a = root / "a"
            dataset_b = root / "b"
            dataset_a.mkdir()
            dataset_b.mkdir()
            (dataset_a / "one.hdf5").write_text("x", encoding="utf-8")
            (dataset_a / "two.hdf5").write_text("x", encoding="utf-8")
            (dataset_b / "one.hdf5").write_text("x", encoding="utf-8")

            params = {"dataset_name": [str(dataset_a), str(dataset_b)], "plane": "Axial"}

            with self.assertRaises(ValueError) as ctx:
                load_neuroimaging_data.AsegDatasetWithAugmentation_Slice_Fused_Input(params)
            self.assertNotIsInstance(ctx.exception, SystemExit)
            self.assertIn("same number of hdf5 files", str(ctx.exception))

    def test_mismatched_file_names_across_datasets_raise_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_a = root / "a"
            dataset_b = root / "b"
            dataset_a.mkdir()
            dataset_b.mkdir()
            (dataset_a / "subject1.hdf5").write_text("x", encoding="utf-8")
            (dataset_b / "subject2.hdf5").write_text("x", encoding="utf-8")

            params = {"dataset_name": [str(dataset_a), str(dataset_b)], "plane": "Axial"}
            instance = load_neuroimaging_data.AsegDatasetWithAugmentation_Slice_Fused_Input(params)

            with self.assertRaises(ValueError) as ctx:
                instance[0]
            self.assertNotIsInstance(ctx.exception, SystemExit)
            self.assertIn("same file name", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
