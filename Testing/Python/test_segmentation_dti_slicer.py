#!/usr/bin/env python3
"""Tests for segmentation/dti_slicer.py's external command construction."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from anatomy.segmentation.dti_slicer import run_dti_feature_extraction


class DtiSlicerCommandConstructionTest(unittest.TestCase):
    def _make_slicer_base(self, root: Path) -> Path:
        slicer_base = root / "SlicerBase"
        (slicer_base / "lib" / "Slicer-5.10").mkdir(parents=True)
        (slicer_base / "Slicer").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        return slicer_base

    def test_paths_with_spaces_and_semicolons_are_passed_literally(self) -> None:
        # Commands used to be built as shell=True strings with a naive
        # f'"{path}"' quote; a path containing a shell metacharacter such as
        # ";" could break out of that quoting. Argument lists passed without
        # shell=True make this impossible: each path is one argv element,
        # unmodified, with no shell parsing involved at all.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slicer_base = self._make_slicer_base(root)

            input_root = root / "input dir; rm -rf ~"
            input_root.mkdir()
            nii_file = input_root / "data.nii.gz"
            bval_file = input_root / "bvals"
            bvec_file = input_root / "bvecs"
            for path in (nii_file, bval_file, bvec_file):
                path.write_text("stub", encoding="utf-8")
            output_folder = root / "out put"

            with mock.patch("anatomy.segmentation.dti_slicer.subprocess.run") as mock_run:
                mock_run.return_value = mock.Mock(returncode=0)
                with self.assertRaises(RuntimeError):
                    # The mocked subprocess never creates DTI_E3.nrrd, so the
                    # function raises at the end; that is expected here and
                    # orthogonal to the argv assertions below.
                    run_dti_feature_extraction(
                        nii_file=nii_file,
                        bval_file=bval_file,
                        bvec_file=bvec_file,
                        output_folder=output_folder,
                        slicer_base=slicer_base,
                        slicer_ext=slicer_base,
                    )

            self.assertTrue(mock_run.call_args_list)
            first_call = mock_run.call_args_list[0]
            (argv,) = first_call.args
            self.assertIsInstance(argv, list)
            self.assertNotIn(True, [first_call.kwargs.get("shell", False)])
            self.assertIn(str(bvec_file), argv)
            self.assertIn(str(bval_file), argv)
            self.assertIn(str(nii_file), argv)
            self.assertIn(str(output_folder / "DWI.nrrd"), argv)

            for call_args in mock_run.call_args_list:
                self.assertFalse(call_args.kwargs.get("shell", False))
                self.assertIsInstance(call_args.args[0], list)

    def test_launcher_wraps_cli_with_slicer_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slicer_base = self._make_slicer_base(root)
            nii_file = root / "data.nii.gz"
            bval_file = root / "bvals"
            bvec_file = root / "bvecs"
            for path in (nii_file, bval_file, bvec_file):
                path.write_text("stub", encoding="utf-8")
            output_folder = root / "out"

            with mock.patch("anatomy.segmentation.dti_slicer.subprocess.run") as mock_run:
                mock_run.return_value = mock.Mock(returncode=0)
                with self.assertRaises(RuntimeError):
                    run_dti_feature_extraction(
                        nii_file=nii_file,
                        bval_file=bval_file,
                        bvec_file=bvec_file,
                        output_folder=output_folder,
                        slicer_base=slicer_base,
                        slicer_ext=slicer_base,
                    )

            self.assertEqual(mock_run.call_count, 7)
            first_argv = mock_run.call_args_list[0].args[0]
            self.assertEqual(first_argv[0], str(slicer_base / "Slicer"))
            self.assertEqual(first_argv[1], "--launch")
            self.assertIn("DWIConvert", first_argv[2])


if __name__ == "__main__":
    unittest.main()
