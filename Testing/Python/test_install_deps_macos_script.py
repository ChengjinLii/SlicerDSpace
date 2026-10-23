"""scripts/install_deps_macos.sh finds PythonSlicer in a stock Slicer.app (macOS F5)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/install_deps_macos.sh"
BASH = Path("/bin/bash")


def _executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


@unittest.skipUnless(BASH.exists(), "/bin/bash is missing")
class InstallDepsMacosScriptTests(unittest.TestCase):
    def run_script(self, *pythonslicer_dirs: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            shutil.copy(SCRIPT, scripts / SCRIPT.name)
            (scripts / "install_dependencies.py").write_text("print('fallback python3')\n", encoding="utf-8")
            contents = root / "Slicer.app/Contents"
            _executable(contents / "MacOS/Slicer", "#!/bin/sh\n")
            for directory in pythonslicer_dirs:
                _executable(contents / directory / "PythonSlicer", f"#!/bin/sh\necho PythonSlicer-from-{directory}\n")
            env = {key: value for key, value in os.environ.items() if key != "PYTHON_BIN"}
            env["SLICER_EXECUTABLE"] = str(contents / "MacOS/Slicer")
            result = subprocess.run(
                [str(BASH), str(scripts / SCRIPT.name)], capture_output=True, text=True, env=env, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()

    def test_pythonslicer_in_contents_bin_is_used(self) -> None:
        self.assertEqual(self.run_script("bin"), "PythonSlicer-from-bin")

    def test_pythonslicer_next_to_the_launcher_is_still_used(self) -> None:
        self.assertEqual(self.run_script("MacOS"), "PythonSlicer-from-MacOS")

    def test_contents_bin_wins_over_the_launcher_directory(self) -> None:
        self.assertEqual(self.run_script("bin", "MacOS"), "PythonSlicer-from-bin")


if __name__ == "__main__":
    unittest.main()
