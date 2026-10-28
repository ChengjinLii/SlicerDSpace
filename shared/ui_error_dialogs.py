"""Small UI error-dialog helpers for SlicerDSpace widgets."""

from __future__ import annotations


def format_actionable_error_message(
    *,
    title: str,
    what: str,
    why: str,
    next_step: str,
    auto_fix: str,
    details: object,
) -> str:
    """Return the full user-facing actionable error message."""

    body = "\n\n".join(
        [
            f"What happened:\n{what}",
            f"Why:\n{why}",
            f"What to do next:\n{next_step}",
            f"Automatic fix:\n{auto_fix}",
            f"Details:\n{details}",
        ]
    )
    return f"{title}\n\n{body}"


def show_actionable_error_dialog(
    *,
    parent,
    title: str,
    what: str,
    why: str,
    next_step: str,
    auto_fix: str,
    details: object,
    actions: tuple[tuple[str, object], ...] = (),
) -> None:
    """Show an actionable error dialog with copyable details and optional buttons."""

    import qt
    import slicer

    message = format_actionable_error_message(
        title=title,
        what=what,
        why=why,
        next_step=next_step,
        auto_fix=auto_fix,
        details=details,
    )
    dialog = qt.QDialog(parent or slicer.util.mainWindow())
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(680)
    layout = qt.QVBoxLayout(dialog)

    summary = qt.QLabel(f"<b>{title}</b>")
    summary.setWordWrap(True)
    layout.addWidget(summary)

    body = qt.QPlainTextEdit()
    body.setReadOnly(True)
    body.setPlainText(message)
    body.setMinimumHeight(260)
    layout.addWidget(body)

    buttons = qt.QHBoxLayout()
    copy_button = qt.QPushButton("Copy details")
    copy_button.connect("clicked()", lambda: qt.QApplication.clipboard().setText(message))
    buttons.addWidget(copy_button)

    for label, callback in actions:
        button = qt.QPushButton(label)
        button.connect("clicked()", callback)
        buttons.addWidget(button)

    buttons.addStretch(1)
    close_button = qt.QPushButton("Close")
    close_button.connect("clicked()", dialog.accept)
    buttons.addWidget(close_button)
    layout.addLayout(buttons)
    dialog.exec_()
