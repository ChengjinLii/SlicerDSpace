#!/usr/bin/env python3
"""Tests for optional WMA/TractCloud backend audit reporting."""

from __future__ import annotations

import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Testing.Python.audit_optional_bundle_backends import build_report


class OptionalBundleBackendAuditTest(unittest.TestCase):
    def test_report_records_missing_optional_backends_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tractography = root / "tractogram.vtk"
            tractography.write_text("# vtk DataFile Version 3.0\n", encoding="utf-8")
            report = build_report(
                Namespace(
                    wma_root=(root / "missing_wma").as_posix(),
                    wma_atlas_dir=(root / "missing_atlas").as_posix(),
                    require_virtual_x=False,
                    require_diffusion_measurements=False,
                    tractcloud_root=(root / "missing_tractcloud").as_posix(),
                    tractcloud_python=None,
                    input_tractography=[tractography.as_posix()],
                )
            )

            self.assertEqual(report["kind"], "optional_bundle_backend_audit")
            self.assertFalse(report["ready"]["wma_org_atlas"])
            self.assertFalse(report["ready"]["tractcloud"])
            self.assertGreaterEqual(len(report["blockers"]), 2)
            self.assertTrue(report["inputs"]["input_tractography"][0]["supported_by_wma"])
            self.assertTrue(report["inputs"]["input_tractography"][0]["supported_by_tractcloud"])


if __name__ == "__main__":
    unittest.main()
