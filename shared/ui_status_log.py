"""Status, log and report-path helpers for the SlicerDDSurfer widget."""

from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Any

from shared.ui_run_state import log_line_html
from shared.ui_styles import RUN_STATUS_TABLE_STYLE, SLICERDDSURFER_UI_STYLE, run_summary_label_style


STATUS_COLORS = {
    "ready": "#2E7D32",
    "running": "#1565C0",
    "waiting": "#EF6C00",
    "warning": "#EF6C00",
    "error": "#C62828",
}


def configure_log_widget(widget: Any, *, line_limit: int) -> None:
    """Configure the Slicer log widget for long background runs."""

    import qt

    if not widget:
        return
    widget.setToolTip(f"Live background log. The UI keeps the latest {line_limit} lines to avoid slowing long runs.")
    try:
        widget.maximumBlockCount = int(line_limit)
    except Exception:
        pass
    try:
        widget.setMaximumBlockCount(int(line_limit))
    except Exception:
        try:
            widget.document().setMaximumBlockCount(int(line_limit))
        except Exception:
            pass
    try:
        widget.setLineWrapMode(qt.QPlainTextEdit.NoWrap)
    except Exception:
        pass


def apply_widget_styles(owner: Any) -> None:
    """Apply global SlicerDDSurfer widget styles."""

    root_widget = getattr(owner, "_uiWidget", None)
    try:
        if root_widget:
            root_widget.setStyleSheet(SLICERDDSURFER_UI_STYLE)
    except Exception:
        try:
            owner.parent.setStyleSheet(SLICERDDSURFER_UI_STYLE)
        except Exception:
            pass
    table = getattr(owner, "_runStatusTable", None)
    if table:
        table.setStyleSheet(RUN_STATUS_TABLE_STYLE)
        try:
            table.verticalHeader().setVisible(False)
        except Exception:
            pass


def set_status(owner: Any, kind: str, message: str) -> None:
    """Update the status label and progress bar."""

    label = getattr(owner.ui, "statusLabel", None)
    if not label:
        return
    progress = getattr(owner.ui, "statusProgressBar", None)
    color = STATUS_COLORS.get(kind, STATUS_COLORS["error"])
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


def set_run_progress_message(owner: Any, message: str) -> None:
    """Update the run-progress label and transient Slicer status bar."""

    import slicer

    label = getattr(owner, "_runStatusHintLabel", None)
    if label:
        label.setText(message)
    slicer.util.showStatusMessage(message, 3000)


def set_run_summary_message(owner: Any, message: str, state: str = "") -> None:
    """Update the run summary label."""

    label = getattr(owner, "_runSummaryLabel", None)
    if not label:
        return
    label.setText(message or "Run summary is not available yet.")
    label.setStyleSheet(run_summary_label_style(state))


def set_existing_report_path(owner: Any, attribute: str, button_attribute: str, report_path: str | Path | None) -> None:
    """Store a report path only if it exists and update its button state."""

    path = Path(str(report_path)).expanduser() if report_path else None
    if path is not None and not path.is_file():
        path = None
    setattr(owner, attribute, path)
    button = getattr(owner, button_attribute, None)
    if button:
        button.enabled = bool(path)


def append_log(owner: Any, text: str) -> None:
    """Append text to the log widget while throttling event processing."""

    import slicer

    if hasattr(owner.ui, "logPlainTextEdit"):
        log_widget = owner.ui.logPlainTextEdit
        for line in str(text).splitlines() or [""]:
            try:
                # Colour errors, warnings and stage transitions (see ui_run_state).
                log_widget.appendHtml(log_line_html(line))
            except Exception:
                log_widget.appendPlainText(line)
        owner._logAppendCount = int(getattr(owner, "_logAppendCount", 0) or 0) + 1
        if owner._logAppendCount % 100 == 0:
            owner._trim_log_widget(owner.ui.logPlainTextEdit)
        owner.ui.logPlainTextEdit.ensureCursorVisible()
    if text.startswith("[Orchestrator] Running "):
        owner._set_run_progress_message(text.replace("[Orchestrator] ", "", 1))
    now = monotonic()
    if now - float(getattr(owner, "_lastProcessEventsAt", 0.0) or 0.0) < 0.15:
        return
    owner._lastProcessEventsAt = now
    try:
        slicer.app.processEvents()
    except Exception:
        pass
