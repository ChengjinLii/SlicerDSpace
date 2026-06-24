#!/usr/bin/env python3
"""Tests for automatic brain-mask estimation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class BrainMaskTest(unittest.TestCase):
    def _write_fake_dwi2mask(self, bin_dir: Path) -> None:
        tool = bin_dir / "dwi2mask"
        tool.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, sys\n"
            "pathlib.Path(sys.argv[2]).write_text('mask\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        tool.chmod(0o755)

    def test_missing_subject_mask_is_generated_with_mrtrix_dwi2mask(self) -> None:
        from shared.pipeline import find_subject_root

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            self._write_fake_dwi2mask(bin_dir)
            subject_root = root / "sub-01"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            (input_dir / "data.nii.gz").write_text("dwi\n", encoding="utf-8")
            (input_dir / "bvals").write_text("0 1000 1000\n", encoding="utf-8")
            (input_dir / "bvecs").write_text("0 1 0\n0 0 1\n0 0 0\n", encoding="utf-8")

            with patch.dict("os.environ", {"SLICERDDSURFER_MRTRIX_BIN_DIR": bin_dir.as_posix()}):
                raw = find_subject_root(subject_root, "sub-01")

            self.assertTrue(raw.mask_path.is_file())
            self.assertTrue((input_dir / "nodif_brain_mask.manifest.json").is_file())
            self.assertEqual(raw.mask_path.read_text(encoding="utf-8"), "mask\n")

    def test_missing_subject_mask_without_dwi2mask_fails_with_setup_message(self) -> None:
        from shared.pipeline import find_subject_root

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "sub-01"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            (input_dir / "data.nii.gz").write_text("dwi\n", encoding="utf-8")
            (input_dir / "bvals").write_text("0 1000\n", encoding="utf-8")
            (input_dir / "bvecs").write_text("0 1\n0 0\n0 0\n", encoding="utf-8")

            with patch.dict("os.environ", {"SLICERDDSURFER_MRTRIX_BIN_DIR": "/missing"}, clear=False):
                with self.assertRaisesRegex(FileNotFoundError, "MRtrix3 dwi2mask"):
                    find_subject_root(subject_root, "sub-01")

    def test_validation_accepts_subject_without_supplied_mask_when_dwi2mask_is_available(self) -> None:
        from shared import InputValidationConfig, validate_subject_inputs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            self._write_fake_dwi2mask(bin_dir)
            subject_root = root / "sub-01"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            (input_dir / "data.nii.gz").write_text("dwi\n", encoding="utf-8")
            (input_dir / "bvals").write_text("0 1000\n", encoding="utf-8")
            (input_dir / "bvecs").write_text("0 1\n0 0\n0 0\n", encoding="utf-8")

            with patch.dict("os.environ", {"SLICERDDSURFER_MRTRIX_BIN_DIR": bin_dir.as_posix()}):
                result = validate_subject_inputs(
                    InputValidationConfig(subject_id="sub-01", input_root=subject_root, dependency_groups=())
                )

            self.assertTrue(result.passed)
            self.assertTrue((input_dir / "nodif_brain_mask.nii.gz").is_file())


if __name__ == "__main__":
    unittest.main()
