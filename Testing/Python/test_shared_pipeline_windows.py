from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import shared.pipeline as pipeline


class SharedPipelineWindowsCompatibilityTest(unittest.TestCase):
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
