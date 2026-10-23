"""Headless CLI lookup finds SlicerDMRI in a stock macOS Slicer.app (macOS F3)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import shared.pipeline as pipeline


def _make_cli(extensions_root: Path, extension: str = "SlicerDMRI") -> Path:
    cli_dir = extensions_root / extension / "lib/Slicer-5.10/cli-modules"
    cli_dir.mkdir(parents=True)
    executable = cli_dir / "DWIToDTIEstimation"
    executable.touch()
    return executable


class CliSearchDirsMacosTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        self.home = self.tmp / "Slicer.app/Contents"
        (self.home / "lib/Slicer-5.10/cli-modules").mkdir(parents=True)
        pipeline._cli_search_dirs.cache_clear()
        self.addCleanup(pipeline._cli_search_dirs.cache_clear)

    def search_dirs(self, platform: str = "darwin") -> tuple[Path, ...]:
        # Headless PythonSlicer has no ``slicer.app``.
        with patch.object(pipeline, "SLICER_IMPORT_ERROR", None), \
             patch.object(pipeline, "slicer", SimpleNamespace(modules=SimpleNamespace())), \
             patch.object(pipeline, "_resolve_slicer_home", return_value=self.home), \
             patch.object(sys, "platform", platform), \
             patch.dict(os.environ, {"HOME": str(self.tmp / "user")}):
            pipeline._cli_search_dirs.cache_clear()
            return pipeline._cli_search_dirs()

    def test_extensions_inside_the_app_bundle_are_searched(self) -> None:
        executable = _make_cli(self.home / "Extensions-34645")
        dirs = self.search_dirs()
        self.assertIn(executable.parent, dirs)
        self.assertEqual(dirs[0], self.home / "lib/Slicer-5.10/cli-modules")

    def test_user_installed_extensions_are_searched_on_macos(self) -> None:
        executable = _make_cli(self.tmp / "user/Library/Application Support/slicer.org/Extensions-34645")
        self.assertIn(executable.parent, self.search_dirs("darwin"))
        self.assertNotIn(executable.parent, self.search_dirs("linux"))

    def test_c1_user_extensions_must_match_the_running_slicer_version(self) -> None:
        # Review C1: the lexical sort could pick a Slicer 5.6/5.10 CLI for a 5.12 runtime.
        self.home = self.tmp / "Slicer512.app/Contents"
        (self.home / "lib/Slicer-5.12/cli-modules").mkdir(parents=True)
        user = self.tmp / "user/Library/Application Support/slicer.org"
        old = self._cli(user / "Extensions-31938", "5.6")
        ten = self._cli(user / "Extensions-9000", "5.10")
        new = self._cli(user / "Extensions-34645", "5.12")
        newer = self._cli(user / "Extensions-35000", "5.12")
        dirs = self.search_dirs()
        self.assertNotIn(old.parent, dirs)
        self.assertNotIn(ten.parent, dirs)
        self.assertEqual(dirs[1:], (newer.parent.resolve(), new.parent.resolve()))

    def test_c1_user_extensions_for_other_versions_only_give_no_cli(self) -> None:
        self.home = self.tmp / "Slicer512.app/Contents"
        (self.home / "lib/Slicer-5.12/cli-modules").mkdir(parents=True)
        old = self._cli(self.tmp / "user/Library/Application Support/slicer.org/Extensions-31938", "5.6")
        dirs = self.search_dirs()
        self.assertNotIn(old.parent, dirs)
        self.assertEqual(dirs, (self.home / "lib/Slicer-5.12/cli-modules",))

    @staticmethod
    def _cli(extensions_root: Path, version: str) -> Path:
        cli_dir = extensions_root / "SlicerDMRI" / f"lib/Slicer-{version}/cli-modules"
        cli_dir.mkdir(parents=True)
        executable = cli_dir / "DWIToDTIEstimation"
        executable.touch()
        return executable

    def test_existing_extension_layout_keeps_priority(self) -> None:
        legacy = _make_cli(self.home / "slicer.org/Extensions-34645", "Legacy")
        bundled = _make_cli(self.home / "Extensions-34645")
        dirs = self.search_dirs()
        self.assertLess(dirs.index(legacy.parent), dirs.index(bundled.parent))


if __name__ == "__main__":
    unittest.main()
