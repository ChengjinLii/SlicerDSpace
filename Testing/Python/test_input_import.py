#!/usr/bin/env python3
"""Tests for external input import planning."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from shared.input_import import InputImportConfig, detect_import_source_kind, prepare_inputs


class InputImportTest(unittest.TestCase):
    def test_detects_canonical_subject_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "sub-01"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs"):
                (input_dir / name).write_text("x\n", encoding="utf-8")

            self.assertEqual(detect_import_source_kind(subject_root), "canonical")

    def test_nifti_source_is_copied_to_canonical_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "dwi.nii.gz"
            source.write_text("dwi\n", encoding="utf-8")
            (root / "dwi.bval").write_text("0 1000\n", encoding="utf-8")
            (root / "dwi.bvec").write_text("0 1\n0 0\n0 0\n", encoding="utf-8")
            (root / "dwi.json").write_text('{"PhaseEncodingDirection": "j"}\n', encoding="utf-8")
            subject_root = root / "prepared" / "sub-01"

            manifest = prepare_inputs(
                InputImportConfig(
                    source=source,
                    subject_root=subject_root,
                    subject_id="sub-01",
                    source_kind="nifti",
                )
            )

            self.assertEqual(manifest["status"], "completed")
            self.assertEqual((subject_root / "input" / "data.nii.gz").read_text(encoding="utf-8"), "dwi\n")
            self.assertTrue((subject_root / "input" / "bvals").is_file())
            self.assertTrue((subject_root / "input" / "bvecs").is_file())
            self.assertEqual(json.loads((subject_root / "input" / "dwi.json").read_text())["PhaseEncodingDirection"], "j")
            self.assertTrue((subject_root / "input" / "input_import_manifest.json").is_file())

    def test_dicom_import_prefers_dcm2niix_for_canonical_nifti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dicom_dir = root / "dicom"
            dicom_dir.mkdir()
            (dicom_dir / "IM0001.dcm").write_text("dicom\n", encoding="utf-8")

            manifest = prepare_inputs(
                InputImportConfig(
                    source=dicom_dir,
                    subject_root=root / "sub-01",
                    subject_id="sub-01",
                    source_kind="dicom",
                    dry_run=True,
                )
            )

            plan = manifest["plan"]
            self.assertEqual(manifest["status"], "planned")
            self.assertEqual(plan["backend"], "dcm2niix")
            self.assertEqual(plan["command"][plan["command"].index("-ba") + 1], "y")
            self.assertIn("-f", plan["command"])
            self.assertIn("data", plan["command"])

    def test_nrrd_import_uses_mrconvert_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nrrd = root / "data.nhdr"
            nrrd.write_text("NRRD0005\n", encoding="utf-8")

            manifest = prepare_inputs(
                InputImportConfig(
                    source=nrrd,
                    subject_root=root / "sub-01",
                    subject_id="sub-01",
                    source_kind="nrrd",
                    dry_run=True,
                )
            )

            plan = manifest["plan"]
            self.assertEqual(plan["backend"], "mrconvert")
            self.assertIn("-export_grad_fsl", plan["command"])
            self.assertTrue(plan["canonical_layout"]["dwi"].endswith("input/data.nii.gz"))

    def test_dicom_to_compat_nrrd_uses_dwiconvert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dicom_dir = root / "dicom"
            dicom_dir.mkdir()
            (dicom_dir / "IM0001").write_text("dicom\n", encoding="utf-8")

            manifest = prepare_inputs(
                InputImportConfig(
                    source=dicom_dir,
                    subject_root=root / "sub-01",
                    subject_id="sub-01",
                    source_kind="dicom",
                    output_kind="compat-nrrd",
                    dry_run=True,
                )
            )

            plan = manifest["plan"]
            self.assertEqual(plan["backend"], "dwiconvert")
            self.assertIn("DicomToNrrd", plan["command"])
            self.assertTrue(plan["canonical_layout"]["compat_nrrd"].endswith("cache/imported_nrrd/data.nhdr"))


if __name__ == "__main__":
    unittest.main()
