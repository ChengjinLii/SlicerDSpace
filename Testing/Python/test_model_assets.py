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
        self.assertIn("segmentation/weights/dti_axial.pt", plan.asset_records)
        self.assertIn("sha256", plan.asset_records["segmentation/weights/dti_axial.pt"])
        self.assertIn("github_lfs", plan.source_ids)
        self.assertIn("slicerdsurfer_models_git", plan.source_ids)
        self.assertIn("DDSURFER_CHECKPOINT_DIR", plan.external_overrides)
        self.assertIn("DDCSR surface model weights", plan.asset_groups)
        self.assertTrue(any("redistribution" in notice for notice in plan.terms_notices))

    def test_manifest_prefers_independent_model_repository_source(self) -> None:
        module = _load_downloader_module()

        manifest = module.load_manifest(REPO_ROOT / "models" / "assets_manifest.json")
        sources = manifest["asset_sources"]

        self.assertEqual(sources["slicerdsurfer_models_git"]["status"], "active")
        self.assertIn(
            "https://github.com/ChengjinLii/SlicerDDSurfer-models/raw/main",
            sources["slicerdsurfer_models_git"]["url_template"],
        )

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
                source_ids=("github_lfs",),
                asset_records={},
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
                source_ids=("mirror",),
                asset_records={
                    "weights/model.pt": {
                        "path": "weights/model.pt",
                        "source_ids": ["mirror"],
                        "size_bytes": len("downloaded"),
                    }
                },
            )

            lockfile = module.build_asset_lockfile(root, plan)

            self.assertEqual(lockfile["schema"], "slicerddsurfer.model_assets.lockfile.v1")
            self.assertEqual(lockfile["asset_groups"], ["unit weights"])
            self.assertEqual(lockfile["terms_notices"], ["confirm terms"])
            self.assertEqual(lockfile["records"][0]["path"], "weights/model.pt")
            self.assertFalse(lockfile["records"][0]["lfs_pointer"])
            self.assertIsNotNone(lockfile["records"][0]["sha256"])
            self.assertEqual(lockfile["records"][0]["source_ids"], ["mirror"])

    def test_verify_asset_plan_reports_size_and_sha256_mismatches(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "weights" / "model.pt"
            asset.parent.mkdir(parents=True)
            asset.write_text("bad", encoding="utf-8")
            plan = module.AssetPlan(
                profile="unit",
                resolved_profiles=("unit",),
                all_lfs=False,
                include_patterns=(),
                required_paths=("weights/model.pt",),
                external_overrides=(),
                asset_groups=(),
                terms_notices=(),
                source_ids=("mirror",),
                asset_records={
                    "weights/model.pt": {
                        "path": "weights/model.pt",
                        "source_ids": ["mirror"],
                        "size_bytes": 10,
                        "sha256": "0" * 64,
                    }
                },
            )

            result = module.verify_asset_plan(root, plan)

        self.assertFalse(result["ok"])
        self.assertEqual(result["hashes_checked"], 1)
        self.assertEqual(result["size_mismatches"][0]["path"], "weights/model.pt")
        self.assertEqual(result["sha256_mismatches"][0]["path"], "weights/model.pt")

    def test_verify_asset_plan_can_skip_hashes_for_ui_status(self) -> None:
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
                asset_groups=(),
                terms_notices=(),
                source_ids=("mirror",),
                asset_records={
                    "weights/model.pt": {
                        "path": "weights/model.pt",
                        "source_ids": ["mirror"],
                        "size_bytes": asset.stat().st_size,
                        "sha256": "0" * 64,
                    }
                },
            )

            result = module.verify_asset_plan(root, plan, check_hashes=False)

        self.assertTrue(result["ok"])
        self.assertEqual(result["hashes_checked"], 0)

    def test_url_download_uses_base_url_and_verifies_checksum(self) -> None:
        module = _load_downloader_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path / "repo"
            mirror = tmp_path / "mirror"
            source_file = mirror / "weights" / "model.pt"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("downloaded", encoding="utf-8")
            expected_sha = module._sha256(source_file)
            plan = module.AssetPlan(
                profile="unit",
                resolved_profiles=("unit",),
                all_lfs=False,
                include_patterns=(),
                required_paths=("weights/model.pt",),
                external_overrides=(),
                asset_groups=(),
                terms_notices=(),
                source_ids=("unit_mirror",),
                asset_records={
                    "weights/model.pt": {
                        "path": "weights/model.pt",
                        "source_ids": ["unit_mirror"],
                        "size_bytes": source_file.stat().st_size,
                        "sha256": expected_sha,
                    }
                },
            )
            manifest = {
                "asset_sources": {},
            }

            module.download_asset_plan(
                repo_root,
                plan,
                manifest,
                source="url",
                base_urls=(mirror.resolve().as_uri(),),
            )
            result = module.verify_asset_plan(repo_root, plan)

        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
