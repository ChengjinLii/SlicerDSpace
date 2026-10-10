#!/usr/bin/env python3
"""Lightweight tests for the headless DDSurfer surface facade."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class SurfacePipelineTest(unittest.TestCase):
    def test_dry_run_writes_manifest_and_qc(self) -> None:
        from anatomy.surface import SurfaceConfig, run_surface

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_surface(
                SurfaceConfig(
                    subject_id="100307",
                    subject_root=root / "100307",
                    output_dir=root / "outputs" / "ddsurfer",
                    execute=False,
                )
            )

            self.assertFalse(result.executed)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "ddsurfer_surface")
            self.assertEqual(manifest["status"], "planned")
            self.assertIn("available", manifest["resources"])
            self.assertEqual(qc["status"], "planned")

    def test_resource_inspection_rejects_legacy_assets(self) -> None:
        from anatomy.surface import SurfaceConfig, inspect_surface_resources

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            checkpoint = root / "ckpts"
            hcp = checkpoint / "hcp"
            template.mkdir()
            hcp.mkdir(parents=True)
            for name in ("100307-FA.nii.gz", "hcp_hemi-left_init_160k.obj", "hcp_hemi-right_init_160k.obj"):
                (template / name).write_text(name, encoding="utf-8")
            for name in (
                "DDCSR_white_lh_Full_DualStream_no_b0_Cascaded.pt",
                "DDCSR_white_rh_Full_DualStream_no_b0_Cascaded.pt",
                "DDCSR_pial_lh_Full_DualStream_no_b0_Cascaded.pt",
                "DDCSR_pial_rh_Full_DualStream_no_b0_Cascaded.pt",
            ):
                (hcp / name).write_text(name, encoding="utf-8")
            atlas = root / "atlas.nii.gz"
            atlas.write_text("atlas", encoding="utf-8")

            status = inspect_surface_resources(
                SurfaceConfig(
                    subject_id="100307",
                    subject_root=root / "100307",
                    output_dir=root / "outputs" / "ddsurfer",
                    template_dir=template,
                    checkpoint_root=checkpoint,
                    registration_atlas=atlas,
                )
            )

            self.assertFalse(status["available"])
            self.assertTrue(status["missing"])


if __name__ == "__main__":
    unittest.main()
