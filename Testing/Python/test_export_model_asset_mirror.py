#!/usr/bin/env python3
"""Tests for export_model_asset_mirror.py."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "export_model_asset_mirror.py"


def _load_exporter_module():
    sys.path.insert(0, SCRIPT_DIR.as_posix())
    spec = importlib.util.spec_from_file_location("export_model_asset_mirror", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_unit_manifest(path: Path, *, sha256: str, size_bytes: int) -> None:
    manifest = {
        "kind": "slicerdsurfer_model_assets",
        "version": 1,
        "default_profile": "unit",
        "default_asset_source_ids": ["unit_mirror"],
        "asset_sources": {
            "unit_mirror": {
                "kind": "url-template",
                "status": "active",
                "base_url": "https://example.invalid/SlicerDDSurfer-models/v0.1.0",
            }
        },
        "profiles": {
            "unit": {
                "required_paths": ["weights/model.pt"],
                "asset_groups": ["unit weights"],
                "terms_notice": ["confirm redistribution terms"],
            }
        },
        "asset_records": {
            "weights/model.pt": {
                "size_bytes": size_bytes,
                "sha256": sha256,
                "source_ids": ["unit_mirror"],
            }
        },
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


class ExportModelAssetMirrorTest(unittest.TestCase):
    def test_export_verified_assets_preserves_relative_paths_and_writes_indexes(self) -> None:
        module = _load_exporter_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path / "repo"
            output_dir = tmp_path / "mirror"
            asset = repo_root / "weights" / "model.pt"
            manifest_path = tmp_path / "assets_manifest.json"
            asset.parent.mkdir(parents=True)
            asset.write_text("downloaded", encoding="utf-8")
            _write_unit_manifest(manifest_path, sha256=_sha256_text("downloaded"), size_bytes=asset.stat().st_size)

            export_manifest = module.export_asset_mirror(
                repo_root=repo_root,
                output_dir=output_dir,
                profile="unit",
                manifest_path=manifest_path,
                mode="copy",
            )

            exported_asset = output_dir / "weights" / "model.pt"
            self.assertEqual(exported_asset.read_text(encoding="utf-8"), "downloaded")
            self.assertTrue((output_dir / "asset_mirror_manifest.json").is_file())
            self.assertTrue((output_dir / "asset_mirror_index.tsv").is_file())
            self.assertEqual(export_manifest["profile"], "unit")
            self.assertEqual(export_manifest["asset_groups"], ["unit weights"])
            self.assertEqual(export_manifest["records"][0]["path"], "weights/model.pt")
            self.assertEqual(export_manifest["records"][0]["sha256"], _sha256_text("downloaded"))

    def test_dry_run_returns_plan_without_writing_output_directory(self) -> None:
        module = _load_exporter_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path / "repo"
            output_dir = tmp_path / "mirror"
            asset = repo_root / "weights" / "model.pt"
            manifest_path = tmp_path / "assets_manifest.json"
            asset.parent.mkdir(parents=True)
            asset.write_text("downloaded", encoding="utf-8")
            _write_unit_manifest(manifest_path, sha256=_sha256_text("downloaded"), size_bytes=asset.stat().st_size)

            export_manifest = module.export_asset_mirror(
                repo_root=repo_root,
                output_dir=output_dir,
                profile="unit",
                manifest_path=manifest_path,
                mode="copy",
                dry_run=True,
            )

            self.assertTrue(export_manifest["dry_run"])
            self.assertFalse(output_dir.exists())

    def test_export_rejects_unverified_assets(self) -> None:
        module = _load_exporter_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path / "repo"
            output_dir = tmp_path / "mirror"
            asset = repo_root / "weights" / "model.pt"
            manifest_path = tmp_path / "assets_manifest.json"
            asset.parent.mkdir(parents=True)
            asset.write_text("changed", encoding="utf-8")
            _write_unit_manifest(manifest_path, sha256="0" * 64, size_bytes=asset.stat().st_size)

            with self.assertRaises(RuntimeError):
                module.export_asset_mirror(
                    repo_root=repo_root,
                    output_dir=output_dir,
                    profile="unit",
                    manifest_path=manifest_path,
                    mode="copy",
                )

            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
