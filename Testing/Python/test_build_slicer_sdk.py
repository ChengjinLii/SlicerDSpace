"""Negative-path SDK harness tests; mock configuration is never build evidence."""

import argparse
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_slicer_sdk import build


ROOT = Path(__file__).resolve().parents[2]


class SlicerSdkHarnessTest(unittest.TestCase):
    def test_python_zero_test_suite_prevents_packaging_even_with_ctest_exit_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / 'mock-sdk-not-release-evidence'
            sdk.mkdir()
            (sdk / 'SlicerConfig.cmake').write_text('# Unit-test fixture only\n')
            output = root / 'build'
            detail = output / 'Testing/Temporary/LastTest.log'
            detail.parent.mkdir(parents=True)
            detail.write_text('Ran 0 tests in 0.000s\n\nNO TESTS RAN\n')
            args = argparse.Namespace(source_root=ROOT, build_dir=output, slicer_dir=sdk,
                                      cmake='cmake', ctest='ctest', cpack='cpack', jobs=1,
                                      timeout=10, package_generator='TGZ')
            with patch('scripts.build_slicer_sdk.platform.platform', return_value='unit-test fixture'), \
                    patch('scripts.build_slicer_sdk.subprocess.check_output', side_effect=['fixture', b'fixture']), \
                    patch('scripts.build_slicer_sdk.subprocess.run',
                          return_value=subprocess.CompletedProcess([], 0)) as runner:
                result = build(args)
            self.assertEqual(result['status'], 'fail')
            self.assertIn('zero-test', result['error'])
            self.assertEqual(runner.call_count, 3)
            self.assertEqual(result['packages'], [])

    def test_ctest_failure_prevents_packaging_and_zero_tests_are_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "mock-sdk-not-release-evidence"
            sdk.mkdir()
            (sdk / "SlicerConfig.cmake").write_text("# Unit-test fixture only\n", encoding="utf-8")
            args = argparse.Namespace(source_root=ROOT, build_dir=root / "build", slicer_dir=sdk,
                                      cmake="cmake", ctest="ctest", cpack="cpack", jobs=1,
                                      timeout=10, package_generator="TGZ")
            results = [subprocess.CompletedProcess([], code) for code in (0, 0, 8)]
            with patch("scripts.build_slicer_sdk.platform.platform", return_value="unit-test fixture"), \
                    patch("scripts.build_slicer_sdk.subprocess.check_output", side_effect=["fixture-commit", b"fixture-diff"]), \
                    patch("scripts.build_slicer_sdk.subprocess.run", side_effect=results) as runner:
                result = build(args)
            self.assertEqual(result["status"], "fail")
            self.assertEqual([step["name"] for step in result["steps"]], ["configure", "build", "ctest"])
            self.assertIn("--no-tests=error", runner.call_args_list[-1].args[0])
            self.assertEqual(result["packages"], [])
            self.assertEqual(result["clean_install_test"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
