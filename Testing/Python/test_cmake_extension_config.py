from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _cmake_executable() -> str | None:
    configured = os.environ.get("CMAKE_EXECUTABLE", "").strip()
    if configured and Path(configured).is_file():
        return configured
    return shutil.which("cmake")


class CMakeExtensionConfigTest(unittest.TestCase):
    def test_extension_configures_with_slicer_cmake_contract(self) -> None:
        cmake = _cmake_executable()
        if not cmake:
            self.skipTest("CMake is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk = root / "mock-slicer-sdk"
            sdk.mkdir()
            (sdk / "SlicerConfig.cmake").write_text(
                "\n".join(
                    (
                        'set(Slicer_USE_FILE "${CMAKE_CURRENT_LIST_DIR}/SlicerUse.cmake")',
                        'set(Slicer_EXTENSION_CPACK "${CMAKE_CURRENT_LIST_DIR}/SlicerExtensionCPack.cmake")',
                        'set(Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR "lib/Slicer-5.10/qt-scripted-modules")',
                        "",
                    )
                ),
                encoding="utf-8",
            )
            (sdk / "SlicerUse.cmake").write_text(
                "\n".join(
                    (
                        "include(CMakeParseArguments)",
                        "macro(slicerMacroBuildScriptedModule)",
                        '  cmake_parse_arguments(SM "WITH_GENERIC_TESTS" "NAME" "SCRIPTS;RESOURCES" ${ARGN})',
                        '  if(NOT SM_NAME OR NOT SM_SCRIPTS)',
                        '    message(FATAL_ERROR "Invalid scripted module declaration")',
                        "  endif()",
                        '  file(WRITE "${CMAKE_BINARY_DIR}/scripted-module.txt" "${SM_NAME}\\n${SM_SCRIPTS}\\n")',
                        "endmacro()",
                        "function(slicer_add_python_unittest)",
                        "endfunction()",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            (sdk / "SlicerExtensionCPack.cmake").write_text(
                'file(WRITE "${CMAKE_BINARY_DIR}/extension-cpack.txt" "${PROJECT_NAME}\\n${EXTENSION_DEPENDS}\\n")\n',
                encoding="utf-8",
            )
            build = root / "build"
            completed = subprocess.run(
                [
                    cmake,
                    "-S",
                    REPO_ROOT.as_posix(),
                    "-B",
                    build.as_posix(),
                    f"-DSlicer_DIR={sdk.as_posix()}",
                    "-DBUILD_TESTING=ON",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            module_contract = (build / "scripted-module.txt").read_text(encoding="utf-8")
            package_contract = (build / "extension-cpack.txt").read_text(encoding="utf-8")
            self.assertIn("SlicerDDSurfer", module_contract)
            self.assertIn("SlicerDDSurfer.py", module_contract)
            self.assertIn("SlicerDDSurfer", package_contract)
            self.assertIn("SlicerDMRI", package_contract)
            self.assertIn("PyTorch", package_contract)


if __name__ == "__main__":
    unittest.main()
