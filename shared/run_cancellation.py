"""Write a terminal "cancelled" state into an orchestration manifest.

When the pipeline CLI (``shared/run_subject_pipeline_cli.py``) receives
SIGTERM -- e.g. from the widget's Cancel button killing the whole process
group (see ``shared/process_group.py``) -- ``run_subject_products()`` is
aborted mid-flight and never gets to write its final manifest. Without this
helper, the on-disk manifest is left showing ``"status": "running"`` (or, if
no checkpoint had been written yet, does not exist at all), giving no
indication that the run was intentionally cancelled rather than still in
progress or crashed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from shared.io_layout import normalize_run_name, subject_layout

# Task-level statuses the orchestrator uses for a task that had not
# finished before the run was interrupted.
_UNFINISHED_TASK_STATUSES = {"running", "pending", "planned", "queued"}


def orchestration_manifest_path(
    subject_root: Path,
    *,
    output_root: Optional[Path] = None,
    run_name: str,
) -> Path:
    """Return the orchestration manifest path for a subject/run, without running it.

    Mirrors shared/orchestrator.py's own
    ``layout.run_metadata / f"{run_name}_orchestration_manifest.json"``
    computation, so a SIGTERM handler installed before
    ``run_subject_products()`` starts can know where to write a cancelled
    manifest even if the orchestrator never gets to write one itself.
    """

    resolved_subject_root = subject_root.expanduser().resolve()
    resolved_output_root = output_root.expanduser().resolve() if output_root is not None else None
    layout = subject_layout(resolved_subject_root, output_root=resolved_output_root)
    normalized_run_name = normalize_run_name(run_name)
    return layout.run_metadata / f"{normalized_run_name}_orchestration_manifest.json"


def cancelled_manifest_payload(
    existing: Optional[dict[str, Any]],
    *,
    subject_id: str,
    run_name: str,
    cancelled_at: str,
) -> dict[str, Any]:
    """Return the manifest payload to write when a run is cancelled.

    If ``existing`` (the manifest checkpoint already on disk, if any) is
    given, its already-recorded task results are preserved, and only the
    top-level status and any still-unfinished task are marked cancelled.
    Otherwise a minimal manifest is created from scratch.
    """

    payload: dict[str, Any] = (
        dict(existing)
        if existing
        else {
            "kind": "slicerdsurfer_orchestration",
            "subject_id": subject_id,
            "run_name": run_name,
            "tasks": [],
        }
    )
    payload["status"] = "cancelled"
    payload["cancelled_at"] = cancelled_at
    tasks = payload.get("tasks")
    if isinstance(tasks, list):
        updated_tasks = []
        for task in tasks:
            if isinstance(task, dict) and task.get("status") in _UNFINISHED_TASK_STATUSES:
                task = {**task, "status": "cancelled"}
            updated_tasks.append(task)
        payload["tasks"] = updated_tasks
    return payload


def write_cancelled_manifest(
    manifest_path: Path,
    *,
    subject_id: str,
    run_name: str,
    cancelled_at: str,
) -> dict[str, Any]:
    """Write (or update) ``manifest_path`` with a terminal "cancelled" state.

    Reads the existing manifest checkpoint if the orchestrator had already
    written one, so already-recorded task results are preserved rather than
    discarded.
    """

    existing: Optional[dict[str, Any]] = None
    try:
        if manifest_path.is_file():
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        existing = None
    payload = cancelled_manifest_payload(
        existing,
        subject_id=subject_id,
        run_name=run_name,
        cancelled_at=cancelled_at,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
