from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.stage_slicer_extension import stage_extension


class StageSlicerExtensionTest(unittest.TestCase):
    def test_staged_module_contains_runtime_assets_but_not_reference_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = stage_extension(Path(tmp), slicer_version="Slicer-5.6", clean=True, link_mode="copy")
            module_dir = Path(str(result["module_dir"]))
            self.assertTrue((module_dir / "models" / "assets_manifest.json").is_file())
            self.assertTrue((module_dir / "shared" / "workflow_catalog.py").is_file())
            self.assertTrue((module_dir / "surface" / "postprocess_docker.py").is_file())
            self.assertEqual(sorted(path.name for path in module_dir.glob("*.py")), ["SlicerDDSurfer.py"])
            self.assertTrue((module_dir / "tractography" / "saf_backend").is_dir())
            self.assertFalse((module_dir / "tractography" / "slicer_dmri_reference").exists())
            self.assertIn("models", result["runtime_entries"])
            self.assertIn("tractography/slicer_dmri_reference", result["excluded_runtime_paths"])

    def test_hardlink_staging_also_excludes_reference_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = stage_extension(Path(tmp), slicer_version="Slicer-5.6", clean=True, link_mode="hardlink")
            module_dir = Path(str(result["module_dir"]))
            self.assertFalse((module_dir / "tractography" / "slicer_dmri_reference").exists())


if __name__ == "__main__":
    unittest.main()
