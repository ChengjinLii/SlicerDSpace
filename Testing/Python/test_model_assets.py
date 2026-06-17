#!/usr/bin/env python3
"""Tests for manifest-driven model asset downloads."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "download_model_assets.py"


def _load_downloader_module():
    spec = importlib.util.spec_from_file_location("download_model_assets", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ModelAssetsTest(unittest.TestCase):
    def test_core_profile_resolves_manifest_includes_and_required_paths(self) -> None:
        module = _load_downloader_module()

        manifest = module.load_manifest(REPO_ROOT / "models" / "assets_manifest.json")
        plan = module.resolve_asset_plan(manifest, "core")

        self.assertEqual(plan.profile, "core")
        self.assertIn("surface", plan.resolved_profiles)
        self.assertIn("segmentation/weights/**", plan.include_patterns)
        self.assertIn("parcellation/weights/**", plan.include_patterns)
        self.assertIn("segmentation/weights/dti_axial.pt", plan.required_paths)
        self.assertIn("DDSURFER_CHECKPOINT_DIR", plan.external_overrides)
        self.assertIn("DDCSR surface model weights", plan.asset_groups)
        self.assertTrue(any("redistribution" in notice for notice in plan.terms_notices))

    def test_quick_gate_alias_resolves_to_core_profile(self) -> None:
        module = _load_downloader_module()

        manifest = module.load_manifest(REPO_ROOT / "models" / "assets_manifest.json")
        plan = module.resolve_asset_plan(manifest, "quick-gate")

        self.assertEqual(plan.profile, "quick-gate")
        self.assertIn("core", plan.resolved_profiles)
        self.assertIn("surface", plan.resolved_profiles)
        self.assertIn("parcellation/weights/**", plan.include_patterns)
        self.assertIn("segmentation/weights/dti_sagittal.pt", plan.required_paths)

    def test_verify_asset_plan_reports_missing_and_lfs_pointer_files(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "weights" / "model.pt"
            asset.parent.mkdir(parents=True)
            plan = module.AssetPlan(
                profile="unit",
                resolved_profiles=("unit",),
                all_lfs=False,
                include_patterns=(),
                required_paths=("weights/model.pt", "weights/missing.pt"),
                external_overrides=(),
                asset_groups=(),
                terms_notices=(),
            )

            asset.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 1\n", encoding="utf-8")
            result = module.verify_asset_plan(root, plan)
            self.assertIn("weights/model.pt", result["lfs_pointers"])
            self.assertIn("weights/missing.pt", result["missing"])
            self.assertFalse(result["ok"])

            (root / "weights" / "missing.pt").write_text("downloaded", encoding="utf-8")
            asset.write_text("downloaded", encoding="utf-8")
            result = module.verify_asset_plan(root, plan)
            self.assertTrue(result["ok"])

    def test_asset_lockfile_records_sha256_and_terms(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "weights" / "model.pt"
            asset.parent.mkdir(parents=True)
            asset.write_text("downloaded", encoding="utf-8")
            plan = module.AssetPlan(
                profile="unit",
                resolved_profiles=("unit",),
                all_lfs=False,
                include_patterns=(),
                required_paths=("weights/model.pt",),
                external_overrides=(),
                asset_groups=("unit weights",),
                terms_notices=("confirm terms",),
            )

            lockfile = module.build_asset_lockfile(root, plan)

            self.assertEqual(lockfile["schema"], "slicerddsurfer.model_assets.lockfile.v1")
            self.assertEqual(lockfile["asset_groups"], ["unit weights"])
            self.assertEqual(lockfile["terms_notices"], ["confirm terms"])
            self.assertEqual(lockfile["records"][0]["path"], "weights/model.pt")
            self.assertFalse(lockfile["records"][0]["lfs_pointer"])
            self.assertIsNotNone(lockfile["records"][0]["sha256"])


if __name__ == "__main__":
    unittest.main()
