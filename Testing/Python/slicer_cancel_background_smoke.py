"""Verify that the Slicer background runner can cancel a running process."""

from __future__ import annotations

from pathlib import Path

import qt
import slicer


SUBJECT_ROOT = Path("/data/chengjin/SlicerDDSurfer-test/100307")
OUTPUT_ROOT = Path("/tmp/slicerdsurfer-cancel-smoke-output")
RUN_NAME = "cancel_smoke"


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
            f"SLICERDDSURFER_CANCEL_INFO={message}",
            flush=True,
        )
        widget._slicer_launcher_program = lambda: "/bin/bash"
        widget._build_background_cli_args = lambda common_run_kwargs, external_paths: [
            "-c",
            "echo '[Orchestrator] Running Microstructure DTI'; sleep 30",
        ]
        widget._cancelSmokeSawRunning = False
        common_run_kwargs = {
            "subject_id": "100307",
            "subject_root": SUBJECT_ROOT,
            "output_root": OUTPUT_ROOT,
            "run_name": RUN_NAME,
            "targets": ["microstructure"],
        }
        widget._startBackgroundPipeline(common_run_kwargs, {}, ["microstructure"])
        qt.QTimer.singleShot(700, _capture_running)
        qt.QTimer.singleShot(1500, widget._onCancelRunClicked)
        qt.QTimer.singleShot(6500, _check)
    except Exception as exc:
        print(f"SLICERDDSURFER_CANCEL_ERROR={exc}", flush=True)
        slicer.app.exit(2)


def _capture_running() -> None:
    widget = _module_widget()
    process = getattr(widget, "_backgroundProcess", None)
    process_running = False
    if process is not None:
        try:
            process_running = process.state() != qt.QProcess.NotRunning
        except Exception:
            process_running = False
    widget._cancelSmokeSawRunning = process_running
    print(f"SLICERDDSURFER_CANCEL_SAW_RUNNING={widget._cancelSmokeSawRunning}", flush=True)


def _check() -> None:
    widget = _module_widget()
    process = getattr(widget, "_backgroundProcess", None)
    process_running = False
    if process is not None:
        try:
            process_running = process.state() != qt.QProcess.NotRunning
        except Exception:
            process_running = False
    manifest = OUTPUT_ROOT / "00_run_metadata" / f"{RUN_NAME}_cancelled_orchestration_manifest.json"
    status_label = widget.ui.statusLabel.text if hasattr(widget.ui, "statusLabel") else ""
    table = getattr(widget, "_runStatusTable", None)
    statuses = []
    if table:
        for row in range(table.rowCount):
            status_item = table.item(row, 1)
            statuses.append(status_item.text() if status_item else "")
    print(f"SLICERDDSURFER_CANCEL_PROCESS_RUNNING={process_running}", flush=True)
    print(f"SLICERDDSURFER_CANCEL_STATUS_LABEL={status_label}", flush=True)
    print(f"SLICERDDSURFER_CANCEL_MANIFEST_EXISTS={manifest.is_file()}", flush=True)
    print(f"SLICERDDSURFER_CANCEL_TABLE_STATUSES={statuses}", flush=True)
    saw_running = bool(getattr(widget, "_cancelSmokeSawRunning", False))
    bad = process_running or not manifest.is_file() or "cancel" not in status_label.lower() or not saw_running
    slicer.app.exit(2 if bad else 0)


def _watchdog() -> None:
    print("SLICERDDSURFER_CANCEL_WATCHDOG_TIMEOUT=True", flush=True)
    slicer.app.exit(3)


qt.QTimer.singleShot(2000, _run)
qt.QTimer.singleShot(20000, _watchdog)
