"""Common scripted-module widget glue for SlicerDDSurfer."""

from __future__ import annotations

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from time import monotonic
from typing import Any, List, Optional

import qt
import slicer
import vtk
from qt import QPixmap, QSignalBlocker

from shared import blocked_target_reasons, normalize_orchestrator_targets


ENVIRONMENT_DEPENDENCY_PATHS: tuple[dict[str, str], ...] = (
    {
        "id": "mrtrix_bin_dir",
        "label": "MRtrix3 bin dir",
        "section": "core-runtime",
        "mode": "dir",
        "tooltip": "Optional. Directory containing mrconvert, dwi2response, dwi2fod, tckgen, tcksift2.",
    },
    {
        "id": "preprocessing_fsl_bin_dir",
        "label": "FSL bin dir",
        "section": "core-runtime",
        "mode": "dir",
        "tooltip": "Optional. Directory containing eddy and topup for MRtrix/FSL preprocessing.",
    },
    {
        "id": "postprocess_freesurfer_home",
        "label": "FreeSurfer home",
        "section": "core-runtime",
        "mode": "dir",
        "tooltip": "Optional. FreeSurfer installation root. FREESURFER_HOME is also detected.",
    },
    {
        "id": "tract_querier_root",
        "label": "TractQuerier root",
        "section": "core-runtime",
        "mode": "dir",
        "tooltip": "Optional. Checkout root used by WMQL when tract_querier is not installed in Slicer Python.",
    },
    {
        "id": "wma_root",
        "label": "WMA root",
        "section": "bundle-backends",
        "mode": "dir",
        "tooltip": "Optional. External WhiteMatterAnalysis checkout root.",
    },
    {
        "id": "wma_atlas_dir",
        "label": "WMA ORG atlas dir",
        "section": "bundle-backends",
        "mode": "dir",
        "tooltip": "Optional. Directory containing ORG-RegAtlas-100HCP and ORG-800FC-100HCP.",
    },
    {
        "id": "slicer_executable",
        "label": "Slicer executable for WMA",
        "section": "bundle-backends",
        "mode": "file",
        "tooltip": "Optional. Slicer executable used by WMA/SlicerDMRI helper calls.",
    },
    {
        "id": "fiber_tract_measurements_cli",
        "label": "FiberTractMeasurements CLI",
        "section": "bundle-backends",
        "mode": "file",
        "tooltip": "Optional. SlicerDMRI FiberTractMeasurements CLI path.",
    },
    {
        "id": "tractcloud_root",
        "label": "TractCloud root",
        "section": "bundle-backends",
        "mode": "dir",
        "tooltip": "Optional. TractCloud package/check-out root.",
    },
    {
        "id": "tractcloud_python_executable",
        "label": "TractCloud Python",
        "section": "bundle-backends",
        "mode": "file",
        "tooltip": "Optional. Dedicated Python executable for TractCloud if not using Slicer Python.",
    },
    {
        "id": "tractcloud_data_dir",
        "label": "TractCloud data/model dir",
        "section": "bundle-backends",
        "mode": "dir",
        "tooltip": "Optional. TractCloud model/data directory.",
    },
)


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

    def _initialize_environment_dependency_path_controls(self) -> None:
        if getattr(self, "_environmentPathLineEdits", None) is not None:
            return
        environment_layout = getattr(self.ui, "environmentLayout", None)
        if not environment_layout:
            return

        self._environmentPathLineEdits = {}
        self._environmentPathStatusLabels = {}
        self._environmentBackendSectionLabels = {}
        self._environmentBackendSectionRows = {"wma": [], "tractcloud": []}
        python_target_label = qt.QLabel(self._python_install_target_text())
        python_target_label.setObjectName("environmentPythonTargetLabel")
        python_target_label.wordWrap = True
        python_target_label.setStyleSheet(
            "QLabel { background: #F5F7F9; color: #455A64; padding: 6px; border-radius: 4px; }"
        )
        python_target_label.visible = False
        self._environmentPythonTargetLabel = python_target_label
        try:
            import ctk

            group_box = ctk.ctkCollapsibleButton()
            group_box.setObjectName("externalBackendsGroup")
            group_box.text = "External Runtime Paths"
            group_box.collapsed = True
            group_box.setToolTip(
                "Discovery order: saved path, environment variables, PATH, then common install paths. "
                "Leave fields empty to rely on automatic discovery."
            )
            form_layout = qt.QFormLayout(group_box)
        except Exception:
            group_box = qt.QGroupBox("External Runtime Paths")
            group_box.setObjectName("externalBackendsGroup")
            group_box.setToolTip(
                "Discovery order: saved path, environment variables, PATH, then common install paths. "
                "Leave fields empty to rely on automatic discovery."
            )
            form_layout = qt.QFormLayout(group_box)
        form_layout.setSpacing(8)
        form_layout.setContentsMargins(10, 10, 10, 10)
        self._environmentAdvancedPathsWidget = group_box
        group_box.setToolTip(
            "Discovery order: saved path, environment variables, PATH, then common install paths. "
            "Leave fields empty to rely on automatic discovery."
        )

        self._add_environment_section_header(
            form_layout,
            "Core Runtime Paths",
            "Configure the shared external toolchain used by preprocessing, post-process, and WMQL. "
            "Leave empty to use saved settings, environment variables, PATH, and common install paths.",
        )
        for item in ENVIRONMENT_DEPENDENCY_PATHS:
            if item.get("section") != "core-runtime":
                continue
            dependency_id = item["id"]
            row = qt.QWidget()
            row_layout = qt.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            line_edit = qt.QLineEdit()
            line_edit.setText(self._read_environment_path_setting(dependency_id))
            line_edit.setPlaceholderText("Auto-detect if empty")
            line_edit.setToolTip(item["tooltip"])
            line_edit.editingFinished.connect(
                lambda dependency_id=dependency_id, line_edit=line_edit: self._on_environment_dependency_path_edited(
                    dependency_id,
                    line_edit,
                )
            )
            row_layout.addWidget(line_edit, 1)

            browse_button = qt.QPushButton("Browse...")
            browse_button.setToolTip(item["tooltip"])
            browse_button.connect(
                "clicked()",
                lambda item=item, line_edit=line_edit: self._browse_environment_dependency_path(item, line_edit),
            )
            row_layout.addWidget(browse_button)

            clear_button = qt.QPushButton("Clear")
            clear_button.connect(
                "clicked()",
                lambda dependency_id=dependency_id, line_edit=line_edit: self._clear_environment_dependency_path(
                    dependency_id,
                    line_edit,
                ),
            )
            row_layout.addWidget(clear_button)

            status_label = qt.QLabel("not checked")
            status_label.setMinimumWidth(130)
            status_label.setStyleSheet("QLabel { color: #78909C; }")
            row_layout.addWidget(status_label)

            form_layout.addRow(item["label"], row)
            self._environmentPathLineEdits[dependency_id] = line_edit
            self._environmentPathStatusLabels[dependency_id] = status_label

        self._add_model_assets_row(form_layout)

        self._add_environment_section_header(
            form_layout,
            "Optional Backend Paths",
            "WMA and TractCloud are optional bundle-extraction backends. Keep them grouped here instead of mixing "
            "them with the core runtime toolchain.",
        )
        for item in ENVIRONMENT_DEPENDENCY_PATHS:
            if item.get("section") != "bundle-backends":
                continue
            dependency_id = item["id"]
            if item.get("section") == "bundle-backends" and dependency_id == "wma_root":
                self._environmentBackendSectionLabels["wma"] = self._add_environment_subsection_label(
                    form_layout,
                    "WMA Paths",
                    "WhiteMatterAnalysis checkout, ORG atlas, and helper Slicer/CLI paths.",
                )
            if item.get("section") == "bundle-backends" and dependency_id == "tractcloud_root":
                self._environmentBackendSectionLabels["tractcloud"] = self._add_environment_subsection_label(
                    form_layout,
                    "TractCloud Paths",
                    "TractCloud checkout, Python runtime, and model/data directory.",
                )
            row = qt.QWidget()
            row_layout = qt.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            line_edit = qt.QLineEdit()
            line_edit.setText(self._read_environment_path_setting(dependency_id))
            line_edit.setPlaceholderText("Auto-detect if empty")
            line_edit.setToolTip(item["tooltip"])
            line_edit.editingFinished.connect(
                lambda dependency_id=dependency_id, line_edit=line_edit: self._on_environment_dependency_path_edited(
                    dependency_id,
                    line_edit,
                )
            )
            row_layout.addWidget(line_edit, 1)

            browse_button = qt.QPushButton("Browse...")
            browse_button.setToolTip(item["tooltip"])
            browse_button.connect(
                "clicked()",
                lambda item=item, line_edit=line_edit: self._browse_environment_dependency_path(item, line_edit),
            )
            row_layout.addWidget(browse_button)

            clear_button = qt.QPushButton("Clear")
            clear_button.connect(
                "clicked()",
                lambda dependency_id=dependency_id, line_edit=line_edit: self._clear_environment_dependency_path(
                    dependency_id,
                    line_edit,
                ),
            )
            row_layout.addWidget(clear_button)

            status_label = qt.QLabel("not checked")
            status_label.setMinimumWidth(130)
            status_label.setStyleSheet("QLabel { color: #78909C; }")
            row_layout.addWidget(status_label)

            form_layout.addRow(item["label"], row)
            self._environmentPathLineEdits[dependency_id] = line_edit
            self._environmentPathStatusLabels[dependency_id] = status_label
            if dependency_id.startswith("wma_") or dependency_id in {"slicer_executable", "fiber_tract_measurements_cli"}:
                self._environmentBackendSectionRows["wma"].append((line_edit, browse_button, clear_button, status_label))
            if dependency_id.startswith("tractcloud_"):
                self._environmentBackendSectionRows["tractcloud"].append((line_edit, browse_button, clear_button, status_label))

        config_buttons = qt.QHBoxLayout()
        import_button = qt.QPushButton("Import dependency config")
        import_button.setToolTip("Load a SlicerDDSurfer dependency config JSON and save the external paths into Slicer settings.")
        import_button.connect("clicked()", self._on_import_dependency_config_clicked)
        export_button = qt.QPushButton("Export dependency config")
        export_button.setToolTip("Save the currently configured external paths as a CLI-compatible JSON config.")
        export_button.connect("clicked()", self._on_export_dependency_config_clicked)
        self._environmentImportConfigButton = import_button
        self._environmentExportConfigButton = export_button
        config_buttons.addWidget(import_button)
        config_buttons.addWidget(export_button)
        config_buttons.addStretch(1)
        form_layout.addRow("Config", config_buttons)

        try:
            insert_index = max(0, environment_layout.count() - 1)
            environment_layout.insertWidget(insert_index, python_target_label)
            insert_index += 1
            environment_layout.insertWidget(insert_index, group_box)
        except Exception:
            environment_layout.addWidget(python_target_label)
            environment_layout.addWidget(group_box)

    def _add_environment_section_header(self, form_layout, title: str, description: str) -> None:
        title_label = qt.QLabel(title)
        title_label.setObjectName("externalSectionTitleLabel")
        title_label.setStyleSheet(
            "QLabel { background: #EAF3ED; border: 1px solid #CFE1D5; border-radius: 8px; "
            "color: #183F2E; font-weight: 700; padding: 8px 10px; }"
        )
        description_label = qt.QLabel(description)
        description_label.setObjectName("externalSectionDescriptionLabel")
        description_label.wordWrap = True
        description_label.setStyleSheet("QLabel { color: #5C7168; padding: 2px 8px 8px 10px; }")
        form_layout.addRow(title_label)
        form_layout.addRow("", description_label)

    def _add_environment_subsection_label(self, form_layout, title: str, description: str):
        title_label = qt.QLabel(title)
        title_label.setObjectName("externalSubsectionTitleLabel")
        title_label.setStyleSheet(
            "QLabel { background: #F4F8F5; border: 1px solid #DDEAE2; border-radius: 7px; "
            "color: #315843; font-weight: 700; padding: 7px 9px; }"
        )
        description_label = qt.QLabel(description)
        description_label.setObjectName("externalSubsectionDescriptionLabel")
        description_label.wordWrap = True
        description_label.setStyleSheet("QLabel { color: #6A7D74; padding: 1px 8px 5px 9px; }")
        form_layout.addRow(title_label)
        form_layout.addRow("", description_label)
        return (title_label, description_label)

    def _add_model_assets_row(self, form_layout) -> None:
        self._add_environment_section_header(
            form_layout,
            "Model assets",
            "DDSurfer, DDParcel, and DDSeg weights/templates are managed together from one manifest instead of "
            "being configured as separate external paths.",
        )
        row = qt.QWidget()
        row_layout = qt.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        summary = qt.QLabel(self._model_assets_summary_text())
        summary.setObjectName("modelAssetsSummaryLabel")
        summary.wordWrap = True
        summary.setStyleSheet(
            "QLabel { background: #F7FAF8; border: 1px solid #D8E4DD; border-radius: 6px; color: #355244; padding: 6px; }"
        )
        row_layout.addWidget(summary, 1)

        guide_button = qt.QPushButton("Open guide")
        guide_button.setToolTip("Open MODEL_ASSETS.md for unified model weights/template download and verification.")
        guide_button.connect("clicked()", self._on_open_model_assets_guide_clicked)
        row_layout.addWidget(guide_button)

        manifest_button = qt.QPushButton("Open manifest")
        manifest_button.setToolTip("Open models/assets_manifest.json.")
        manifest_button.connect("clicked()", self._on_open_model_assets_manifest_clicked)
        row_layout.addWidget(manifest_button)

        form_layout.addRow("Model assets bundle", row)

    def _model_assets_summary_text(self) -> str:
        manifest = Path(__file__).resolve().parent.parent / "models" / "assets_manifest.json"
        command = "python3 scripts/download_model_assets.py --profile core"
        return (
            "Unified source: models/assets_manifest.json. "
            "Default bundled resources are auto-detected from the repository. "
            f"Refresh or verify with `{command}`."
            if manifest.is_file()
            else f"Unified source expected at {manifest}. Refresh or verify with `{command}`."
        )

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

    def _python_install_target_text(self) -> str:
        executable = sys.executable or "unknown"
        return (
            "Python install target: current Slicer Python environment "
            f"({executable}). External tools are never installed silently."
        )

    def _environment_dependency_config_payload(self) -> dict[str, object]:
        widgets = getattr(self, "_environmentPathLineEdits", {}) or {}
        external_dependencies = {}
        for item in ENVIRONMENT_DEPENDENCY_PATHS:
            dependency_id = item["id"]
            widget = widgets.get(dependency_id)
            value = self._line_edit_text(widget) if widget else self._read_environment_path_setting(dependency_id)
            if value:
                external_dependencies[dependency_id] = value
        return {
            "kind": "slicerdsurfer_dependency_config",
            "version": 1,
            "python_install_target": sys.executable or "",
            "external_dependencies": external_dependencies,
        }

    def _apply_environment_dependency_config(self, payload: dict[str, object]) -> int:
        data = payload.get("external_dependencies", payload)
        if not isinstance(data, dict):
            raise ValueError("Dependency config must contain an external_dependencies object.")
        widgets = getattr(self, "_environmentPathLineEdits", {}) or {}
        applied = 0
        for item in ENVIRONMENT_DEPENDENCY_PATHS:
            dependency_id = item["id"]
            value = str(data.get(dependency_id) or "").strip()
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
            slicer.util.errorDisplay(f"Failed to import dependency config:\n{exc}", parent=self.parent)
            return
        self.appendLog(f"[Environment] Imported dependency config: {path} ({applied} path(s))")
        slicer.util.infoDisplay(f"Imported {applied} dependency path(s). Run Check environment dependencies next.", parent=self.parent)

    def _initialize_run_status_panel(self) -> None:
        if getattr(self, "_runStatusTable", None) is not None:
            return
        configuration_layout = getattr(self.ui, "configurationLayout", None)
        if not configuration_layout:
            return
        try:
            import ctk

            panel = ctk.ctkCollapsibleButton()
            panel.text = "Run Plan & Progress"
            panel.collapsed = False
            panel_layout = qt.QVBoxLayout(panel)
        except Exception:
            panel = qt.QGroupBox("Run Plan & Progress")
            panel_layout = qt.QVBoxLayout(panel)

        hint = qt.QLabel("Run plan has not been generated yet.")
        hint.setWordWrap(True)
        hint.setStyleSheet("QLabel { color: #546E7A; }")
        panel_layout.addWidget(hint)

        summary = qt.QLabel("Run summary will appear after a plan or run completes.")
        summary.wordWrap = True
        summary.setObjectName("runSummaryLabel")
        panel_layout.addWidget(summary)

        report_button = qt.QPushButton("Open latest report")
        report_button.enabled = False
        report_button.setToolTip("Open the latest generated SlicerDDSurfer HTML report.")
        report_button.connect("clicked()", self._on_open_latest_report_clicked)
        panel_layout.addWidget(report_button)

        output_tree_button = qt.QPushButton("Open output tree")
        output_tree_button.enabled = False
        output_tree_button.setToolTip("Open the latest annotated SlicerDDSurfer output-tree HTML report.")
        output_tree_button.connect("clicked()", self._on_open_output_tree_report_clicked)
        panel_layout.addWidget(output_tree_button)

        table = qt.QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Target", "State", "Reason", "Manifest", "QC", "Logs"])
        table.setMinimumHeight(150)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(qt.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        try:
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(0, qt.QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, qt.QHeaderView.ResizeToContents)
        except Exception:
            pass
        table.cellDoubleClicked.connect(self._on_run_status_table_double_clicked)
        panel_layout.addWidget(table)

        try:
            insert_index = max(0, configuration_layout.count() - 1)
            configuration_layout.insertWidget(insert_index, panel)
        except Exception:
            configuration_layout.addWidget(panel)

        self._runStatusPanel = panel
        self._runStatusHintLabel = hint
        self._runSummaryLabel = summary
        self._runReportButton = report_button
        self._runOutputTreeButton = output_tree_button
        self._latestReportPath = None
        self._latestOutputTreePath = None
        self._runStatusTable = table

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
        targets = [target for target in self._selected_product_targets() if target != "validation"]
        if targets:
            target_text = ", ".join(targets)
        else:
            target_text = "none"
        freewater, noddi = self._microstructure_stage_flags()
        micro_stages = ["dti"]
        if freewater:
            micro_stages.append("freewater")
        if noddi:
            micro_stages.append("noddi")
        text = (
            f"Selected targets: {target_text}\n"
            f"Backends: preprocessing={(self._parameterNode.preprocessingBackend or 'dipy').strip() or 'dipy'}, "
            f"tractography={self._tractography_backend_text()}, bundles={self._bundle_backend_text()}, "
            f"microstructure={','.join(micro_stages)}, "
            f"connectome={(self._parameterNode.connectomeBackend or 'python').strip() or 'python'}"
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
        style = """
        QFrame#headerFrame {
          background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F2F8F4, stop:1 #E9F2F5);
          border: 1px solid #CBD8D2;
          border-radius: 10px;
          padding: 14px;
        }
        QLabel#headlineLabel {
          color: #163526;
          font-size: 21px;
          font-weight: 700;
        }
        QWidget#externalBackendsGroup,
        ctkCollapsibleButton#externalBackendsGroup,
        QGroupBox#externalBackendsGroup {
          background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FCFEFC, stop:1 #F4F8F5);
          border: 1px solid #CADBD0;
          border-radius: 14px;
          padding: 8px;
        }
        QLabel#subtitleLabel,
        QLabel#environmentHintLabel,
        QLabel#logHintLabel {
          color: #536B61;
          font-size: 12px;
        }
        QLabel#externalSectionTitleLabel {
          background: #EAF3ED;
          border: 1px solid #CFE1D5;
          border-radius: 8px;
          color: #183F2E;
          font-size: 14px;
          font-weight: 700;
          padding: 8px 10px;
        }
        QLabel#externalSectionDescriptionLabel {
          color: #5C7168;
          font-size: 11px;
          padding: 2px 8px 8px 10px;
        }
        QLabel#externalSubsectionTitleLabel {
          background: #F4F8F5;
          border: 1px solid #DDEAE2;
          border-radius: 7px;
          color: #315843;
          font-size: 12px;
          font-weight: 700;
          padding: 7px 9px;
        }
        QLabel#externalSubsectionDescriptionLabel {
          color: #6A7D74;
          font-size: 11px;
          padding: 1px 8px 5px 9px;
        }
        QLabel#modelAssetsSummaryLabel {
          background-color: #F6FAF7;
          border: 1px solid #D6E3DA;
          border-radius: 8px;
          color: #294B3B;
          padding: 8px 10px;
          font-size: 11px;
        }
        QWidget#externalBackendsGroup QLineEdit {
          background: white;
          border: 1px solid #CBD8D0;
          border-radius: 8px;
          padding: 7px 10px;
          min-height: 20px;
        }
        QWidget#externalBackendsGroup QLineEdit:focus {
          border: 1px solid #2D7C92;
          background: #FCFEFD;
        }
        QWidget#externalBackendsGroup QPushButton {
          border: 1px solid #CFDCD4;
          border-radius: 8px;
          padding: 6px 12px;
          background: #FFFFFF;
          color: #31503F;
        }
        QWidget#externalBackendsGroup QPushButton:hover:!disabled {
          background: #F0F6F2;
          border: 1px solid #BCD3C4;
        }
        QLabel#selectedProductsSummaryLabel {
          background-color: #F8FBF8;
          border: 1px solid #D6E3DA;
          border-left: 4px solid #1D6C45;
          border-radius: 7px;
          color: #294B3B;
          padding: 8px 10px;
          font-family: "Menlo", "Consolas", monospace;
          font-size: 11px;
        }
        QLabel#runSummaryLabel {
          background-color: #F7FAF8;
          border: 1px solid #D8E4DD;
          border-left: 4px solid #6B7E73;
          border-radius: 7px;
          color: #2F4038;
          padding: 7px 9px;
          font-size: 11px;
        }
        QPushButton#runSelectedButton {
          background-color: #1D6C45;
          border: 1px solid #155336;
          border-radius: 7px;
          color: white;
          font-weight: 700;
          padding: 8px 16px;
        }
        QPushButton#runSelectedButton:hover:!disabled {
          background-color: #155336;
        }
        QPushButton#validateButton {
          background-color: transparent;
          border: 1px solid #2D7C92;
          border-radius: 7px;
          color: #2D7C92;
          font-weight: 600;
          padding: 6px 12px;
        }
        QPushButton#validateButton:hover:!disabled {
          background-color: rgba(45, 124, 146, 0.10);
        }
        QPushButton#clearLogButton {
          background-color: transparent;
          border: 1px solid #B8C6C0;
          border-radius: 6px;
          color: #43594F;
          padding: 4px 9px;
        }
        QPushButton#clearLogButton:hover:!disabled {
          background-color: rgba(184, 198, 192, 0.28);
        }
        QPlainTextEdit#logPlainTextEdit {
          background-color: #132018;
          border: 1px solid #2E4B39;
          border-radius: 8px;
          color: #E5F0DF;
          font-family: "Menlo", "Consolas", monospace;
          font-size: 11px;
          selection-background-color: #2D7C92;
        }
        """
        root_widget = getattr(self, "_uiWidget", None)
        try:
            if root_widget:
                root_widget.setStyleSheet(style)
        except Exception:
            try:
                self.parent.setStyleSheet(style)
            except Exception:
                pass
        table = getattr(self, "_runStatusTable", None)
        if table:
            table.setStyleSheet(
                "QTableWidget { background: #FBFCFA; alternate-background-color: #F2F6F3; "
                "gridline-color: #D7E0DA; selection-background-color: #DCEBE2; selection-color: #163526; } "
                "QHeaderView::section { background: #E6EFE9; color: #294B3B; font-weight: 700; padding: 5px; border: 0; }"
            )
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
        palette = {
            "completed": ("#F0FAF3", "#1D6C45", "#174D32"),
            "passed": ("#F0FAF3", "#1D6C45", "#174D32"),
            "skipped": ("#F3F7F4", "#6B7E73", "#2F4038"),
            "planned": ("#EEF6FF", "#2D7C92", "#163E50"),
            "running": ("#EEF6FF", "#2D7C92", "#163E50"),
            "partial": ("#FFF8EA", "#E28A11", "#6B3F00"),
            "blocked": ("#FFF3E8", "#EF6C00", "#6B3F00"),
            "failed": ("#FDECEC", "#C62828", "#6B1A1A"),
            "cancelled": ("#FFF3E8", "#EF6C00", "#6B3F00"),
            "unknown": ("#F3F7F4", "#6B7E73", "#2F4038"),
        }
        background, accent, text = palette.get(state, palette["unknown"])
        label.setText(message or "Run summary is not available yet.")
        label.setStyleSheet(
            "QLabel#runSummaryLabel { "
            f"background-color: {background}; border: 1px solid #D8E4DD; "
            f"border-left: 4px solid {accent}; border-radius: 7px; color: {text}; "
            "padding: 7px 9px; font-size: 11px; }"
        )

    def _run_summary_from_manifest(self, manifest: dict[str, Any]) -> tuple[str, str]:
        report_paths = manifest.get("report_paths") or {}
        qc_path = ""
        if isinstance(report_paths, dict):
            qc_path = str(report_paths.get("qc_summary_json_latest") or report_paths.get("qc_summary_json") or "")
        if not qc_path:
            return "", ""
        path = Path(qc_path).expanduser()
        if not path.is_file():
            return "", ""
        try:
            qc_summary = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return f"Report summary unavailable: {exc}", "unknown"
        summary = qc_summary.get("summary") if isinstance(qc_summary, dict) else {}
        if not isinstance(summary, dict):
            return "", ""
        status = str(summary.get("status") or "unknown")
        interpretation = str(summary.get("interpretation") or "").strip()
        elapsed = str(summary.get("elapsed_time") or "").strip()
        tasks = summary.get("tasks") if isinstance(summary.get("tasks"), dict) else {}
        task_text = ", ".join(f"{key}={value}" for key, value in sorted(tasks.items())) if tasks else "no task counts"
        parts = [f"Status: {status}", f"Tasks: {task_text}"]
        if elapsed:
            parts.append(f"Elapsed: {elapsed}")
        if interpretation:
            parts.append(interpretation)
        return " | ".join(parts), status

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
        item = qt.QTableWidgetItem(text or "")
        if text:
            item.setToolTip(text)
        if state:
            colors = {
                "queued": qt.QColor("#546E7A"),
                "running": qt.QColor("#1565C0"),
                "will_run": qt.QColor("#1565C0"),
                "completed": qt.QColor("#2E7D32"),
                "passed": qt.QColor("#2E7D32"),
                "skipped": qt.QColor("#546E7A"),
                "blocked": qt.QColor("#C62828"),
                "failed": qt.QColor("#C62828"),
                "cancelled": qt.QColor("#EF6C00"),
            }
            color = colors.get(state)
            if color:
                item.setForeground(color)
        return item

    def _set_run_status_table_rows(self, rows: list[dict[str, str]]) -> None:
        table = getattr(self, "_runStatusTable", None)
        if not table:
            return
        try:
            table.setUpdatesEnabled(False)
        except Exception:
            pass
        try:
            table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                state = row.get("status", "")
                values = [
                    row.get("target") or row.get("name") or "",
                    state,
                    row.get("reason", ""),
                    row.get("manifest_path", ""),
                    row.get("qc_path", ""),
                    row.get("logs_dir", ""),
                ]
                for col, value in enumerate(values):
                    table.setItem(row_index, col, self._table_item(str(value or ""), state))
            table.resizeRowsToContents()
        finally:
            try:
                table.setUpdatesEnabled(True)
            except Exception:
                pass

    def _update_run_status_table_item(self, key_candidates: tuple[str, ...], status: str, reason: str = "") -> None:
        table = getattr(self, "_runStatusTable", None)
        if not table:
            return
        keys = {key for key in key_candidates if key}
        for row in range(table.rowCount):
            target_item = table.item(row, 0)
            if not target_item:
                continue
            target = str(target_item.text() if callable(getattr(target_item, "text", None)) else target_item.text)
            if target not in keys:
                continue
            try:
                table.setUpdatesEnabled(False)
            except Exception:
                pass
            try:
                table.setItem(row, 1, self._table_item(status, status))
                if reason:
                    table.setItem(row, 2, self._table_item(reason, status))
                try:
                    table.resizeRowToContents(row)
                except Exception:
                    table.resizeRowsToContents()
            finally:
                try:
                    table.setUpdatesEnabled(True)
                except Exception:
                    pass
            return

    def _task_keys_for_running_line(self, line: str) -> tuple[str, ...]:
        lowered = line.lower()
        if "dwi preprocessing" in lowered:
            return ("preprocessing", "preprocessing.dwi")
        if "ddseg" in lowered:
            return ("segmentation", "segmentation.ddseg")
        if "ddparcel" in lowered:
            return ("parcellation", "parcellation.ddparcel")
        if "ddsurfer surface" in lowered:
            return ("surface", "surface.ddsurfer")
        if "ddsurfer postprocess" in lowered:
            return ("surface_postprocess", "surface.ddsurfer_postprocess")
        if "microstructure" in lowered:
            return ("microstructure", "microstructure.dti")
        if "csd/act" in lowered:
            return ("tractography", "tractography.csd_act")
        if "dti tractography" in lowered:
            return ("tractography", "tractography.dti_det")
        if "wmql" in lowered:
            return ("bundles", "bundles.wmql")
        if "saf" in lowered:
            return ("saf", "tractography.saf")
        if "wma" in lowered:
            return ("wma", "bundles.wma")
        if "tractcloud" in lowered:
            return ("tractcloud", "bundles.tractcloud")
        if "connectome" in lowered:
            return ("connectome", "connectome.streamline_count")
        return ()

    def _update_run_plan_table(self, plan) -> None:
        rows = []
        for item in getattr(plan, "items", ()) or ():
            status = "queued" if item.status == "will_run" else item.status
            rows.append(
                {
                    "target": item.target,
                    "status": status,
                    "reason": item.reason,
                    "manifest_path": "",
                    "qc_path": "",
                    "logs_dir": "",
                }
            )
        summary = getattr(plan, "to_dict", lambda: {"summary": {}})().get("summary", {})
        self._set_run_status_table_rows(rows)
        blocked = int(summary.get("blocked", 0) or 0)
        will_run = int(summary.get("will_run", 0) or 0)
        skipped = int(summary.get("skipped", 0) or 0)
        plan_state = "blocked" if blocked and not (will_run or skipped) else ("partial" if blocked else "planned")
        self._set_run_summary_message(
            f"Plan: {will_run} will run, {skipped} skipped/reused, {blocked} blocked.",
            plan_state,
        )
        self._set_run_progress_message(
            f"Run plan ready: {summary.get('will_run', 0)} will run, "
            f"{summary.get('skipped', 0)} skipped, {summary.get('blocked', 0)} blocked."
        )

    def _update_run_result_table(self, result) -> None:
        rows = []
        manifest_data = {}
        try:
            manifest_data = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest_data = {}
        manifest_tasks = {task.get("name"): task for task in manifest_data.get("tasks", []) if isinstance(task, dict)}
        for task in getattr(result, "tasks", ()) or ():
            manifest_task = manifest_tasks.get(task.name, {})
            rows.append(
                {
                    "target": task.name,
                    "status": task.status,
                    "reason": task.reason,
                    "manifest_path": manifest_task.get("normalized_manifest_path") or (task.manifest_path.as_posix() if task.manifest_path else ""),
                    "qc_path": manifest_task.get("normalized_qc_path") or (task.qc_path.as_posix() if task.qc_path else ""),
                    "logs_dir": manifest_task.get("normalized_logs_dir", ""),
                }
            )
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

    def _environment_dependency_path_kwargs(self) -> dict[str, Optional[Path]]:
        widgets = getattr(self, "_environmentPathLineEdits", {}) or {}
        kwargs: dict[str, Optional[Path]] = {}
        for item in ENVIRONMENT_DEPENDENCY_PATHS:
            dependency_id = item["id"]
            widget = widgets.get(dependency_id)
            value = self._line_edit_text(widget) if widget else self._read_environment_path_setting(dependency_id)
            kwargs[dependency_id] = Path(value).expanduser() if value else None
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
        colors = {
            "available": "#2E7D32",
            "missing": "#C62828",
            "pending": "#EF6C00",
            "unchecked": "#78909C",
            "inactive": "#90A4AE",
        }
        label.setText(text)
        label.setStyleSheet(f"QLabel {{ color: {colors.get(state, colors['unchecked'])}; font-weight: 600; }}")

    def _path_status_dependencies(self, result, dependency_id: str) -> list:
        statuses = list(getattr(result, "statuses", ()) or ())
        command_groups = {
            "mrtrix_bin_dir": {
                "command:mrconvert",
                "command:dwi2response",
                "command:dwi2fod",
                "command:mtnormalise",
                "command:tckgen",
                "command:tcksift2",
                "command:tckstats",
                "command:tckconvert",
                "command:tck2connectome",
                "command:dwidenoise",
                "command:mrdegibbs",
                "command:dwifslpreproc",
            },
            "preprocessing_fsl_bin_dir": {"command:eddy", "command:topup"},
            "postprocess_freesurfer_home": {
                "env:freesurfer_home",
                "command:recon-all",
                "command:mris_sphere",
                "command:mris_curvature",
                "command:mris_inflate",
                "command:mris_register",
                "command:mri_label2label",
                "command:mri_surf2surf",
                "command:mri_annotation2label",
                "command:mri_segstats",
            },
            "tract_querier_root": {"path:tract_querier_root", "path:tract_querier_root_script", "python:tract_querier"},
            "wma_root": {"env:wma_root", "path:wma_root_path", "command:wm_apply_ORG_atlas_to_subject.sh"},
            "wma_atlas_dir": {"setting:wma_org_atlas", "path:wma_org_atlas", "path:wma_org_atlas_ORG-RegAtlas-100HCP", "path:wma_org_atlas_ORG-800FC-100HCP"},
            "slicer_executable": {"env:slicer_executable", "path:slicer_executable_path"},
            "fiber_tract_measurements_cli": {"path:fiber_tract_measurements_cli"},
            "tractcloud_root": {"env:tractcloud_root", "path:tractcloud_root_path", "python:tractcloud"},
            "tractcloud_python_executable": {"path:tractcloud_python"},
            "tractcloud_data_dir": {"path:tractcloud_data_dir"},
        }
        keys = command_groups.get(dependency_id, set())
        return [item for item in statuses if item.key in keys]

    def _format_detected_source(self, source: str) -> str:
        if not source or source in {"not found", "not configured"}:
            return "not found"
        if source == "user setting":
            return "using saved path"
        if source.startswith("env:"):
            return "detected from " + source
        if source == "PATH":
            return "detected from PATH"
        if source == "common path":
            return "detected from common path"
        return source

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
            if not dependencies:
                self._set_environment_path_status_label(label, "not used by current selection", "inactive")
                continue
            available = [dependency for dependency in dependencies if dependency.status == "available"]
            if available:
                source = available[0].details.get("detected_source", "")
                self._set_environment_path_status_label(
                    label,
                    self._format_detected_source(source),
                    "available",
                )
            else:
                self._set_environment_path_status_label(label, "not found", "missing")

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
        node = self._parameterNode
        if node:
            self._sync_path_widget(getattr(self.ui, "inputDirectoryPath", None), node.inputDirectory or "")
            self._sync_path_widget(getattr(self.ui, "outputDirectoryPath", None), node.outputDirectory or "")
            self._sync_combo_text(getattr(self.ui, "predictModeComboBox", None), node.predictMode or "all")
            self._sync_combo_text(getattr(self.ui, "deviceComboBox", None), node.device or "auto")

            self._sync_line_edit(getattr(self.ui, "postprocessSubjectLineEdit", None), node.postprocessSubjectId or "")
            self._sync_path_widget(getattr(self.ui, "postprocessNativePath", None), node.postprocessNativeDir or "")
            self._sync_path_widget(getattr(self.ui, "postprocessMriPath", None), node.postprocessMriDir or "")
            self._sync_path_widget(getattr(self.ui, "postprocessRepoPath", None), node.postprocessRepoDir or "")
            self._sync_path_widget(getattr(self.ui, "postprocessLicensePath", None), node.postprocessLicensePath or "")
            self._sync_combo_text(
                getattr(self.ui, "postprocessModeComboBox", None),
                node.postprocessMode or "whole",
            )
            self._sync_line_edit(getattr(self.ui, "postprocessImageLineEdit", None), node.postprocessDockerImage or "")
            self._sync_checkbox(getattr(self.ui, "postprocessForceCheckBox", None), bool(node.postprocessForce))

            self._sync_line_edit(getattr(self.ui, "ddparcelSubjectLineEdit", None), node.ddparcelSubjectId or "")
            self._sync_path_widget(getattr(self.ui, "ddparcelInputRootPath", None), node.ddparcelInputRoot or "")
            self._sync_path_widget(getattr(self.ui, "ddparcelOutputRootPath", None), node.ddparcelOutputRoot or "")
            self._sync_path_widget(getattr(self.ui, "ddparcelAtlasPath", None), node.ddparcelAtlasPath or "")
            self._sync_spinbox(getattr(self.ui, "ddparcelFlipSpinBox", None), int(node.ddparcelFlip))

            self._sync_line_edit(
                getattr(self.ui, "microstructureSubjectLineEdit", None),
                node.microstructureSubjectId or "",
            )
            self._sync_path_widget(
                getattr(self.ui, "microstructureInputRootPath", None),
                node.microstructureInputRoot or "",
            )
            self._sync_path_widget(
                getattr(self.ui, "microstructureOutputPath", None),
                node.microstructureOutputDir or "",
            )
            self._sync_path_widget(getattr(self.ui, "microstructureRoiPath", None), node.microstructureRoiPath or "")
            self._sync_combo_text(
                getattr(self.ui, "microstructureFitComboBox", None),
                (node.microstructureFitMethod or "wls").lower(),
            )
            self._sync_checkbox(
                getattr(self.ui, "microstructureRunFreeWaterCheckBox", None),
                bool(node.microstructureRunFreeWater),
            )
            self._sync_checkbox(
                getattr(self.ui, "microstructureRunNoddiCheckBox", None),
                bool(node.microstructureRunNoddi),
            )
            self._sync_checkbox(
                getattr(self.ui, "microstructureForceRecomputeCheckBox", None),
                bool(node.microstructureForceRecompute),
            )

            self._sync_path_widget(getattr(self.ui, "ddsegMaskPath", None), node.ddsegMaskPath or "")
            self._sync_path_widget(getattr(self.ui, "ddsegDwiPath", None), node.ddsegDwiPath or "")
            self._sync_path_widget(getattr(self.ui, "ddsegBvalPath", None), node.ddsegBvalPath or "")
            self._sync_path_widget(getattr(self.ui, "ddsegBvecPath", None), node.ddsegBvecPath or "")
            self._sync_path_widget(getattr(self.ui, "ddsegOutputPath", None), node.ddsegOutputDir or "")
            self._sync_path_widget(getattr(self.ui, "ddsegWeightsPath", None), node.ddsegWeightsDir or "")
            self._sync_path_widget(getattr(self.ui, "ddsegSlicerBasePath", None), node.ddsegSlicerBase or "")
            self._sync_path_widget(getattr(self.ui, "ddsegSlicerExtPath", None), node.ddsegSlicerExt or "")
            self._sync_combo_text(
                getattr(self.ui, "ddsegDeviceComboBox", None),
                node.ddsegDevice or "auto",
                via_index=False,
            )
            self._sync_checkbox(getattr(self.ui, "ddsegSoftmaxCheckBox", None), bool(node.ddsegApplySoftmax))
            self._sync_checkbox(getattr(self.ui, "targetPreprocessingCheckBox", None), bool(node.targetPreprocessing))
            self._sync_combo_text(
                getattr(self.ui, "preprocessingBackendComboBox", None),
                node.preprocessingBackend or "dipy",
                via_index=False,
            )
            self._sync_line_edit(getattr(self.ui, "orchestrationRunNameLineEdit", None), node.orchestrationRunName or "")
            self._sync_combo_text(
                getattr(self.ui, "orchestrationTractographyBackendComboBox", None),
                node.orchestrationTractographyBackend or "csd_act",
                via_index=False,
            )
            self._sync_combo_text(
                getattr(self.ui, "orchestrationBundleBackendComboBox", None),
                getattr(node, "orchestrationBundleBackend", "wmql") or "wmql",
                via_index=False,
            )
            self._sync_spinbox(
                getattr(self.ui, "orchestrationSelectStreamlinesSpinBox", None),
                int(node.orchestrationSelectStreamlines),
            )
            self._sync_combo_text(
                getattr(self.ui, "orchestrationMicrostructureStagesComboBox", None),
                self._microstructure_stages_text(),
                via_index=False,
            )
            self._sync_checkbox(getattr(self.ui, "batchModeCheckBox", None), bool(getattr(node, "batchMode", False)))
            self._sync_path_widget(getattr(self.ui, "batchRootPath", None), getattr(node, "batchRoot", "") or "")
            self._sync_spinbox(getattr(self.ui, "batchSizeSpinBox", None), int(getattr(node, "batchSize", 1) or 1))
            self._sync_combo_text(
                getattr(self.ui, "batchArrangeInputsComboBox", None),
                getattr(node, "batchArrangeInputs", "none") or "none",
                via_index=False,
            )
            self._sync_combo_text(
                getattr(self.ui, "connectomeBackendComboBox", None),
                node.connectomeBackend or "python",
                via_index=False,
            )
            self._sync_checkbox(
                getattr(self.ui, "connectomeCompressMrtrixDenseCheckBox", None),
                bool(node.connectomeCompressMrtrixDense),
            )
            self._sync_combo_text(
                getattr(self.ui, "unifiedTorchDeviceComboBox", None),
                node.device or node.ddsegDevice or "auto",
                via_index=False,
            )
            self._sync_checkbox(
                getattr(self.ui, "autoInstallPythonDependenciesCheckBox", None),
                bool(node.autoInstallPythonDependencies),
            )
            self._sync_checkbox(getattr(self.ui, "targetSurfaceCheckBox", None), bool(node.targetSurface))
            self._sync_checkbox(getattr(self.ui, "targetParcellationCheckBox", None), bool(node.targetParcellation))
            self._sync_checkbox(getattr(self.ui, "targetSegmentationCheckBox", None), bool(node.targetSegmentation))
            self._sync_checkbox(getattr(self.ui, "targetMicrostructureCheckBox", None), bool(node.targetMicrostructure))
            self._sync_checkbox(getattr(self.ui, "targetTractographyCheckBox", None), bool(node.targetTractography))
            self._sync_checkbox(getattr(self.ui, "targetBundlesCheckBox", None), bool(node.targetBundles))
            self._sync_checkbox(getattr(self.ui, "targetConnectomeCheckBox", None), bool(node.targetConnectome))

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
        return "Test1"

    def _is_auto_generated_run_name(self, run_name: str) -> bool:
        normalized = (run_name or "").strip()
        if normalized in {"", "Test1"}:
            return True
        if normalized.endswith("_ui"):
            legacy_stem = normalized[:-3]
            return legacy_stem in {"csd_act", "tractography", "saf", "dti_det"}
        return False

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

        uses_act_streamlines = backend in {"csd_act", "saf"}
        streamline_spinbox.enabled = uses_act_streamlines
        streamline_label.text = "ACT/SAF streamlines" if uses_act_streamlines else "Streamline count"

        if backend == "csd_act":
            description = (
                "Number of streamlines requested from MRtrix CSD/ACT. "
                "Use 100000 or more for analysis-scale bundle/connectome tests."
            )
        elif backend == "saf":
            description = (
                "Number of streamlines generated during the MRtrix CSD/ACT stage before SAF filtering. "
                "Use 100000 or more for analysis-scale SAF tests."
            )
        else:
            description = (
                "DTI deterministic tracking does not use MRtrix ACT streamline selection. "
                "This setting is ignored for the current tractography backend."
            )

        streamline_label.toolTip = description
        streamline_spinbox.toolTip = description
        self._refresh_bundle_backend_highlight()

    def _refresh_bundle_backend_highlight(self, *, bundle_backend: Optional[str] = None) -> None:
        backend = (bundle_backend or self._bundle_backend_text() or "wmql").strip().lower() or "wmql"
        active_sections = set()
        if backend in {"wma", "all"}:
            active_sections.add("wma")
        if backend in {"tractcloud", "all"}:
            active_sections.add("tractcloud")

        label_groups = getattr(self, "_environmentBackendSectionLabels", {}) or {}
        row_groups = getattr(self, "_environmentBackendSectionRows", {}) or {}
        for key in ("wma", "tractcloud"):
            title_label, description_label = label_groups.get(key, (None, None))
            active = key in active_sections
            title_style = (
                "QLabel { background: #E4F4EA; border: 1px solid #AFCDBA; border-left: 4px solid #287A4A; "
                "border-radius: 8px; color: #173D2A; font-weight: 800; padding: 7px 10px; }"
                if active
                else "QLabel { background: #F4F8F5; border: 1px solid #DDEAE2; border-radius: 7px; "
                "color: #315843; font-weight: 700; padding: 7px 9px; }"
            )
            description_style = (
                "QLabel { background: #F7FCF8; border-radius: 7px; color: #3F6754; padding: 4px 9px 7px 10px; }"
                if active
                else "QLabel { color: #6A7D74; padding: 1px 8px 5px 9px; }"
            )
            if title_label:
                title_label.setStyleSheet(title_style)
            if description_label:
                description_label.setStyleSheet(description_style)

            for widgets in row_groups.get(key, []):
                for widget in widgets:
                    if widget is None:
                        continue
                    if hasattr(widget, "setStyleSheet"):
                        if active and widget.__class__.__name__ in {"QLineEdit", "ctkPathLineEdit"}:
                            widget.setStyleSheet(
                                "QLineEdit { background: #FCFEFC; border: 1px solid #7EB892; "
                                "border-radius: 8px; padding: 7px 10px; }"
                            )
                        elif active and widget.__class__.__name__ == "QPushButton":
                            widget.setStyleSheet(
                                "QPushButton { background: #F7FCF8; border: 1px solid #A9CBB4; "
                                "color: #1E5A3F; border-radius: 8px; padding: 6px 12px; }"
                            )
                        elif not active and widget.__class__.__name__ == "QPushButton":
                            widget.setStyleSheet("")
                        elif not active and widget.__class__.__name__ in {"QLineEdit", "ctkPathLineEdit"}:
                            widget.setStyleSheet("")

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
        selected: list[str] = []
        if bool(node.targetPreprocessing):
            selected.append("DWI Preprocessing")
        if bool(node.targetSurface):
            selected.append("Surface / DDSurfer")
        if bool(node.targetParcellation):
            selected.append("Parcellation / DDParcel")
        if bool(node.targetSegmentation):
            selected.append("Segmentation / DDSeg")
        if bool(node.targetMicrostructure):
            selected.append("Microstructure")
        if bool(node.targetTractography):
            selected.append("Tractography")
        if bool(node.targetBundles):
            selected.append("Bundles")
        if bool(node.targetConnectome):
            selected.append("Connectome")
        return selected

    def _selected_orchestrator_targets(self) -> tuple[str, ...]:
        node = self._parameterNode
        if not node:
            return ()
        targets = ["validation"]
        if bool(node.targetSegmentation):
            targets.append("segmentation")
        if bool(node.targetParcellation):
            targets.append("parcellation")
        if bool(node.targetMicrostructure):
            targets.append("microstructure")
        if bool(node.targetTractography):
            targets.append("tractography")
        if bool(node.targetBundles):
            targets.append("bundles")
        if bool(node.targetConnectome):
            targets.append("connectome")
        return tuple(targets)

    def _selected_product_targets(self) -> tuple[str, ...]:
        node = self._parameterNode
        if not node:
            return ()
        product_targets = ["validation"]
        if bool(node.targetPreprocessing):
            product_targets.append("preprocessing")
        if bool(node.targetSegmentation):
            product_targets.append("segmentation")
        if bool(node.targetParcellation):
            product_targets.append("parcellation")
        if bool(node.targetSurface):
            product_targets.append("surface")
        if bool(node.targetMicrostructure):
            product_targets.append("microstructure")
        if bool(node.targetTractography):
            product_targets.append("tractography")
        if bool(node.targetBundles):
            product_targets.append("bundles")
        if bool(node.targetConnectome):
            product_targets.append("connectome")
        return normalize_orchestrator_targets(
            tuple(product_targets),
            tractography_backend=self._tractography_backend_text(),
            bundle_backend=self._bundle_backend_text(),
            microstructure_run_free_water=self._microstructure_stage_flags()[0],
            microstructure_run_noddi=self._microstructure_stage_flags()[1],
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
        stages = {stage.strip().lower() for stage in self._microstructure_stages_text().replace("+", ",").split(",") if stage.strip()}
        if "all" in stages:
            stages.update({"dti", "freewater", "noddi"})
        return "freewater" in stages, "noddi" in stages

    def _selected_environment_targets(self) -> tuple[str, ...]:
        node = self._parameterNode
        if not node:
            return ()
        return tuple(dict.fromkeys(target for target in self._selected_product_targets() if target))

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

    def _add_cli_path_arg(self, args: list[str], flag: str, value: Optional[Path]) -> None:
        if value is not None:
            args.extend([flag, value.expanduser().as_posix()])

    def _build_background_cli_args(self, common_run_kwargs: dict[str, Any], external_paths: dict[str, Optional[Path]]) -> list[str]:
        node = self._parameterNode
        repo_root = Path(__file__).resolve().parent.parent
        cli_script = repo_root / "shared" / "run_subject_pipeline_cli.py"
        if not cli_script.is_file():
            cli_script = repo_root / "run_subject_pipeline.py"
        output_root = common_run_kwargs.get("output_root")
        args = [
            "--launch",
            "PythonSlicer",
            cli_script.as_posix(),
            "--subject-root",
            common_run_kwargs["subject_root"].expanduser().as_posix(),
            "--subject-id",
            str(common_run_kwargs["subject_id"]),
            "--run-name",
            str(common_run_kwargs["run_name"]),
            "--targets",
            ",".join(common_run_kwargs["targets"]),
            "--execute",
            "--print-manifest-only",
            "--preprocessing-backend",
            (node.preprocessingBackend or "dipy").strip() if node else "dipy",
            "--tractography-backend",
            str(common_run_kwargs["tractography_backend"]),
            "--bundle-backend",
            str(common_run_kwargs["bundle_backend"]),
            "--connectome-backend",
            str(common_run_kwargs["connectome_backend"]),
            "--select-streamlines",
            str(common_run_kwargs["select_streamlines"]),
            "--ddseg-device",
            str(common_run_kwargs["ddseg_device"]),
            "--surface-device",
            str(common_run_kwargs["surface_device"]),
        ]
        if output_root is not None:
            args.extend(["--output-root", output_root.expanduser().as_posix()])
        microstructure_stages = ["dti"]
        if common_run_kwargs.get("microstructure_run_free_water"):
            microstructure_stages.append("freewater")
        if common_run_kwargs.get("microstructure_run_noddi"):
            microstructure_stages.append("noddi")
        args.extend(["--microstructure-stages", ",".join(microstructure_stages)])
        if common_run_kwargs.get("connectome_compress_mrtrix_dense"):
            args.append("--compress-mrtrix-dense")
        self._add_cli_path_arg(args, "--mrtrix-bin-dir", external_paths.get("mrtrix_bin_dir"))
        self._add_cli_path_arg(args, "--preprocessing-mrtrix-bin-dir", external_paths.get("mrtrix_bin_dir"))
        self._add_cli_path_arg(args, "--preprocessing-fsl-bin-dir", external_paths.get("preprocessing_fsl_bin_dir"))
        self._add_cli_path_arg(args, "--postprocess-freesurfer-home", external_paths.get("postprocess_freesurfer_home"))
        self._add_cli_path_arg(args, "--tract-querier-root", external_paths.get("tract_querier_root"))
        self._add_cli_path_arg(args, "--wma-root", external_paths.get("wma_root"))
        self._add_cli_path_arg(args, "--wma-atlas-dir", external_paths.get("wma_atlas_dir"))
        self._add_cli_path_arg(args, "--slicer-executable", external_paths.get("slicer_executable"))
        self._add_cli_path_arg(args, "--fiber-tract-measurements-cli", external_paths.get("fiber_tract_measurements_cli"))
        self._add_cli_path_arg(args, "--tractcloud-root", external_paths.get("tractcloud_root"))
        self._add_cli_path_arg(args, "--tractcloud-python-executable", external_paths.get("tractcloud_python_executable"))
        self._add_cli_path_arg(args, "--tractcloud-data-dir", external_paths.get("tractcloud_data_dir"))
        return args

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
        batch_script = repo_root / "scripts" / "run_batch_pipeline.py"
        output_root = common_run_kwargs.get("output_root")
        args = [
            "--launch",
            "PythonSlicer",
            batch_script.as_posix(),
            "--batch-root",
            batch_root.expanduser().as_posix(),
            "--batch-size",
            str(max(1, int(batch_size))),
            "--run-name",
            str(common_run_kwargs["run_name"]),
            "--arrange-inputs",
            arrange_inputs,
            "--execute",
            "--targets",
            ",".join(common_run_kwargs["targets"]),
            "--preprocessing-backend",
            (node.preprocessingBackend or "dipy").strip() if node else "dipy",
            "--tractography-backend",
            str(common_run_kwargs["tractography_backend"]),
            "--bundle-backend",
            str(common_run_kwargs["bundle_backend"]),
            "--connectome-backend",
            str(common_run_kwargs["connectome_backend"]),
            "--select-streamlines",
            str(common_run_kwargs["select_streamlines"]),
            "--ddseg-device",
            str(common_run_kwargs["ddseg_device"]),
            "--surface-device",
            str(common_run_kwargs["surface_device"]),
        ]
        if output_root is not None:
            args.extend(["--output-root", output_root.expanduser().as_posix()])
        microstructure_stages = ["dti"]
        if common_run_kwargs.get("microstructure_run_free_water"):
            microstructure_stages.append("freewater")
        if common_run_kwargs.get("microstructure_run_noddi"):
            microstructure_stages.append("noddi")
        args.extend(["--microstructure-stages", ",".join(microstructure_stages)])
        if common_run_kwargs.get("connectome_compress_mrtrix_dense"):
            args.append("--compress-mrtrix-dense")
        self._add_cli_path_arg(args, "--mrtrix-bin-dir", external_paths.get("mrtrix_bin_dir"))
        self._add_cli_path_arg(args, "--preprocessing-mrtrix-bin-dir", external_paths.get("mrtrix_bin_dir"))
        self._add_cli_path_arg(args, "--preprocessing-fsl-bin-dir", external_paths.get("preprocessing_fsl_bin_dir"))
        self._add_cli_path_arg(args, "--postprocess-freesurfer-home", external_paths.get("postprocess_freesurfer_home"))
        self._add_cli_path_arg(args, "--tract-querier-root", external_paths.get("tract_querier_root"))
        self._add_cli_path_arg(args, "--wma-root", external_paths.get("wma_root"))
        self._add_cli_path_arg(args, "--wma-atlas-dir", external_paths.get("wma_atlas_dir"))
        self._add_cli_path_arg(args, "--slicer-executable", external_paths.get("slicer_executable"))
        self._add_cli_path_arg(args, "--fiber-tract-measurements-cli", external_paths.get("fiber_tract_measurements_cli"))
        self._add_cli_path_arg(args, "--tractcloud-root", external_paths.get("tractcloud_root"))
        self._add_cli_path_arg(args, "--tractcloud-python-executable", external_paths.get("tractcloud_python_executable"))
        self._add_cli_path_arg(args, "--tractcloud-data-dir", external_paths.get("tractcloud_data_dir"))
        return args

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
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, bytearray):
            return bytes(value).decode("utf-8", errors="replace")
        try:
            return bytes(value).decode("utf-8", errors="replace")
        except Exception:
            pass
        try:
            raw = value.data()
        except Exception:
            return ""
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        if isinstance(raw, bytearray):
            return bytes(raw).decode("utf-8", errors="replace")
        if isinstance(raw, str):
            return raw
        return ""

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
        if getattr(self, "_backgroundManifestPath", None):
            return self._backgroundManifestPath
        candidates = []
        text = getattr(self, "_backgroundOutputBuffer", "") or ""
        for line in text.splitlines():
            line = line.strip()
            if line.endswith("_orchestration_manifest.json"):
                candidates.append(Path(line))
        return next((path for path in reversed(candidates) if path.is_file()), None)

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
        rows = []
        blocked = 0
        failed = 0
        completed_like = 0
        for task in manifest.get("tasks", []):
            status = str(task.get("status") or "")
            if status == "blocked":
                blocked += 1
            if status == "failed":
                failed += 1
            if status in {"completed", "passed", "skipped"}:
                completed_like += 1
            rows.append(
                {
                    "target": str(task.get("name") or ""),
                    "status": status,
                    "reason": str(task.get("reason") or ""),
                    "manifest_path": str(task.get("normalized_manifest_path") or task.get("manifest_path") or ""),
                    "qc_path": str(task.get("normalized_qc_path") or task.get("qc_path") or ""),
                    "logs_dir": str(task.get("normalized_logs_dir") or ""),
                }
            )
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
        rows = []
        failed = 0
        completed = 0
        for result in manifest.get("results", []):
            returncode = int(result.get("returncode", 1))
            status = "completed" if returncode == 0 else "failed"
            if returncode == 0:
                completed += 1
            else:
                failed += 1
            rows.append(
                {
                    "target": str(result.get("subject_id") or ""),
                    "status": status,
                    "reason": f"return code {returncode}",
                    "manifest_path": str(manifest_path),
                    "qc_path": "",
                    "logs_dir": str(Path(str(result.get("stdout_log") or "")).parent)
                    if result.get("stdout_log")
                    else "",
                }
            )
        skipped = manifest.get("skipped", []) or []
        for item in skipped:
            rows.append(
                {
                    "target": str(item.get("subject_id") or item.get("path") or ""),
                    "status": "skipped",
                    "reason": str(item.get("reason") or "missing input"),
                    "manifest_path": str(manifest_path),
                    "qc_path": "",
                    "logs_dir": "",
                }
            )
        self._set_run_status_table_rows(rows)
        total = len(manifest.get("subjects", []) or [])
        if failed:
            self._setStatus("error", f"Batch failed: {failed} subject(s)")
        else:
            self._setStatus("ready", "Batch completed")
        self._set_latest_report_path(None)
        self._set_latest_output_tree_path(None)
        self._set_run_progress_message(f"Batch finished. Manifest: {manifest_path}")
        self._set_run_summary_message(
            f"Status: batch completed | Subjects: {total} | Completed: {completed} | "
            f"Failed: {failed} | Skipped: {len(skipped)} | Manifest: {manifest_path}",
            "failed" if failed else "completed",
        )

    def _onBackgroundProcessError(self, error) -> None:
        self.appendLog(f"[Background] QProcess error: {error}")

    def _mark_unfinished_rows(self, status: str, reason: str) -> None:
        table = getattr(self, "_runStatusTable", None)
        if not table:
            return
        try:
            table.setUpdatesEnabled(False)
        except Exception:
            pass
        try:
            for row in range(table.rowCount):
                status_item = table.item(row, 1)
                current = str(status_item.text() if status_item else "")
                if current in {"completed", "passed", "skipped", "blocked", "failed", "cancelled"}:
                    continue
                table.setItem(row, 1, self._table_item(status, status))
                table.setItem(row, 2, self._table_item(reason, status))
            table.resizeRowsToContents()
        finally:
            try:
                table.setUpdatesEnabled(True)
            except Exception:
                pass

    def _write_cancelled_manifest(self) -> Path:
        context = getattr(self, "_backgroundRunContext", {}) or {}
        subject_root = Path(context.get("subject_root") or ".").expanduser().resolve()
        output_root = context.get("output_root")
        outputs = Path(output_root).expanduser().resolve() if output_root else subject_root / "outputs"
        run_name = str(context.get("run_name") or "slicerdsurfer")
        run_metadata = outputs / "00_run_metadata"
        run_metadata.mkdir(parents=True, exist_ok=True)
        manifest_path = run_metadata / f"{run_name}_cancelled_orchestration_manifest.json"
        payload = {
            "kind": "slicerddsurfer_product_orchestration",
            "version": 1,
            "status": "cancelled",
            "subject_id": str(context.get("subject_id") or ""),
            "subject_root": subject_root.as_posix(),
            "output_root": outputs.as_posix(),
            "run_name": run_name,
            "targets": list(context.get("targets") or []),
            "started_at": context.get("started_at"),
            "cancelled_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "reason": "User cancelled the background SlicerDDSurfer job from the UI.",
        }
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

        if batch_mode:
            batch_root_text = (getattr(self._parameterNode, "batchRoot", "") or subject_root_text).strip()
            if not batch_root_text:
                slicer.util.errorDisplay("Batch root is required in Batch mode.", parent=self.parent)
                return
            batch_root = Path(batch_root_text).expanduser()
            if not batch_root.is_dir():
                slicer.util.errorDisplay(f"Batch root does not exist:\n{batch_root}", parent=self.parent)
                return
            batch_size = max(1, int(getattr(self._parameterNode, "batchSize", 1) or 1))
            arrange_inputs = (getattr(self._parameterNode, "batchArrangeInputs", "none") or "none").strip() or "none"
            common_run_kwargs = dict(
                subject_id="batch",
                subject_root=batch_root,
                output_root=Path(output_root_text).expanduser() if output_root_text else None,
                targets=selected_targets,
                run_name=run_name,
                tractography_backend=self._tractography_backend_text(),
                bundle_backend=self._bundle_backend_text(),
                resume=True,
                microstructure_run_free_water=run_free_water,
                microstructure_run_noddi=run_noddi,
                select_streamlines=max(1, int(self._parameterNode.orchestrationSelectStreamlines)),
                ddseg_device=ddseg_device,
                surface_device=surface_device,
                connectome_backend=(self._parameterNode.connectomeBackend or "python").strip(),
                connectome_compress_mrtrix_dense=bool(self._parameterNode.connectomeCompressMrtrixDense),
                preflight_blocked_targets={},
            )
            self.appendLog(
                f"Submitting batch products to background runner: root={batch_root}, "
                f"batch_size={batch_size}, targets={', '.join(selected)}"
            )
            self._startBackgroundBatchPipeline(
                common_run_kwargs,
                external_paths,
                selected,
                batch_root=batch_root,
                batch_size=batch_size,
                arrange_inputs=arrange_inputs,
            )
            return

        if not subject_root_text or not subject_id:
            slicer.util.errorDisplay("Subject ID and subject root are required before running.", parent=self.parent)
            return
        doctor_kwargs = self._environment_check_kwargs(
            subject_root_text=subject_root_text,
            output_root_text=output_root_text,
            external_paths=external_paths,
        )
        doctor_signature = self._environment_check_signature(doctor_kwargs)
        doctor_result = self._cached_environment_result(doctor_signature)
        try:
            if doctor_result is None:
                doctor_result = self.logic.runEnvironmentDoctor(**doctor_kwargs)
                self._cache_environment_result(doctor_result, doctor_signature)
            else:
                self.appendLog("[Environment] Reusing recent dependency check; inputs and selected targets are unchanged.")
        except Exception as exc:
            self.appendLog(f"Environment check failed: {exc}")
            slicer.util.errorDisplay(f"Environment check failed:\n{exc}", parent=self.parent)
            self._setStatus("error", "Environment check failed")
            return
        self._update_environment_result_label(doctor_result)
        self._update_environment_path_status_labels(doctor_result)
        if doctor_result.blocker_count and auto_install_python and doctor_result.missing_python_packages:
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
                doctor_result = self.logic.runEnvironmentDoctor(**doctor_kwargs)
                self._cache_environment_result(doctor_result, doctor_signature)
                self._update_environment_result_label(doctor_result)
                self._update_environment_path_status_labels(doctor_result)
            except Exception as exc:
                self._save_python_install_status(tuple(doctor_result.missing_python_packages), "failed", str(exc))
                self.appendLog(f"Dependency installation failed: {exc}")
                slicer.util.errorDisplay(f"Dependency installation failed:\n{exc}", parent=self.parent)
                self._setPipelineActive(False)
                self._setStatus("error", "Dependency installation failed")
                return

        preflight_blockers = {
            target: reason
            for target, reason in blocked_target_reasons(doctor_result).items()
            if target in selected_targets
        }

        subject_root = Path(subject_root_text).expanduser()
        common_run_kwargs = dict(
            subject_id=subject_id,
            subject_root=subject_root,
            output_root=Path(output_root_text).expanduser() if output_root_text else None,
            targets=selected_targets,
            run_name=run_name,
            tractography_backend=self._tractography_backend_text(),
            bundle_backend=self._bundle_backend_text(),
            resume=True,
            microstructure_run_free_water=run_free_water,
            microstructure_run_noddi=run_noddi,
            select_streamlines=max(1, int(self._parameterNode.orchestrationSelectStreamlines)),
            ddseg_device=ddseg_device,
            surface_device=surface_device,
            mrtrix_bin_dir=external_paths.get("mrtrix_bin_dir"),
            preprocessing_mrtrix_bin_dir=external_paths.get("mrtrix_bin_dir"),
            preprocessing_fsl_bin_dir=external_paths.get("preprocessing_fsl_bin_dir"),
            tract_querier_root=external_paths.get("tract_querier_root"),
            connectome_backend=(self._parameterNode.connectomeBackend or "python").strip(),
            connectome_compress_mrtrix_dense=bool(self._parameterNode.connectomeCompressMrtrixDense),
            preflight_blocked_targets=preflight_blockers,
        )
        try:
            plan = self.logic.planSelectedProductOrchestration(**common_run_kwargs)
            self._update_run_plan_table(plan)
            blocked_plan_items = [item for item in plan.items if item.status == "blocked"]
            if blocked_plan_items:
                self.appendLog(
                    "Run plan blocked target(s): "
                    + "; ".join(f"{item.target}: {item.reason}" for item in blocked_plan_items)
                )
                environment_blockers = {
                    item.target: item.reason
                    for item in blocked_plan_items
                    if item.reason_category == "environment"
                }
                if environment_blockers:
                    runnable_targets = tuple(item.target for item in plan.items if item.status != "blocked")
                    self._show_partial_run_notice(environment_blockers, runnable_targets)
        except Exception as exc:
            self.appendLog(f"Run planning failed: {exc}")
            slicer.util.errorDisplay(f"Run planning failed:\n{exc}", parent=self.parent)
            self._setStatus("error", "Run planning failed")
            return

        self.appendLog("Submitting selected products to background runner: " + ", ".join(selected))
        self._startBackgroundPipeline(common_run_kwargs, external_paths, selected)

    def _show_partial_run_notice(self, blockers: dict[str, str], runnable_targets: tuple[str, ...]) -> None:
        blocked_text = "\n".join(f"- {target}: {reason}" for target, reason in blockers.items())
        runnable_text = ", ".join(target for target in runnable_targets if target != "validation") or "none"
        message = (
            "Some selected products are blocked by missing dependencies. "
            "Runnable targets will still run.\n\n"
            f"Blocked:\n{blocked_text}\n\n"
            f"Runnable targets: {runnable_text}"
        )
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
        missing = [item for item in result.statuses if item.status == "missing"]
        return sorted(missing, key=lambda item: (not item.required, item.kind, item.label.lower()))

    def _environment_summary_text(self, result) -> str:
        missing_items = self._missing_environment_items(result)
        optional_count = sum(1 for item in missing_items if not item.required)
        if not missing_items:
            return "Environment ready. All selected targets are runnable with the detected setup."
        status_text = (
            f"{len(result.runnable_targets)} runnable, "
            f"{len(result.blocked_targets)} need setup, "
            f"{result.blocker_count} required missing"
        )
        if optional_count:
            status_text += f", {optional_count} optional missing"
        if result.missing_python_packages:
            status_text += f". Python packages available for auto-install: {len(result.missing_python_packages)}"
        preview = ", ".join(item.label for item in missing_items[:3])
        if len(missing_items) > 3:
            preview += f", +{len(missing_items) - 3} more"
        return f"{status_text}.\nNeeds attention: {preview}"

    def _environment_detail_lines(self, result) -> list[str]:
        missing_items = self._missing_environment_items(result)
        optional_count = sum(1 for item in missing_items if not item.required)
        lines = [
            f"Checked targets: {', '.join(result.targets) if result.targets else 'none'}",
            (
                f"Runnable targets: {len(result.runnable_targets)}; "
                f"blocked targets: {len(result.blocked_targets)}; "
                f"missing required items: {result.blocker_count}; "
                f"missing optional items: {optional_count}"
            ),
        ]
        if result.blocked_targets:
            lines.append("Blocked targets: " + ", ".join(result.blocked_targets))
        if result.missing_python_packages:
            lines.append("Auto-installable Python packages: " + ", ".join(result.missing_python_packages))
        if result.missing_external_groups:
            lines.append("Manual setup groups: " + ", ".join(result.missing_external_groups))
        if not missing_items:
            lines.append("No missing dependencies detected for the selected targets.")
        else:
            preview = ", ".join(item.label for item in missing_items[:6])
            if len(missing_items) > 6:
                preview += f", ... ({len(missing_items)} total)"
            lines.append("Missing items: " + preview)
        return lines

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
        previous = getattr(self, "_environmentDialog", None)
        if previous:
            try:
                previous.close()
            except Exception:
                pass

        dialog = qt.QDialog(slicer.util.mainWindow())
        dialog.setWindowTitle("SlicerDDSurfer Environment Dependencies")
        dialog.resize(900, 640)
        dialog.setStyleSheet(
            """
            QDialog {
              background: #F4F7F6;
            }
            QLabel#environmentSummaryLabel {
              background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #EEF6F1, stop:1 #F7FBF9);
              color: #173126;
              padding: 14px 16px;
              border: 1px solid #CADCD1;
              border-radius: 10px;
              font-weight: 600;
            }
            QFrame#environmentItemFrame {
              border: 1px solid #D5DEDC;
              border-radius: 10px;
              background: #FFFFFF;
            }
            QLabel#environmentItemText {
              color: #223238;
              background: transparent;
            }
            QPushButton {
              min-height: 30px;
              padding: 6px 14px;
              border: 1px solid #C8D4D1;
              border-radius: 8px;
              background: #FFFFFF;
              color: #173126;
            }
            QPushButton:hover {
              background: #F1F6F4;
            }
            QPushButton:pressed {
              background: #E3EEE8;
            }
            QPlainTextEdit {
              background: #FFFFFF;
              color: #4A5C5F;
              border: 1px solid #D7E0DE;
              border-radius: 8px;
              padding: 6px;
            }
            QScrollArea {
              border: none;
              background: transparent;
            }
            """
        )
        self._environmentDialog = dialog

        layout = qt.QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        summary_label = qt.QLabel(self._environment_summary_text(result))
        summary_label.setObjectName("environmentSummaryLabel")
        summary_label.wordWrap = True
        layout.addWidget(summary_label)

        button_row = qt.QHBoxLayout()
        install_all_button = qt.QPushButton("Install Python packages")
        install_all_button.toolTip = (
            self._python_install_target_text()
            + " External tools, licenses, and model resources require manual setup."
        )
        install_all_button.enabled = bool(result.missing_python_packages)
        install_all_button.connect("clicked()", self._onInstallAllEnvironmentItemsClicked)
        button_row.addWidget(install_all_button)

        notes_button = qt.QPushButton("Manual setup notes")
        notes_button.enabled = any(item.status == "missing" and item.kind != "python" for item in result.statuses)
        notes_button.connect("clicked()", lambda: self._show_environment_install_notes(result))
        button_row.addWidget(notes_button)

        detail_button = qt.QPushButton("Show summary details")
        detail_button.checkable = True
        detail_button.checked = False
        button_row.addWidget(detail_button)
        button_row.addStretch(1)

        close_button = qt.QPushButton("Close")
        close_button.connect("clicked()", dialog.close)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        details = qt.QPlainTextEdit()
        details.setReadOnly(True)
        details.visible = False
        details.setMaximumHeight(120)
        details.setPlainText("\n".join(self._environment_detail_lines(result)))
        detail_button.connect("toggled(bool)", details.setVisible)
        detail_button.connect(
            "toggled(bool)",
            lambda checked: detail_button.setText("Hide summary details" if checked else "Show summary details"),
        )
        layout.addWidget(details)

        missing_items = self._missing_environment_items(result)
        if missing_items:
            scroll = qt.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll_widget = qt.QWidget()
            scroll_layout = qt.QVBoxLayout(scroll_widget)
            for item in missing_items:
                scroll_layout.addWidget(self._build_environment_item_row(item))
            scroll_layout.addStretch(1)
            scroll.setWidget(scroll_widget)
            layout.addWidget(scroll)
        else:
            ready_label = qt.QLabel("All selected targets are runnable with the currently detected environment.")
            ready_label.wordWrap = True
            ready_label.setStyleSheet("QLabel { color: #2E7D32; padding: 12px; }")
            layout.addWidget(ready_label)

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _build_environment_item_row(self, item):
        frame = qt.QFrame()
        frame.setObjectName("environmentItemFrame")
        frame.setFrameShape(qt.QFrame.StyledPanel)
        layout = qt.QHBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        text = qt.QLabel(self._environment_item_text(item))
        text.setObjectName("environmentItemText")
        text.wordWrap = True
        try:
            text.setTextInteractionFlags(qt.Qt.TextSelectableByMouse | qt.Qt.TextSelectableByKeyboard)
        except Exception:
            pass
        layout.addWidget(text, 1)

        button = qt.QPushButton("Install" if item.kind == "python" else "Install / setup")
        button.toolTip = item.install_hint or "Show setup instructions."
        button.connect("clicked()", lambda: self._onInstallEnvironmentItemClicked(item))
        layout.addWidget(button)
        return frame

    def _environment_item_text(self, item) -> str:
        required = "required" if item.required else "optional"
        targets = ", ".join(item.targets) if item.targets else "none"
        lines = [
            f"{item.label} ({required})",
            f"Key: {item.key}",
            f"Targets: {targets}",
        ]
        details = item.details or {}
        if details.get("detected_source"):
            lines.append(f"Detected source: {details.get('detected_source')}")
        if item.kind == "python":
            lines.append(f"Package: {details.get('package') or item.label}")
            lines.append(f"Python: {details.get('python_executable') or 'current Slicer Python'}")
            install_requirement = details.get("install_requirement")
            if install_requirement and install_requirement != details.get("package"):
                lines.append(f"Install source: {install_requirement}")
        elif item.kind == "command":
            lines.append(f"Command: {details.get('command') or item.label}")
            if details.get("bin_dir"):
                lines.append(f"Configured bin dir: {details.get('bin_dir')}")
        elif item.kind == "path":
            lines.append(f"Path: {details.get('path') or ''}")
            lines.append(f"Expected type: {details.get('path_kind') or 'file'}")
        elif item.kind == "env":
            env_names = ", ".join((details.get("env") or {}).keys())
            lines.append(f"Environment variable(s): {env_names}")
        elif item.kind == "device":
            lines.append(f"Requested device: {details.get('requested_device') or ''}")
        elif item.kind == "setting":
            lines.append(details.get("notes") or "Provide the required setting before running.")
        if item.install_hint:
            lines.append(f"Suggested fix: {item.install_hint}")
        checked_locations = details.get("checked_locations") or []
        if checked_locations:
            preview = ", ".join(checked_locations[:3])
            if len(checked_locations) > 3:
                preview += f", ... ({len(checked_locations)} checked)"
            lines.append(f"Checked locations: {preview}")
        return "\n".join(line for line in lines if line)

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
            slicer.util.errorDisplay(f"Dependency installation failed:\n{exc}", parent=self.parent)
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
