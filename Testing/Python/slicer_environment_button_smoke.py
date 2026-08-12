"""Click the environment dependency button in a real Slicer session."""

from __future__ import annotations

import qt
import slicer


def _module_widget():
    try:
        return slicer.util.getModuleWidget("SlicerDDSurfer")
    except Exception:
        module = slicer.util.getModule("SlicerDDSurfer")
        return module.widgetRepresentation().self()


def _run() -> None:
    try:
        slicer.util.selectModule("SlicerDDSurfer")
        widget = _module_widget()
        widget.ui.validateButton.click()
        qt.QTimer.singleShot(9000, _check)
    except Exception as exc:
        print(f"SLICERDDSURFER_ENV_CLICK_ERROR={exc}", flush=True)
        slicer.app.exit(2)


def _check() -> None:
    widget = _module_widget()
    log = widget.ui.logPlainTextEdit.toPlainText() if hasattr(widget.ui, "logPlainTextEdit") else ""
    status = widget.ui.statusLabel.text if hasattr(widget.ui, "statusLabel") else ""
    environment_label = (
        widget.ui.environmentResultLabel.text if hasattr(widget.ui, "environmentResultLabel") else ""
    )
    path_widgets = getattr(widget, "_environmentPathLineEdits", {}) or {}
    status_widgets = getattr(widget, "_environmentPathStatusLabels", {}) or {}
    status_texts = {key: label.text for key, label in status_widgets.items()}
    run_status_table = getattr(widget, "_runStatusTable", None)
    run_status_panel = getattr(widget, "_runStatusPanel", None)
    advanced_paths = getattr(widget, "_environmentAdvancedPathsWidget", None)
    advanced_collapsed = bool(getattr(advanced_paths, "collapsed", False)) if advanced_paths else False
    settings_roundtrip_ok = False
    if "mrtrix_bin_dir" in path_widgets:
        test_path = "/tmp/slicerdsurfer-smoke-mrtrix"
        widget._save_environment_path_setting("mrtrix_bin_dir", test_path)
        settings_roundtrip_ok = (
            str(slicer.app.userSettings().value(widget._environment_settings_key("mrtrix_bin_dir"), ""))
            == test_path
        )
        widget._save_environment_path_setting("mrtrix_bin_dir", "")
    dialog = getattr(widget, "_environmentDialog", None)
    environment_result = getattr(widget, "_lastEnvironmentResult", None)
    missing_items = widget._missing_environment_items(environment_result) if environment_result else []
    per_item_action_required = bool(missing_items)
    dialog_visible = bool(dialog and dialog.isVisible())
    dialog_button_texts = []
    dialog_button_names = []
    if dialog:
        try:
            dialog_buttons = dialog.findChildren(qt.QPushButton)
            dialog_button_texts = [button.text for button in dialog_buttons]
            dialog_button_names = [button.objectName for button in dialog_buttons]
        except Exception as exc:
            dialog_button_texts = [f"BUTTON_DISCOVERY_FAILED:{exc}"]
    import_config_button = getattr(widget, "_environmentImportConfigButton", None)
    export_config_button = getattr(widget, "_environmentExportConfigButton", None)
    python_target_label = getattr(widget, "_environmentPythonTargetLabel", None)
    widget_button_texts = [
        import_config_button.text if import_config_button else "",
        export_config_button.text if export_config_button else "",
    ]
    python_target_visible = bool(
        python_target_label
        and python_target_label.isVisible()
        and "Python install target: current Slicer Python environment" in python_target_label.text
    )
    print(f"SLICERDDSURFER_ENV_CLICK_STATUS={status}", flush=True)
    print(f"SLICERDDSURFER_ENV_RESULT_LABEL={environment_label}", flush=True)
    print(f"SLICERDDSURFER_ENV_PATH_WIDGET_COUNT={len(path_widgets)}", flush=True)
    print(f"SLICERDDSURFER_ENV_PATH_STATUS_COUNT={len(status_widgets)}", flush=True)
    print(f"SLICERDDSURFER_ENV_PATH_STATUSES={status_texts}", flush=True)
    print(f"SLICERDDSURFER_RUN_STATUS_TABLE_PRESENT={bool(run_status_table)}", flush=True)
    print(f"SLICERDDSURFER_RUN_STATUS_PANEL_PRESENT={bool(run_status_panel)}", flush=True)
    print(f"SLICERDDSURFER_ENV_ADVANCED_COLLAPSED={advanced_collapsed}", flush=True)
    print(f"SLICERDDSURFER_ENV_SETTINGS_ROUNDTRIP={settings_roundtrip_ok}", flush=True)
    print(f"SLICERDDSURFER_ENV_DIALOG_VISIBLE={dialog_visible}", flush=True)
    print(f"SLICERDDSURFER_ENV_DIALOG_BUTTONS={dialog_button_texts}", flush=True)
    print(f"SLICERDDSURFER_ENV_DIALOG_BUTTON_NAMES={dialog_button_names}", flush=True)
    print(f"SLICERDDSURFER_ENV_PER_ITEM_ACTION_REQUIRED={per_item_action_required}", flush=True)
    print(f"SLICERDDSURFER_ENV_WIDGET_BUTTONS={widget_button_texts}", flush=True)
    print(f"SLICERDDSURFER_ENV_PYTHON_TARGET_VISIBLE={python_target_visible}", flush=True)
    print("SLICERDDSURFER_ENV_CLICK_LOG_TAIL_BEGIN", flush=True)
    print(log[-3000:], flush=True)
    print("SLICERDDSURFER_ENV_CLICK_LOG_TAIL_END", flush=True)
    bad = (
        "Subject ID and subject directory are required" in log
        or "Validation failed" in status
        or "runnable" not in environment_label.lower()
        or len(path_widgets) < 8
        or len(status_widgets) < len(path_widgets)
        or not run_status_table
        or not run_status_panel
        or not any(text != "not checked" for text in status_texts.values())
        or not advanced_collapsed
        or not settings_roundtrip_ok
        or not dialog_visible
        or environment_result is None
        or "environmentInstallAllButton" not in dialog_button_names
        or (
            per_item_action_required
            and "environmentItemActionButton" not in dialog_button_names
        )
        or import_config_button is None
        or export_config_button is None
        or python_target_visible
    )
    slicer.app.exit(2 if bad else 0)


qt.QTimer.singleShot(6000, _run)
