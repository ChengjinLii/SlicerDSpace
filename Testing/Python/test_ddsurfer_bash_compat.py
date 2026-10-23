"""DDSurfer shell scripts run under bash 3.2, the stock macOS /bin/bash (macOS F2, F6)."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "anatomy/surface/ddsurfer_backend"
BASH = Path("/bin/bash")
# C8: constructs that bash 3.2 (stock macOS /bin/bash) does not parse or run.
BASH4_ONLY = re.compile(
    r"\b(?:mapfile|readarray)\b"                     # builtins new in bash 4.0
    r"|\b(?:declare|local|typeset)\s+-[a-zA-Z]*[An]\b"  # associative arrays, namerefs
    r"|\$\{[A-Za-z_]\w*(?:,,?|\^\^?)[^}]*\}"        # case conversion ${v,,} ${v^^} ${v,} ${v^}
    r"|\[\[\s+-v\s"                                  # [[ -v var ]]
    r"|\$\{[A-Za-z_]\w*\[-\d+\]\}"                  # negative array index
    r"|;;&|;&"                                       # case fall-through terminators
    r"|\|&|&>>"                                      # |& and &>> redirections
    r"|\bwait\s+-n\b|\bcoproc\b",
    re.MULTILINE,
)


class Bash32CompatibilityTests(unittest.TestCase):
    def test_no_bash4_constructs_in_backend_scripts(self) -> None:
        scripts = sorted(BACKEND.rglob("*.sh"))
        self.assertTrue(scripts)
        for script in scripts:
            with self.subTest(script=script.name):
                self.assertIsNone(BASH4_ONLY.search(script.read_text(encoding="utf-8")))

    def test_c8_detector_flags_bash4_constructs_and_accepts_bash3_ones(self) -> None:
        flagged = [
            'mapfile -t lines < f', 'x=$(foo); readarray -t a < f', 'declare -A m', 'declare -n ref=v', 'local -n ref=v',
            'echo "${v,,}"', 'echo "${v^^}"', 'echo "${v,}"', 'echo "${v^}"', '[[ -v NAME ]] && true',
            'echo "${a[-1]}"', 'case $x in a) y;& b) z;; esac', 'case $x in a) y;;& esac',
            'cmd |& tee log', 'cmd &>> log', 'wait -n', 'coproc FOO { sleep 1; }',
        ]
        for text in flagged:
            with self.subTest(text=text):
                self.assertIsNotNone(BASH4_ONLY.search(text))
        accepted = [
            'RAW_FILES=()', 'declare -a list', 'local count=0', 'echo "${ARGS[@]+"${ARGS[@]}"}"', 'echo "${a[0]}"',
            'v=${x:-default}', 'cmd >> log 2>&1', 'cmd > log 2>&1', 'case $x in a) y;; esac', 'wait', '[[ -n "$v" ]]',
            'echo "${v%%.*}"', 'echo "${v#*,}"',
        ]
        for text in accepted:
            with self.subTest(text=text):
                self.assertIsNone(BASH4_ONLY.search(text))

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


    @unittest.skipUnless(BASH.exists(), "/bin/bash is missing")
    def test_wrapper_with_no_arguments_does_not_trip_nounset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "python-stub"
            stub.write_text('#!/bin/sh\necho "argc=$#"\n', encoding="utf-8")
            stub.chmod(0o755)
            env = {**os.environ, "PYTHON_BIN": str(stub)}
            result = subprocess.run(
                [str(BASH), str(BACKEND / "run_ddsurfer_pipeline.sh")],
                capture_output=True, text=True, env=env, check=False,
            )
        self.assertNotIn("unbound variable", result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "argc=1")


if __name__ == "__main__":
    unittest.main()
