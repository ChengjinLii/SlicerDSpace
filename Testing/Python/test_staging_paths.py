#!/usr/bin/env python3
"""Tests for shared/staging_paths.py's subject-id validation before rmtree."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.staging_paths import resolve_staging_subject_dir, validate_staging_subject_id


class ValidateStagingSubjectIdTest(unittest.TestCase):
    def test_accepts_typical_subject_ids(self) -> None:
        for subject_id in ("100307", "sub-01", "subject_01", "S1.2"):
            self.assertEqual(validate_staging_subject_id(subject_id), subject_id)

    def test_rejects_empty_string(self) -> None:
        with self.assertRaises(ValueError):
            validate_staging_subject_id("")

    def test_rejects_dot_and_dotdot(self) -> None:
        with self.assertRaises(ValueError):
            validate_staging_subject_id(".")
        with self.assertRaises(ValueError):
            validate_staging_subject_id("..")

    def test_rejects_path_separators(self) -> None:
        for subject_id in ("../escape", "a/b", "a\\b", "/etc/passwd", "..\\..\\escape"):
            with self.assertRaises(ValueError):
                validate_staging_subject_id(subject_id)

    def test_rejects_other_shell_or_glob_metacharacters(self) -> None:
        for subject_id in ("sub;rm -rf", "sub*", "sub?", "sub id", "sub\x00id"):
            with self.assertRaises(ValueError):
                validate_staging_subject_id(subject_id)


class ResolveStagingSubjectDirTest(unittest.TestCase):
    def test_returns_resolved_path_under_staging_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            staging_root = Path(tmp) / "staging"
            staging_root.mkdir()

            resolved = resolve_staging_subject_dir(staging_root, "100307")

            self.assertEqual(resolved, (staging_root / "100307").resolve())
            self.assertTrue(str(resolved).startswith(str(staging_root.resolve())))

    def test_rejects_traversal_subject_id_before_any_filesystem_access(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            staging_root = Path(tmp) / "staging"
            staging_root.mkdir()
            sibling = Path(tmp) / "sibling_should_survive"
            sibling.mkdir()
            (sibling / "keepme.txt").write_text("keep", encoding="utf-8")

            with self.assertRaises(ValueError):
                resolve_staging_subject_dir(staging_root, "..")

            with self.assertRaises(ValueError):
                resolve_staging_subject_dir(staging_root, "../sibling_should_survive")

            # Nothing outside staging_root was touched.
            self.assertTrue((sibling / "keepme.txt").is_file())

    def test_rejects_symlink_escape_even_when_name_passes_the_regex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            staging_root = Path(tmp) / "staging"
            staging_root.mkdir()
            outside_target = Path(tmp) / "outside"
            outside_target.mkdir()
            (outside_target / "keepme.txt").write_text("keep", encoding="utf-8")
            # A subject_id that passes the character allow-list, but whose
            # staging_root/subject_id path is itself a symlink pointing
            # outside staging_root.
            escape_link = staging_root / "100307"
            escape_link.symlink_to(outside_target, target_is_directory=True)

            with self.assertRaises(ValueError):
                resolve_staging_subject_dir(staging_root, "100307")

            self.assertTrue((outside_target / "keepme.txt").is_file())


if __name__ == "__main__":
    unittest.main()
