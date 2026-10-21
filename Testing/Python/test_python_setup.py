"""Native packaging capability detection, compatibility and restart guards."""

import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from shared import python_setup as setup
from shared.ui_selected_setup import python_setup_commands


class PythonSetupTests(unittest.TestCase):
    def test_fresh_external_python_can_use_pips_vendored_parser(self):
        with patch.dict("sys.modules", {"packaging": None, "packaging.requirements": None}):
            invalid, requirement, canonicalize = setup._packaging_api()
            self.assertEqual(requirement("numpy>=1").name, "numpy")
            self.assertEqual(canonicalize("Simple_ITK"), "simple-itk")

    def test_installed_requirements_do_not_invoke_an_installer(self):
        with patch.object(setup, "requirement_satisfied", return_value=True), \
                patch.object(setup.subprocess, "run") as run:
            self.assertEqual(setup.install_requirements(("numpy>=1",))["backend"], "already_satisfied")
        run.assert_not_called()

    def test_native_api_is_used_only_when_present(self):
        native = SimpleNamespace(pip_ensure=Mock())
        versions = {"numpy": "1.26.4", "vtk": "9.5.2"}
        with patch.object(setup, "installed_versions", return_value=versions), \
                patch.object(setup, "requirement_satisfied", side_effect=(False, True)), \
                patch.object(setup.importlib, "import_module", return_value=native):
            record = setup.install_requirements(("nibabel>=5",))
            kwargs = native.pip_ensure.call_args.kwargs
            self.assertFalse(kwargs["prompt_install"])
            self.assertFalse(kwargs["prompt_restart"])
        self.assertEqual(record["backend"], "slicer.packaging")

    def test_old_slicer_worker_protects_existing_core_versions(self):
        calls = []
        def run(argv, **kwargs):
            constraints = Path(argv[argv.index("--constraint") + 1]).read_text()
            self.assertIn("numpy==1.26.4", constraints)
            self.assertIn("torch==2.5.1+cu121", constraints)
            self.assertIn("--", argv)
            calls.append(argv)
        unavailable = ModuleNotFoundError("No native packaging", name="slicer.packaging")
        with patch.object(setup, "installed_versions", return_value={"numpy": "1.26.4", "torch": "2.5.1+cu121"}), \
                patch.object(setup, "requirement_satisfied", side_effect=(False, True)), \
                patch.object(setup.importlib, "import_module", side_effect=unavailable), \
                patch.object(setup.subprocess, "run", side_effect=run):
            record = setup.install_requirements(("nibabel>=5",))
        self.assertEqual(record["backend"], "python_subprocess_compatibility")
        self.assertEqual(len(calls), 1)

    def test_loaded_package_updates_require_restart(self):
        self.assertEqual(setup.restart_packages({"numpy": "1"}, {"numpy": "2"}, ("NumPy",)), ["numpy"])
        self.assertEqual(setup.restart_packages({"numpy": "1"}, {"numpy": "2"}, ("other",)), [])

    def test_native_api_failure_is_not_hidden_by_fallback(self):
        with patch.object(setup, "requirement_satisfied", return_value=False), \
                patch.object(setup.importlib, "import_module", side_effect=RuntimeError("broken native API")), \
                patch.object(setup.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "broken native"):
                setup.install_requirements(("nibabel",))
        run.assert_not_called()

    def test_missing_torchvision_uses_official_helper_even_if_torch_exists(self):
        installed = {"torch>=2.0.0"}
        logic = Mock()
        def install(**kwargs):
            installed.add("torchvision")
            return object()
        logic.installTorch.side_effect = install
        helper = SimpleNamespace(PyTorchUtilsLogic=lambda: logic)
        with patch.dict("sys.modules", {"PyTorchUtils": helper}), \
                patch.object(setup, "requirement_satisfied", side_effect=lambda value: value in installed), \
                patch.object(setup.subprocess, "run") as pip:
            result = setup.install_requirements(("torchvision",), torch_minimum="2.0.0", torchvision_required=True)
        logic.installTorch.assert_called_once_with(askConfirmation=False, torchVersionRequirement=">=2.0.0")
        self.assertEqual(result["backend"], "PyTorch_extension")
        pip.assert_not_called()

    def test_requests_keep_different_python_environments_separate(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"PYTHONHOME": "/Slicer/runtime"}):
            owner = SimpleNamespace(_latestEnvironmentReportDir=temp,
                _lastEnvironmentResult=SimpleNamespace(statuses=(SimpleNamespace(kind="python", details={
                    "package": "numpy", "python_executable": "/external/python"}),)),
                _setup_python_command=lambda python: (python, []) if python else ("Slicer", ["--launch", "PythonSlicer"]))
            commands, receipts = python_setup_commands(owner, ("numpy", "nibabel"))
            self.assertEqual(len(commands), 2)
            first = json.loads(Path(commands[0][1][commands[0][1].index("--request") + 1]).read_text())
            second = json.loads(Path(commands[1][1][commands[1][1].index("--request") + 1]).read_text())
            self.assertFalse(first["protect_bundled"])
            self.assertTrue(second["protect_bundled"])
            self.assertNotEqual(receipts[0], receipts[1])
            self.assertIsNone(commands[0][2]["PYTHONHOME"])
            self.assertNotIn("PYTHONHOME", commands[1][2])


if __name__ == "__main__":
    unittest.main()
