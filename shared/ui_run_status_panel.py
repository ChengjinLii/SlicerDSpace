"""Qt helpers for the SlicerDDSurfer run-status panel."""

from __future__ import annotations


def install_run_status_panel(widget) -> None:
    """Create the run progress area (4. Run) and the results panel (5. Results).

    Kept as the historical entry point; the widgets are built by
    ``shared.ui_run_history`` so the run selector, stage table and scene
    actions live together under 5. Results.
    """

    if getattr(widget, "_runStatusTable", None) is not None:
        return
    from shared.ui_run_history import install_results_panel, install_run_progress_panel

    install_run_progress_panel(widget)
    install_results_panel(widget)


def table_item(text: str, state: str = ""):
    """Return a styled run-status table item."""

    import qt

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


def set_run_status_table_rows(widget, rows: list[dict[str, str]]) -> None:
    """Replace all run-status table rows."""

    table = getattr(widget, "_runStatusTable", None)
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
                table.setItem(row_index, col, table_item(str(value or ""), state))
        table.resizeRowsToContents()
    finally:
        try:
            table.setUpdatesEnabled(True)
        except Exception:
            pass


def update_run_status_table_item(widget, key_candidates: tuple[str, ...], status: str, reason: str = "") -> None:
    """Update one existing run-status table row matching a target key."""

    table = getattr(widget, "_runStatusTable", None)
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
            table.setItem(row, 1, table_item(status, status))
            if reason:
                table.setItem(row, 2, table_item(reason, status))
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


def mark_unfinished_rows(widget, status: str, reason: str) -> None:
    """Mark queued/running table rows as failed or cancelled."""

    table = getattr(widget, "_runStatusTable", None)
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
            table.setItem(row, 1, table_item(status, status))
            table.setItem(row, 2, table_item(reason, status))
        table.resizeRowsToContents()
    finally:
        try:
            table.setUpdatesEnabled(True)
        except Exception:
            pass
