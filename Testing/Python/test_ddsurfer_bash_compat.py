"""DDSurfer shell scripts run under bash 3.2, the stock macOS /bin/bash (macOS F2)."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "anatomy/surface/ddsurfer_backend"
BASH = Path("/bin/bash")
BASH4_ONLY = re.compile(r"^\s*(?:mapfile|readarray)\b|\bdeclare\s+-A\b", re.MULTILINE)


class Bash32CompatibilityTests(unittest.TestCase):
    def test_no_bash4_constructs_in_backend_scripts(self) -> None:
        scripts = sorted(BACKEND.rglob("*.sh"))
        self.assertTrue(scripts)
        for script in scripts:
            with self.subTest(script=script.name):
                self.assertIsNone(BASH4_ONLY.search(script.read_text(encoding="utf-8")))

    @unittest.skipUnless(BASH.exists(), "/bin/bash is missing")
    def test_dti_raw_path_parsing_keeps_paths_with_spaces(self) -> None:
        text = (BACKEND / "preprocessing/dti.sh").read_text(encoding="utf-8")
        match = re.search(r"^RAW_FILES=\(\)\n.*?done <<<\"\$RAW_PATHS\"\n", text, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(match, "RAW_FILES loop not found in dti.sh")
        paths = ["/data/my subject/dwi.nii.gz", "/data/my subject/bvals", "/data/my subject/bvecs", "/data/mask.nii.gz"]
        script = (
            "set -euo pipefail\nIFS=$'\\n\\t'\n"
            f"RAW_PATHS=$(printf '%s\\n' {' '.join(repr(path) for path in paths)})\n"
            f"{match.group(0)}"
            "printf '%s\\n' \"${#RAW_FILES[@]}\"\n"
            "printf '%s\\n' \"${RAW_FILES[@]}\"\n"
        )
        result = subprocess.run([str(BASH), "-c", script], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["4", *paths])


if __name__ == "__main__":
    unittest.main()
