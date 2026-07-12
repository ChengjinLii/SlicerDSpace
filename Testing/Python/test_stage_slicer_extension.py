from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.stage_slicer_extension import stage_extension


class StageSlicerExtensionTest(unittest.TestCase):
    def test_staged_module_contains_model_asset_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = stage_extension(Path(tmp), slicer_version="Slicer-5.6", clean=True, link_mode="copy")
            module_dir = Path(str(result["module_dir"]))
            self.assertTrue((module_dir / "models" / "assets_manifest.json").is_file())
            self.assertIn("models", result["runtime_entries"])


if __name__ == "__main__":
    unittest.main()
