"""The headless environment doctor checks the SlicerDMRI CLIs like the GUI doctor does (macOS F4)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from shared import run_subject_pipeline_cli as cli
import shared.pipeline as pipeline
from shared.environment import DependencySpec, EnvironmentDoctorConfig, _slicer_cli_statuses, run_environment_doctor


def _native_spec(targets=("microstructure",)) -> DependencySpec:
    return DependencySpec(key="python:slicer.util", kind="python", label="slicer.util", required=True, targets=targets)


def _available(spec: DependencySpec):
    return SimpleNamespace(
        key=spec.key, kind=spec.kind, label=spec.label, status="available", required=True,
        targets=spec.targets, details={}, install_group="slicer-runtime", install_hint="")


def _doctor(config: EnvironmentDoctorConfig, finder):
    spec = _native_spec()
    with patch("shared.environment.build_dependency_specs", return_value=(spec,)), \
         patch("shared.environment._check_spec", return_value=_available(spec)), \
         patch("shared.pipeline.resolve_cli_executable", side_effect=finder):
        return run_environment_doctor(config)


class HeadlessDoctorCliModuleTests(unittest.TestCase):
    config = EnvironmentDoctorConfig(
        targets=("microstructure",), repo_root=Path("."), check_slicer_cli_modules=True)

    def test_missing_cli_modules_are_blockers(self) -> None:
        def missing(name):
            raise RuntimeError(f"Required CLI module is not available: {name}")

        report = _doctor(self.config, missing)
        statuses = {item.key: item for item in report.statuses}
        for key in ("slicer_cli:dwitodtiestimation", "slicer_cli:diffusiontensorscalarmeasurements"):
            self.assertEqual(statuses[key].status, "missing", key)
            self.assertTrue(statuses[key].required)
            self.assertEqual(statuses[key].targets, ("microstructure",))
            self.assertTrue(statuses[key].install_hint)
        self.assertEqual(report.blocker_count, 2)

    def test_found_cli_modules_are_available(self) -> None:
        report = _doctor(self.config, lambda name: f"/slicer/cli-modules/{name}")
        statuses = {item.key: item for item in report.statuses}
        self.assertEqual(statuses["slicer_cli:dwitodtiestimation"].status, "available")
        self.assertEqual(statuses["slicer_cli:dwitodtiestimation"].details["path"], "/slicer/cli-modules/DWIToDTIEstimation")
        self.assertEqual(report.blocker_count, 0)

    def test_c2_cli_search_runs_in_the_selected_interpreter(self) -> None:
        selected = Path(tempfile.gettempdir()) / "selected-venv" / "bin" / "python"
        payload = {"DWIToDTIEstimation": ["/selected/cli/DWIToDTIEstimation", ""],
                   "DiffusionTensorScalarMeasurements": ["", "not in the selected runtime"]}
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

        def caller_runtime(name):
            raise AssertionError("the caller's runtime must not be searched")

        config = EnvironmentDoctorConfig(targets=("microstructure",), repo_root=Path("."),
                                         check_slicer_cli_modules=True, python_executable=selected)
        with patch("shared.environment.subprocess.run", side_effect=fake_run):
            report = _doctor(config, caller_runtime)
        statuses = {item.key: item for item in report.statuses}
        self.assertEqual(calls[0][0], selected.as_posix())
        self.assertEqual(statuses["slicer_cli:dwitodtiestimation"].details["path"], "/selected/cli/DWIToDTIEstimation")
        self.assertEqual(statuses["slicer_cli:dwitodtiestimation"].status, "available")
        self.assertEqual(statuses["slicer_cli:diffusiontensorscalarmeasurements"].status, "missing")

    def test_c2_same_interpreter_keeps_the_in_process_search(self) -> None:
        config = EnvironmentDoctorConfig(targets=("microstructure",), repo_root=Path("."),
                                         check_slicer_cli_modules=True, python_executable=Path(sys.executable))
        with patch("shared.environment.subprocess.run", side_effect=AssertionError("no subprocess")):
            report = _doctor(config, lambda name: f"/in-process/{name}")
        statuses = {item.key: item for item in report.statuses}
        self.assertEqual(statuses["slicer_cli:dwitodtiestimation"].details["path"], "/in-process/DWIToDTIEstimation")

    def test_c7_unreadable_cli_folder_gives_a_status_not_a_traceback(self) -> None:
        class Unreadable:
            def iterdir(self):
                raise PermissionError(13, "Permission denied")

        with patch.object(pipeline, "SLICER_IMPORT_ERROR", None), \
             patch.object(pipeline, "slicer", SimpleNamespace(modules=SimpleNamespace())), \
             patch.object(pipeline, "_cli_search_dirs", return_value=(Unreadable(),)):
            statuses = _slicer_cli_statuses(("microstructure",))
        self.assertEqual({item.status for item in statuses}, {"missing"})
        self.assertIn("Permission denied", statuses[0].details["error"])

    def test_default_config_and_gui_check_are_unchanged(self) -> None:
        def unexpected(name):
            raise AssertionError("CLI search must not run")

        plain = EnvironmentDoctorConfig(targets=("microstructure",), repo_root=Path("."))
        self.assertEqual(_doctor(plain, unexpected).blocker_count, 0)
        gui = EnvironmentDoctorConfig(targets=("microstructure",), repo_root=Path("."), loaded_slicer_modules=())
        report = _doctor(gui, unexpected)
        self.assertEqual([item.key for item in report.statuses][-1], "slicer_module:dwitodtiestimation")

    def test_cli_doctor_config_enables_the_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = cli.build_parser().parse_args(["--subject-root", str(Path(tmp) / "sub-01"), "--no-user-config"])
            config = cli._environment_config_from_args(args, targets=("microstructure",), output_root=None)
        self.assertTrue(config.check_slicer_cli_modules)


if __name__ == "__main__":
    unittest.main()
