#!/usr/bin/env python3
"""Tests for third-party licensing/notice files (no YAML dependency; see below).

CITATION.cff is checked with plain string assertions rather than by parsing
it as YAML: PyYAML is not installed in this repository's CI environment, and
this module must not introduce a new test dependency that is unavailable
there.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class LicenseFileTest(unittest.TestCase):
    def test_license_no_longer_links_the_gitignored_broken_path(self) -> None:
        text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertNotIn("third_party/REFERENCE_SOURCES.md", text)
        self.assertIn("THIRD_PARTY_NOTICES.md", text)


class ThirdPartyNoticesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    def test_file_exists_at_repo_root(self) -> None:
        self.assertTrue((REPO_ROOT / "THIRD_PARTY_NOTICES.md").is_file())

    def test_documents_fastsurfer_derived_code(self) -> None:
        self.assertIn("FastSurfer", self.text)
        self.assertIn("parcellation/models/networks.py", self.text)
        self.assertIn("parcellation/data_loader/conform.py", self.text)
        self.assertIn("Apache", self.text)

    def test_documents_saf_backend(self) -> None:
        self.assertIn("saf_backend", self.text)
        self.assertIn("MIT", self.text)
        self.assertIn("10.1016/j.neuroimage.2022.119423", self.text)

    def test_documents_pnlbwh_conversion_honestly(self) -> None:
        self.assertIn("pnlbwh/conversion", self.text)
        self.assertIn("parcellation/conversion", self.text)
        # Must not claim a specific license for this code: it is not
        # recorded anywhere in this repository.
        self.assertIn("not recorded", self.text.lower())

    def test_documents_freesurfer_color_lut(self) -> None:
        self.assertIn("FreeSurferColorLUT.txt", self.text)
        self.assertIn("FreeSurfer", self.text)

    def test_does_not_assert_the_unverified_ddsurfer_doi_as_fact(self) -> None:
        # The DOI may be *mentioned* while explaining why it was not
        # recorded, but this file must not present it as a confirmed fact.
        self.assertIn("does not appear anywhere in this repository", self.text)


class LicensesDirectoryTest(unittest.TestCase):
    def test_apache_license_text_is_present_and_genuine(self) -> None:
        path = REPO_ROOT / "licenses" / "Apache-2.0.txt"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("Apache License", text)
        self.assertIn("Version 2.0, January 2004", text)
        self.assertIn("TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION", text)
        # A genuine copy of the license is long; a stub/placeholder would not be.
        self.assertGreater(len(text.splitlines()), 100)

    def test_fastsurfer_notice_lists_every_derived_file(self) -> None:
        path = REPO_ROOT / "licenses" / "NOTICE-FastSurfer.txt"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        for derived_file in (
            "parcellation/models/losses.py",
            "parcellation/models/networks.py",
            "parcellation/models/solver.py",
            "parcellation/models/sub_module.py",
            "parcellation/data_loader/augmentation.py",
            "parcellation/data_loader/conform.py",
            "parcellation/data_loader/load_neuroimaging_data.py",
        ):
            self.assertIn(derived_file, text)
            # Every listed file must actually carry the header this notice
            # reproduces, so the notice cannot silently drift from the code.
            header = (REPO_ROOT / derived_file).read_text(encoding="utf-8")
            self.assertIn("Licensed under the Apache License, Version 2.0", header)


class CMakePackagingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (REPO_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

    def test_saf_backend_license_is_packaged(self) -> None:
        self.assertIn("tractography/saf_backend/LICENSE.md", self.text)

    def test_third_party_notices_and_licenses_directory_are_packaged(self) -> None:
        self.assertIn("THIRD_PARTY_NOTICES.md", self.text)
        self.assertIn('file(GLOB LICENSE_FILES "licenses/*")', self.text)
        self.assertIn("${LICENSE_FILES}", self.text)


class CitationCffTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (REPO_ROOT / "CITATION.cff").read_text(encoding="utf-8")

    def test_has_a_references_section_with_ddsurfer(self) -> None:
        self.assertIn("references:", self.text)
        self.assertIn("DDSurfer", self.text)

    def test_does_not_assert_the_unverified_doi(self) -> None:
        # The brief that prompted this file's update proposed
        # doi 10.1002/advs.76596 for the DDSurfer paper; that DOI does not
        # appear anywhere in this repository's own README/docs, so it must
        # not be recorded as a `doi:` field (a bare mention while explaining
        # the omission, as in the TODO comment, is fine).
        self.assertNotIn("doi: 10.1002/advs.76596", self.text)
        self.assertNotIn('doi: "10.1002/advs.76596"', self.text)

    def test_has_a_todo_for_the_unverified_doi(self) -> None:
        self.assertIn("TODO", self.text)

    def test_notes_that_ddparcel_and_ddseg_also_need_citation(self) -> None:
        self.assertIn("DDParcel", self.text)
        self.assertIn("DDSeg", self.text)


if __name__ == "__main__":
    unittest.main()
