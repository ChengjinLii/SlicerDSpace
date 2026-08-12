from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "install_dependencies.py"


def _load_install_dependencies_module():
    spec = importlib.util.spec_from_file_location("install_dependencies", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class InstallDependenciesProfileTest(unittest.TestCase):
    def test_named_profiles_are_exposed_by_parser(self) -> None:
        module = _load_install_dependencies_module()
        parser = module.build_parser()

        args = parser.parse_args(["--profile", "core", "--platform", "Linux"])

        self.assertEqual(args.profile, "core")
        self.assertIn("core", module.DEPENDENCY_PROFILES)
        self.assertIn("segmentation", module.DEPENDENCY_PROFILES["core"])
        self.assertIn("bundles", module.DEPENDENCY_PROFILES)
        self.assertIn("full", module.DEPENDENCY_PROFILES)

    def test_all_and_profile_conflict_is_documented_by_main(self) -> None:
        module = _load_install_dependencies_module()
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            module.main(["--all", "--profile", "core"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("Use either --all or --profile, not both.", stderr.getvalue())

    def test_offline_wheelhouse_options_are_forwarded_to_pip(self) -> None:
        module = _load_install_dependencies_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheelhouse = root / "wheelhouse"
            wheelhouse.mkdir()
            completed = subprocess.CompletedProcess([], 0, stdout="ok\n", stderr="")
            with mock.patch.object(module.subprocess, "run", return_value=completed) as run:
                results = module._install_python_packages(
                    "PythonSlicer.exe",
                    ("scikit-learn",),
                    root / "report",
                    pip_find_links=wheelhouse,
                    pip_no_index=True,
                )

            command = run.call_args.args[0]
            self.assertIn("--no-index", command)
            self.assertEqual(command[command.index("--find-links") + 1], wheelhouse.resolve().as_posix())
            self.assertEqual(command[-1], "scikit-learn")
            self.assertEqual(results[0].status, "passed")

    def test_macos_wrapper_generates_a_darwin_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "macos-plan"
            environment = os.environ.copy()
            environment["PYTHON_BIN"] = sys.executable
            completed = subprocess.run(
                [
                    "bash",
                    (REPO_ROOT / "scripts" / "install_deps_macos.sh").as_posix(),
                    "--output-dir",
                    output_dir.as_posix(),
                    "--tractography-backend",
                    "dti_det",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env=environment,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["environment"]["platform"], "Darwin")
            self.assertEqual(payload["environment"]["host_platform"], platform.system())
            self.assertTrue((output_dir / "dependency_profile.json").is_file())


if __name__ == "__main__":
    unittest.main()
