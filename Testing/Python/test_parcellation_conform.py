#!/usr/bin/env python3
"""Tests that parcellation/data_loader/conform.py raises instead of exiting.

conform.py's getscale() and is_conform() used sys.exit() to report bad
input. sys.exit() raises SystemExit, which is not caught by ordinary
``except Exception`` handlers and, if uncaught, terminates the whole
interpreter -- unacceptable when these functions run inside the long-lived
Slicer process. They must raise an ordinary exception instead.
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Stub only for the duration of this one import (if the real package is not
# installed): conform.py's tested functions (getscale, is_conform) never use
# nibabel directly, but the module does `import nibabel as nib` at import
# time. Scoping the stub to this import keeps it from leaking into other
# test files in the same process that need the real nibabel installed.
with mock.patch.dict(sys.modules, {"nibabel": types.ModuleType("nibabel")}):
    from anatomy.parcellation.data_loader import conform


class GetscaleRaisesInsteadOfExitingTest(unittest.TestCase):
    def test_negative_min_raises_value_error_not_system_exit(self) -> None:
        # getscale() clips its input to >= 0 before computing src_min, which
        # makes the "min below 0" branch unreachable through normal input;
        # force it by making the clip a no-op, mirroring what would happen
        # if that clip were ever removed or bypassed upstream.
        data = np.array([-5.0, 1.0, 2.0, 3.0])
        with mock.patch.object(conform.np, "clip", side_effect=lambda arr, a_min, a_max: arr):
            with self.assertRaises(ValueError) as ctx:
                conform.getscale(data, 0, 255)
        self.assertNotIsInstance(ctx.exception, SystemExit)


class FakeHeader:
    def __init__(self, zooms):
        self._zooms = zooms

    def get_zooms(self):
        return self._zooms


_LIA_AFFINE_3X3 = np.array([[-1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])


class FakeImage:
    def __init__(self, shape, zooms=(1.0, 1.0, 1.0), affine=None):
        self.shape = shape
        self.header = FakeHeader(zooms)
        self.affine = affine if affine is not None else _LIA_AFFINE_3X3


class IsConformRaisesInsteadOfExitingTest(unittest.TestCase):
    def test_multiple_frames_raises_value_error_not_system_exit(self) -> None:
        img = FakeImage(shape=(256, 256, 256, 2))
        with self.assertRaises(ValueError) as ctx:
            conform.is_conform(img)
        self.assertNotIsInstance(ctx.exception, SystemExit)
        self.assertIn("Multiple input frames", str(ctx.exception))

    def test_single_frame_conformed_image_returns_true(self) -> None:
        img = FakeImage(shape=(256, 256, 256, 1))
        self.assertTrue(conform.is_conform(img))

    def test_non_conform_dimensions_return_false_without_raising(self) -> None:
        img = FakeImage(shape=(128, 128, 128))
        self.assertFalse(conform.is_conform(img))


if __name__ == "__main__":
    unittest.main()
