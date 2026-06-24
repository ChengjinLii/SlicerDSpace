#!/usr/bin/env python3
"""Tests for release-facing Slicer extension metadata."""

from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class SlicerExtensionMetadataTest(unittest.TestCase):
    def test_extension_metadata_audit_passes(self) -> None:
        from scripts.audit_slicer_extension_metadata import audit

        result = audit(REPO_ROOT)

        self.assertEqual(result["status"], "pass", result["findings"])
        self.assertEqual(result["s4ext_depends"], result["cmake_depends"])


if __name__ == "__main__":
    unittest.main()
