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
    subject_root = root / SUBJECT_ID
    input_dir = subject_root / "input"
    _write(input_dir / "data.nii.gz")
    _write(input_dir / "nodif_brain_mask.nii.gz")
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
                )
            )

            self.assertTrue(result.passed)
            self.assertEqual(result.error_count, 0)
            self.assertEqual(result.warning_count, 0)
            self.assertTrue(result.report_path and result.report_path.is_file())
            self.assertEqual(result.metrics["gradients"]["count"], 4)
            self.assertEqual(result.metrics["gradients"]["shells_rounded"], [1000, 2000])
            self.assertEqual(result.metrics["bids_metadata"]["phase_encoding_direction"], "j-")

    def test_missing_metadata_warns_but_does_not_block_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = _make_subject_root(Path(tmp), metadata=False)

            result = validate_subject_inputs(
                InputValidationConfig(
                    subject_id=SUBJECT_ID,
                    input_root=subject_root,
                    dependency_groups=(),
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
                    write_report=False,
                )
            )

            self.assertFalse(result.passed)
            self.assertTrue(any(issue.category == "gradient" for issue in result.messages))


if __name__ == "__main__":
    unittest.main()
