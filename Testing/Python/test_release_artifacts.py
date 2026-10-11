#!/usr/bin/env python3
"""Tests for release artifact metadata generation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class ReleaseArtifactsTest(unittest.TestCase):
    def test_default_output_is_outside_the_root_directory(self) -> None:
        from scripts.build_release_artifacts import build_parser

        self.assertEqual(build_parser().parse_args([]).output_dir,
                         REPO_ROOT / "ignore/releases/v0.1.0")

    def test_build_release_artifacts_writes_code_only_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "artifacts"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/build_release_artifacts.py",
                    "--output-dir",
                    output_dir.as_posix(),
                    "--profile",
                    "core",
                ],
                cwd=REPO_ROOT,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((output_dir / "code_only_archive_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "slicerdsurfer_code_only_release_archive_manifest")
            self.assertIn("LICENSE.txt", manifest["required_metadata_files"])
            self.assertNotIn("LICENSE", manifest["required_metadata_files"])
            self.assertIn("segmentation/weights/**", manifest["asset_exclusion_patterns"])
            self.assertTrue((output_dir / "model_assets_core_lock.json").is_file())
            self.assertTrue((output_dir / "asset_exclusion_checklist.md").is_file())


if __name__ == "__main__":
    unittest.main()
