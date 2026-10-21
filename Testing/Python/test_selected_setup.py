"""Selected-route planning, phase orchestration and honest readiness states."""

from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

from shared.selected_setup import build_setup_plan
from shared.ui_selected_setup import extension_states, prepare_selected_environment
from shared.environment import DependencySpec, EnvironmentDoctorConfig, run_environment_doctor


def item(key, group="python", kind="python", targets=("validation",), package="numpy>=1", required=True):
    return SimpleNamespace(key=key, label=key, install_group=group, kind=kind, targets=targets,
                           required=required, status="missing", install_hint="Review " + key,
                           details={"package": package} if package else {})


def result(*items, targets=("validation",), blockers=None):
    return SimpleNamespace(statuses=items, targets=targets,
                           blocker_count=len(items) if blockers is None else blockers)


class SelectedSetupTests(unittest.TestCase):
    def test_importable_slicer_is_not_proof_that_native_dti_module_is_loaded(self):
        spec = DependencySpec(key='python:slicer.util', kind='python', label='slicer.util', required=True,
                              targets=('microstructure',))
        checked = SimpleNamespace(key=spec.key, kind='python', label=spec.label, status='available', required=True,
                                  targets=spec.targets, details={}, install_group='slicer-runtime', install_hint='')
        with patch('shared.environment.build_dependency_specs', return_value=(spec,)), \
                patch('shared.environment._check_spec', return_value=checked):
            config = EnvironmentDoctorConfig(targets=('microstructure',), repo_root=Path('.'), loaded_slicer_modules=())
            report = run_environment_doctor(config)
            self.assertEqual(report.blocker_count, 1)
            self.assertEqual(report.statuses[-1].key, 'slicer_module:dwitodtiestimation')
            from dataclasses import replace
            report = run_environment_doctor(replace(config, loaded_slicer_modules=('dwitodtiestimation',)))
            self.assertEqual(report.blocker_count, 0)
    def test_slicer_510_installed_is_not_loaded_and_nonexposed_api_is_not_called(self):
        manager = Mock(spec=('isExtensionInstalled', 'isExtensionEnabled'))
        manager.isExtensionInstalled.side_effect = lambda name: name in ('SlicerDMRI', 'PyTorch')
        manager.isExtensionEnabled.return_value = True
        with patch('importlib.util.find_spec', return_value=None):
            installed, loaded = extension_states(manager, SimpleNamespace())
        self.assertEqual(installed, ['SlicerDMRI', 'PyTorch'])
        self.assertEqual(loaded, [])
        plan = build_setup_plan(result(), need_dti=True, installed_extensions=installed, loaded_extensions=loaded)
        self.assertEqual(plan['restart_extensions'], ['SlicerDMRI'])
        with patch('importlib.util.find_spec', return_value=object()):
            _, loaded = extension_states(manager, SimpleNamespace(dwitodtiestimation=object()))
        self.assertEqual(loaded, ['SlicerDMRI', 'PyTorch'])

    def test_empty_or_ready_routes_do_not_install_unselected_backends(self):
        plan = build_setup_plan(result(), installed_extensions=("SlicerDMRI", "PyTorch"), need_dti=True,
                                system="Linux", machine="x86_64")
        for key in ("extensions", "python_packages", "asset_profiles", "managed_profiles", "manual_items"):
            self.assertEqual(plan[key], [], key)

    def test_only_missing_required_selected_items_are_included(self):
        plan = build_setup_plan(result(item("mrconvert", "mrtrix", "command", package=None),
                                       item("eddy", "fsl", "command", package=None),
                                       item("brain_mask_backend", "brain_mask", "setting", package=None),
                                       item("weights", "model-resources", "path", ("segmentation",), None),
                                       item("unused", "wma", "command", package=None, required=False)),
                                gpu_available=True, need_dti=True, need_torch=True,
                                system="Linux", machine="x86_64")
        self.assertEqual(plan["managed_profiles"], ["mrtrix", "fsl_cuda", "pnl_cnn"])
        self.assertEqual(plan["asset_profiles"], ["segmentation"])
        self.assertEqual(plan["extensions"], ["SlicerDMRI", "PyTorch"])
        self.assertTrue(plan["fsl_license_required"] and plan["pnl_terms_required"])
        self.assertEqual(plan["manual_items"], [])

    def test_ukf_is_optional_and_platform_limits_remain_visible(self):
        missing = result(item("brain_mask_backend", "brain_mask", "setting", package=None))
        plan = build_setup_plan(missing, need_ukf=True, system="Windows", machine="AMD64")
        self.assertEqual(plan["extensions"], ["SlicerDMRI", "UKFTractography"])
        self.assertEqual(plan["managed_profiles"], [])
        self.assertEqual(plan["unsupported_profiles"], ["pnl_cnn"])
        self.assertEqual(plan["manual_items"][0]["key"], "brain_mask_backend")

    def test_existing_managed_tools_are_verified_even_without_missing_items(self):
        plan = build_setup_plan(result(), existing_managed_profiles=("mrtrix",), repair=True,
                                system="Linux", machine="x86_64")
        self.assertEqual(plan["managed_profiles"], ["mrtrix"])
        self.assertTrue(plan["repair"])

    def owner(self, report):
        owner = Mock()
        owner._setupJob = owner._pipelineActive = owner._selectedSetupActive = owner._setupRestartRequired = False
        owner._parameterNode = SimpleNamespace(brainMaskBackend="provided")
        owner._onboardingLanguage = "en"
        owner._run_environment_dependency_check.return_value = report
        owner._tractography_backend_text.return_value = "csd_act"
        return owner

    def run_preparation(self, owner, report, *, manager=None, confirm=True):
        manager = manager or Mock()
        manager.isExtensionInstalled.return_value = True
        slicer = SimpleNamespace(app=SimpleNamespace(extensionsManagerModel=lambda: manager),
                                 modules=SimpleNamespace(), util=SimpleNamespace(infoDisplay=Mock()))
        return patch.dict("sys.modules", {"slicer": slicer}), manager

    def test_cancelled_confirmation_has_no_install_or_settings_side_effect(self):
        owner = self.owner(result(item("missing")))
        context, manager = self.run_preparation(owner, owner._run_environment_dependency_check.return_value)
        with context, patch("shared.ui_selected_setup._confirm", return_value=False):
            self.assertFalse(prepare_selected_environment(owner))
        manager.installExtensionFromServer.assert_not_called()
        owner._install_python_packages_from_environment_dialog.assert_not_called()
        owner._save_environment_path_setting.assert_not_called()

    def test_python_models_and_runtime_phases_finish_with_a_fresh_check(self):
        initial = result(item("numpy"), item("weights", "model-resources", "path", ("segmentation",), None))
        owner = self.owner(result())
        owner._install_python_packages_from_environment_dialog.side_effect = lambda packages, on_complete: on_complete(True)
        owner._install_model_assets_from_environment_dialog.side_effect = lambda profile, on_complete: on_complete(True, "verified")
        context, _ = self.run_preparation(owner, initial)
        with tempfile.TemporaryDirectory() as temp, context, patch("shared.ui_selected_setup._confirm", return_value=True), \
                patch("shared.ui_environment_check.start_environment_check", side_effect=lambda widget, callback, **kwargs: callback(owner._run_environment_dependency_check()) or True), \
                patch("shared.user_config.default_user_config_path", return_value=Path(temp) / "config.json"):
            self.assertTrue(prepare_selected_environment(owner, initial))
            receipt = next(Path(temp).glob("setup-history/*/result.json"))
            self.assertEqual(json.loads(receipt.read_text())["status"], "ready")
        owner._install_model_assets_from_environment_dialog.assert_called_once()
        self.assertFalse(owner._selectedSetupActive)
        owner._run_environment_dependency_check.assert_called_once()

    def test_ready_environment_skips_confirmation_installation_and_redundant_check(self):
        report = result()
        owner = self.owner(report)
        context, manager = self.run_preparation(owner, report)
        with tempfile.TemporaryDirectory() as temp, context, patch("shared.ui_selected_setup._confirm") as confirm, \
                patch("shared.user_config.default_user_config_path", return_value=Path(temp) / "config.json"):
            self.assertTrue(prepare_selected_environment(owner, report))
            receipt = next(Path(temp).glob("setup-history/*/result.json"))
            self.assertEqual(json.loads(receipt.read_text())["status"], "ready")
            confirm.assert_not_called()
        manager.installExtensionFromServer.assert_not_called()
        owner._run_environment_dependency_check.assert_not_called()
        owner._install_python_packages_from_environment_dialog.assert_not_called()

    def test_failure_stops_the_chain_and_releases_preparation_lock(self):
        initial = result(item("numpy"))
        owner = self.owner(initial)
        owner._install_python_packages_from_environment_dialog.side_effect = lambda packages, on_complete: on_complete(False)
        context, _ = self.run_preparation(owner, initial)
        with tempfile.TemporaryDirectory() as temp, context, patch("shared.ui_selected_setup._confirm", return_value=True), \
                patch("shared.user_config.default_user_config_path", return_value=Path(temp) / "config.json"):
            prepare_selected_environment(owner, initial)
        self.assertFalse(owner._selectedSetupActive)
        owner._install_model_assets_from_environment_dialog.assert_not_called()
        self.assertEqual(owner._setStatus.call_args.args[0], "warning")

    def test_extension_install_requires_restart_not_false_readiness(self):
        owner = self.owner(result(targets=("microstructure",)))
        context, manager = self.run_preparation(owner, owner._run_environment_dependency_check.return_value)
        manager.isExtensionInstalled.return_value = False
        manager.installExtensionFromServer.return_value = True
        with tempfile.TemporaryDirectory() as temp, context, patch("shared.ui_selected_setup._confirm", return_value=True), \
                patch("shared.user_config.default_user_config_path", return_value=Path(temp) / "config.json"):
            prepare_selected_environment(owner)
        manager.installExtensionFromServer.assert_called_once_with("SlicerDMRI", False)
        self.assertTrue(owner._setupRestartRequired)
        self.assertFalse(owner._selectedSetupActive)
        owner._install_python_packages_from_environment_dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
