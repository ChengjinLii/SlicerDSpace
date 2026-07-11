"""Validate an extension-like SlicerDDSurfer staged install in real Slicer."""

from __future__ import annotations

import os
from pathlib import Path

import qt
import slicer


MODULE_DIR = Path(os.environ.get("SLICERDDSURFER_EXTENSION_MODULE_DIR", ""))
FORBIDDEN_MODULES = (
    "workflow_catalog",
    "run_subject_pipeline",
    "release_audit",
    "generate_subject_report",
    "install_dependencies",
)


def _module_registered(name: str) -> bool:
    return hasattr(slicer.modules, name.lower())


def _maximum_block_count(widget) -> int:
    try:
        value = widget.maximumBlockCount()
        return int(value)
    except Exception:
        pass
    try:
        value = widget.document().maximumBlockCount()
        return int(value)
    except Exception:
        return 0


def _run() -> None:
    try:
        top_level_py = sorted(path.name for path in MODULE_DIR.glob("*.py")) if MODULE_DIR.is_dir() else []
        forbidden_registered = [name for name in FORBIDDEN_MODULES if _module_registered(name)]
        slicer.util.selectModule("SlicerDDSurfer")
        module = slicer.util.getModule("SlicerDDSurfer")
        target_registered = _module_registered("SlicerDDSurfer") or module is not None
        widget = module.widgetRepresentation().self()
        logic_ready = bool(getattr(widget, "logic", None))
        parameter_node_ready = bool(getattr(widget, "_parameterNode", None))
        run_panel_ready = bool(getattr(widget, "_runStatusPanel", None))
        env_paths_ready = bool(getattr(widget, "_environmentPathLineEdits", None))
        prepare_widgets = getattr(widget, "_prepareInputWidgets", {}) or {}
        prepare_required = {
            "source_kind",
            "source",
            "subject_root",
            "subject_id",
            "bval",
            "bvec",
            "metadata",
            "mask",
            "backend",
            "output_kind",
            "preview_button",
            "prepare_button",
            "manifest_button",
        }
        prepare_inputs_ready = prepare_required.issubset(set(prepare_widgets))
        model_assets_ready = all(
            bool(getattr(widget, name, None))
            for name in (
                "_modelAssetsSummaryLabel",
                "_modelAssetsCheckStatusButton",
                "_modelAssetsVerifyCoreButton",
                "_modelAssetsWriteLockfileButton",
            )
        )
        onboarding_widgets = getattr(widget, "_onboardingWidgets", {}) or {}
        onboarding_ready = all(
            key in onboarding_widgets
            for key in ("language_combo", "wizard_button", "demo_button", "diagnostic_button", "config_button", "dashboard")
        )
        language_switch_ready = False
        language_json_ready = False
        platform_examples_ready = False
        stateful_wizard_ready = False
        shared_targets_json_ready = False
        common_settings_auto_save_ready = False
        original_language_index = -1
        if onboarding_ready:
            combo = onboarding_widgets["language_combo"]
            original_language_index = int(combo.currentIndex)
            zh_index = combo.findData("zh")
            if zh_index >= 0:
                combo.setCurrentIndex(zh_index)
                slicer.app.processEvents()
                if parameter_node_ready:
                    widget._parameterNode.targetPreprocessing = True
                    widget._parameterNode.targetTractography = True
                    widget._save_common_user_settings()
                headline = getattr(widget.ui, "headlineLabel", None)
                headline_text = str(headline.text if headline else "")
                language_switch_ready = "运行工作台" in headline_text
                examples_label = onboarding_widgets.get("examples")
                examples_text = str(examples_label.text if examples_label else "")
                platform_examples_ready = "本机路径示例" in examples_text and "/home/name/data/sub-01" in examples_text
                try:
                    from shared.user_config import load_user_config

                    user_config = load_user_config()
                    language_json_ready = user_config["ui"]["language"] == "zh"
                    saved_targets = set(user_config["run_defaults"]["targets"])
                    shared_targets_json_ready = {"validation", "preprocessing", "tractography"}.issubset(
                        saved_targets
                    )
                except Exception:
                    language_json_ready = False
            def inspect_and_close_wizard() -> None:
                wizard_widgets = getattr(widget, "_firstRunWizardWidgets", {}) or {}
                wizard_dialog = wizard_widgets.get("dialog")
                if wizard_dialog:
                    wizard_dialog.accept()

            qt.QTimer.singleShot(250, inspect_and_close_wizard)
            widget._on_show_first_run_wizard_clicked()
            wizard_widgets = getattr(widget, "_firstRunWizardWidgets", {}) or {}
            stateful_wizard_ready = bool(
                wizard_widgets.get("dialog")
                and wizard_widgets.get("progress")
                and wizard_widgets.get("scroll")
                and len(tuple(wizard_widgets.get("status_labels", ()))) == 5
                and len(tuple(button for button in wizard_widgets.get("action_buttons", ()) if button)) == 5
            )
        if parameter_node_ready:
            widget._parameterNode.subjectId = "json-auto-save-smoke"
            widget._checkCanApply()
            wait_loop = qt.QEventLoop()
            qt.QTimer.singleShot(600, wait_loop.quit)
            wait_loop.exec_()
            try:
                from shared.user_config import load_user_config

                common_settings_auto_save_ready = (
                    load_user_config()["recent"]["subject_id"] == "json-auto-save-smoke"
                )
            except Exception:
                common_settings_auto_save_ready = False
        summary_label = getattr(widget, "_selectedProductsSummaryLabel", None)
        summary_text = ""
        if summary_label:
            summary_text_attr = getattr(summary_label, "text", "")
            summary_text = str(summary_text_attr() if callable(summary_text_attr) else summary_text_attr)
        selection_summary_ready = bool(summary_label and "Selected targets:" in summary_text)
        log_widget = getattr(widget.ui, "logPlainTextEdit", None)
        log_block_limit = _maximum_block_count(log_widget) if log_widget else 0
        configured_log_limit = int(getattr(widget, "_logLineLimit", 0) or 0)
        log_limit_ready = configured_log_limit == 4000
        environment_cache_ttl = float(getattr(widget, "_environmentCacheTtlSeconds", 0.0) or 0.0)
        environment_cache_ready = environment_cache_ttl > 0.0
        demo_ready = False
        demo_auto_dispatch_ready = False
        original_info_display = slicer.util.infoDisplay
        original_run_selected = widget._onRunSelectedClicked
        try:
            dispatched = []
            slicer.util.infoDisplay = lambda *args, **kwargs: None
            widget._onRunSelectedClicked = lambda: dispatched.append(True)
            widget._on_try_demo_clicked()
            slicer.app.processEvents()
            demo_root = Path(str(widget._parameterNode.inputDirectory))
            demo_ready = all(
                (demo_root / "input" / name).is_file()
                for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz")
            )
            demo_ready = demo_ready and widget._parameterNode.orchestrationTractographyBackend == "dti_det"
            demo_auto_dispatch_ready = bool(dispatched)
        finally:
            slicer.util.infoDisplay = original_info_display
            widget._onRunSelectedClicked = original_run_selected
        module_file = MODULE_DIR / "SlicerDDSurfer.py"
        module_file_is_symlink = module_file.is_symlink()
        print(f"SLICERDDSURFER_EXTENSION_MODULE_DIR={MODULE_DIR}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_TOP_LEVEL_PY={top_level_py}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_TARGET_REGISTERED={target_registered}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_FORBIDDEN_REGISTERED={forbidden_registered}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_MODULE_FILE_SYMLINK={module_file_is_symlink}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_LOGIC_READY={logic_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_PARAMETER_NODE_READY={parameter_node_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_RUN_PANEL_READY={run_panel_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_ENV_PATHS_READY={env_paths_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_PREPARE_INPUTS_READY={prepare_inputs_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_MODEL_ASSETS_READY={model_assets_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_ONBOARDING_READY={onboarding_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_LANGUAGE_SWITCH_READY={language_switch_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_LANGUAGE_JSON_READY={language_json_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_PLATFORM_EXAMPLES_READY={platform_examples_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_STATEFUL_WIZARD_READY={stateful_wizard_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_SHARED_TARGETS_JSON_READY={shared_targets_json_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_COMMON_SETTINGS_AUTO_SAVE_READY={common_settings_auto_save_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_SELECTION_SUMMARY_READY={selection_summary_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_LOG_BLOCK_LIMIT={log_block_limit}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_CONFIGURED_LOG_LIMIT={configured_log_limit}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_ENV_CACHE_TTL={environment_cache_ttl}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_DEMO_READY={demo_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_DEMO_AUTO_DISPATCH_READY={demo_auto_dispatch_ready}", flush=True)
        bad = (
            top_level_py != ["SlicerDDSurfer.py"]
            or not target_registered
            or forbidden_registered
            or module_file_is_symlink
            or not logic_ready
            or not parameter_node_ready
            or not run_panel_ready
            or not env_paths_ready
            or not prepare_inputs_ready
            or not model_assets_ready
            or not onboarding_ready
            or not language_switch_ready
            or not language_json_ready
            or not platform_examples_ready
            or not stateful_wizard_ready
            or not shared_targets_json_ready
            or not common_settings_auto_save_ready
            or not selection_summary_ready
            or not log_limit_ready
            or not environment_cache_ready
            or not demo_ready
            or not demo_auto_dispatch_ready
        )
        if onboarding_ready and original_language_index >= 0:
            onboarding_widgets["language_combo"].setCurrentIndex(original_language_index)
            slicer.app.processEvents()
        slicer.app.exit(2 if bad else 0)
    except Exception as exc:
        print(f"SLICERDDSURFER_EXTENSION_INSTALL_ERROR={exc}", flush=True)
        slicer.app.exit(2)


qt.QTimer.singleShot(6000, _run)
