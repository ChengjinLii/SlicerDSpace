#!/usr/bin/env python3
"""Tests for shared subject-root input validation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from shared import InputValidationConfig, validate_subject_inputs


SUBJECT_ID = "100307"


def _write(path: Path, content: str = "placeholder") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_subject_root(root: Path, *, metadata: bool = True) -> Path:
    import nibabel as nib
    import numpy as np

    subject_root = root / SUBJECT_ID
    input_dir = subject_root / "input"
    input_dir.mkdir(parents=True)
    data = np.ones((5, 5, 5, 4), dtype=np.float32)
    mask = np.zeros((5, 5, 5), dtype=np.uint8)
    mask[1:4, 1:4, 1:4] = 1
    nib.save(nib.Nifti1Image(data, np.eye(4)), input_dir / "data.nii.gz")
    nib.save(nib.Nifti1Image(mask, np.eye(4)), input_dir / "nodif_brain_mask.nii.gz")
    _write(input_dir / "bvals", "0 1000 1000 2000\n")
    _write(input_dir / "bvecs", "0 1 0 0\n0 0 1 0\n0 0 0 1\n")
    if metadata:
        _write(
            input_dir / "data.json",
            json.dumps({"PhaseEncodingDirection": "j-", "TotalReadoutTime": 0.065}),
        )
    return subject_root


class InputValidationTest(unittest.TestCase):
    def test_valid_subject_root_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = _make_subject_root(Path(tmp))
            output_dir = subject_root / "outputs" / "validation"

            result = validate_subject_inputs(
                InputValidationConfig(
                    subject_id=SUBJECT_ID,
                    input_root=subject_root,
                    output_dir=output_dir,
                    dependency_groups=(),
                    brain_mask_backend="provided",
                )
            )

            self.assertTrue(result.passed)
            self.assertEqual(result.error_count, 0)
            self.assertEqual(result.warning_count, 0)
            self.assertTrue(result.report_path and result.report_path.is_file())
            self.assertEqual(result.metrics["gradients"]["count"], 4)
            self.assertEqual(result.metrics["gradients"]["shells_rounded"], [1000, 2000])
            self.assertEqual(result.metrics["bids_metadata"]["phase_encoding_direction"], "j-")
            self.assertEqual(result.metrics["brain_mask_selection"]["backend"], "provided")
            self.assertTrue(result.metrics["brain_mask_qc"]["geometry_pass"])
            self.assertEqual(result.metrics["brain_mask_qc"]["brain_voxels"], 27)

    def test_missing_metadata_warns_but_does_not_block_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = _make_subject_root(Path(tmp), metadata=False)

            result = validate_subject_inputs(
                InputValidationConfig(
                    subject_id=SUBJECT_ID,
                    input_root=subject_root,
                    dependency_groups=(),
                    brain_mask_backend="provided",
                )
            )

            self.assertTrue(result.passed)
            self.assertEqual(result.error_count, 0)
            self.assertEqual(result.warning_count, 1)
            self.assertEqual(result.messages[0].category, "metadata")

    def test_missing_required_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = _make_subject_root(Path(tmp))
            (subject_root / "input" / "bvecs").unlink()

            result = validate_subject_inputs(
                InputValidationConfig(
                    subject_id=SUBJECT_ID,
                    input_root=subject_root,
                    dependency_groups=(),
                    brain_mask_backend="provided",
                    write_report=False,
                )
            )

            self.assertFalse(result.passed)
            self.assertGreaterEqual(result.error_count, 1)

    def test_gradient_shape_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = _make_subject_root(Path(tmp))
            _write(subject_root / "input" / "bvecs", "0 1 0\n0 0 1\n")

            result = validate_subject_inputs(
                InputValidationConfig(
                    subject_id=SUBJECT_ID,
                    input_root=subject_root,
                    dependency_groups=(),
                    brain_mask_backend="provided",
                    write_report=False,
                )
            )

            self.assertFalse(result.passed)
            self.assertTrue(any(issue.category == "gradient" for issue in result.messages))

    def test_gradient_count_must_match_dwi_volume_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_subject_root(Path(tmp))
            _write(root / 'input/bvals', '0 1000 1000\n')
            _write(root / 'input/bvecs', '0 1 0\n0 0 1\n0 0 0\n')
            result = validate_subject_inputs(InputValidationConfig(
                SUBJECT_ID, root, dependency_groups=(), brain_mask_backend='provided'))
            self.assertFalse(result.passed)
            self.assertTrue(any(issue.category == 'gradient' and 'volume' in issue.message for issue in result.messages))

    def test_nonfinite_gradients_produce_a_structured_report(self):
        for value in ('inf', '-inf', 'nan'):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                root = _make_subject_root(Path(tmp))
                _write(root / 'input/bvals', f'0 1000 1000 {value}\n')
                result = validate_subject_inputs(InputValidationConfig(
                    SUBJECT_ID, root, dependency_groups=(), brain_mask_backend='provided'))
                self.assertFalse(result.passed)
                self.assertTrue(any('non-finite' in issue.message for issue in result.messages))
                json.loads(result.report_path.read_text(), parse_constant=lambda value: self.fail(value))

    def test_dwi_must_be_four_dimensional(self):
        import nibabel as nib
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_subject_root(Path(tmp))
            nib.save(nib.Nifti1Image(np.ones((5, 5, 5), dtype=np.float32), np.eye(4)), root / 'input/data.nii.gz')
            result = validate_subject_inputs(InputValidationConfig(
                SUBJECT_ID, root, dependency_groups=(), brain_mask_backend='provided'))
            self.assertFalse(result.passed)
            self.assertTrue(any(issue.category == 'dwi' for issue in result.messages))


if __name__ == "__main__":
    unittest.main()
