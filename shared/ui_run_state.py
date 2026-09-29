"""Pure presentation rules for run state, button enablement and log lines.

Kept free of Qt so the rules can be unit tested; the Qt glue lives in
``shared/ui_run_history.py`` and ``shared/module_widget.py``.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RunStatePresentation:
    label: str
    color: str
    busy: bool = False


# Mirrors the states of Slicer's CLI progress bar (Idle, Running, Completed,
# Completed with errors, Cancelled) so the module reads like a core module.
RUN_STATES: dict[str, RunStatePresentation] = {
    "idle": RunStatePresentation("Idle", "#607D8B"),
    "preflight": RunStatePresentation("Checking environment", "#1565C0", busy=True),
    "running": RunStatePresentation("Running", "#1565C0", busy=True),
    "completed": RunStatePresentation("Completed", "#2E7D32"),
    "completed_with_blocks": RunStatePresentation("Completed with blocked stages", "#E65100"),
    "failed": RunStatePresentation("Completed with errors", "#C62828"),
    "cancelled": RunStatePresentation("Cancelled", "#E65100"),
}


def run_state_presentation(state: str) -> RunStatePresentation:
    """Return label/colour for a run state; unknown states read as idle."""

    return RUN_STATES.get((state or "").strip(), RUN_STATES["idle"])


def run_state_from_manifest_status(status: str) -> str:
    """Map an orchestration/batch manifest status to a run state key."""

    value = (status or "").strip()
    if value == "partial_failed":
        return "failed"
    if value in RUN_STATES and value not in {"preflight"}:
        return value
    return "idle"


def progress_bar_format(done: int, total: int) -> str:
    """Text shown inside the progress bar."""

    if total <= 0:
        return "Waiting for the run plan…"
    noun = "stage" if total == 1 else "stages"
    return f"{done} / {total} {noun}"


@dataclass(frozen=True)
class ButtonState:
    enabled: bool
    tooltip: str


RUN_BUTTON_READY_TOOLTIP = (
    "Check dependencies for the selected targets, then start a monitored background run. "
    "Missing Python packages are installed first only when that option is enabled."
)


def run_button_state(
    *,
    pipeline_active: bool,
    selected_targets: Iterable[str],
    batch_mode: bool,
    subject_id: str,
    subject_root_text: str,
    batch_root_text: str = "",
    topup_errors: Iterable[str] = (),
) -> ButtonState:
    """Decide whether "Preflight and run" is clickable and explain why not."""

    if pipeline_active:
        return ButtonState(False, "A run is in progress. Use 'Cancel running job' to stop it.")
    if not [target for target in selected_targets if target and target != "validation"]:
        return ButtonState(False, "Select at least one product under 2. Targets.")
    if batch_mode:
        if not (batch_root_text or subject_root_text).strip():
            return ButtonState(False, "Set 'Batch root' under Analysis settings (or a Subject root) for batch mode.")
    else:
        missing = []
        if not (subject_id or "").strip():
            missing.append("Subject ID")
        if not (subject_root_text or "").strip():
            missing.append("Subject root")
        if missing:
            return ButtonState(False, "Fill in " + " and ".join(missing) + " under 1. Inputs.")
    errors = [error for error in topup_errors if error]
    if errors:
        return ButtonState(False, "Fix distortion-correction settings under 3. Route and parameters: " + errors[0])
    return ButtonState(True, RUN_BUTTON_READY_TOOLTIP)


def result_actions_state(*, has_subject_run: bool, is_batch: bool, error: str = "") -> ButtonState:
    """Enablement for Load / reuse, Replace, Append copy and Clear run."""

    if error:
        return ButtonState(False, error)
    if is_batch:
        return ButtonState(False, "Batch runs list one entry per subject; choose a subject's run to load its images.")
    if not has_subject_run:
        return ButtonState(False, "Choose a run in the list above, or use Browse… to add a run folder.")
    return ButtonState(True, "Manage only scene nodes owned by this run; source files are never deleted.")


LOG_LEVEL_COLORS = {
    "error": "#FF8A80",
    "warning": "#FFD180",
    "stage": "#82B1FF",
    "success": "#B9F6CA",
    "info": "#E0E0E0",
}

_ERROR_PATTERN = re.compile(r"\b(error|failed|failure|traceback|exception|fatal)\b", re.IGNORECASE)
_WARNING_PATTERN = re.compile(r"\b(warning|warn|blocked|cancelled|skipped|deprecated)\b", re.IGNORECASE)
_SUCCESS_PATTERN = re.compile(r"\b(completed|passed|succeeded|ready to run|environment ready)\b", re.IGNORECASE)


def log_line_level(line: str) -> str:
    """Classify a pipeline log line for colouring."""

    text = line or ""
    if text.startswith("[Orchestrator] Running ") or text.startswith("[Background] Starting"):
        return "stage"
    if _ERROR_PATTERN.search(text):
        return "error"
    if _WARNING_PATTERN.search(text):
        return "warning"
    if _SUCCESS_PATTERN.search(text):
        return "success"
    return "info"


def log_line_html(line: str) -> str:
    """Escape a log line and wrap it in a coloured span (whitespace preserved)."""

    level = log_line_level(line)
    escaped = html.escape(line or "", quote=False)
    weight = "font-weight:600;" if level in {"stage", "error"} else ""
    return f'<span style="white-space:pre;color:{LOG_LEVEL_COLORS[level]};{weight}">{escaped}</span>'
