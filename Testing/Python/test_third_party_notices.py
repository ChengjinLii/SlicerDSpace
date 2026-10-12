"""License checks verify notices, never imply unrestricted model redistribution."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.audit_third_party import REQUIRED_RECORDS, audit
from scripts.stage_slicer_extension import stage_extension


ROOT = Path(__file__).resolve().parents[2]


class ThirdPartyNoticesTest(unittest.TestCase):
    def test_notice_bytes_survive_autocrlf_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            paths = [".gitattributes", *REQUIRED_RECORDS.values()]
            for relative in paths:
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            subprocess.run(["git", "init", "--quiet"], cwd=source, check=True, capture_output=True)
            subprocess.run(["git", "add", "--", *paths], cwd=source, check=True, capture_output=True)
            output = root / "autocrlf-checkout"
            subprocess.run(["git", "-c", "core.autocrlf=true", "checkout-index", "-a",
                            f"--prefix={output.as_posix()}/"], cwd=source, check=True, capture_output=True)
            for relative in REQUIRED_RECORDS.values():
                expected = (ROOT / relative).read_bytes()
                self.assertNotIn(b"\r\n", expected)
                self.assertEqual((output / relative).read_bytes(), expected, relative)

    def staged(self, directory):
        install = stage_extension(Path(directory), slicer_version="Slicer-5.10", clean=True, link_mode="copy")
        return Path(install["module_dir"])

    def test_current_records_are_packaged(self):
        result = audit(ROOT)
        self.assertEqual(result["status"], "pass", result["findings"])
        self.assertEqual(len(result["checked"]), len(REQUIRED_RECORDS))
        self.assertIn("model weights", result["remaining_review"])
        self.assertFalse((ROOT / "LICENSE").exists())

    def test_installed_record_passes_without_source_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.staged(directory)
            self.assertEqual(audit(root)["status"], "pass")

    def test_missing_or_altered_license_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.staged(directory)
            (root / "licenses/FreeSurfer.txt").write_text("replacement", encoding="utf-8")
            self.assertIn("Changed license text: licenses/FreeSurfer.txt", audit(root)["findings"])
            (root / "anatomy/surface/ddsurfer_backend/LICENSE.txt").unlink()
            self.assertEqual(audit(root)["status"], "fail")

    def test_mutable_source_and_missing_record_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.staged(directory)
            path = root / "licenses/provenance.json"
            spec = json.loads(path.read_text(encoding="utf-8"))
            spec["records"][0]["source"] = "https://github.com/pnlbwh/conversion/blob/master/LICENSE"
            spec["records"] = [record for record in spec["records"] if record["id"] != "pytorch3d"]
            path.write_text(json.dumps(spec), encoding="utf-8")
            findings = audit(root)["findings"]
            self.assertIn("Unpinned license source: conversion", findings)
            self.assertIn("Missing license record: pytorch3d", findings)

    def test_notice_cannot_be_excluded_from_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.staged(directory)
            path = root / "scripts/extension_runtime/runtime_resources.json"
            spec = json.loads(path.read_text(encoding="utf-8"))
            spec["excluded_prefixes"].append("licenses/FreeSurfer.txt")
            path.write_text(json.dumps(spec), encoding="utf-8")
            self.assertIn("License omitted from runtime package: licenses/FreeSurfer.txt", audit(root)["findings"])


if __name__ == "__main__":
    unittest.main()
