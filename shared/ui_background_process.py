"""Small background-process helpers for the SlicerDDSurfer widget."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def qprocess_is_running(process: Any) -> bool:
    """Return True if a Qt process appears to be running."""

    if process is None:
        return False
    try:
        import qt

        return process.state() != qt.QProcess.NotRunning
    except Exception:
        return False


def build_background_run_context(
    common_run_kwargs: dict[str, Any],
    selected_workflows: list[str],
    *,
    batch_root: Path | None = None,
    batch_size: int | None = None,
) -> dict[str, Any]:
    """Build the context stored while a background run is active."""

    is_batch = batch_root is not None
    context = {
        "subject_id": "batch" if is_batch else common_run_kwargs["subject_id"],
        "subject_root": batch_root if is_batch else common_run_kwargs["subject_root"],
        "output_root": common_run_kwargs.get("output_root"),
        "run_name": common_run_kwargs["run_name"],
        "targets": common_run_kwargs["targets"],
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "selected_workflows": selected_workflows,
    }
    if batch_size is not None:
        context["batch_size"] = batch_size
    return context
