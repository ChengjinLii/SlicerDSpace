"""Small UI error-dialog helpers for SlicerDDSurfer widgets."""

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
