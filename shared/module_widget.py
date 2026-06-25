"""Common scripted-module widget glue for SlicerDDSurfer."""

from __future__ import annotations

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
from shared.ui_error_dialogs import format_actionable_error_message
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
from shared.ui_styles import (
    RUN_STATUS_TABLE_STYLE,
    SLICERDDSURFER_UI_STYLE,
    run_summary_label_style,
)
from shared.ui_run_status_panel import (
    install_run_status_panel,
    mark_unfinished_rows,
    set_run_status_table_rows,
    table_item,
    update_run_status_table_item,
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
        return (
            ("subjectId", str),
            ("inputDirectory", str),
            ("outputDirectory", str),
            ("orchestrationRunName", str),
            ("orchestrationTractographyBackend", str),
            ("orchestrationBundleBackend", str),
            ("orchestrationSelectStreamlines", int),
            ("orchestrationMicrostructureStages", str),
            ("connectomeBackend", str),
            ("connectomeCompressMrtrixDense", bool),
            ("autoInstallPythonDependencies", bool),
            ("batchMode", bool),
            ("batchRoot", str),
            ("batchSize", int),
            ("batchArrangeInputs", str),
            ("targetPreprocessing", bool),
            ("targetSurface", bool),
            ("targetParcellation", bool),
            ("targetSegmentation", bool),
            ("targetMicrostructure", bool),
            ("targetTractography", bool),
            ("targetBundles", bool),
            ("targetConnectome", bool),
        )

    def _coerce_user_setting_value(self, value: Any, value_type: type) -> Any:
        if value_type is bool:
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "on"}
        if value_type is int:
            return int(value)
        return str(value or "")

    def _restore_common_user_settings_to_node(self) -> None:
        node = self._parameterNode
        if not node:
            return
        settings = slicer.app.userSettings()
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
        message = format_actionable_error_message(
            title=title,
            what=what,
            why=why,
            next_step=next_step,
            auto_fix=auto_fix,
            details=details,
        )
        slicer.util.errorDisplay(message, parent=self.parent)

    def _initialize_environment_dependency_path_controls(self) -> None:
        if getattr(self, "_environmentPathLineEdits", None) is not None:
            return
        environment_layout = getattr(self.ui, "environmentLayout", None)
        if not environment_layout:
            return
        install_environment_dependency_path_controls(self, environment_layout)

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
        self._open_local_path(
            Path(__file__).resolve().parent.parent / "MODEL_ASSETS.md",
            missing_message="MODEL_ASSETS.md is not available in the current repository checkout.",
        )

    def _on_open_model_assets_manifest_clicked(self) -> None:
        self._open_local_path(
            Path(__file__).resolve().parent.parent / "models" / "assets_manifest.json",
            missing_message="models/assets_manifest.json is not available in the current repository checkout.",
        )

    def _on_open_model_asset_terms_clicked(self) -> None:
        self._open_local_path(
            Path(__file__).resolve().parent.parent / "MODEL_ASSET_TERMS.md",
            missing_message="MODEL_ASSET_TERMS.md is not available in the current repository checkout.",
        )

    def _on_open_release_notes_clicked(self) -> None:
        self._open_local_path(
            Path(__file__).resolve().parent.parent / "RELEASE_NOTES_v0.1.0.md",
            missing_message="RELEASE_NOTES_v0.1.0.md is not available in the current repository checkout.",
        )

    def _on_show_model_asset_provenance_clicked(self) -> None:
        slicer.util.infoDisplay(
            model_assets_provenance_text(Path(__file__).resolve().parent.parent),
            windowTitle="SlicerDDSurfer model asset provenance",
            parent=self.parent,
        )

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
        log_widget = getattr(self.ui, "logPlainTextEdit", None)
        if not log_widget:
            return
        log_widget.setToolTip(
            f"Live background log. The UI keeps the latest {self._logLineLimit} lines to avoid slowing long runs."
        )
        try:
            log_widget.maximumBlockCount = int(self._logLineLimit)
        except Exception:
            pass
        try:
            log_widget.setMaximumBlockCount(int(self._logLineLimit))
        except Exception:
            try:
                log_widget.document().setMaximumBlockCount(int(self._logLineLimit))
            except Exception:
                pass
        try:
            log_widget.setLineWrapMode(qt.QPlainTextEdit.NoWrap)
        except Exception:
            pass

    def _apply_slicerddsurfer_ui_style(self) -> None:
        root_widget = getattr(self, "_uiWidget", None)
        try:
            if root_widget:
                root_widget.setStyleSheet(SLICERDDSURFER_UI_STYLE)
        except Exception:
            try:
                self.parent.setStyleSheet(SLICERDDSURFER_UI_STYLE)
            except Exception:
                pass
        table = getattr(self, "_runStatusTable", None)
        if table:
            table.setStyleSheet(RUN_STATUS_TABLE_STYLE)
            try:
                table.verticalHeader().setVisible(False)
            except Exception:
                pass

    def _set_run_progress_message(self, message: str) -> None:
        label = getattr(self, "_runStatusHintLabel", None)
        if label:
            label.setText(message)
        slicer.util.showStatusMessage(message, 3000)

    def _set_run_summary_message(self, message: str, state: str = "") -> None:
        label = getattr(self, "_runSummaryLabel", None)
        if not label:
            return
        label.setText(message or "Run summary is not available yet.")
        label.setStyleSheet(run_summary_label_style(state))

    def _run_summary_from_manifest(self, manifest: dict[str, Any]) -> tuple[str, str]:
        return run_summary_from_manifest(manifest)

    def _set_run_summary_from_manifest(self, manifest: dict[str, Any], fallback: str = "") -> None:
        message, status = self._run_summary_from_manifest(manifest)
        if message:
            self._set_run_summary_message(message, status)
        elif fallback:
            self._set_run_summary_message(fallback, "unknown")

    def _set_latest_report_path(self, report_path: str | Path | None) -> None:
        path = Path(str(report_path)).expanduser() if report_path else None
        if path is not None and not path.is_file():
            path = None
        self._latestReportPath = path
        button = getattr(self, "_runReportButton", None)
        if button:
            button.enabled = bool(path)

    def _set_latest_output_tree_path(self, report_path: str | Path | None) -> None:
        path = Path(str(report_path)).expanduser() if report_path else None
        if path is not None and not path.is_file():
            path = None
        self._latestOutputTreePath = path
        button = getattr(self, "_runOutputTreeButton", None)
        if button:
            button.enabled = bool(path)

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
            atlas_path = self.resourcePath("Data/100HCP-population-mean-T2.nii.gz")
            if atlas_path and os.path.exists(atlas_path):
                self._parameterNode.ddparcelAtlasPath = atlas_path

        ddseg_weights_dir = self.logic.segmentation_dir / "weights"
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
        if hasattr(self.ui, "logPlainTextEdit"):
            self.ui.logPlainTextEdit.appendPlainText(text)
            self._logAppendCount = int(getattr(self, "_logAppendCount", 0) or 0) + 1
            if self._logAppendCount % 100 == 0:
                self._trim_log_widget(self.ui.logPlainTextEdit)
            self.ui.logPlainTextEdit.ensureCursorVisible()
        if text.startswith("[Orchestrator] Running "):
            self._set_run_progress_message(text.replace("[Orchestrator] ", "", 1))
        now = monotonic()
        if now - float(getattr(self, "_lastProcessEventsAt", 0.0) or 0.0) < 0.15:
            return
        self._lastProcessEventsAt = now
        try:
            slicer.app.processEvents()
        except Exception:
            pass

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
            try:
                if process and process.state() != qt.QProcess.NotRunning:
                    slicer.util.infoDisplay("A SlicerDDSurfer job is already running.", parent=self.parent)
                    return
            except Exception:
                pass

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
        self._backgroundRunContext = {
            "subject_id": common_run_kwargs["subject_id"],
            "subject_root": common_run_kwargs["subject_root"],
            "output_root": common_run_kwargs.get("output_root"),
            "run_name": common_run_kwargs["run_name"],
            "targets": common_run_kwargs["targets"],
            "started_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "selected_workflows": selected_workflows,
        }
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
            try:
                if process and process.state() != qt.QProcess.NotRunning:
                    slicer.util.infoDisplay("A SlicerDDSurfer job is already running.", parent=self.parent)
                    return
            except Exception:
                pass

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
        self._backgroundRunContext = {
            "subject_id": "batch",
            "subject_root": batch_root,
            "output_root": common_run_kwargs.get("output_root"),
            "run_name": common_run_kwargs["run_name"],
            "targets": common_run_kwargs["targets"],
            "started_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "selected_workflows": selected_workflows,
            "batch_size": batch_size,
        }
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
        return doctor_result

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
        label = getattr(self.ui, "statusLabel", None)
        if not label:
            return
        progress = getattr(self.ui, "statusProgressBar", None)
        palette = {
            "ready": "#2E7D32",
            "running": "#1565C0",
            "waiting": "#EF6C00",
            "warning": "#EF6C00",
            "error": "#C62828",
        }
        color = palette.get(kind, palette["error"])
        label.setText(message)
        label.setStyleSheet(
            f"background-color: {color}; color: white; padding: 4px 10px; border-radius: 6px; font-weight: 600;"
        )
        if not progress:
            return
        if kind == "running":
            progress.setRange(0, 0)
        elif kind == "ready":
            progress.setRange(0, 100)
            progress.setValue(100)
        else:
            progress.setRange(0, 100)
            progress.setValue(0)

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
        return result

    def _update_environment_status(self, result) -> None:
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
        self._install_python_packages_from_environment_dialog(tuple(result.missing_python_packages))

    def _onInstallEnvironmentItemClicked(self, item) -> None:
        package = (item.details or {}).get("package")
        if item.kind == "python" and package:
            self._install_python_packages_from_environment_dialog((package,))
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
        try:
            self.logic.installMissingPythonDependencies(unique_packages)
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
