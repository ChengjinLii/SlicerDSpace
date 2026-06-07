"""Exercise the Slicer run-plan/result table with a real module click."""

from __future__ import annotations

import os
from pathlib import Path

import qt
import slicer


SUBJECT_ROOT = Path(os.environ.get("SLICERDDSURFER_SMOKE_SUBJECT_ROOT", "/data/chengjin/SlicerDDSurfer-test/100307"))
SUBJECT_ID = os.environ.get("SLICERDDSURFER_SMOKE_SUBJECT_ID", SUBJECT_ROOT.name)
RUN_NAME = os.environ.get("SLICERDDSURFER_SMOKE_RUN_NAME", "csd_act")
TRACTOGRAPHY_BACKEND = os.environ.get("SLICERDDSURFER_SMOKE_TRACTOGRAPHY_BACKEND", "saf")
BUNDLE_BACKEND = os.environ.get("SLICERDDSURFER_SMOKE_BUNDLE_BACKEND", "all")
MICROSTRUCTURE_STAGES = os.environ.get("SLICERDDSURFER_SMOKE_MICROSTRUCTURE_STAGES", "dti,freewater,noddi")


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
        slicer.util.infoDisplay = lambda message, *args, **kwargs: print(
            f"SLICERDDSURFER_RUN_PANEL_INFO={message}",
            flush=True,
        )
        node = widget._parameterNode
        with slicer.util.NodeModify(node):
            node.subjectId = SUBJECT_ID
            node.inputDirectory = SUBJECT_ROOT.as_posix()
            node.outputDirectory = ""
            node.targetPreprocessing = True
            node.targetSegmentation = False
            node.targetParcellation = False
            node.targetSurface = False
            node.targetMicrostructure = True
            node.targetTractography = True
            node.targetBundles = True
            node.targetConnectome = True
            node.orchestrationRunName = RUN_NAME
            node.orchestrationTractographyBackend = TRACTOGRAPHY_BACKEND
            node.orchestrationBundleBackend = BUNDLE_BACKEND
            node.orchestrationMicrostructureStages = MICROSTRUCTURE_STAGES
            node.connectomeBackend = "python"
            node.autoInstallPythonDependencies = False
        widget._checkCanApply()
        widget.ui.runSelectedButton.click()
        _poll(0)
    except Exception as exc:
        print(f"SLICERDDSURFER_RUN_PANEL_ERROR={exc}", flush=True)
        slicer.app.exit(2)


def _poll(count: int) -> None:
    widget = _module_widget()
    process = getattr(widget, "_backgroundProcess", None)
    if process is not None:
        try:
            if process.state() != qt.QProcess.NotRunning and count < 240:
                qt.QTimer.singleShot(1000, lambda: _poll(count + 1))
                return
        except Exception:
            pass
    _check()


def _check() -> None:
    widget = _module_widget()
    table = getattr(widget, "_runStatusTable", None)
    row_count = table.rowCount if table else 0
    statuses = []
    targets = []
    if table:
        for row in range(row_count):
            target_item = table.item(row, 0)
            status_item = table.item(row, 1)
            targets.append(target_item.text() if target_item else "")
            statuses.append(status_item.text() if status_item else "")
    status_label = widget.ui.statusLabel.text if hasattr(widget.ui, "statusLabel") else ""
    hint = getattr(widget, "_runStatusHintLabel", None)
    hint_text = hint.text if hint else ""
    report_button = getattr(widget, "_runReportButton", None)
    latest_report = getattr(widget, "_latestReportPath", None)
    manifest = SUBJECT_ROOT / "outputs" / "00_run_metadata" / f"{RUN_NAME}_orchestration_manifest.json"
    plan = SUBJECT_ROOT / "outputs" / "00_run_metadata" / f"{RUN_NAME}_run_plan.json"
    print(f"SLICERDDSURFER_RUN_PANEL_STATUS_LABEL={status_label}", flush=True)
    print(f"SLICERDDSURFER_RUN_PANEL_HINT={hint_text}", flush=True)
    print(f"SLICERDDSURFER_RUN_PANEL_ROW_COUNT={row_count}", flush=True)
    print(f"SLICERDDSURFER_RUN_PANEL_TARGETS={targets}", flush=True)
    print(f"SLICERDDSURFER_RUN_PANEL_STATUSES={statuses}", flush=True)
    print(f"SLICERDDSURFER_RUN_PANEL_MANIFEST_EXISTS={manifest.is_file()}", flush=True)
    print(f"SLICERDDSURFER_RUN_PANEL_PLAN_EXISTS={plan.is_file()}", flush=True)
    print(f"SLICERDDSURFER_RUN_PANEL_REPORT_BUTTON_ENABLED={bool(report_button and report_button.enabled)}", flush=True)
    print(f"SLICERDDSURFER_RUN_PANEL_LATEST_REPORT={latest_report}", flush=True)
    bad = (
        row_count < 4
        or not any(status in {"blocked", "skipped", "passed", "completed"} for status in statuses)
        or not manifest.is_file()
        or not plan.is_file()
        or not (report_button and report_button.enabled)
        or not latest_report
        or not latest_report.is_file()
    )
    slicer.app.exit(2 if bad else 0)


qt.QTimer.singleShot(6000, _run)
