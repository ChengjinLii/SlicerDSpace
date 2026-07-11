"""Common scripted-module widget glue for SlicerDDSurfer."""

from __future__ import annotations

import importlib.util
import os
import json
import platform
import sys
from pathlib import Path
from datetime import datetime
from time import monotonic
from typing import Any, List, Optional

import qt
import slicer
import vtk
from qt import QPixmap, QSignalBlocker

from shared.dependency_config import UI_DEPENDENCY_PATHS
from shared.docs import doc_path
from shared.input_import import InputImportConfig, detect_import_source_kind, prepare_inputs
from shared.model_assets import model_asset_path
from shared.ui_error_dialogs import show_actionable_error_dialog
from shared.ui_environment_dialog import show_environment_results_dialog
from shared.ui_environment_paths import (
    add_environment_path_row,
    add_environment_section_header,
    add_environment_subsection_label,
    add_model_assets_row,
    install_environment_dependency_path_controls,
)
from shared.ui_environment_panel import (
    dependency_profile_payload,
    environment_detail_lines,
    environment_item_text,
    environment_missing_items,
    environment_path_status_from_dependencies,
    environment_path_status_style,
    environment_summary_text,
    external_dependencies_from_profile,
    format_detected_source,
    model_assets_provenance_text,
    optional_backend_label_styles,
    optional_backend_widget_style,
    path_status_dependencies,
    python_install_target_text,
)
from shared.ui_prepare_inputs import install_prepare_inputs_panel
from shared.ui_output_loading import qbytearray_to_text
from shared.ui_parameter_sync import sync_parameter_node_to_ui
from shared.ui_run_controller import (
    BackendSelection,
    ProductTargetFlags,
    RunSelection,
    active_bundle_backend_sections,
    build_background_cli_args,
    build_batch_run_kwargs,
    build_batch_background_cli_args,
    build_single_subject_run_kwargs,
    cancelled_manifest_path_and_payload,
    default_run_name_for_backend,
    extract_background_manifest_path,
    is_auto_generated_run_name,
    microstructure_stage_flags,
    blocked_plan_items,
    blocked_plan_log_text,
    environment_blockers_from_plan,
    partial_run_notice_text,
    preflight_blockers_for_targets,
    runnable_targets_from_plan,
    rows_from_batch_manifest,
    rows_from_plan,
    rows_from_result,
    rows_from_single_subject_manifest,
    run_summary_from_manifest,
    selected_environment_targets,
    selected_orchestrator_targets,
    selected_product_targets,
    selected_products_summary,
    selected_workflows,
    streamline_control_state,
    task_keys_for_running_line,
    validate_batch_run_options,
    validate_single_subject_inputs,
)
from shared.ui_settings import coerce_user_setting_value, common_user_setting_specs
from shared.ui_status_log import (
    append_log,
    apply_widget_styles,
    configure_log_widget,
    set_existing_report_path,
    set_run_progress_message,
    set_run_summary_message,
    set_status,
)
from shared.ui_background_process import build_background_run_context, qprocess_is_running
from shared.ui_run_status_panel import (
    install_run_status_panel,
    mark_unfinished_rows,
    set_run_status_table_rows,
    table_item,
    update_run_status_table_item,
)
from shared.ui_onboarding import (
    LANGUAGE_SETTING,
    apply_onboarding_language,
    capability_dashboard_text,
    diagnostic_report_text,
    install_onboarding_panel,
    maybe_show_first_run_wizard,
    normalized_language,
    prepare_demo_for_owner,
    show_first_run_wizard,
)
from shared.user_config import (
    default_user_config_path,
    load_user_config,
    update_user_config,
)


ENVIRONMENT_DEPENDENCY_PATHS = UI_DEPENDENCY_PATHS


class SharedWidgetMixin:
    """Shared UI helpers used across the unified SlicerDDSurfer widget."""

    def _connect_common_ui(self) -> None:
        if hasattr(self.ui, "runSelectedButton"):
            self.ui.runSelectedButton.connect("clicked()", self._onRunSelectedClicked)
        if hasattr(self.ui, "validateButton"):
            self.ui.validateButton.connect("clicked()", self._onValidateClicked)
        if hasattr(self.ui, "clearLogButton"):
            self.ui.clearLogButton.connect("clicked()", self._onClearLogClicked)
        if hasattr(self.ui, "unifiedTorchDeviceComboBox"):
            self.ui.unifiedTorchDeviceComboBox.currentTextChanged.connect(self._onUnifiedTorchDeviceChanged)
        if hasattr(self.ui, "orchestrationTractographyBackendComboBox"):
            self.ui.orchestrationTractographyBackendComboBox.currentTextChanged.connect(
                self._onTractographyBackendChanged
            )
        if hasattr(self.ui, "orchestrationBundleBackendComboBox"):
            self.ui.orchestrationBundleBackendComboBox.currentTextChanged.connect(
                self._onBundleBackendChanged
            )
        if hasattr(self.ui, "batchRootPath"):
            try:
                self.ui.batchRootPath.currentPathChanged.connect(self._onBatchRootPathChanged)
            except Exception:
                self.ui.batchRootPath.connect("currentPathChanged(QString)", self._onBatchRootPathChanged)

    def _initialize_common_ui_state(self) -> None:
        self._populateDeviceCombo()
        self._lastProcessEventsAt = 0.0
        self._logLineLimit = 4000
        self._autoLoadResultLimit = 12
        self._logAppendCount = 0
        self._environmentCacheTtlSeconds = 300.0
        self._lastEnvironmentSignature = None
        self._lastEnvironmentCheckedAt = 0.0
        if hasattr(self.ui, "subjectIdLineEdit"):
            self.ui.subjectIdLineEdit.setClearButtonEnabled(True)
        environment_hint = getattr(self.ui, "environmentHintLabel", None)
        if environment_hint:
            environment_hint.visible = False
        if hasattr(self.ui, "applyButton"):
            self.ui.applyButton.setAutoDefault(True)
            self.ui.applyButton.visible = False

        self._configure_workflow_shell()
        self._hide_legacy_product_panels()
        self._initialize_onboarding_panel()
        self._initialize_prepare_inputs_panel()
        self._initialize_environment_dependency_path_controls()
        self._initialize_product_selection_summary()
        self._initialize_run_status_panel()
        self._initialize_background_run_controls()
        self._apply_slicerddsurfer_ui_style()
        self._configure_log_widget()
        self._refresh_advanced_run_settings()

        for widget_name in (
            "surfaceOptionsSectionLabel",
            "predictModeLabel",
            "predictModeComboBox",
            "deviceLabel",
            "deviceComboBox",
            "cleanupLabel",
            "cleanupCheckBox",
        ):
            widget = getattr(self.ui, widget_name, None)
            if widget:
                widget.visible = False

        logo_label = getattr(self.ui, "logoLabel", None)
        if logo_label:
            logo_path = self.resourcePath("Icons/SlicerDDSurfer.png")
            if os.path.exists(logo_path):
                logo_label.setPixmap(QPixmap(logo_path))

        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        progress = getattr(self.ui, "statusProgressBar", None)
        if progress:
            progress.setRange(0, 100)
            progress.setValue(0)

        self._setStatus("waiting", "Waiting for input")
        self.initializeParameterNode()
        maybe_show_first_run_wizard(self)

    def _configure_workflow_shell(self) -> None:
        """Keep the top-level UI focused on input, products, and execution."""

        text_updates = {
            "environmentCollapsibleButton": "Advanced: Dependency profile",
            "configurationCollapsibleButton": "Run workflow",
            "advancedRunCollapsibleButton": "Advanced settings: backends, batch, streamlines",
            "runSelectedButton": "Preflight and run",
        }
        for widget_name, text in text_updates.items():
            widget = getattr(self.ui, widget_name, None)
            if widget:
                try:
                    widget.text = text
                except Exception:
                    try:
                        widget.setText(text)
                    except Exception:
                        pass
        label_updates = {
            "configurationSectionLabel": "<b>1. Choose input</b>",
            "targetsSectionLabel": "<b>2. Choose products</b>",
            "runStepSectionLabel": "<b>3. Run</b>",
        }
        for widget_name, text in label_updates.items():
            widget = getattr(self.ui, widget_name, None)
            if widget:
                widget.setText(text)
        for widget_name in ("environmentCollapsibleButton", "advancedRunCollapsibleButton"):
            widget = getattr(self.ui, widget_name, None)
            if widget:
                try:
                    widget.collapsed = True
                except Exception:
                    pass
        workflow = getattr(self.ui, "configurationCollapsibleButton", None)
        if workflow:
            try:
                workflow.collapsed = False
            except Exception:
                pass

    def _initialize_background_run_controls(self) -> None:
        if getattr(self, "_cancelRunButton", None) is not None:
            return
        actions_layout = getattr(self.ui, "selectedActionsLayout", None)
        if not actions_layout:
            return
        cancel_button = qt.QPushButton("Cancel running job")
        cancel_button.enabled = False
        cancel_button.setToolTip("Stop the background SlicerDDSurfer pipeline process and write a cancellation manifest.")
        cancel_button.setStyleSheet(
            "QPushButton { border: 1px solid #C62828; color: #C62828; border-radius: 6px; padding: 7px 14px; background: transparent; } "
            "QPushButton:hover:!disabled { background-color: rgba(198,40,40,0.1); }"
        )
        cancel_button.connect("clicked()", self._onCancelRunClicked)
        actions_layout.addWidget(cancel_button)
        self._cancelRunButton = cancel_button
        self._backgroundProcess = None
        self._backgroundOutputBuffer = ""
        self._backgroundManifestPath = None
        self._backgroundCancelRequested = False
        self._backgroundRunContext = {}

    def _hide_legacy_product_panels(self) -> None:
        """Hide old per-product forms; unified subject parameters now drive all runs."""
        for widget_name in (
            "dockerPostprocessCollapsibleButton",
            "ddparcelCollapsibleButton",
            "microstructureCollapsibleButton",
            "ddsegCollapsibleButton",
            "infoCollapsibleButton",
        ):
            widget = getattr(self.ui, widget_name, None)
            if widget:
                widget.visible = False

    def _environment_settings_key(self, dependency_id: str) -> str:
        return f"SlicerDDSurfer/ExternalDependencies/{dependency_id}"

    def _user_settings_key(self, name: str) -> str:
        return f"SlicerDDSurfer/UserSettings/{name}"

    def _common_user_setting_specs(self) -> tuple[tuple[str, type], ...]:
        return common_user_setting_specs()

    def _coerce_user_setting_value(self, value: Any, value_type: type) -> Any:
        return coerce_user_setting_value(value, value_type)

    def _restore_common_user_settings_to_node(self) -> None:
        node = self._parameterNode
        if not node:
            return
        settings = slicer.app.userSettings()
        config = None
        try:
            config_path = default_user_config_path().expanduser()
            if config_path.is_file():
                config = load_user_config(config_path)
                configured_dependencies = config.get("external_dependencies", {})
                for item in ENVIRONMENT_DEPENDENCY_PATHS:
                    dependency_id = item["id"]
                    value = configured_dependencies.get(dependency_id)
                    if value:
                        settings.setValue(self._environment_settings_key(dependency_id), value)
                    else:
                        settings.remove(self._environment_settings_key(dependency_id))
        except Exception as exc:
            self.appendLog(f"[Settings] Shared user config could not be restored: {exc}")
        with slicer.util.NodeModify(node):
            for attribute, value_type in self._common_user_setting_specs():
                key = self._user_settings_key(attribute)
                try:
                    has_key = bool(settings.contains(key))
                except Exception:
                    has_key = settings.value(key, None) is not None
                if not has_key:
                    continue
                try:
                    setattr(node, attribute, self._coerce_user_setting_value(settings.value(key), value_type))
                except Exception:
                    continue
        if config is not None:
            recent = config.get("recent", {})
            defaults = config.get("run_defaults", {})
            targets = set(defaults.get("targets", ()) or ())
            with slicer.util.NodeModify(node):
                node.subjectId = str(recent.get("subject_id") or node.subjectId or "")
                node.inputDirectory = str(recent.get("subject_root") or node.inputDirectory or "")
                node.outputDirectory = str(recent.get("output_root") or node.outputDirectory or "")
                node.orchestrationRunName = str(defaults.get("run_name") or node.orchestrationRunName or "Test1")
                node.preprocessingBackend = str(defaults.get("preprocessing_backend") or node.preprocessingBackend or "dipy")
                node.orchestrationTractographyBackend = str(
                    defaults.get("tractography_backend") or node.orchestrationTractographyBackend or "csd_act"
                )
                node.orchestrationBundleBackend = str(
                    defaults.get("bundle_backend") or node.orchestrationBundleBackend or "wmql"
                )
                stages = defaults.get("microstructure_stages") or ["dti"]
                node.orchestrationMicrostructureStages = ",".join(str(value) for value in stages)
                node.connectomeBackend = str(defaults.get("connectome_backend") or node.connectomeBackend or "python")
                node.orchestrationSelectStreamlines = int(
                    defaults.get("select_streamlines") or node.orchestrationSelectStreamlines or 100000
                )
                node.autoInstallPythonDependencies = bool(
                    defaults.get("auto_install_python_dependencies", node.autoInstallPythonDependencies)
                )
                if targets:
                    node.targetPreprocessing = "preprocessing" in targets
                    node.targetSurface = "surface" in targets
                    node.targetParcellation = "parcellation" in targets
                    node.targetSegmentation = "segmentation" in targets
                    node.targetMicrostructure = bool(
                        targets & {"microstructure", "microstructure_freewater", "microstructure_noddi"}
                    )
                    node.targetTractography = bool(targets & {"tractography", "saf"})
                    node.targetBundles = bool(targets & {"bundles", "wma", "tractcloud"})
                    node.targetConnectome = "connectome" in targets
        else:
            self._save_common_user_settings()

    def _save_common_user_settings(self) -> None:
        node = self._parameterNode
        if not node:
            return
        settings = slicer.app.userSettings()
        for attribute, _value_type in self._common_user_setting_specs():
            try:
                value = getattr(node, attribute)
            except Exception:
                continue
            settings.setValue(self._user_settings_key(attribute), value)
        targets = list(self._selected_product_targets())
        stages = [value.strip() for value in (node.orchestrationMicrostructureStages or "dti").split(",") if value.strip()]
        external_dependencies = {
            item["id"]: self._read_environment_path_setting(item["id"]) or None
            for item in ENVIRONMENT_DEPENDENCY_PATHS
        }
        try:
            _, path = update_user_config(
                {
                    "recent": {
                        "subject_id": node.subjectId or "",
                        "subject_root": node.inputDirectory or "",
                        "output_root": node.outputDirectory or "",
                    },
                    "run_defaults": {
                        "run_name": node.orchestrationRunName or "Test1",
                        "targets": targets,
                        "preprocessing_backend": node.preprocessingBackend or "dipy",
                        "tractography_backend": node.orchestrationTractographyBackend or "csd_act",
                        "bundle_backend": node.orchestrationBundleBackend or "wmql",
                        "microstructure_stages": stages or ["dti"],
                        "connectome_backend": node.connectomeBackend or "python",
                        "select_streamlines": int(node.orchestrationSelectStreamlines),
                        "auto_install_python_dependencies": bool(node.autoInstallPythonDependencies),
                    },
                    "external_dependencies": external_dependencies,
                }
            )
            self._sharedUserConfigPath = path
        except Exception as exc:
            self.appendLog(f"[Settings] Shared user config could not be saved: {exc}")

    def _schedule_common_user_settings_save(self) -> None:
        if not self._parameterNode:
            return
        timer = getattr(self, "_commonUserSettingsSaveTimer", None)
        if timer is None:
            timer = qt.QTimer(self.parent)
            timer.setSingleShot(True)
            timer.setInterval(350)
            timer.connect("timeout()", self._save_common_user_settings)
            self._commonUserSettingsSaveTimer = timer
        timer.start()

    def _save_python_install_status(self, packages: tuple[str, ...], status: str, detail: str = "") -> None:
        try:
            payload = {
                "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "packages": list(packages),
                "status": status,
                "detail": detail,
            }
            slicer.app.userSettings().setValue(
                self._user_settings_key("lastPythonInstall"),
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception:
            pass

    def _read_environment_path_setting(self, dependency_id: str) -> str:
        settings = slicer.app.userSettings()
        value = settings.value(self._environment_settings_key(dependency_id), "")
        return str(value or "").strip()

    def _save_environment_path_setting(self, dependency_id: str, value: str) -> None:
        settings = slicer.app.userSettings()
        clean_value = (value or "").strip()
        if clean_value:
            settings.setValue(self._environment_settings_key(dependency_id), clean_value)
        else:
            settings.remove(self._environment_settings_key(dependency_id))
        try:
            _, path = update_user_config(
                {"external_dependencies": {dependency_id: clean_value or None}}
            )
            self._sharedUserConfigPath = path
        except Exception as exc:
            self.appendLog(f"[Settings] Dependency path JSON could not be saved: {exc}")

    def _line_edit_text(self, line_edit) -> str:
        text_attr = getattr(line_edit, "text", "")
        return str(text_attr() if callable(text_attr) else text_attr).strip()

    def _show_actionable_error(
        self,
        *,
        title: str,
        what: str,
        why: str,
        next_step: str,
        auto_fix: str,
        details: object,
    ) -> None:
        actions = [
            ("Re-check environment", self._onValidateClicked),
            ("Open dependency guide", self._on_open_model_assets_guide_clicked),
        ]
        lower_title = title.lower()
        if "model asset" in lower_title or "model" in lower_title:
            actions.insert(0, ("Choose/download model assets", lambda: self._install_model_assets_from_environment_dialog(profile="core")))
            actions.append(("Open model asset folder", self._on_open_model_assets_root_clicked))
        show_actionable_error_dialog(
            parent=self.parent,
            title=title,
            what=what,
            why=why,
            next_step=next_step,
            auto_fix=auto_fix,
            details=details,
            actions=tuple(actions),
        )

    def _on_open_model_assets_root_clicked(self) -> None:
        try:
            module = self._load_model_assets_module()
            configured = self._environment_dependency_path_kwargs().get("model_assets_dir")
            asset_root = configured if isinstance(configured, Path) and str(configured) else module.configured_model_assets_root()
            self._open_local_path(Path(asset_root), missing_message="The configured model asset root does not exist yet.")
        except Exception as exc:
            slicer.util.infoDisplay(f"Model asset root is unavailable:\n{exc}", parent=self.parent)

    def _initialize_environment_dependency_path_controls(self) -> None:
        if getattr(self, "_environmentPathLineEdits", None) is not None:
            return
        environment_layout = getattr(self.ui, "environmentLayout", None)
        if not environment_layout:
            return
        install_environment_dependency_path_controls(self, environment_layout)

    def _initialize_prepare_inputs_panel(self) -> None:
        if getattr(self, "_prepareInputWidgets", None) is not None:
            return
        configuration_layout = getattr(self.ui, "configurationLayout", None)
        if not configuration_layout:
            return
        install_prepare_inputs_panel(self, configuration_layout)

    def _initialize_onboarding_panel(self) -> None:
        if getattr(self, "_onboardingWidgets", None) is not None:
            return
        configuration_layout = getattr(self.ui, "configurationLayout", None)
        if not configuration_layout:
            return
        install_onboarding_panel(self, configuration_layout)
        settings = slicer.app.userSettings()
        try:
            config = load_user_config()
            self._sharedUserConfigPath = default_user_config_path()
            configured_language = config.get("ui", {}).get("language")
        except Exception:
            configured_language = None
        language = normalized_language(str(configured_language or settings.value(LANGUAGE_SETTING, "en") or "en"))
        self._onboardingLanguage = language
        apply_onboarding_language(self, language)

    def _on_onboarding_language_changed(self, *args) -> None:
        combo = (getattr(self, "_onboardingWidgets", {}) or {}).get("language_combo")
        language = "en"
        if combo:
            try:
                language = str(combo.itemData(combo.currentIndex) or "en")
            except Exception:
                language = str(getattr(combo, "currentText", "English") or "English")
        language = normalized_language(language)
        self._onboardingLanguage = language
        slicer.app.userSettings().setValue(LANGUAGE_SETTING, language)
        try:
            _, path = update_user_config({"ui": {"language": language}})
            self._sharedUserConfigPath = path
        except Exception as exc:
            self.appendLog(f"[Settings] Language JSON could not be saved: {exc}")
        apply_onboarding_language(self, language)

    def _update_onboarding_dashboard(self, result=None) -> None:
        dashboard = (getattr(self, "_onboardingWidgets", {}) or {}).get("dashboard")
        if not dashboard:
            return
        language = getattr(self, "_onboardingLanguage", "en")
        dashboard.setText(capability_dashboard_text(result, language=language))

    def _on_show_first_run_wizard_clicked(self) -> None:
        show_first_run_wizard(self)

    def _on_try_demo_clicked(self) -> None:
        try:
            subject_root = prepare_demo_for_owner(self)
            result = self._run_environment_dependency_check()
            if result is not None:
                self._update_environment_result_label(result)
                self._update_environment_path_status_labels(result)
                self._update_environment_status(result)
                self._update_onboarding_dashboard(result)
            language = getattr(self, "_onboardingLanguage", "en")
            if language == "zh":
                message = (
                    "合成示例数据已准备完成。\n\n"
                    f"Subject root: {subject_root}\n\n"
                    "将使用 DTI microstructure + dti_det tractography 轻量流程。关闭此提示后，"
                    "SlicerDDSurfer 会自动执行 preflight 并开始运行。"
                )
            else:
                message = (
                    "Synthetic demo subject is ready.\n\n"
                    f"Subject root: {subject_root}\n\n"
                    "SlicerDDSurfer will run the lightweight DTI microstructure + dti_det tractography workflow. "
                    "Close this message to start preflight and execution automatically."
                )
            slicer.util.infoDisplay(
                message,
                parent=self.parent,
            )
            qt.QTimer.singleShot(0, self._onRunSelectedClicked)
        except Exception as exc:
            self._show_actionable_error(
                title="Demo Setup Failed",
                what="SlicerDDSurfer could not prepare the synthetic demo subject.",
                why="The temporary directory may be unavailable, or required Python packages such as nibabel/numpy are missing.",
                next_step="Run Check environment dependencies, install missing Python packages, then try Demo again.",
                auto_fix="No external software or model files were modified.",
                details=exc,
            )

    def _on_copy_diagnostic_report_clicked(self) -> None:
        report = diagnostic_report_text(self)
        try:
            qt.QApplication.clipboard().setText(report)
            slicer.util.infoDisplay("Diagnostic report copied to clipboard.", parent=self.parent)
        except Exception:
            slicer.util.infoDisplay(report, windowTitle="SlicerDDSurfer diagnostic report", parent=self.parent)

    def _on_open_user_config_clicked(self) -> None:
        path = default_user_config_path().expanduser()
        try:
            if not path.is_file():
                _, path = update_user_config({})
            self._sharedUserConfigPath = path
            self._open_local_path(path, missing_message="The shared user configuration JSON is not available.")
        except Exception as exc:
            slicer.util.infoDisplay(f"Could not open shared user configuration:\n{exc}", parent=self.parent)

    def _add_environment_path_row(self, form_layout, item: dict[str, str]) -> None:
        add_environment_path_row(self, form_layout, item)

    def _add_environment_section_header(self, form_layout, title: str, description: str) -> None:
        add_environment_section_header(form_layout, title, description)

    def _add_environment_subsection_label(self, form_layout, title: str, description: str):
        return add_environment_subsection_label(form_layout, title, description)

    def _add_model_assets_row(self, form_layout) -> None:
        add_model_assets_row(self, form_layout)

    def _open_local_path(self, path: Path, *, missing_message: str) -> None:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            slicer.util.infoDisplay(missing_message, parent=self.parent)
            return
        try:
            opened = qt.QDesktopServices.openUrl(qt.QUrl.fromLocalFile(resolved.as_posix()))
        except Exception as exc:
            slicer.util.errorDisplay(f"Failed to open path:\n{exc}", parent=self.parent)
            return
        if not opened:
            slicer.util.infoDisplay(f"Path: {resolved}", parent=self.parent)

    def _on_open_model_assets_guide_clicked(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        self._open_local_path(
            doc_path(repo_root, "model_assets"),
            missing_message="docs/assets/MODEL_ASSETS.md is not available in the current repository checkout.",
        )

    def _on_open_model_assets_manifest_clicked(self) -> None:
        self._open_local_path(
            Path(__file__).resolve().parent.parent / "models" / "assets_manifest.json",
            missing_message="models/assets_manifest.json is not available in the current repository checkout.",
        )

    def _on_open_model_asset_terms_clicked(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        self._open_local_path(
            doc_path(repo_root, "model_asset_terms"),
            missing_message="docs/assets/MODEL_ASSET_TERMS.md is not available in the current repository checkout.",
        )

    def _on_open_release_notes_clicked(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        self._open_local_path(
            doc_path(repo_root, "release_notes"),
            missing_message="docs/release/RELEASE_NOTES_v0.1.0.md is not available in the current repository checkout.",
        )

    def _on_show_model_asset_provenance_clicked(self) -> None:
        slicer.util.infoDisplay(
            model_assets_provenance_text(Path(__file__).resolve().parent.parent),
            windowTitle="SlicerDDSurfer model asset provenance",
            parent=self.parent,
        )

    def _load_model_assets_module(self):
        module_name = "slicerdsurfer_download_model_assets"
        cached = sys.modules.get(module_name)
        if cached is not None:
            return cached
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "download_model_assets.py"
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load model asset helper: {script_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def _model_asset_verification(self, profile: str, *, check_hashes: bool = True) -> tuple[object, object, dict[str, Any]]:
        module = self._load_model_assets_module()
        repo_root = Path(__file__).resolve().parent.parent
        manifest = module.load_manifest(repo_root / "models" / "assets_manifest.json")
        plan = module.resolve_asset_plan(manifest, profile)
        configured = self._environment_dependency_path_kwargs().get("model_assets_dir")
        asset_root = module.resolve_model_assets_root(
            explicit=configured if isinstance(configured, Path) else None,
            repo_root=repo_root,
            required_paths=tuple(plan.required_paths),
            prefer_existing_legacy=True,
        )
        verification = module.verify_asset_plan(asset_root, plan, check_hashes=check_hashes)
        verification["asset_root"] = asset_root.as_posix()
        return module, plan, verification

    def _format_model_asset_status_line(self, profile: str, verification: dict[str, Any]) -> str:
        checked = int(verification.get("checked_count") or 0)
        missing = list(verification.get("missing") or [])
        pointers = list(verification.get("lfs_pointers") or [])
        if verification.get("ok"):
            if int(verification.get("hashes_checked") or 0) > 0:
                return f"{profile}=verified ({checked} file(s))"
            return f"{profile}=present ({checked} file(s))"
        problems = []
        if missing:
            problems.append(f"{len(missing)} missing")
        if pointers:
            problems.append(f"{len(pointers)} LFS pointer")
        problem_text = ", ".join(problems) if problems else "not verified"
        return f"{profile}=needs download ({checked} checked; {problem_text})"

    def _set_model_assets_status_text(self, text: str) -> None:
        label = getattr(self, "_modelAssetsSummaryLabel", None)
        if label:
            label.setText(text)
        self.appendLog("[Model assets] " + text)

    def _on_check_model_assets_status_clicked(self) -> None:
        try:
            _, _, core = self._model_asset_verification("core", check_hashes=False)
            _, _, all_assets = self._model_asset_verification("all", check_hashes=False)
        except Exception as exc:
            self._show_actionable_error(
                title="Model Asset Status Failed",
                what="SlicerDDSurfer could not verify the model asset manifest.",
                why="The checkout is missing the manifest, Git LFS metadata is unavailable, or the manifest profile is invalid.",
                next_step="Set Model assets root or run scripts/download_model_assets.sh --profile core --asset-root <asset-root>, then check status again.",
                auto_fix="Use the Verify core button for local verification; large downloads are not started by Check status.",
                details=exc,
            )
            return
        text = (
            f"Unified source: models/assets_manifest.json. Asset root: {core.get('asset_root')}. Current status: "
            + self._format_model_asset_status_line("core", core)
            + "; "
            + self._format_model_asset_status_line("all", all_assets)
            + "."
        )
        self._set_model_assets_status_text(text)

    def _on_verify_core_model_assets_clicked(self) -> None:
        try:
            _, _, verification = self._model_asset_verification("core")
        except Exception as exc:
            self._show_actionable_error(
                title="Core Model Asset Verification Failed",
                what="SlicerDDSurfer could not verify the core model assets.",
                why="The manifest or Git LFS file list could not be read.",
                next_step="Set Model assets root or run scripts/download_model_assets.sh --profile core --asset-root <asset-root> and retry.",
                auto_fix="This button verifies existing files only; it does not download large Git LFS objects.",
                details=exc,
            )
            return
        line = self._format_model_asset_status_line("core", verification)
        missing = list(verification.get("missing") or [])
        pointers = list(verification.get("lfs_pointers") or [])
        details = ""
        if missing or pointers:
            details = f" Missing: {missing[:5]}; LFS pointers: {pointers[:5]}"
        self._set_model_assets_status_text(f"Core model assets: {line}.{details}")
        if verification.get("ok"):
            slicer.util.infoDisplay("Core model assets are verified.", parent=self.parent)
        else:
            slicer.util.infoDisplay(
                "Core model assets are not complete. Run scripts/download_model_assets.sh --profile core --asset-root <asset-root>.",
                parent=self.parent,
            )

    def _on_write_model_asset_lockfile_clicked(self) -> None:
        selected = qt.QFileDialog.getSaveFileName(
            slicer.util.mainWindow(),
            "Write SlicerDDSurfer model asset lockfile",
            str(Path.home() / "model_assets_core_lock.json"),
            "JSON files (*.json)",
        )
        path_text = selected[0] if isinstance(selected, tuple) else selected
        path_text = str(path_text or "").strip()
        if not path_text:
            return
        try:
            module, plan, verification = self._model_asset_verification("core")
            if not verification.get("ok"):
                raise RuntimeError(
                    "Core assets are not fully verified: "
                    f"missing={verification.get('missing')}, lfs_pointers={verification.get('lfs_pointers')}"
                )
            repo_root = Path(__file__).resolve().parent.parent
            asset_root = Path(str(verification.get("asset_root"))).expanduser().resolve()
            lockfile = module.build_asset_lockfile(asset_root, plan)
            lockfile["asset_root"] = asset_root.as_posix()
            path = Path(path_text).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(lockfile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except Exception as exc:
            self._show_actionable_error(
                title="Model Asset Lockfile Failed",
                what="SlicerDDSurfer could not write the core model asset lockfile.",
                why="Core assets are missing, still Git LFS pointers, or the destination path is not writable.",
                next_step="Verify the core assets first, then choose a writable JSON destination.",
                auto_fix="Not available. Lockfiles must be generated from verified local files.",
                details=exc,
            )
            return
        self._set_model_assets_status_text(f"Core model asset lockfile written: {path}")
        slicer.util.infoDisplay(f"Model asset lockfile written:\n{path}", parent=self.parent)

    def _on_open_environment_report_dir_clicked(self) -> None:
        report_dir = getattr(self, "_latestEnvironmentReportDir", None)
        if not report_dir:
            slicer.util.infoDisplay("Run Check environment dependencies first.", parent=self.parent)
            return
        self._open_local_path(Path(report_dir), missing_message="The latest environment report directory is unavailable.")

    def _on_open_install_logs_dir_clicked(self) -> None:
        report_dir = getattr(self, "_latestEnvironmentReportDir", None)
        if not report_dir:
            slicer.util.infoDisplay("Run Check environment dependencies or install Python packages first.", parent=self.parent)
            return
        self._open_local_path(Path(report_dir), missing_message="The latest install log directory is unavailable.")

    def _python_install_target_text(self) -> str:
        return python_install_target_text(sys.executable or "unknown")

    def _environment_dependency_config_payload(self) -> dict[str, object]:
        widgets = getattr(self, "_environmentPathLineEdits", {}) or {}
        external_dependencies = {}
        for item in ENVIRONMENT_DEPENDENCY_PATHS:
            dependency_id = item["id"]
            widget = widgets.get(dependency_id)
            value = self._line_edit_text(widget) if widget else self._read_environment_path_setting(dependency_id)
            if value:
                external_dependencies[dependency_id] = value
        return dependency_profile_payload(
            external_dependencies,
            python_executable=sys.executable or "",
            platform_text=platform.platform(),
        )

    def _remember_environment_report_dir(self, subject_root_text: str, output_root_text: str) -> None:
        try:
            subject_root = Path(subject_root_text).expanduser().resolve() if subject_root_text else None
            output_root = Path(output_root_text).expanduser().resolve() if output_root_text else None
            if subject_root is not None and subject_root.exists():
                from shared.io_layout import subject_layout

                report_dir = subject_layout(subject_root, output_root=output_root).run_metadata / "environment"
            elif output_root is not None:
                report_dir = output_root / "00_run_metadata" / "environment"
            else:
                report_dir = Path(str(slicer.app.temporaryPath)) / "SlicerDDSurfer" / "00_run_metadata" / "environment"
            self._latestEnvironmentReportDir = report_dir
        except Exception:
            self._latestEnvironmentReportDir = None

    def _apply_environment_dependency_config(self, payload: dict[str, object]) -> int:
        data = external_dependencies_from_profile(payload)
        widgets = getattr(self, "_environmentPathLineEdits", {}) or {}
        applied = 0
        for item in ENVIRONMENT_DEPENDENCY_PATHS:
            dependency_id = item["id"]
            value = data.get(dependency_id, "")
            widget = widgets.get(dependency_id)
            if widget:
                widget.setText(value)
            self._save_environment_path_setting(dependency_id, value)
            status_label = (getattr(self, "_environmentPathStatusLabels", {}) or {}).get(dependency_id)
            if status_label:
                self._set_environment_path_status_label(status_label, "check pending", "pending" if value else "unchecked")
            if value:
                applied += 1
        return applied

    def _on_export_dependency_config_clicked(self) -> None:
        selected = qt.QFileDialog.getSaveFileName(
            slicer.util.mainWindow(),
            "Export SlicerDDSurfer dependency config",
            str(Path.home() / "slicerdsurfer-deps.json"),
            "JSON files (*.json)",
        )
        path_text = selected[0] if isinstance(selected, tuple) else selected
        path_text = str(path_text or "").strip()
        if not path_text:
            return
        path = Path(path_text).expanduser()
        payload = self._environment_dependency_config_payload()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.appendLog(f"[Environment] Exported dependency config: {path}")
        slicer.util.infoDisplay(f"Dependency config exported:\n{path}", parent=self.parent)

    def _on_import_dependency_config_clicked(self) -> None:
        selected = qt.QFileDialog.getOpenFileName(
            slicer.util.mainWindow(),
            "Import SlicerDDSurfer dependency config",
            str(Path.home()),
            "JSON files (*.json)",
        )
        path_text = selected[0] if isinstance(selected, tuple) else selected
        path_text = str(path_text or "").strip()
        if not path_text:
            return
        path = Path(path_text).expanduser()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            applied = self._apply_environment_dependency_config(payload)
        except Exception as exc:
            self._show_actionable_error(
                title="Dependency Config Import Failed",
                what="SlicerDDSurfer could not read or apply the selected dependency profile.",
                why="The file is not valid JSON, does not contain external_dependencies, or contains incompatible values.",
                next_step="Select a SlicerDDSurfer dependency profile JSON exported by this module, then rerun the environment scan.",
                auto_fix="Not available for malformed config files.",
                details=exc,
            )
            return
        self.appendLog(f"[Environment] Imported dependency config: {path} ({applied} path(s)); re-running environment scan.")
        slicer.util.infoDisplay(
            f"Imported {applied} dependency path(s). A fresh environment scan will verify this machine.",
            parent=self.parent,
        )
        self._onValidateClicked()

    def _prepare_inputs_widget_text(self, key: str) -> str:
        widget = (getattr(self, "_prepareInputWidgets", {}) or {}).get(key)
        if not widget:
            return ""
        return self._line_edit_text(widget)

    def _prepare_inputs_combo_text(self, key: str, default: str) -> str:
        widget = (getattr(self, "_prepareInputWidgets", {}) or {}).get(key)
        if not widget:
            return default
        value = getattr(widget, "currentText", "")
        return str(value() if callable(value) else value or default).strip() or default

    def _prepare_inputs_checked(self, key: str) -> bool:
        widget = (getattr(self, "_prepareInputWidgets", {}) or {}).get(key)
        return bool(widget and widget.isChecked())

    def _set_prepare_inputs_widget_text(self, key: str, value: str) -> None:
        widget = (getattr(self, "_prepareInputWidgets", {}) or {}).get(key)
        if widget:
            widget.setText(value)

    def _shared_input_directory_text(self) -> str:
        widget = getattr(self.ui, "inputDirectoryPath", None)
        if widget:
            current_path = getattr(widget, "currentPath", "")
            return str(current_path() if callable(current_path) else current_path).strip()
        node = self._parameterNode
        return str((node.inputDirectory if node else "") or "").strip()

    def _shared_subject_id_text(self) -> str:
        widget = getattr(self.ui, "subjectIdLineEdit", None)
        if widget:
            text = self._line_edit_text(widget)
            if text:
                return text
        node = self._parameterNode
        return str((node.subjectId if node else "") or "").strip()

    def _browse_prepare_input_source_path(self, key: str) -> None:
        source_kind = self._prepare_inputs_combo_text("source_kind", "auto")
        start_dir = self._prepare_inputs_widget_text(key) or self._shared_input_directory_text() or os.path.expanduser("~")
        if source_kind in {"dicom", "canonical"}:
            selected = qt.QFileDialog.getExistingDirectory(
                slicer.util.mainWindow(),
                "Select DWI source folder",
                start_dir,
            )
            selected_text = str(selected or "").strip()
        else:
            selected = qt.QFileDialog.getOpenFileName(
                slicer.util.mainWindow(),
                "Select DWI source file",
                start_dir,
                "DWI files (*.nii *.nii.gz *.nrrd *.nhdr);;All files (*)",
            )
            selected_text = selected[0] if isinstance(selected, tuple) else selected
            selected_text = str(selected_text or "").strip()
        if selected_text:
            self._set_prepare_inputs_widget_text(key, selected_text)

    def _browse_prepare_input_subject_root(self, key: str) -> None:
        start_dir = self._prepare_inputs_widget_text(key) or self._shared_input_directory_text() or os.path.expanduser("~")
        selected = qt.QFileDialog.getExistingDirectory(
            slicer.util.mainWindow(),
            "Select destination subject root",
            start_dir,
        )
        selected_text = str(selected or "").strip()
        if selected_text:
            self._set_prepare_inputs_widget_text(key, selected_text)

    def _browse_prepare_input_file(self, key: str) -> None:
        start_dir = self._prepare_inputs_widget_text(key) or self._prepare_inputs_widget_text("source") or os.path.expanduser("~")
        selected = qt.QFileDialog.getOpenFileName(
            slicer.util.mainWindow(),
            "Select sidecar file",
            start_dir,
            "DWI sidecars (*.bval *.bvec *.json *.nii *.nii.gz);;All files (*)",
        )
        selected_text = selected[0] if isinstance(selected, tuple) else selected
        selected_text = str(selected_text or "").strip()
        if selected_text:
            self._set_prepare_inputs_widget_text(key, selected_text)

    def _prepare_inputs_config(self, *, force_dry_run: bool = False) -> InputImportConfig:
        source_text = self._prepare_inputs_widget_text("source")
        subject_root_text = self._prepare_inputs_widget_text("subject_root") or self._shared_input_directory_text()
        subject_id = self._prepare_inputs_widget_text("subject_id") or self._shared_subject_id_text()
        if not source_text:
            raise ValueError("Select a DICOM folder, NIfTI file, NRRD/NHDR file, or canonical subject root.")
        if not subject_root_text:
            raise ValueError("Select the destination subject root.")
        if not subject_id:
            raise ValueError("Enter a subject ID.")

        source = Path(source_text).expanduser()
        source_kind_text = self._prepare_inputs_combo_text("source_kind", "auto")
        source_kind = detect_import_source_kind(source) if source_kind_text == "auto" else source_kind_text
        backend = self._prepare_inputs_combo_text("backend", "auto")
        output_kind = self._prepare_inputs_combo_text("output_kind", "canonical-nifti")

        def optional_path(key: str) -> Optional[Path]:
            value = self._prepare_inputs_widget_text(key)
            return Path(value).expanduser() if value else None

        external_paths = self._environment_dependency_path_kwargs()
        mrtrix_bin_dir = external_paths.get("mrtrix_bin_dir") or external_paths.get("preprocessing_mrtrix_bin_dir")
        mrconvert = (Path(mrtrix_bin_dir) / "mrconvert") if mrtrix_bin_dir else None

        return InputImportConfig(
            source=source,
            subject_root=Path(subject_root_text).expanduser(),
            subject_id=subject_id,
            source_kind=source_kind,
            backend=backend,
            output_kind=output_kind,
            bval_path=optional_path("bval"),
            bvec_path=optional_path("bvec"),
            metadata_path=optional_path("metadata"),
            mask_path=optional_path("mask"),
            mrconvert_executable=mrconvert,
            dry_run=force_dry_run or self._prepare_inputs_checked("dry_run"),
            force=self._prepare_inputs_checked("force"),
        )

    def _on_prepare_inputs_preview_clicked(self) -> None:
        try:
            manifest = prepare_inputs(self._prepare_inputs_config(force_dry_run=True))
        except Exception as exc:
            self._show_actionable_error(
                title="Input Import Preview Failed",
                what="SlicerDDSurfer could not build an input import plan.",
                why="The selected source path, sidecars, source type, backend, or destination subject root is invalid.",
                next_step="Check the source path and sidecar paths, or set Source type explicitly instead of auto.",
                auto_fix="Not available. The preview does not mutate files.",
                details=exc,
            )
            return
        self.appendLog("[Prepare Inputs] Dry-run plan:\n" + json.dumps(manifest, indent=2, sort_keys=True))
        slicer.util.infoDisplay("Input import plan created. See the SlicerDDSurfer log for details.", parent=self.parent)

    def _on_prepare_inputs_clicked(self) -> None:
        try:
            config = self._prepare_inputs_config(force_dry_run=False)
            manifest = prepare_inputs(config)
        except Exception as exc:
            self._show_actionable_error(
                title="Input Import Failed",
                what="SlicerDDSurfer could not prepare the selected external inputs.",
                why="The import backend failed, sidecar files are missing, or the destination already contains files without overwrite enabled.",
                next_step="Review the selected paths and backend. Enable overwrite only if replacing the destination input files is intended.",
                auto_fix="Not available. External converters such as dcm2niix, MRtrix3 mrconvert, and SlicerDMRI DWIConvert must be installed separately.",
                details=exc,
            )
            return

        status = str(manifest.get("status") or "completed")
        subject_root = Path(config.subject_root).expanduser().resolve()
        self.appendLog("[Prepare Inputs] Result:\n" + json.dumps(manifest, indent=2, sort_keys=True))
        if status == "completed":
            self._sync_path_widget(getattr(self.ui, "inputDirectoryPath", None), subject_root.as_posix())
            self._sync_line_edit(getattr(self.ui, "subjectIdLineEdit", None), config.subject_id)
            if self._parameterNode:
                with slicer.util.NodeModify(self._parameterNode):
                    self._parameterNode.inputDirectory = subject_root.as_posix()
                    self._parameterNode.subjectId = config.subject_id
            self._apply_shared_inputs_to_workflow_fields()
            self._checkCanApply()
            slicer.util.infoDisplay(
                f"Inputs prepared for {config.subject_id}:\n{subject_root / 'input' / 'input_import_manifest.json'}",
                parent=self.parent,
            )
        else:
            slicer.util.infoDisplay("Dry-run completed. No files were written; see the log for the planned import.", parent=self.parent)

    def _on_open_prepare_input_manifest_clicked(self) -> None:
        subject_root_text = self._prepare_inputs_widget_text("subject_root") or self._shared_input_directory_text()
        if not subject_root_text:
            slicer.util.infoDisplay("Select a subject root first.", parent=self.parent)
            return
        manifest_path = Path(subject_root_text).expanduser() / "input" / "input_import_manifest.json"
        self._open_local_path(
            manifest_path,
            missing_message="input/input_import_manifest.json is not available for the selected subject root.",
        )

    def _initialize_run_status_panel(self) -> None:
        install_run_status_panel(self)

    def _initialize_product_selection_summary(self) -> None:
        if getattr(self, "_selectedProductsSummaryLabel", None) is not None:
            return
        configuration_layout = getattr(self.ui, "configurationLayout", None)
        if not configuration_layout:
            return
        summary = qt.QLabel("Selected products will appear here after the parameter node is ready.")
        summary.wordWrap = True
        summary.setObjectName("selectedProductsSummaryLabel")
        try:
            summary.setTextInteractionFlags(qt.Qt.TextSelectableByMouse | qt.Qt.TextSelectableByKeyboard)
        except Exception:
            pass
        summary.visible = False
        self._selectedProductsSummaryLabel = summary
        try:
            configuration_layout.insertWidget(2, summary)
        except Exception:
            configuration_layout.addWidget(summary)

    def _refresh_selected_products_summary(self) -> None:
        label = getattr(self, "_selectedProductsSummaryLabel", None)
        if not label:
            return
        if not self._parameterNode:
            label.setText("Selected products will appear here after the parameter node is ready.")
            return
        text, target_text = selected_products_summary(
            self._selected_product_targets(),
            BackendSelection(
                preprocessing=(self._parameterNode.preprocessingBackend or "dipy").strip() or "dipy",
                tractography=self._tractography_backend_text(),
                bundles=self._bundle_backend_text(),
                microstructure_stages=self._microstructure_stages_text(),
                connectome=(self._parameterNode.connectomeBackend or "python").strip() or "python",
            ),
        )
        label.setText(text)
        run_button = getattr(self.ui, "runSelectedButton", None)
        if run_button:
            run_button.setToolTip(
                "Run selected products after environment preflight. Current selection: " + target_text
            )

    def _configure_log_widget(self) -> None:
        configure_log_widget(getattr(self.ui, "logPlainTextEdit", None), line_limit=int(self._logLineLimit))

    def _apply_slicerddsurfer_ui_style(self) -> None:
        apply_widget_styles(self)

    def _set_run_progress_message(self, message: str) -> None:
        set_run_progress_message(self, message)

    def _set_run_summary_message(self, message: str, state: str = "") -> None:
        set_run_summary_message(self, message, state)

    def _run_summary_from_manifest(self, manifest: dict[str, Any]) -> tuple[str, str]:
        return run_summary_from_manifest(manifest)

    def _set_run_summary_from_manifest(self, manifest: dict[str, Any], fallback: str = "") -> None:
        message, status = self._run_summary_from_manifest(manifest)
        if message:
            self._set_run_summary_message(message, status)
        elif fallback:
            self._set_run_summary_message(fallback, "unknown")

    def _set_latest_report_path(self, report_path: str | Path | None) -> None:
        set_existing_report_path(self, "_latestReportPath", "_runReportButton", report_path)

    def _set_latest_output_tree_path(self, report_path: str | Path | None) -> None:
        set_existing_report_path(self, "_latestOutputTreePath", "_runOutputTreeButton", report_path)

    def _on_open_latest_report_clicked(self) -> None:
        report_path = getattr(self, "_latestReportPath", None)
        if not report_path:
            slicer.util.infoDisplay("No generated report is available yet.", parent=self.parent)
            return
        try:
            opened = qt.QDesktopServices.openUrl(qt.QUrl.fromLocalFile(Path(report_path).as_posix()))
        except Exception as exc:
            slicer.util.errorDisplay(f"Failed to open report:\n{exc}", parent=self.parent)
            return
        if not opened:
            slicer.util.infoDisplay(f"Report path: {report_path}", parent=self.parent)

    def _on_open_output_tree_report_clicked(self) -> None:
        report_path = getattr(self, "_latestOutputTreePath", None)
        if not report_path:
            slicer.util.infoDisplay("No generated output-tree report is available yet.", parent=self.parent)
            return
        try:
            opened = qt.QDesktopServices.openUrl(qt.QUrl.fromLocalFile(Path(report_path).as_posix()))
        except Exception as exc:
            slicer.util.errorDisplay(f"Failed to open output-tree report:\n{exc}", parent=self.parent)
            return
        if not opened:
            slicer.util.infoDisplay(f"Output-tree report path: {report_path}", parent=self.parent)

    def _table_item(self, text: str, state: str = ""):
        return table_item(text, state)

    def _set_run_status_table_rows(self, rows: list[dict[str, str]]) -> None:
        set_run_status_table_rows(self, rows)

    def _update_run_status_table_item(self, key_candidates: tuple[str, ...], status: str, reason: str = "") -> None:
        update_run_status_table_item(self, key_candidates, status, reason)

    def _task_keys_for_running_line(self, line: str) -> tuple[str, ...]:
        return task_keys_for_running_line(line)

    def _update_run_plan_table(self, plan) -> None:
        rows, summary, plan_state = rows_from_plan(plan)
        self._set_run_status_table_rows(rows)
        self._set_run_summary_message(
            f"Plan: {summary['will_run']} will run, {summary['skipped']} skipped/reused, {summary['blocked']} blocked.",
            plan_state,
        )
        self._set_run_progress_message(
            f"Run plan ready: {summary['will_run']} will run, "
            f"{summary['skipped']} skipped, {summary['blocked']} blocked."
        )

    def _update_run_result_table(self, result) -> None:
        manifest_data = {}
        try:
            manifest_data = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest_data = {}
        rows = rows_from_result(result, manifest_data)
        self._set_run_status_table_rows(rows)
        if manifest_data:
            self._set_run_summary_from_manifest(manifest_data, fallback=f"Run finished. Manifest: {result.run_manifest_path}")
        self._set_run_progress_message(f"Run finished. Manifest: {result.run_manifest_path}")

    def _on_run_status_table_double_clicked(self, row: int, column: int) -> None:
        table = getattr(self, "_runStatusTable", None)
        if not table or column < 3:
            return
        item = table.item(row, column)
        if not item:
            return
        path_text = str(item.text() if callable(getattr(item, "text", None)) else item.text).strip()
        if not path_text:
            return
        path = Path(path_text).expanduser()
        if not path.exists():
            return
        qt.QDesktopServices.openUrl(qt.QUrl.fromLocalFile(path.as_posix()))

    def _browse_environment_dependency_path(self, item: dict[str, str], line_edit) -> None:
        current = self._line_edit_text(line_edit)
        start_dir = current if current else os.path.expanduser("~")
        if item.get("mode") == "file":
            selected = qt.QFileDialog.getOpenFileName(
                slicer.util.mainWindow(),
                f"Select {item['label']}",
                start_dir,
            )
        else:
            selected = qt.QFileDialog.getExistingDirectory(
                slicer.util.mainWindow(),
                f"Select {item['label']}",
                start_dir,
            )
        selected_text = selected[0] if isinstance(selected, tuple) else selected
        selected_text = str(selected_text or "").strip()
        if not selected_text:
            return
        line_edit.setText(selected_text)
        self._save_environment_path_setting(item["id"], selected_text)
        status_label = (getattr(self, "_environmentPathStatusLabels", {}) or {}).get(item["id"])
        if status_label:
            self._set_environment_path_status_label(status_label, "check pending", "pending")

    def _clear_environment_dependency_path(self, dependency_id: str, line_edit) -> None:
        line_edit.setText("")
        self._save_environment_path_setting(dependency_id, "")
        status_label = (getattr(self, "_environmentPathStatusLabels", {}) or {}).get(dependency_id)
        if status_label:
            self._set_environment_path_status_label(status_label, "check pending", "pending")

    def _on_environment_dependency_path_edited(self, dependency_id: str, line_edit) -> None:
        self._save_environment_path_setting(dependency_id, self._line_edit_text(line_edit))
        status_label = (getattr(self, "_environmentPathStatusLabels", {}) or {}).get(dependency_id)
        if status_label:
            self._set_environment_path_status_label(status_label, "check pending", "pending")

    def _environment_dependency_path_kwargs(self) -> dict[str, Any]:
        widgets = getattr(self, "_environmentPathLineEdits", {}) or {}
        kwargs: dict[str, Any] = {}
        for item in ENVIRONMENT_DEPENDENCY_PATHS:
            dependency_id = item["id"]
            widget = widgets.get(dependency_id)
            value = self._line_edit_text(widget) if widget else self._read_environment_path_setting(dependency_id)
            kwargs[dependency_id] = value if item.get("value_type") == "text" else (Path(value).expanduser() if value else None)
        return kwargs

    def _environment_check_kwargs(
        self,
        *,
        subject_root_text: str = "",
        output_root_text: str = "",
        external_paths: Optional[dict[str, Optional[Path]]] = None,
    ) -> dict[str, Any]:
        node = self._parameterNode
        if not node:
            return {}
        external_paths = external_paths if external_paths is not None else self._environment_dependency_path_kwargs()
        subject_root_text = (subject_root_text or (node.inputDirectory or "")).strip()
        output_root_text = (output_root_text or (node.outputDirectory or "")).strip()
        return {
            "targets": self._selected_environment_targets(),
            "subject_root": Path(subject_root_text).expanduser() if subject_root_text else None,
            "output_root": Path(output_root_text).expanduser() if output_root_text else None,
            "preprocessing_backend": (node.preprocessingBackend or "dipy").strip(),
            "tractography_backend": self._tractography_backend_text(),
            "connectome_backend": (node.connectomeBackend or "python").strip(),
            "ddseg_device": (node.ddsegDevice or "auto").strip() or "auto",
            "surface_device": (node.device or "auto").strip() or "auto",
            "microstructure_run_free_water": self._microstructure_stage_flags()[0],
            "microstructure_run_noddi": self._microstructure_stage_flags()[1],
            **external_paths,
        }

    def _environment_check_signature(self, kwargs: dict[str, Any]) -> tuple:
        normalized = []
        for key, value in sorted(kwargs.items()):
            if isinstance(value, Path):
                normalized.append((key, value.expanduser().as_posix()))
            elif isinstance(value, tuple):
                normalized.append((key, tuple(str(item) for item in value)))
            else:
                normalized.append((key, value))
        return tuple(normalized)

    def _cache_environment_result(self, result, signature: tuple) -> None:
        self._lastEnvironmentResult = result
        self._lastEnvironmentSignature = signature
        self._lastEnvironmentCheckedAt = monotonic()
        try:
            payload = {
                "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "signature": signature,
                "summary": result.to_dict() if hasattr(result, "to_dict") else {},
            }
            slicer.app.userSettings().setValue(
                self._user_settings_key("lastEnvironmentCheck"),
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception:
            pass

    def _cached_environment_result(self, signature: tuple):
        result = getattr(self, "_lastEnvironmentResult", None)
        if result is None or getattr(self, "_lastEnvironmentSignature", None) != signature:
            return None
        age = monotonic() - float(getattr(self, "_lastEnvironmentCheckedAt", 0.0) or 0.0)
        if age > float(getattr(self, "_environmentCacheTtlSeconds", 300.0) or 300.0):
            return None
        return result

    def _set_environment_path_status_label(self, label, text: str, state: str) -> None:
        label.setText(text)
        label.setStyleSheet(environment_path_status_style(state))

    def _path_status_dependencies(self, result, dependency_id: str) -> list:
        return path_status_dependencies(result, dependency_id)

    def _format_detected_source(self, source: str) -> str:
        return format_detected_source(source)

    def _update_environment_path_status_labels(self, result=None) -> None:
        labels = getattr(self, "_environmentPathStatusLabels", {}) or {}
        if not labels:
            return
        for item in ENVIRONMENT_DEPENDENCY_PATHS:
            dependency_id = item["id"]
            label = labels.get(dependency_id)
            if not label:
                continue
            if result is None:
                self._set_environment_path_status_label(label, "not checked", "unchecked")
                continue
            dependencies = self._path_status_dependencies(result, dependency_id)
            text, state = environment_path_status_from_dependencies(dependencies)
            self._set_environment_path_status_label(label, text, state)

    def cleanup(self) -> None:
        self.removeObservers()

    def enter(self) -> None:
        self.initializeParameterNode()

    def exit(self) -> None:
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)

    def onSceneStartClose(self, caller, event) -> None:
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        self.setParameterNode(self.logic.getParameterNode())
        if not self._parameterNode:
            return

        if not (self._parameterNode.ddparcelAtlasPath or "").strip():
            module_root = Path(__file__).resolve().parent.parent
            atlas_path = model_asset_path("Resources/Data/100HCP-population-mean-T2.nii.gz", repo_root=module_root)
            if atlas_path.is_file():
                self._parameterNode.ddparcelAtlasPath = atlas_path.as_posix()

        ddseg_weights_dir = model_asset_path("segmentation/weights", repo_root=Path(__file__).resolve().parent.parent)
        if not (self._parameterNode.ddsegWeightsDir or "").strip() and ddseg_weights_dir.is_dir():
            self._parameterNode.ddsegWeightsDir = ddseg_weights_dir.as_posix()

        slicer_base = self._default_slicer_base_dir()
        if not (self._parameterNode.ddsegSlicerBase or "").strip() and slicer_base is not None:
            self._parameterNode.ddsegSlicerBase = slicer_base.as_posix()

        slicer_dmri = self._default_slicerdmri_dir()
        if not (self._parameterNode.ddsegSlicerExt or "").strip() and slicer_dmri is not None:
            self._parameterNode.ddsegSlicerExt = slicer_dmri.as_posix()

    def _default_slicer_base_dir(self) -> Optional[Path]:
        app = getattr(slicer, "app", None)
        if app is None:
            return None
        try:
            return Path(str(app.slicerHome)).resolve()
        except Exception:
            return None

    def _default_slicerdmri_dir(self) -> Optional[Path]:
        slicer_base = self._default_slicer_base_dir()
        if slicer_base is None:
            return None
        extensions_root = slicer_base / "slicer.org"
        if not extensions_root.is_dir():
            return None
        for candidate in sorted(extensions_root.glob("Extensions-*/*")):
            if candidate.is_dir() and candidate.name == "SlicerDMRI":
                return candidate.resolve()
        return None

    def _jump_to_module(self, target: str) -> None:
        """Handle navigation button clicks."""
        if target == "DDSeg":
            try:
                slicer.util.selectModule("SlicerDDSurfer")
                panel = getattr(self.ui, "ddsegCollapsibleButton", None)
                if panel:
                    panel.collapsed = False
                    panel.raise_()
            except Exception:
                pass
            slicer.util.showStatusMessage("DDSeg pipeline is available in this module", 3000)
            return
        if target == "LOCAL_DDSURFER":
            try:
                slicer.util.selectModule("SlicerDDSurfer")
                if hasattr(self, "ui") and getattr(self.ui, "configurationCollapsibleButton", None):
                    self.ui.configurationCollapsibleButton.collapsed = False
            except Exception:
                pass
            slicer.util.showStatusMessage("Jumped to DDSurfer configuration", 3000)
            return

        if target == "LOCAL_MICROSTRUCTURE":
            try:
                slicer.util.selectModule("SlicerDDSurfer")
                panel = getattr(self.ui, "microstructureCollapsibleButton", None)
                if panel:
                    panel.collapsed = False
                    panel.raise_()
            except Exception:
                pass
            slicer.util.showStatusMessage("Jumped to microstructure workflow", 3000)
            return

        try:
            slicer.util.selectModule(target)
            slicer.util.showStatusMessage(f"Jumped to {target}", 3000)
        except Exception:
            slicer.util.infoDisplay(f"Module {target} not installed or not yet implemented. Coming soon.")

    def setParameterNode(self, inputParameterNode) -> None:
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._restore_common_user_settings_to_node()
            self._checkCanApply()

    def _sync_path_widget(self, widget, desired: str) -> None:
        if not widget or widget.currentPath == desired:
            return
        blocker = QSignalBlocker(widget)
        widget.setCurrentPath(desired)
        del blocker

    def _sync_line_edit(self, widget, desired: str) -> None:
        if not widget:
            return
        current_text = widget.text() if callable(getattr(widget, "text", None)) else widget.text
        if current_text == desired:
            return
        blocker = QSignalBlocker(widget)
        widget.setText(desired)
        del blocker

    def _sync_combo_text(self, widget, desired: str, *, via_index: bool = True) -> None:
        if not widget or widget.currentText == desired:
            return
        blocker = QSignalBlocker(widget)
        if via_index:
            index = widget.findText(desired)
            if index >= 0:
                widget.setCurrentIndex(index)
        else:
            widget.setCurrentText(desired)
        del blocker

    def _sync_checkbox(self, widget, desired: bool) -> None:
        if not widget or widget.isChecked() == desired:
            return
        blocker = QSignalBlocker(widget)
        widget.setChecked(desired)
        del blocker

    def _sync_spinbox(self, widget, desired: int) -> None:
        if not widget or widget.value == desired:
            return
        blocker = QSignalBlocker(widget)
        widget.value = desired
        del blocker

    def _checkCanApply(self, caller=None, event=None) -> None:
        sync_parameter_node_to_ui(self)
        self._refresh_selected_products_summary()
        self._refresh_advanced_run_settings()
        self.validateInputs(manual=False)
        self._schedule_common_user_settings_save()

    def _update_parameter_node(self, attribute: str, value: Any) -> bool:
        if not self._parameterNode:
            return False
        with slicer.util.NodeModify(self._parameterNode):
            setattr(self._parameterNode, attribute, value)
        return True

    def _onUnifiedTorchDeviceChanged(self, value: str) -> None:
        if not self._parameterNode:
            return
        device = (value or "auto").strip() or "auto"
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.device = device
            self._parameterNode.ddsegDevice = device
        self._checkCanApply()

    def _onTractographyBackendChanged(self, value: str) -> None:
        self._refresh_advanced_run_settings(backend=(value or "").strip() or None)

    def _onBundleBackendChanged(self, value: str) -> None:
        self._refresh_bundle_backend_highlight(bundle_backend=(value or "").strip() or None)

    def _onBatchRootPathChanged(self, value: str) -> None:
        self._update_parameter_node("batchRoot", str(value or "").strip())

    def _default_run_name_for_backend(self, backend: str) -> str:
        return default_run_name_for_backend(backend)

    def _is_auto_generated_run_name(self, run_name: str) -> bool:
        return is_auto_generated_run_name(run_name)

    def _refresh_advanced_run_settings(self, *, backend: Optional[str] = None) -> None:
        backend = (backend or self._tractography_backend_text() or "csd_act").strip() or "csd_act"
        run_name_edit = getattr(self.ui, "orchestrationRunNameLineEdit", None)
        current_run_name = self._line_edit_text(run_name_edit) if run_name_edit else ""
        desired_default = self._default_run_name_for_backend(backend)
        if run_name_edit and self._is_auto_generated_run_name(current_run_name) and current_run_name != desired_default:
            run_name_edit.setText(desired_default)
            self._update_parameter_node("orchestrationRunName", desired_default)

        streamline_label = getattr(self.ui, "orchestrationSelectStreamlinesLabel", None)
        streamline_spinbox = getattr(self.ui, "orchestrationSelectStreamlinesSpinBox", None)
        if not streamline_label or not streamline_spinbox:
            self._refresh_bundle_backend_highlight()
            return

        control_state = streamline_control_state(backend)
        streamline_spinbox.enabled = control_state.enabled
        streamline_label.text = control_state.label
        streamline_label.toolTip = control_state.tooltip
        streamline_spinbox.toolTip = control_state.tooltip
        self._refresh_bundle_backend_highlight()

    def _refresh_bundle_backend_highlight(self, *, bundle_backend: Optional[str] = None) -> None:
        active_sections = active_bundle_backend_sections(bundle_backend or self._bundle_backend_text())

        label_groups = getattr(self, "_environmentBackendSectionLabels", {}) or {}
        row_groups = getattr(self, "_environmentBackendSectionRows", {}) or {}
        for key in ("wma", "tractcloud"):
            title_label, description_label = label_groups.get(key, (None, None))
            active = key in active_sections
            title_style, description_style = optional_backend_label_styles(active)
            if title_label:
                title_label.setStyleSheet(title_style)
            if description_label:
                description_label.setStyleSheet(description_style)

            for widgets in row_groups.get(key, []):
                for widget in widgets:
                    if widget is None:
                        continue
                    if hasattr(widget, "setStyleSheet"):
                        style = optional_backend_widget_style(widget.__class__.__name__, active)
                        if style is not None:
                            widget.setStyleSheet(style)

    def appendLog(self, text: str) -> None:
        append_log(self, text)

    def _trim_log_widget(self, log_widget) -> None:
        limit = int(getattr(self, "_logLineLimit", 4000) or 4000)
        if limit <= 0:
            return
        block_count = 0
        try:
            block_count = int(log_widget.document().blockCount())
        except Exception:
            pass
        if block_count and block_count <= limit + 200:
            return
        try:
            lines = str(log_widget.toPlainText()).splitlines()
        except Exception:
            return
        if len(lines) <= limit + 200:
            return
        log_widget.setPlainText("\n".join(lines[-limit:]))

    def _onClearLogClicked(self) -> None:
        if hasattr(self.ui, "logPlainTextEdit"):
            self.ui.logPlainTextEdit.clear()

    def _selected_workflows(self) -> list[str]:
        node = self._parameterNode
        if not node:
            return []
        return selected_workflows(self._product_target_flags())

    def _selected_orchestrator_targets(self) -> tuple[str, ...]:
        node = self._parameterNode
        if not node:
            return ()
        return selected_orchestrator_targets(self._product_target_flags())

    def _selected_product_targets(self) -> tuple[str, ...]:
        node = self._parameterNode
        if not node:
            return ()
        freewater, noddi = self._microstructure_stage_flags()
        return selected_product_targets(
            self._product_target_flags(),
            tractography_backend=self._tractography_backend_text(),
            bundle_backend=self._bundle_backend_text(),
            microstructure_freewater=freewater,
            microstructure_noddi=noddi,
        )

    def _product_target_flags(self) -> ProductTargetFlags:
        node = self._parameterNode
        if not node:
            return ProductTargetFlags()
        return ProductTargetFlags(
            preprocessing=bool(node.targetPreprocessing),
            surface=bool(node.targetSurface),
            parcellation=bool(node.targetParcellation),
            segmentation=bool(node.targetSegmentation),
            microstructure=bool(node.targetMicrostructure),
            tractography=bool(node.targetTractography),
            bundles=bool(node.targetBundles),
            connectome=bool(node.targetConnectome),
        )

    def _tractography_backend_text(self) -> str:
        node = self._parameterNode
        return ((node.orchestrationTractographyBackend if node else "") or "csd_act").strip() or "csd_act"

    def _bundle_backend_text(self) -> str:
        node = self._parameterNode
        return ((getattr(node, "orchestrationBundleBackend", "") if node else "") or "wmql").strip() or "wmql"

    def _microstructure_stages_text(self) -> str:
        node = self._parameterNode
        if not node:
            return "dti"
        text = (getattr(node, "orchestrationMicrostructureStages", "") or "").strip().lower()
        if text:
            return text
        stages = ["dti"]
        if bool(getattr(node, "orchestrationRunFreeWater", False)):
            stages.append("freewater")
        if bool(getattr(node, "orchestrationRunNoddi", False)):
            stages.append("noddi")
        return ",".join(stages)

    def _microstructure_stage_flags(self) -> tuple[bool, bool]:
        node = self._parameterNode
        return microstructure_stage_flags(
            self._microstructure_stages_text(),
            legacy_freewater=bool(getattr(node, "orchestrationRunFreeWater", False)) if node else False,
            legacy_noddi=bool(getattr(node, "orchestrationRunNoddi", False)) if node else False,
        )

    def _selected_environment_targets(self) -> tuple[str, ...]:
        node = self._parameterNode
        if not node:
            return ()
        return selected_environment_targets(self._selected_product_targets())

    def _apply_shared_inputs_to_workflow_fields(self) -> None:
        """Populate empty product-specific fields from the shared subject setup."""
        node = self._parameterNode
        if not node:
            return
        subject_id = (node.subjectId or "").strip()
        subject_root = (node.inputDirectory or "").strip()
        with slicer.util.NodeModify(node):
            if subject_id:
                if not (node.ddparcelSubjectId or "").strip():
                    node.ddparcelSubjectId = subject_id
                if not (node.microstructureSubjectId or "").strip():
                    node.microstructureSubjectId = subject_id
            if subject_root:
                if not (node.ddparcelInputRoot or "").strip():
                    node.ddparcelInputRoot = subject_root
                if not (node.microstructureInputRoot or "").strip():
                    node.microstructureInputRoot = subject_root
                if not (node.ddsegDwiPath or "").strip():
                    node.ddsegDwiPath = subject_root

    def _slicer_launcher_program(self) -> str:
        launcher_path = getattr(slicer.app, "launcherExecutableFilePath", "")
        launcher_path = launcher_path() if callable(launcher_path) else launcher_path
        launcher_path = str(launcher_path or "").strip()
        if launcher_path and Path(launcher_path).name != "SlicerApp-real":
            return launcher_path
        app_path = getattr(slicer.app, "applicationFilePath", "")
        app_path = app_path() if callable(app_path) else app_path
        app_path = str(app_path or "").strip()
        if app_path:
            app_candidate = Path(app_path)
            if app_candidate.name == "SlicerApp-real":
                for candidate in (
                    app_candidate.parent.parent / "Slicer",
                    app_candidate.parent / "Slicer",
                ):
                    if candidate.is_file():
                        return candidate.as_posix()
            return app_path
        slicer_home = str(getattr(slicer.app, "slicerHome", "") or "").strip()
        if slicer_home:
            for candidate in (Path(slicer_home) / "Slicer", Path(slicer_home).parent / "Slicer"):
                if candidate.is_file():
                    return candidate.as_posix()
        return "Slicer"

    def _build_background_cli_args(self, common_run_kwargs: dict[str, Any], external_paths: dict[str, Optional[Path]]) -> list[str]:
        node = self._parameterNode
        repo_root = Path(__file__).resolve().parent.parent
        return build_background_cli_args(
            common_run_kwargs,
            external_paths,
            repo_root=repo_root,
            preprocessing_backend=(node.preprocessingBackend or "dipy").strip() if node else "dipy",
        )

    def _build_batch_background_cli_args(
        self,
        common_run_kwargs: dict[str, Any],
        external_paths: dict[str, Optional[Path]],
        *,
        batch_root: Path,
        batch_size: int,
        arrange_inputs: str,
    ) -> list[str]:
        node = self._parameterNode
        repo_root = Path(__file__).resolve().parent.parent
        return build_batch_background_cli_args(
            common_run_kwargs,
            external_paths,
            repo_root=repo_root,
            batch_root=batch_root,
            batch_size=batch_size,
            arrange_inputs=arrange_inputs,
            preprocessing_backend=(node.preprocessingBackend or "dipy").strip() if node else "dipy",
        )

    def _startBackgroundPipeline(
        self,
        common_run_kwargs: dict[str, Any],
        external_paths: dict[str, Optional[Path]],
        selected_workflows: list[str],
    ) -> None:
        if getattr(self, "_backgroundProcess", None) is not None:
            process = self._backgroundProcess
            if qprocess_is_running(process):
                slicer.util.infoDisplay("A SlicerDDSurfer job is already running.", parent=self.parent)
                return

        process = qt.QProcess(self.parent)
        process.setWorkingDirectory(Path(__file__).resolve().parent.parent.as_posix())
        process.setProcessChannelMode(qt.QProcess.MergedChannels)
        process.connect("readyReadStandardOutput()", self._onBackgroundProcessReadyRead)
        process.connect("finished(int,QProcess::ExitStatus)", self._onBackgroundProcessFinished)
        process.connect("errorOccurred(QProcess::ProcessError)", self._onBackgroundProcessError)

        program = self._slicer_launcher_program()
        args = self._build_background_cli_args(common_run_kwargs, external_paths)
        self._backgroundProcess = process
        self._backgroundOutputBuffer = ""
        self._backgroundManifestPath = None
        self._backgroundCancelRequested = False
        self._backgroundRunContext = build_background_run_context(common_run_kwargs, selected_workflows)
        self.appendLog("[Background] Starting: " + program + " " + " ".join(args))
        self._setPipelineActive(True)
        self._set_run_progress_message("Background execution submitted.")
        process.start(program, args)
        if not process.waitForStarted(5000):
            self._setPipelineActive(False)
            self._setStatus("error", "Failed to start background job")
            self.appendLog("[Background] Failed to start process.")

    def _startBackgroundBatchPipeline(
        self,
        common_run_kwargs: dict[str, Any],
        external_paths: dict[str, Optional[Path]],
        selected_workflows: list[str],
        *,
        batch_root: Path,
        batch_size: int,
        arrange_inputs: str,
    ) -> None:
        if getattr(self, "_backgroundProcess", None) is not None:
            process = self._backgroundProcess
            if qprocess_is_running(process):
                slicer.util.infoDisplay("A SlicerDDSurfer job is already running.", parent=self.parent)
                return

        process = qt.QProcess(self.parent)
        process.setWorkingDirectory(Path(__file__).resolve().parent.parent.as_posix())
        process.setProcessChannelMode(qt.QProcess.MergedChannels)
        process.connect("readyReadStandardOutput()", self._onBackgroundProcessReadyRead)
        process.connect("finished(int,QProcess::ExitStatus)", self._onBackgroundProcessFinished)
        process.connect("errorOccurred(QProcess::ProcessError)", self._onBackgroundProcessError)

        program = self._slicer_launcher_program()
        args = self._build_batch_background_cli_args(
            common_run_kwargs,
            external_paths,
            batch_root=batch_root,
            batch_size=batch_size,
            arrange_inputs=arrange_inputs,
        )
        self._backgroundProcess = process
        self._backgroundOutputBuffer = ""
        self._backgroundManifestPath = None
        self._backgroundCancelRequested = False
        self._backgroundRunContext = build_background_run_context(
            common_run_kwargs,
            selected_workflows,
            batch_root=batch_root,
            batch_size=batch_size,
        )
        self.appendLog("[Background] Starting batch: " + program + " " + " ".join(args))
        self._setPipelineActive(True)
        self._set_run_progress_message(f"Batch execution submitted for {batch_root}.")
        process.start(program, args)
        if not process.waitForStarted(5000):
            self._setPipelineActive(False)
            self._setStatus("error", "Failed to start batch job")
            self.appendLog("[Background] Failed to start batch process.")

    def _onBackgroundProcessReadyRead(self) -> None:
        process = getattr(self, "_backgroundProcess", None)
        if process is None:
            return
        data = self._qbytearray_to_text(process.readAllStandardOutput())
        self._backgroundOutputBuffer += data
        while "\n" in self._backgroundOutputBuffer:
            line, self._backgroundOutputBuffer = self._backgroundOutputBuffer.split("\n", 1)
            self._handleBackgroundOutputLine(line.rstrip())

    def _qbytearray_to_text(self, value) -> str:
        return qbytearray_to_text(value)

    def _handleBackgroundOutputLine(self, line: str) -> None:
        if not line:
            return
        self.appendLog(line)
        if line.startswith("[Orchestrator] Running "):
            keys = self._task_keys_for_running_line(line)
            self._update_run_status_table_item(keys, "running", line.replace("[Orchestrator] ", "", 1))
        if line.endswith("_orchestration_manifest.json"):
            path = Path(line.strip())
            if path.is_file():
                self._backgroundManifestPath = path

    def _extract_background_manifest_path(self) -> Optional[Path]:
        return extract_background_manifest_path(
            getattr(self, "_backgroundOutputBuffer", "") or "",
            explicit_path=getattr(self, "_backgroundManifestPath", None),
        )

    def _onBackgroundProcessFinished(self, exit_code: int, exit_status) -> None:
        if getattr(self, "_backgroundOutputBuffer", ""):
            tail = self._backgroundOutputBuffer
            self._backgroundOutputBuffer = ""
            for line in tail.splitlines():
                self._handleBackgroundOutputLine(line.rstrip())
        cancelled = bool(getattr(self, "_backgroundCancelRequested", False))
        process_failed = exit_code != 0 and not cancelled
        manifest_path = self._extract_background_manifest_path()
        self._setPipelineActive(False)
        if cancelled:
            cancel_manifest = self._write_cancelled_manifest()
            self._mark_unfinished_rows("cancelled", "User cancelled the background job.")
            self.appendLog(f"[Background] Cancelled. Manifest: {cancel_manifest}")
            self._setStatus("warning", "Pipeline cancelled")
            self._set_latest_report_path(None)
            self._set_latest_output_tree_path(None)
            self._set_run_progress_message(f"Pipeline cancelled. Manifest: {cancel_manifest}")
            self._set_run_summary_message("Status: cancelled | User cancelled the background job.", "cancelled")
        elif process_failed:
            self._mark_unfinished_rows("failed", f"Background process exited with code {exit_code}")
            self._setStatus("error", f"Pipeline failed: exit code {exit_code}")
            self._set_latest_report_path(None)
            self._set_latest_output_tree_path(None)
            self._set_run_progress_message(f"Pipeline failed: exit code {exit_code}")
            self._set_run_summary_message(f"Status: failed | Background process exited with code {exit_code}.", "failed")
        elif manifest_path and manifest_path.is_file():
            self._load_background_manifest_result(manifest_path)
        else:
            self._mark_unfinished_rows("failed", "Background process finished without a manifest path.")
            self._setStatus("error", "Pipeline failed: no manifest")
            self._set_latest_report_path(None)
            self._set_latest_output_tree_path(None)
            self._set_run_progress_message("Pipeline failed: no manifest path was reported.")
            self._set_run_summary_message("Status: failed | Background process finished without a manifest path.", "failed")
        self._backgroundProcess = None
        self._backgroundCancelRequested = False

    def _load_background_manifest_result(self, manifest_path: Path) -> None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._mark_unfinished_rows("failed", f"Unable to read manifest: {exc}")
            self._setStatus("error", "Pipeline failed: invalid manifest")
            return
        if manifest.get("kind") == "slicerdsurfer_batch_run":
            self._load_background_batch_manifest_result(manifest_path, manifest)
            return
        rows, counts = rows_from_single_subject_manifest(manifest)
        blocked = counts["blocked"]
        failed = counts["failed"]
        completed_like = counts["completed_like"]
        self._set_run_status_table_rows(rows)
        if failed:
            self._setStatus("error", f"Completed with {failed} failed task(s)")
        elif blocked and completed_like:
            self._setStatus("warning", f"Partial results: {blocked} blocked task(s)")
        elif blocked:
            self._setStatus("error", f"Completed with {blocked} blocked task(s)")
        else:
            self._setStatus("ready", "Pipeline completed")
        report_path = ""
        report_paths = manifest.get("report_paths") or {}
        if isinstance(report_paths, dict):
            report_path = str(report_paths.get("report_html_latest") or report_paths.get("report_html") or "")
        self._set_latest_report_path(report_path)
        output_tree_path = ""
        output_tree_report_paths = manifest.get("output_tree_report_paths") or {}
        if isinstance(output_tree_report_paths, dict):
            output_tree_path = str(output_tree_report_paths.get("report_html_latest") or output_tree_report_paths.get("report_html") or "")
        self._set_latest_output_tree_path(output_tree_path)
        self._set_run_summary_from_manifest(manifest, fallback=f"Run finished. Manifest: {manifest_path}")
        auto_load_limit = int(getattr(self, "_autoLoadResultLimit", 12))
        self._set_run_progress_message(f"Run finished. Loading up to {auto_load_limit} key result node(s)...")
        loaded_count = 0
        if self.logic:
            try:
                loaded = self.logic.loadKeyResultsFromManifest(
                    manifest_path,
                    max_items=auto_load_limit,
                )
                loaded_count = len(loaded.get("loaded", []))
            except Exception as exc:
                self.appendLog(f"[Slicer] Auto-load skipped: {exc}")
        message = f"Run finished. Manifest: {manifest_path}"
        if loaded_count:
            message += (
                f" Auto-loaded {loaded_count} key result node(s)"
                f" (limit {auto_load_limit})."
            )
        if report_path:
            message += f" Report: {report_path}"
        if output_tree_path:
            message += f" Output tree: {output_tree_path}"
        self._set_run_progress_message(message)

    def _load_background_batch_manifest_result(self, manifest_path: Path, manifest: dict[str, Any]) -> None:
        rows, counts = rows_from_batch_manifest(manifest_path, manifest)
        failed = counts["failed"]
        completed = counts["completed"]
        skipped = counts["skipped"]
        total = counts["total"]
        self._set_run_status_table_rows(rows)
        if failed:
            self._setStatus("error", f"Batch failed: {failed} subject(s)")
        else:
            self._setStatus("ready", "Batch completed")
        self._set_latest_report_path(None)
        self._set_latest_output_tree_path(None)
        self._set_run_progress_message(f"Batch finished. Manifest: {manifest_path}")
        self._set_run_summary_message(
            f"Status: batch completed | Subjects: {total} | Completed: {completed} | "
            f"Failed: {failed} | Skipped: {skipped} | Manifest: {manifest_path}",
            "failed" if failed else "completed",
        )

    def _onBackgroundProcessError(self, error) -> None:
        self.appendLog(f"[Background] QProcess error: {error}")

    def _mark_unfinished_rows(self, status: str, reason: str) -> None:
        mark_unfinished_rows(self, status, reason)

    def _write_cancelled_manifest(self) -> Path:
        context = getattr(self, "_backgroundRunContext", {}) or {}
        manifest_path, payload = cancelled_manifest_path_and_payload(
            context,
            cancelled_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest_path

    def _onCancelRunClicked(self) -> None:
        process = getattr(self, "_backgroundProcess", None)
        if process is None:
            return
        try:
            if process.state() == qt.QProcess.NotRunning:
                return
        except Exception:
            return
        self._backgroundCancelRequested = True
        self.appendLog("[Background] Cancellation requested by user.")
        self._set_run_progress_message("Cancelling background job...")
        process.terminate()
        qt.QTimer.singleShot(3000, lambda: self._kill_background_process_if_running(process))

    def _kill_background_process_if_running(self, process) -> None:
        try:
            if process and process.state() != qt.QProcess.NotRunning:
                process.kill()
        except Exception:
            pass

    def _environment_doctor_result_for_run(self, doctor_kwargs: dict, doctor_signature: tuple):
        doctor_result = self._cached_environment_result(doctor_signature)
        try:
            if doctor_result is None:
                doctor_result = self.logic.runEnvironmentDoctor(**doctor_kwargs)
                self._cache_environment_result(doctor_result, doctor_signature)
            else:
                self.appendLog("[Environment] Reusing recent dependency check; inputs and selected targets are unchanged.")
        except Exception as exc:
            self.appendLog(f"Environment check failed: {exc}")
            self._show_actionable_error(
                title="Environment Check Failed",
                what="SlicerDDSurfer could not complete the dependency preflight scan.",
                why="A configured path, Python executable, environment variable, or external probe raised an exception.",
                next_step="Check the External Runtime Paths values, clear stale paths, then run Check environment dependencies again.",
                auto_fix="Python packages can be installed on demand after a successful scan; external tools are never changed silently.",
                details=exc,
            )
            self._setStatus("error", "Environment check failed")
            return None
        self._update_environment_result_label(doctor_result)
        self._update_environment_path_status_labels(doctor_result)
        self._latestEnvironmentReportDir = self._environment_report_dir_from_kwargs(doctor_kwargs)
        return doctor_result

    def _environment_report_dir_from_kwargs(self, doctor_kwargs: dict) -> Optional[Path]:
        try:
            subject_root = doctor_kwargs.get("subject_root")
            output_root = doctor_kwargs.get("output_root")
            if subject_root is not None and Path(subject_root).expanduser().exists():
                from shared.io_layout import subject_layout

                return subject_layout(Path(subject_root).expanduser().resolve(), output_root=output_root).run_metadata / "environment"
            if output_root is not None:
                return Path(output_root).expanduser().resolve() / "00_run_metadata" / "environment"
            return Path(str(slicer.app.temporaryPath)) / "SlicerDDSurfer" / "00_run_metadata" / "environment"
        except Exception:
            return None

    def _install_missing_python_before_run(self, doctor_result, doctor_kwargs: dict, doctor_signature: tuple):
        self.appendLog(
            "Missing Python packages detected; installing before run: "
            + ", ".join(doctor_result.missing_python_packages)
        )
        self._setPipelineActive(True)
        self._setStatus("running", "Installing Python dependencies...")
        slicer.util.showStatusMessage("Installing missing Python dependencies...", 0)
        try:
            packages = tuple(doctor_result.missing_python_packages)
            self.logic.installMissingPythonDependencies(packages)
            self._save_python_install_status(packages, "completed")
            updated_result = self.logic.runEnvironmentDoctor(**doctor_kwargs)
            self._cache_environment_result(updated_result, doctor_signature)
            self._update_environment_result_label(updated_result)
            self._update_environment_path_status_labels(updated_result)
            return updated_result
        except Exception as exc:
            self._save_python_install_status(tuple(doctor_result.missing_python_packages), "failed", str(exc))
            self.appendLog(f"Dependency installation failed: {exc}")
            self._show_actionable_error(
                title="Python Dependency Installation Failed",
                what="SlicerDDSurfer could not install the missing Python packages into the selected Python environment.",
                why="pip returned an error, the Python executable is not writable, or the package is unavailable for this platform.",
                next_step="Open the generated install_missing_python script from the environment report and run it in a terminal to inspect the full pip output.",
                auto_fix="Automatic Python install was attempted and failed. External tools still require manual setup.",
                details=exc,
            )
            self._setPipelineActive(False)
            self._setStatus("error", "Dependency installation failed")
            return None

    def _onRunSelectedClicked(self) -> None:
        if not self._parameterNode or not self.logic:
            return
        self._save_common_user_settings()
        selected = self._selected_workflows()
        if not selected:
            slicer.util.errorDisplay("Select at least one target product to run.", parent=self.parent)
            return

        self._apply_shared_inputs_to_workflow_fields()
        batch_mode = bool(getattr(self._parameterNode, "batchMode", False))
        subject_root_text = (self._parameterNode.inputDirectory or "").strip()
        subject_id = (self._parameterNode.subjectId or "").strip()
        output_root_text = (self._parameterNode.outputDirectory or "").strip()
        surface_device = (self._parameterNode.device or "auto").strip() or "auto"
        ddseg_device = (self._parameterNode.ddsegDevice or "auto").strip() or "auto"
        run_free_water, run_noddi = self._microstructure_stage_flags()
        selected_targets = self._selected_product_targets()
        auto_install_python = bool(self._parameterNode.autoInstallPythonDependencies)
        external_paths = self._environment_dependency_path_kwargs()
        run_name = (self._parameterNode.orchestrationRunName or "Test1").strip() or "Test1"
        selection = RunSelection(
            subject_id=subject_id,
            subject_root_text=subject_root_text,
            output_root_text=output_root_text,
            selected_targets=selected_targets,
            run_name=run_name,
            tractography_backend=self._tractography_backend_text(),
            bundle_backend=self._bundle_backend_text(),
            microstructure_freewater=run_free_water,
            microstructure_noddi=run_noddi,
            select_streamlines=max(1, int(self._parameterNode.orchestrationSelectStreamlines)),
            ddseg_device=ddseg_device,
            surface_device=surface_device,
            connectome_backend=(self._parameterNode.connectomeBackend or "python").strip(),
            connectome_compress_mrtrix_dense=bool(self._parameterNode.connectomeCompressMrtrixDense),
        )

        if batch_mode:
            batch_root_text = (getattr(self._parameterNode, "batchRoot", "") or subject_root_text).strip()
            batch_options, error = validate_batch_run_options(
                batch_root_text,
                fallback_subject_root_text=subject_root_text,
                batch_size=int(getattr(self._parameterNode, "batchSize", 1) or 1),
                arrange_inputs=getattr(self._parameterNode, "batchArrangeInputs", "none") or "none",
            )
            if error or batch_options is None:
                slicer.util.errorDisplay(error, parent=self.parent)
                return
            common_run_kwargs = build_batch_run_kwargs(selection, batch_root=batch_options.batch_root)
            self.appendLog(
                f"Submitting batch products to background runner: root={batch_options.batch_root}, "
                f"batch_size={batch_options.batch_size}, targets={', '.join(selected)}"
            )
            self._startBackgroundBatchPipeline(
                common_run_kwargs,
                external_paths,
                selected,
                batch_root=batch_options.batch_root,
                batch_size=batch_options.batch_size,
                arrange_inputs=batch_options.arrange_inputs,
            )
            return

        input_error = validate_single_subject_inputs(subject_root_text, subject_id)
        if input_error:
            slicer.util.errorDisplay(input_error, parent=self.parent)
            return
        doctor_kwargs = self._environment_check_kwargs(
            subject_root_text=subject_root_text,
            output_root_text=output_root_text,
            external_paths=external_paths,
        )
        doctor_signature = self._environment_check_signature(doctor_kwargs)
        doctor_result = self._environment_doctor_result_for_run(doctor_kwargs, doctor_signature)
        if doctor_result is None:
            return
        if doctor_result.blocker_count and auto_install_python and doctor_result.missing_python_packages:
            doctor_result = self._install_missing_python_before_run(doctor_result, doctor_kwargs, doctor_signature)
            if doctor_result is None:
                return

        preflight_blockers = preflight_blockers_for_targets(doctor_result, selected_targets)
        common_run_kwargs = build_single_subject_run_kwargs(
            selection,
            external_paths,
            preflight_blocked_targets=preflight_blockers,
        )
        try:
            plan = self.logic.planSelectedProductOrchestration(**common_run_kwargs)
            self._update_run_plan_table(plan)
            blocked_items = blocked_plan_items(plan)
            if blocked_items:
                self.appendLog("Run plan blocked target(s): " + blocked_plan_log_text(blocked_items))
                environment_blockers = environment_blockers_from_plan(plan)
                if environment_blockers:
                    self._show_partial_run_notice(environment_blockers, runnable_targets_from_plan(plan))
        except Exception as exc:
            self.appendLog(f"Run planning failed: {exc}")
            self._show_actionable_error(
                title="Run Planning Failed",
                what="SlicerDDSurfer could not build the selected product run plan.",
                why="The selected targets, backend choices, or input/output paths are inconsistent.",
                next_step="Review Subject Setup, selected products, backend choices, and the output directory, then run the plan again.",
                auto_fix="Not available for invalid run configuration.",
                details=exc,
            )
            self._setStatus("error", "Run planning failed")
            return

        self.appendLog("Submitting selected products to background runner: " + ", ".join(selected))
        self._startBackgroundPipeline(common_run_kwargs, external_paths, selected)

    def _show_partial_run_notice(self, blockers: dict[str, str], runnable_targets: tuple[str, ...]) -> None:
        message = partial_run_notice_text(blockers, runnable_targets)
        slicer.util.infoDisplay(message, windowTitle="SlicerDDSurfer partial run", parent=self.parent)

    def _setStatus(self, kind: str, message: str) -> None:
        set_status(self, kind, message)

    def _summarise_missing(self, missing: List[str]) -> str:
        if not missing:
            return "Ready to run."
        preview = "; ".join(missing[:3])
        if len(missing) > 3:
            preview += " ..."
        return "Waiting: " + preview

    def _setWidgetError(self, widget, has_error: bool) -> None:
        if not widget:
            return
        border_style = "border: 1px solid #C62828;" if has_error else ""
        class_name = widget.metaObject().className() if hasattr(widget, "metaObject") else ""
        if class_name == "ctkPathLineEdit":
            widget.setStyleSheet(f"ctkPathLineEdit {{ {border_style} }}")
        else:
            widget.setStyleSheet(border_style)

    def _populateDeviceCombo(self) -> None:
        combo = getattr(self.ui, "deviceComboBox", None)
        if not combo:
            return
        current = combo.currentText if combo.count else "auto"
        combo.clear()
        combo.addItem("auto")
        combo.addItem("cpu")
        combo.addItem("cuda:0")
        index = combo.findText(current)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _onValidateClicked(self) -> None:
        self._save_common_user_settings()
        result = self._run_environment_dependency_check()
        if result is None:
            return
        self._update_environment_result_label(result)
        self._update_environment_path_status_labels(result)
        self._show_environment_results_dialog(result)
        self._update_environment_status(result)

    def _run_environment_dependency_check(self):
        node = self._parameterNode
        if not node or not self.logic:
            self.appendLog("Environment check failed. Parameter node or logic is unavailable.")
            self._setStatus("error", "Environment check failed")
            self._update_environment_result_label(None, error="Parameter node or logic is unavailable.")
            return None

        output_dir = (node.outputDirectory or "").strip()
        subject_root_text = (node.inputDirectory or "").strip()
        subject_root = Path(subject_root_text).expanduser() if subject_root_text else None
        if subject_root is not None and not subject_root.exists():
            self.appendLog(
                "[Environment] Subject root is not available yet; dependency report will be written outside the subject tree."
            )

        self.appendLog("Starting environment dependency check...")
        external_paths = self._environment_dependency_path_kwargs()
        kwargs = self._environment_check_kwargs(
            subject_root_text=subject_root_text,
            output_root_text=output_dir,
            external_paths=external_paths,
        )
        signature = self._environment_check_signature(kwargs)
        try:
            result = self.logic.runEnvironmentDependencyCheck(**kwargs)
        except Exception as exc:
            self.appendLog(f"Environment check failed: {exc}")
            self._setStatus("error", "Environment check failed")
            self._update_environment_result_label(None, error=str(exc))
            return None

        self._cache_environment_result(result, signature)
        self._remember_environment_report_dir(subject_root_text, output_dir)
        return result

    def _update_environment_status(self, result) -> None:
        self._update_onboarding_dashboard(result)
        if result.blocker_count:
            self._setStatus("error", f"Environment: {result.blocker_count} missing required item(s)")
        else:
            self._setStatus("ready", "Environment ready")

    def _missing_environment_items(self, result) -> list:
        return environment_missing_items(result)

    def _environment_summary_text(self, result) -> str:
        return environment_summary_text(result)

    def _environment_detail_lines(self, result) -> list[str]:
        return environment_detail_lines(result)

    def _update_environment_result_label(self, result, *, error: Optional[str] = None) -> None:
        label = getattr(self.ui, "environmentResultLabel", None)
        if not label:
            return
        if error:
            label.setText(f"Environment check failed: {error}")
            label.setStyleSheet("QLabel#environmentResultLabel { color: #C62828; padding-top: 4px; }")
            return
        if result is None:
            label.setText("No environment check has been run yet.")
            label.setStyleSheet("QLabel#environmentResultLabel { color: #546E7A; padding-top: 4px; }")
            return
        color = "#C62828" if result.blocker_count else "#2E7D32"
        label.setText(self._environment_summary_text(result))
        label.setStyleSheet(f"QLabel#environmentResultLabel {{ color: {color}; padding-top: 4px; }}")

    def _show_environment_results_dialog(self, result) -> None:
        show_environment_results_dialog(
            owner=self,
            result=result,
            python_install_target=self._python_install_target_text(),
            on_install_all=self._onInstallAllEnvironmentItemsClicked,
            on_show_notes=lambda: self._show_environment_install_notes(result),
            on_install_item=self._onInstallEnvironmentItemClicked,
        )

    def _build_environment_item_row(self, item):
        from shared.ui_environment_dialog import build_environment_item_row

        return build_environment_item_row(item, on_install_item=self._onInstallEnvironmentItemClicked)

    def _environment_item_text(self, item) -> str:
        return environment_item_text(item)

    def _onInstallAllEnvironmentItemsClicked(self) -> None:
        result = getattr(self, "_lastEnvironmentResult", None)
        if result is None:
            slicer.util.infoDisplay("Run the environment check first.", parent=self.parent)
            return
        model_missing = self._missing_model_resource_items(result)
        if result.missing_python_packages:
            self._install_python_packages_from_environment_dialog(tuple(result.missing_python_packages))
        if model_missing:
            self._install_model_assets_from_environment_dialog(profile="core")
        external_missing = [
            item
            for item in self._missing_environment_items(result)
            if (item.kind != "python" or not (item.details or {}).get("package"))
            and (item.install_group if hasattr(item, "install_group") else "") != "model-resources"
        ]
        if external_missing:
            slicer.util.infoDisplay(
                "System-level tools and application runtimes are not installed silently. Use each dependency row "
                "to choose an existing path, or open Manual setup notes for platform-specific instructions.",
                windowTitle="External tool setup",
                parent=self.parent,
            )

    def _onInstallEnvironmentItemClicked(self, item) -> None:
        package = (item.details or {}).get("package")
        if item.kind == "python" and package:
            self._install_python_packages_from_environment_dialog((package,))
            return
        if self._is_model_resource_item(item):
            self._install_model_assets_from_environment_dialog(profile="core")
            return
        if self._configure_path_for_environment_item(item):
            return
        self._show_environment_install_notes_for_item(item)

    def _install_python_packages_from_environment_dialog(self, packages: tuple[str, ...]) -> None:
        unique_packages = tuple(dict.fromkeys(package for package in packages if package and package.strip()))
        if not unique_packages:
            slicer.util.infoDisplay("No auto-installable Python packages are missing.", parent=self.parent)
            return
        if not self.logic:
            slicer.util.errorDisplay("Logic is unavailable; cannot install dependencies.", parent=self.parent)
            return

        self.appendLog("[Environment] Installing from UI: " + ", ".join(unique_packages))
        self._setStatus("running", "Installing Python dependencies...")
        progress = qt.QProgressDialog("Installing Python dependencies...", "Cancel", 0, len(unique_packages), slicer.util.mainWindow())
        progress.setWindowTitle("SlicerDDSurfer dependency install")
        progress.setWindowModality(qt.Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        def on_progress(index: int, total: int, message: str) -> None:
            progress.setMaximum(max(1, total))
            progress.setValue(max(0, min(index, total)))
            progress.setLabelText(message)
            slicer.app.processEvents()

        try:
            self.logic.installMissingPythonDependencies(unique_packages, progress_callback=on_progress)
            progress.setValue(len(unique_packages))
            self._save_python_install_status(tuple(unique_packages), "completed")
        except Exception as exc:
            self._save_python_install_status(tuple(unique_packages), "failed", str(exc))
            self.appendLog(f"[Environment] Dependency installation failed: {exc}")
            self._setStatus("error", "Dependency installation failed")
            self._show_actionable_error(
                title="Python Dependency Installation Failed",
                what="SlicerDDSurfer could not install the selected Python package(s).",
                why="pip returned an error, the selected Slicer Python is not writable, or the package is unavailable for this platform.",
                next_step="Use the generated install_missing_python script from the environment report, or install the package manually into Slicer Python.",
                auto_fix="Automatic Python install was attempted and failed. External tools are not installed automatically.",
                details=exc,
            )
            return
        finally:
            try:
                progress.close()
            except Exception:
                pass

        result = self._run_environment_dependency_check()
        if result is None:
            return
        self._update_environment_result_label(result)
        self._update_environment_path_status_labels(result)
        self._update_environment_status(result)
        self._show_environment_results_dialog(result)

    def _show_environment_install_notes(self, result) -> None:
        missing = [item for item in self._missing_environment_items(result) if item.kind != "python"]
        if not missing:
            slicer.util.infoDisplay("No manual setup items are missing.", parent=self.parent)
            return
        message = "\n\n".join(self._environment_item_text(item) for item in missing)
        slicer.util.infoDisplay(message, windowTitle="SlicerDDSurfer manual setup notes", parent=self.parent)

    def _show_environment_install_notes_for_item(self, item) -> None:
        slicer.util.infoDisplay(
            self._environment_item_text(item),
            windowTitle=f"Install / setup: {item.label}",
            parent=self.parent,
        )

    def _is_model_resource_item(self, item) -> bool:
        return str(getattr(item, "install_group", "") or "") == "model-resources" or str(getattr(item, "key", "")).startswith(
            "path:dd"
        )

    def _missing_model_resource_items(self, result) -> list:
        return [item for item in self._missing_environment_items(result) if self._is_model_resource_item(item)]

    def _environment_setting_for_item(self, item) -> tuple[str | None, str]:
        key = str(getattr(item, "key", "") or "")
        group = str(getattr(item, "install_group", "") or "")
        if self._is_model_resource_item(item):
            return "model_assets_dir", "dir"
        if key == "env:freesurfer_home" or group == "freesurfer":
            return "postprocess_freesurfer_home", "dir"
        if group == "mrtrix":
            return "mrtrix_bin_dir", "dir"
        if group == "fsl":
            return "preprocessing_fsl_bin_dir", "dir"
        if group == "wma":
            return "wma_root", "dir"
        if group == "tractcloud":
            if "data" in key:
                return "tractcloud_data_dir", "dir"
            if "python" in key:
                return "tractcloud_python_executable", "file"
            return "tractcloud_root", "dir"
        if group == "slicer":
            return "slicer_executable", "file"
        if group == "slicer-dmri":
            return "fiber_tract_measurements_cli", "file"
        if "tract_querier" in key:
            return "tract_querier_root", "dir"
        return None, "dir"

    def _configure_path_for_environment_item(self, item) -> bool:
        setting_key, mode = self._environment_setting_for_item(item)
        if not setting_key:
            return False
        start = self._read_environment_path_setting(setting_key) or str(Path.home())
        if mode == "file":
            selected = qt.QFileDialog.getOpenFileName(
                slicer.util.mainWindow(),
                f"Choose {item.label}",
                start,
            )
            selected_text = selected[0] if isinstance(selected, tuple) else selected
        else:
            selected_text = qt.QFileDialog.getExistingDirectory(
                slicer.util.mainWindow(),
                f"Choose {item.label}",
                start,
            )
        selected_text = str(selected_text or "").strip()
        if not selected_text:
            return True
        self._save_environment_path_setting(setting_key, selected_text)
        line_edit = (getattr(self, "_environmentPathLineEdits", {}) or {}).get(setting_key)
        if line_edit:
            line_edit.setText(selected_text)
        self.appendLog(f"[Environment] Saved {setting_key}: {selected_text}")
        result = self._run_environment_dependency_check()
        if result is not None:
            self._show_environment_results_dialog(result)
        return True

    def _install_model_assets_from_environment_dialog(self, *, profile: str = "core") -> None:
        module = self._load_model_assets_module()
        repo_root = Path(__file__).resolve().parent.parent
        configured = self._environment_dependency_path_kwargs().get("model_assets_dir")
        default_root = configured if isinstance(configured, Path) and str(configured) else module.configured_model_assets_root()
        selected = qt.QFileDialog.getExistingDirectory(
            slicer.util.mainWindow(),
            "Choose SlicerDDSurfer model asset root",
            default_root.expanduser().as_posix(),
        )
        asset_root = Path(str(selected or default_root)).expanduser().resolve()
        if not asset_root:
            return
        self._save_environment_path_setting("model_assets_dir", asset_root.as_posix())
        line_edit = (getattr(self, "_environmentPathLineEdits", {}) or {}).get("model_assets_dir")
        if line_edit:
            line_edit.setText(asset_root.as_posix())

        progress = qt.QProgressDialog("Preparing model asset download...", "Cancel", 0, 0, slicer.util.mainWindow())
        progress.setWindowTitle("SlicerDDSurfer model assets")
        progress.setWindowModality(qt.Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        try:
            manifest = module.load_manifest(repo_root / "models" / "assets_manifest.json")
            plan = module.resolve_asset_plan(manifest, profile)
            self.appendLog(f"[Model assets] Downloading profile={profile} into {asset_root}")
            progress.setLabelText(f"Downloading model assets to {asset_root} ...")
            slicer.app.processEvents()
            module.download_asset_plan(
                asset_root,
                plan,
                manifest,
                source="url",
                source_ids=("slicerdsurfer_models_git",),
                base_urls=(),
                allow_planned_sources=False,
                force=False,
            )
            progress.setRange(0, 100)
            progress.setValue(80)
            progress.setLabelText("Verifying model asset checksums...")
            slicer.app.processEvents()
            verification = module.verify_asset_plan(asset_root, plan)
            if not verification.get("ok"):
                raise RuntimeError(json.dumps(verification, indent=2, sort_keys=True))
            progress.setValue(100)
        except Exception as exc:
            self.appendLog(f"[Model assets] Download/verification failed: {exc}")
            self._show_actionable_error(
                title="Model Asset Download Failed",
                what="SlicerDDSurfer could not download or verify the selected model assets.",
                why="The asset source may be unreachable, the selected directory may not be writable, or checksum verification failed.",
                next_step=(
                    "Choose a writable Model assets root, or run "
                    f"python3 scripts/download_model_assets.py --profile {profile} --asset-root {asset_root} "
                    "--source url --source-id slicerdsurfer_models_git in a terminal."
                ),
                auto_fix="No system-level software was modified. Only the selected model asset directory was targeted.",
                details=exc,
            )
            return
        finally:
            try:
                progress.close()
            except Exception:
                pass

        self._set_model_assets_status_text(f"Model assets profile={profile} verified at {asset_root}")
        result = self._run_environment_dependency_check()
        if result is not None:
            self._show_environment_results_dialog(result)

    def _setPipelineActive(self, active: bool) -> None:
        self._pipelineActive = active
        if active:
            if hasattr(self.ui, "applyButton"):
                self.ui.applyButton.enabled = False
            if hasattr(self.ui, "runSelectedButton"):
                self.ui.runSelectedButton.enabled = False
            if hasattr(self.ui, "validateButton"):
                self.ui.validateButton.enabled = False
            if getattr(self, "_cancelRunButton", None):
                self._cancelRunButton.enabled = True
            self._setStatus("running", "Running pipeline...")
            self._lastStatusMessage = "Running pipeline..."
        else:
            if hasattr(self.ui, "runSelectedButton"):
                self.ui.runSelectedButton.enabled = True
            self.validateInputs(manual=False)
            if getattr(self, "_cancelRunButton", None):
                self._cancelRunButton.enabled = False
