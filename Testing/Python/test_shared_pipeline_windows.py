from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import shared.pipeline as pipeline


class SharedPipelineWindowsCompatibilityTest(unittest.TestCase):
    def test_macos_app_root_and_launcher_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "Slicer.app"
            home = app / "Contents"
            (home / "lib/Slicer-5.10").mkdir(parents=True)
            (home / "MacOS").mkdir()
            (home / "bin").mkdir()
            (home / "MacOS/Slicer").touch()
            (home / "bin/PythonSlicer").touch()
            fake = SimpleNamespace(app=SimpleNamespace(slicerHome=str(app)))
            with patch.object(pipeline, "SLICER_IMPORT_ERROR", None), patch.object(pipeline, "slicer", fake):
                self.assertEqual(pipeline._resolve_slicer_home(), home)
                self.assertEqual(Path(pipeline.resolve_launcher_executable()), home / "MacOS/Slicer")
                self.assertEqual(Path(pipeline.resolve_pythonslicer_executable()), home / "bin/PythonSlicer")

    def test_cli_library_variable_matches_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "cli-modules/CLI"
            executable.parent.mkdir()
            for platform, variable in (("win32", "PATH"), ("darwin", "DYLD_LIBRARY_PATH"), ("linux", "LD_LIBRARY_PATH")):
                with self.subTest(platform=platform), patch.object(sys, "platform", platform):
                    env = pipeline.build_cli_environment(str(executable))
                    self.assertIn(str(executable.parent), env[variable])

    def test_cli_in_an_additional_factory_search_path_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'home'
            extra = Path(tmp) / 'external-cli'
            home.mkdir()
            extra.mkdir()
            executable = extra / 'DWIToDTIEstimation'
            executable.touch()
            factory = SimpleNamespace(searchPaths=[str(extra)])
            app = SimpleNamespace(moduleManager=lambda: SimpleNamespace(factoryManager=lambda: factory))
            pipeline._cli_search_dirs.cache_clear()
            try:
                with patch.object(pipeline, 'SLICER_IMPORT_ERROR', None), \
                     patch.object(pipeline, 'slicer', SimpleNamespace(modules=SimpleNamespace(), app=app)), \
                     patch.object(pipeline, '_resolve_slicer_home', return_value=home):
                    self.assertEqual(Path(pipeline.resolve_cli_executable('dwitodtiestimation')), executable)
            finally:
                pipeline._cli_search_dirs.cache_clear()

    def test_cli_fallback_selects_exe_and_not_xml_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cli_dir = Path(tmp)
            (cli_dir / "DWIToDTIEstimation.xml").write_text("<executable />", encoding="utf-8")
            executable = cli_dir / "DWIToDTIEstimation.exe"
            executable.write_bytes(b"")
            with (
                patch.object(pipeline, "SLICER_IMPORT_ERROR", None),
                patch.object(pipeline, "slicer", SimpleNamespace(modules=SimpleNamespace())),
                patch.object(pipeline, "_cli_search_dirs", return_value=(cli_dir,)),
            ):
                self.assertEqual(Path(pipeline.resolve_cli_executable("DWIToDTIEstimation")), executable)

    def test_windows_launcher_fallbacks_accept_exe_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            slicer_home = Path(tmp)
            slicer_launcher = slicer_home / "Slicer.exe"
            python_slicer = slicer_home / "bin" / "PythonSlicer.exe"
            python_slicer.parent.mkdir(parents=True)
            slicer_launcher.write_bytes(b"")
            python_slicer.write_bytes(b"")
            with (
                patch.object(pipeline, "SLICER_IMPORT_ERROR", None),
                patch.object(pipeline, "slicer", SimpleNamespace()),
                patch.object(pipeline, "_resolve_slicer_home", return_value=slicer_home),
            ):
                self.assertEqual(Path(pipeline.resolve_launcher_executable()), slicer_launcher)
                self.assertEqual(Path(pipeline.resolve_pythonslicer_executable()), python_slicer)


if __name__ == "__main__":
    unittest.main()
