#!/usr/bin/env python3
"""Tests for prepare_model_asset_upload.py."""

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
SCRIPT_PATH = SCRIPT_DIR / "prepare_model_asset_upload.py"


def _load_module():
    sys.path.insert(0, SCRIPT_DIR.as_posix())
    spec = importlib.util.spec_from_file_location("prepare_model_asset_upload", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_mirror(root: Path) -> None:
    asset = root / "weights" / "model.pt"
    asset.parent.mkdir(parents=True)
    asset.write_text("downloaded", encoding="utf-8")
    sha = hashlib.sha256(b"downloaded").hexdigest()
    (root / "asset_mirror_manifest.json").write_text(
        json.dumps(
            {
                "kind": "slicerdsurfer_model_asset_mirror",
                "profile": "core",
                "git_commit": "abc",
                "records": [
                    {
                        "path": "weights/model.pt",
                        "size_bytes": asset.stat().st_size,
                        "expected_size_bytes": asset.stat().st_size,
                        "sha256": sha,
                        "expected_sha256": sha,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


class PrepareModelAssetUploadTest(unittest.TestCase):
    def test_default_github_target_uses_renamed_model_repository(self) -> None:
        module = _load_module()
        args = module.build_parser().parse_args(['--mirror-dir', '/tmp/example-mirror'])
        self.assertEqual(args.repository, 'ChengjinLii/SlicerDSpace-models')

    def test_github_release_plan_validates_mirror_and_lists_files(self) -> None:
        module = _load_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_mirror(root)

            plan = module.build_upload_plan(
                mirror_dir=root,
                target="github-release",
                release_tag="v0.1.0",
                repository="owner/models",
                hf_repo="owner/models",
                zenodo_record="123",
            )

        self.assertEqual(plan["target"], "github-release")
        self.assertEqual(plan["file_count"], 1)
        self.assertIn("gh release create", " ".join(plan["commands"]))

    def test_huggingface_plan_uses_dataset_repository(self) -> None:
        module = _load_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_mirror(root)

            plan = module.build_upload_plan(
                mirror_dir=root,
                target="huggingface",
                release_tag="v0.1.0",
                repository="owner/models",
                hf_repo="owner/models",
                zenodo_record="123",
            )

        self.assertEqual(plan["target"], "huggingface")
        self.assertIn("huggingface.co/datasets/owner/models", plan["destination"])


if __name__ == "__main__":
    unittest.main()
