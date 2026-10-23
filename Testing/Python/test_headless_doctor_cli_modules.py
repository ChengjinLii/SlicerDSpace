"""The headless environment doctor checks the SlicerDMRI CLIs like the GUI doctor does (macOS F4)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from shared import run_subject_pipeline_cli as cli
from shared.environment import DependencySpec, EnvironmentDoctorConfig, run_environment_doctor


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
