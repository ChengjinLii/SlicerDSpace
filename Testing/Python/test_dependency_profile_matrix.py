from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class DependencyProfileMatrixTest(unittest.TestCase):
    def test_matrix_script_writes_per_platform_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "matrix"
            completed = subprocess.run(
                [
                    sys.executable,
                    (REPO_ROOT / "scripts" / "dependency_profile_matrix.py").as_posix(),
                    "--output-dir",
                    output_dir.as_posix(),
                    "--platforms",
                    "Linux,Darwin,Windows",
                    "--targets",
                    "validation",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            matrix_path = Path(completed.stdout.strip())
            self.assertEqual(matrix_path, output_dir / "dependency_profile_matrix.json")
            payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "slicerddsurfer.dependency_profile_matrix.v1")
            self.assertEqual(payload["targets"], ["validation"])
            self.assertEqual([row["platform"] for row in payload["rows"]], ["Linux", "Darwin", "Windows"])
            self.assertTrue(payload["scan_policy"]["non_native_rows_are_dry_run"])
            for row in payload["rows"]:
                profile_path = Path(row["report_paths"]["profile"])
                report_path = Path(row["report_paths"]["json"])
                self.assertTrue(profile_path.is_file())
                self.assertTrue(report_path.is_file())
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                self.assertEqual(profile["platform"], row["platform"])
                self.assertEqual(profile["host_platform"], row["host_platform"])
                self.assertTrue(profile["portability_policy"]["revalidate_after_import"])


if __name__ == "__main__":
    unittest.main()
