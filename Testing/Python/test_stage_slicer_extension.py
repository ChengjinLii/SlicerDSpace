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
            self.assertTrue((module_dir / "anatomy" / "__init__.py").is_file())
            self.assertTrue((module_dir / "anatomy" / "surface" / "postprocess_docker.py").is_file())
            self.assertTrue((module_dir / "anatomy" / "surface" / "ddsurfer_backend" / "model" / "ddsurfer.py").is_file())
            for legacy in ("surface", "segmentation", "parcellation"):
                self.assertFalse((module_dir / legacy).exists(), legacy)
            for retired in ("anatomy/surface/models", "anatomy/surface/networks", "anatomy/parcellation/models/solver.py",
                            "anatomy/parcellation/models/losses.py", "anatomy/parcellation/models/organize_weights.sh",
                            "docs/archive/legacy-copy-20260523"):
                self.assertFalse((module_dir / retired).exists(), retired)
            self.assertEqual(sorted(path.name for path in module_dir.glob("*.py")), ["SlicerDDSurfer.py"])
            self.assertTrue((module_dir / "tractography" / "saf_backend").is_dir())
            for excluded in ("docs/site", "docs/website", "website", "Testing",
                             "docs/release/PERFORMANCE_OPTIMIZATIONS.md",
                             "docs/release/benchmarks/complete_models_20261020.json",
                             "scripts/benchmark_complete_models.py"):
                self.assertFalse((module_dir / excluded).exists(), excluded)
            from shared.docs import DOC_PATHS
            for guide in DOC_PATHS.values():
                self.assertTrue((module_dir / guide).is_file(), str(guide))
            self.assertTrue((module_dir / "licenses/DIPY.txt").is_file())
            self.assertTrue((module_dir / "tractography/wmql_queries/AF_CST.qry").is_file())
            self.assertTrue((module_dir / "scripts/wsl/WslCommandBridge.cs").is_file())
            self.assertFalse((module_dir / "tractography" / "slicer_dmri_reference").exists())
            self.assertIn("models", result["runtime_entries"])
            self.assertIn("tractography/slicer_dmri_reference", result["excluded_runtime_paths"])

    def test_hardlink_staging_also_excludes_reference_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = stage_extension(Path(tmp), slicer_version="Slicer-5.6", clean=True, link_mode="hardlink")
            module_dir = Path(str(result["module_dir"]))
            self.assertFalse((module_dir / "tractography" / "slicer_dmri_reference").exists())

    def test_clean_restaging_removes_the_old_flat_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = stage_extension(root, slicer_version="Slicer-5.10", clean=True, link_mode="copy")
            module_dir = Path(str(result["module_dir"]))
            for domain in ("surface", "parcellation", "segmentation"):
                legacy = module_dir / domain
                legacy.mkdir()
                (legacy / "__init__.py").write_text("# previous installation\n", encoding="utf-8")
            stage_extension(root, slicer_version="Slicer-5.10", clean=True, link_mode="copy")
            for domain in ("surface", "parcellation", "segmentation"):
                self.assertFalse((module_dir / domain).exists())
                self.assertTrue((module_dir / "anatomy" / domain / "__init__.py").is_file())

    def test_restaging_without_clean_removes_retired_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = stage_extension(root, slicer_version="Slicer-5.10", clean=True, link_mode="copy")
            module_dir = Path(str(result["module_dir"]))
            stale = module_dir / "docs/release/PERFORMANCE_OPTIMIZATIONS.md"
            stale.write_text("old installed report\n", encoding="utf-8")
            stage_extension(root, slicer_version="Slicer-5.10", clean=False, link_mode="copy")
            self.assertFalse(stale.exists())
            self.assertTrue((module_dir / "docs/release/RELEASE_NOTES_v0.1.0.md").is_file())


if __name__ == "__main__":
    unittest.main()
