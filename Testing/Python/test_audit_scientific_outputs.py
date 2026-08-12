#!/usr/bin/env python3
"""Tests for the multi-subject scientific output audit."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ScientificOutputAuditTest(unittest.TestCase):
    def _fixture(
        self,
        root: Path,
        *,
        invalid_fa: bool = False,
        ddseg_only: bool = False,
    ) -> Path:
        import nibabel as nib
        import numpy as np

        subject_root = root / "input-subject"
        input_dir = subject_root / "input"
        input_dir.mkdir(parents=True)
        affine = np.eye(4)
        dwi = np.ones((3, 3, 3, 7), dtype=np.float32)
        mask = np.ones((3, 3, 3), dtype=np.uint8)
        nib.save(nib.Nifti1Image(dwi, affine), input_dir / "data.nii.gz")
        nib.save(nib.Nifti1Image(mask, affine), input_dir / "nodif_brain_mask.nii.gz")

        output_root = root / "outputs"
        subject_output = output_root / "sub-01"
        dti_dir = subject_output / "02_microstructure" / "dti"
        tract_dir = subject_output / "04_tractography" / "tractograms" / "dti_det" / "Test1"
        metadata_dir = subject_output / "00_run_metadata"
        dti_dir.mkdir(parents=True)
        tract_dir.mkdir(parents=True)
        metadata_dir.mkdir(parents=True)

        l1 = np.full(mask.shape, 0.0015, dtype=np.float32)
        l2 = np.full(mask.shape, 0.0006, dtype=np.float32)
        l3 = np.full(mask.shape, 0.0003, dtype=np.float32)
        arrays = {
            "fa": np.full(mask.shape, 1.2 if invalid_fa else 0.5, dtype=np.float32),
            "md": (l1 + l2 + l3) / 3.0,
            "ad": l1,
            "rd": (l2 + l3) / 2.0,
            "l1": l1,
            "l2": l2,
            "l3": l3,
            "trace": l1 + l2 + l3,
        }
        outputs: dict[str, str] = {}
        for key, array in arrays.items():
            path = dti_dir / f"sub-01_dti_{key.upper()}.nii.gz"
            nib.save(nib.Nifti1Image(array, affine), path)
            outputs[key] = path.as_posix()

        tract_path = tract_dir / "sub-01-dti-deterministic.trk"
        tractogram = nib.streamlines.Tractogram(
            [np.asarray([[0.25, 0.25, 0.25], [1.25, 1.25, 1.25]], dtype=np.float32)],
            affine_to_rasmm=np.eye(4),
        )
        nib.streamlines.save(tractogram, tract_path.as_posix())
        tasks = [
            {"name": "microstructure.dti", "status": "completed", "outputs": outputs},
            {
                "name": "tractography.dti_det",
                "status": "completed",
                "outputs": {"tractogram_trk": tract_path.as_posix()},
            },
        ]
        if ddseg_only:
            ddseg_dir = subject_output / "03_structural" / "ddseg"
            ddseg_dir.mkdir(parents=True)
            segmentation = np.ones(mask.shape, dtype=np.uint8)
            segmentation[:, :, 1] = 2
            segmentation[:, :, 2] = 3
            segmentation_path = ddseg_dir / "SegmentationMap_GMWMCSF.nii.gz"
            nib.save(nib.Nifti1Image(segmentation, affine), segmentation_path)
            ddseg_outputs = {"segmentation": segmentation_path.as_posix()}
            for label, key in ((1, "gm"), (2, "wm"), (3, "csf")):
                path = ddseg_dir / f"ProbabilisticMap_{key.upper()}.nii.gz"
                nib.save(
                    nib.Nifti1Image((segmentation == label).astype(np.float32), affine),
                    path,
                )
                ddseg_outputs[f"{key}_probability"] = path.as_posix()
            tasks.append(
                {
                    "name": "segmentation.ddseg",
                    "status": "completed",
                    "outputs": ddseg_outputs,
                }
            )

        manifest = {
            "subject_id": "sub-01",
            "subject_root": subject_root.as_posix(),
            "output_root": subject_output.as_posix(),
            "tasks": tasks,
        }
        (metadata_dir / "Test1_orchestration_manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        return output_root

    def test_valid_dti_and_tractography_batch_passes(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(Path(tmp))
            report = audit_output_root(
                output_root,
                require_dti=True,
                require_tractography=True,
                min_subjects=1,
            )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["summary"]["passed_subjects"], 1)

    def test_out_of_range_fa_fails(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(Path(tmp), invalid_fa=True)
            report = audit_output_root(output_root, require_dti=True)

        self.assertEqual(report["status"], "failed")
        failed_names = {
            check["name"]
            for check in report["subjects"][0]["checks"]
            if not check["passed"]
        }
        self.assertIn("dti.fa.range", failed_names)

    def test_partial_structural_route_ignores_unselected_routes(self) -> None:
        from scripts.audit_scientific_outputs import audit_output_root

        with tempfile.TemporaryDirectory() as tmp:
            output_root = self._fixture(Path(tmp), ddseg_only=True)
            report = audit_output_root(output_root, require_dti=True)
            full_structural_report = audit_output_root(output_root, require_structural=True)

        self.assertEqual(report["status"], "passed")
        check_names = {check["name"] for check in report["subjects"][0]["checks"]}
        self.assertIn("structural.ddseg.segmentation_exists", check_names)
        self.assertFalse(any(name.startswith("structural.ddparcel") for name in check_names))
        self.assertFalse(any(name.startswith("structural.ddsurfer") for name in check_names))
        self.assertEqual(full_structural_report["status"], "failed")
        required_check = next(
            check
            for check in full_structural_report["subjects"][0]["checks"]
            if check["name"] == "required.structural"
        )
        self.assertFalse(required_check["passed"])


if __name__ == "__main__":
    unittest.main()
