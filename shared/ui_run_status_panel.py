"""Qt helpers for the SlicerDDSurfer run-status panel."""

from __future__ import annotations


def install_run_status_panel(widget) -> None:
    """Create and attach the run-plan/progress panel to a Slicer widget."""

    if getattr(widget, "_runStatusTable", None) is not None:
        return
    configuration_layout = getattr(widget.ui, "configurationLayout", None)
    if not configuration_layout:
        return
    import qt

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
    report_button.connect("clicked()", widget._on_open_latest_report_clicked)
    panel_layout.addWidget(report_button)

    output_tree_button = qt.QPushButton("Open output tree")
    output_tree_button.enabled = False
    output_tree_button.setToolTip("Open the latest annotated SlicerDDSurfer output-tree HTML report.")
    output_tree_button.connect("clicked()", widget._on_open_output_tree_report_clicked)
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
    table.cellDoubleClicked.connect(widget._on_run_status_table_double_clicked)
    panel_layout.addWidget(table)

    try:
        insert_index = max(0, configuration_layout.count() - 1)
        configuration_layout.insertWidget(insert_index, panel)
    except Exception:
        configuration_layout.addWidget(panel)

    widget._runStatusPanel = panel
    widget._runStatusHintLabel = hint
    widget._runSummaryLabel = summary
    widget._runReportButton = report_button
    widget._runOutputTreeButton = output_tree_button
    widget._latestReportPath = None
    widget._latestOutputTreePath = None
    widget._runStatusTable = table


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
