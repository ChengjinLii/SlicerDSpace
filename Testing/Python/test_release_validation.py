#!/usr/bin/env python3
"""Tests for the release validation runner."""

from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace


class ReleaseValidationTest(unittest.TestCase):
    def test_build_validation_steps_cover_release_evidence_chain(self) -> None:
        from scripts.release_validation import build_validation_steps

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            subject_root = root / "subject"
            batch_root = root / "batch"
            subject_root.mkdir()
            batch_root.mkdir()
            args = SimpleNamespace(
                subject_root=subject_root,
                subject_id="sub-01",
                output_root=root / "outputs",
                batch_root=batch_root,
                report_dir=root / "report",
                run_name="Test1",
                execute=False,
                dependency_config=root / "deps.json",
                jobs=2,
                arrange_inputs="symlink",
                tractography_backend="csd_act",
                connectome_backend="python",
                skip_slicer_smoke=True,
                skip_asset_checks=False,
                asset_mirror_dir=root / "core_mirror",
                all_asset_mirror_dir=root / "all_mirror",
                run_fresh_clone_smoke=True,
                fresh_clone_asset_profile="core",
                slicer_launcher=Path("/missing/Slicer"),
                xvfb_run=Path("/missing/xvfb-run"),
            )

            steps = build_validation_steps(args, ["--skip-environment-check"])

            names = [step.name for step in steps]
            self.assertIn("single_subject_all_backends", names)
            self.assertIn("batch_validation", names)
            self.assertIn("bundle_backend_wmql", names)
            self.assertIn("bundle_backend_wma", names)
            self.assertIn("bundle_backend_tractcloud", names)
            self.assertIn("output_tree_html", names)
            self.assertIn("repository_release_audit", names)
            self.assertIn("model_assets_core_verify", names)
            self.assertIn("model_assets_all_verify", names)
            self.assertIn("asset_mirror_core_verify", names)
            self.assertIn("asset_mirror_all_verify", names)
            self.assertIn("fresh_clone_smoke", names)
            self.assertIn("slicer_extension_install_smoke", names)
            self.assertIn("slicer_extension_manager_install_smoke", names)
            self.assertIn("slicer_dependency_workflow_smoke", names)
            self.assertIn("slicer_demo_workflow_smoke", names)
            self.assertIn("slicer_environment_button_smoke", names)
            self.assertIn("slicer_run_plan_panel_smoke", names)
            self.assertIn("slicer_output_tree_button_smoke", names)
            self.assertIn("slicer_cancel_background_smoke", names)
            single_command = next(step.command for step in steps if step.name == "single_subject_all_backends")
            self.assertIn("--bundle-backend", single_command)
            self.assertIn("all", single_command)
            self.assertIn("--plan", single_command)
            batch_command = next(step.command for step in steps if step.name == "batch_validation")
            self.assertIn("--jobs", batch_command)
            self.assertIn("2", batch_command)
            self.assertIn("--dependency-config", batch_command)
            slicer_smokes = [
                step
                for step in steps
                if step.name
                in {
                    "slicer_extension_install_smoke",
                    "slicer_extension_manager_install_smoke",
                    "slicer_dependency_workflow_smoke",
                    "slicer_demo_workflow_smoke",
                    "slicer_environment_button_smoke",
                    "slicer_run_plan_panel_smoke",
                    "slicer_output_tree_button_smoke",
                    "slicer_cancel_background_smoke",
                }
            ]
            self.assertEqual(len(slicer_smokes), 8)
            self.assertTrue(all(step.skipped for step in slicer_smokes))
            core_assets = next(step.command for step in steps if step.name == "model_assets_core_verify")
            self.assertIn("--profile", core_assets)
            self.assertIn("core", core_assets)
            core_mirror = next(step.command for step in steps if step.name == "asset_mirror_core_verify")
            self.assertIn("--repo-root", core_mirror)
            self.assertIn("--asset-root", core_mirror)
            self.assertEqual(core_mirror[core_mirror.index("--asset-root") + 1], (root / "core_mirror").as_posix())
            self.assertIn("--manifest", core_mirror)
            fresh_clone = next(step.command for step in steps if step.name == "fresh_clone_smoke")
            self.assertEqual(fresh_clone[0], "env")
            self.assertIn("SMOKE_ASSET_PROFILE=core", fresh_clone)
            self.assertIn("SMOKE_ASSET_MODE=download", fresh_clone)

    def test_slicer_smoke_step_uses_staged_module_env_and_disable_cli(self) -> None:
        from scripts.release_validation import build_validation_steps

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject_root = root / "subject"
            subject_root.mkdir()
            launcher = root / "Slicer"
            xvfb_run = root / "xvfb-run"
            launcher.write_text("#!/usr/bin/env sh\n", encoding="utf-8")
            xvfb_run.write_text("#!/usr/bin/env sh\n", encoding="utf-8")
            args = SimpleNamespace(
                subject_root=subject_root,
                subject_id="sub-01",
                output_root=root / "outputs",
                batch_root=None,
                report_dir=root / "report",
                run_name="Test1",
                execute=False,
                dependency_config=None,
                jobs=1,
                arrange_inputs="none",
                tractography_backend="csd_act",
                connectome_backend="python",
                skip_slicer_smoke=False,
                skip_asset_checks=True,
                asset_mirror_dir=None,
                all_asset_mirror_dir=None,
                run_fresh_clone_smoke=False,
                fresh_clone_asset_profile="core",
                slicer_launcher=launcher,
                xvfb_run=xvfb_run,
            )

            steps = build_validation_steps(args, [])

            stage = next(step for step in steps if step.name == "stage_slicer_extension")
            self.assertIn("--link-mode", stage.command)
            self.assertIn("copy", stage.command)
            self.assertIn("cmake_extension_config_contract", [step.name for step in steps])
            package = next(step for step in steps if step.name == "package_slicer_extension")
            self.assertIn("package_slicer_extension.py", " ".join(package.command))
            self.assertIn("SlicerDSpace.tar.gz", " ".join(package.command))
            slicer_smoke = next(step for step in steps if step.name == "slicer_extension_install_smoke")
            self.assertFalse(slicer_smoke.skipped)
            self.assertEqual(slicer_smoke.command[0], "env")
            self.assertTrue(
                any(part.startswith("SLICERDSPACE_EXTENSION_MODULE_DIR=") for part in slicer_smoke.command)
            )
            self.assertTrue(any(part.startswith("SLICERDSPACE_SMOKE_SUBJECT_ROOT=") for part in slicer_smoke.command))
            self.assertTrue(any(part.startswith("SLICERDSPACE_SMOKE_SUBJECT_ID=sub-01") for part in slicer_smoke.command))
            self.assertIn("SLICERDSPACE_SMOKE_MICROSTRUCTURE_STAGES=dti", slicer_smoke.command)
            self.assertIn("SLICERDSPACE_SMOKE_PLAN_ONLY=1", slicer_smoke.command)
            self.assertIn("SLICERDSPACE_DEMO_EXPECT_NODE_TYPE=model", slicer_smoke.command)
            self.assertTrue(any(part.startswith("PATH=") for part in slicer_smoke.command))
            self.assertIn("--disable-cli-modules", slicer_smoke.command)
            planned_smoke_names = [step.name for step in steps if step.name.endswith("_smoke")]
            self.assertIn("slicer_environment_button_smoke", planned_smoke_names)
            self.assertIn("slicer_extension_manager_install_smoke", planned_smoke_names)
            self.assertIn("slicer_dependency_workflow_smoke", planned_smoke_names)
            self.assertIn("slicer_demo_workflow_smoke", planned_smoke_names)
            self.assertIn("slicer_run_plan_panel_smoke", planned_smoke_names)
            self.assertIn("slicer_output_tree_button_smoke", planned_smoke_names)
            self.assertIn("slicer_cancel_background_smoke", planned_smoke_names)

    def test_completion_audit_reports_passed_when_all_release_evidence_passes(self) -> None:
        from scripts.release_validation import build_completion_audit

        args = SimpleNamespace(execute=False, fresh_clone_asset_profile="core")
        results = [
            {"name": "repository_release_audit", "status": "passed", "required": False},
            {"name": "model_assets_core_verify", "status": "passed", "required": False},
            {"name": "model_assets_all_verify", "status": "passed", "required": False},
            {"name": "asset_mirror_core_verify", "status": "passed", "required": False},
            {"name": "asset_mirror_all_verify", "status": "passed", "required": False},
            {"name": "stage_slicer_extension", "status": "passed", "required": False},
            {"name": "cmake_extension_config_contract", "status": "passed", "required": False},
            {"name": "package_slicer_extension", "status": "passed", "required": False},
            {"name": "slicer_extension_install_smoke", "status": "passed", "required": False},
            {"name": "slicer_extension_manager_install_smoke", "status": "passed", "required": False},
            {"name": "slicer_dependency_workflow_smoke", "status": "passed", "required": False},
            {"name": "slicer_demo_workflow_smoke", "status": "passed", "required": False},
            {"name": "slicer_environment_button_smoke", "status": "passed", "required": False},
            {"name": "slicer_run_plan_panel_smoke", "status": "passed", "required": False},
            {"name": "slicer_output_tree_button_smoke", "status": "passed", "required": False},
            {"name": "slicer_cancel_background_smoke", "status": "passed", "required": False},
            {"name": "single_subject_all_backends", "status": "passed", "required": True},
            {"name": "bundle_backend_wmql", "status": "passed", "required": False},
            {"name": "bundle_backend_wma", "status": "passed", "required": False},
            {"name": "bundle_backend_tractcloud", "status": "passed", "required": False},
            {"name": "output_tree_html", "status": "passed", "required": False},
            {"name": "representative_outputs", "status": "passed", "required": False},
            {"name": "fresh_clone_smoke", "status": "passed", "required": False},
        ]

        audit = build_completion_audit(args, results)

        self.assertEqual(audit["overall_status"], "passed")
        self.assertEqual(audit["code_and_model_asset_boundary"]["status"], "documented")
        statuses = {item["requirement"]: item["status"] for item in audit["coverage"]}
        self.assertEqual(statuses["local_release_regression"], "passed")
        self.assertEqual(statuses["slicer_gui_smoke"], "passed")
        self.assertEqual(statuses["scientific_workflow_smoke"], "passed")
        self.assertEqual(statuses["fresh_clone_release_smoke"], "passed")

    def test_completion_audit_reports_incomplete_when_optional_evidence_is_skipped(self) -> None:
        from scripts.release_validation import build_completion_audit

        args = SimpleNamespace(execute=False, fresh_clone_asset_profile="core")
        results = [
            {"name": "repository_release_audit", "status": "passed", "required": False},
            {"name": "model_assets_core_verify", "status": "passed", "required": False},
            {"name": "model_assets_all_verify", "status": "passed", "required": False},
            {"name": "asset_mirror_core_verify", "status": "skipped", "required": False, "reason": "not provided"},
            {"name": "asset_mirror_all_verify", "status": "skipped", "required": False, "reason": "not provided"},
            {"name": "stage_slicer_extension", "status": "skipped", "required": False, "reason": "skipped"},
            {"name": "cmake_extension_config_contract", "status": "skipped", "required": False, "reason": "skipped"},
            {"name": "package_slicer_extension", "status": "skipped", "required": False, "reason": "skipped"},
            {"name": "slicer_extension_install_smoke", "status": "skipped", "required": False, "reason": "skipped"},
            {"name": "slicer_extension_manager_install_smoke", "status": "skipped", "required": False, "reason": "skipped"},
            {"name": "slicer_dependency_workflow_smoke", "status": "skipped", "required": False, "reason": "skipped"},
            {"name": "slicer_demo_workflow_smoke", "status": "skipped", "required": False, "reason": "skipped"},
            {"name": "slicer_environment_button_smoke", "status": "skipped", "required": False, "reason": "skipped"},
            {"name": "slicer_run_plan_panel_smoke", "status": "skipped", "required": False, "reason": "skipped"},
            {"name": "slicer_output_tree_button_smoke", "status": "skipped", "required": False, "reason": "skipped"},
            {"name": "slicer_cancel_background_smoke", "status": "skipped", "required": False, "reason": "skipped"},
            {"name": "single_subject_all_backends", "status": "passed", "required": True},
            {"name": "bundle_backend_wmql", "status": "passed", "required": False},
            {"name": "bundle_backend_wma", "status": "passed", "required": False},
            {"name": "bundle_backend_tractcloud", "status": "passed", "required": False},
            {"name": "output_tree_html", "status": "passed", "required": False},
            {"name": "representative_outputs", "status": "passed", "required": False},
            {"name": "fresh_clone_smoke", "status": "skipped", "required": False, "reason": "skipped"},
        ]

        audit = build_completion_audit(args, results)

        self.assertEqual(audit["overall_status"], "incomplete")
        statuses = {item["requirement"]: item["status"] for item in audit["coverage"]}
        self.assertEqual(statuses["local_release_regression"], "skipped")
        self.assertEqual(statuses["slicer_gui_smoke"], "skipped")
        self.assertEqual(statuses["fresh_clone_release_smoke"], "skipped")

    def test_completion_audit_treats_intentionally_skipped_slicer_smoke_as_skipped(self) -> None:
        from scripts.release_validation import build_completion_audit

        args = SimpleNamespace(execute=False, fresh_clone_asset_profile="core")
        results = [
            {"name": "repository_release_audit", "status": "passed", "required": False},
            {"name": "model_assets_core_verify", "status": "passed", "required": False},
            {"name": "model_assets_all_verify", "status": "passed", "required": False},
            {"name": "asset_mirror_core_verify", "status": "passed", "required": False},
            {"name": "asset_mirror_all_verify", "status": "passed", "required": False},
            {
                "name": "slicer_extension_install_smoke",
                "status": "skipped",
                "required": False,
                "reason": "--skip-slicer-smoke",
            },
            {"name": "single_subject_all_backends", "status": "passed", "required": True},
            {"name": "bundle_backend_wmql", "status": "passed", "required": False},
            {"name": "bundle_backend_wma", "status": "passed", "required": False},
            {"name": "bundle_backend_tractcloud", "status": "passed", "required": False},
            {"name": "output_tree_html", "status": "passed", "required": False},
            {"name": "representative_outputs", "status": "passed", "required": False},
            {"name": "fresh_clone_smoke", "status": "passed", "required": False},
        ]

        audit = build_completion_audit(args, results)

        statuses = {item["requirement"]: item["status"] for item in audit["coverage"]}
        self.assertEqual(statuses["slicer_gui_smoke"], "skipped")

    def test_run_step_records_timeout_bytes_without_crashing(self) -> None:
        import subprocess

        from scripts import release_validation

        def raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=["slow"], timeout=1, output=b"partial out", stderr=b"partial err")

        with tempfile.TemporaryDirectory() as tmp, mock.patch("scripts.release_validation.subprocess.run", raise_timeout):
            report_dir = Path(tmp)
            result = release_validation._run_step(
                release_validation.ValidationStep("slow_step", ("slow",), required=False),
                report_dir,
                timeout_seconds=1,
            )

            self.assertEqual(result["status"], "failed")
            self.assertIn("timed out", result["error"])
            self.assertEqual((report_dir / "logs" / "slow_step.stdout.log").read_text(encoding="utf-8"), "partial out")
            self.assertEqual((report_dir / "logs" / "slow_step.stderr.log").read_text(encoding="utf-8"), "partial err")

    def test_run_step_replaces_invalid_utf8_without_crashing(self) -> None:
        import subprocess

        from scripts import release_validation

        completed = subprocess.CompletedProcess(
            args=["mixed-output"],
            returncode=0,
            stdout=b"valid\ninvalid:\xe5\n",
            stderr=b"warning:\xff\n",
        )
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "scripts.release_validation.subprocess.run", return_value=completed
        ):
            report_dir = Path(tmp)
            result = release_validation._run_step(
                release_validation.ValidationStep("mixed_output", ("mixed-output",), required=False),
                report_dir,
                timeout_seconds=1,
            )

            stdout = (report_dir / "logs" / "mixed_output.stdout.log").read_text(encoding="utf-8")
            stderr = (report_dir / "logs" / "mixed_output.stderr.log").read_text(encoding="utf-8")
            self.assertEqual(result["status"], "passed")
            self.assertIn("invalid:\ufffd", stdout)
            self.assertIn("warning:\ufffd", stderr)


if __name__ == "__main__":
    unittest.main()
