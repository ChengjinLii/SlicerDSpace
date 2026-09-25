"""Validate subject-id-derived staging directories before destructive cleanup.

Several release/postprocess helpers build a per-subject staging directory as
``staging_root / subject_id`` and, when re-staging, ``shutil.rmtree()`` it.
``subject_id`` can originate from a CLI argument or a discovered directory
name; without validation, a value such as ``".."`` or one containing a path
separator could make the deleted directory land outside ``staging_root``
entirely. Use :func:`resolve_staging_subject_dir` wherever such a directory
is computed immediately before an ``rmtree`` call.
"""

from __future__ import annotations

import re
from pathlib import Path

# Conservative allow-list: letters, digits, dot, underscore, hyphen. This
# also excludes "/" and "\\", so a validated subject_id can never introduce
# a path separator on any platform.
_SAFE_SUBJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_staging_subject_id(subject_id: str) -> str:
    """Return ``subject_id`` if it is safe to use as a staging directory name.

    Raises ``ValueError`` for an empty string, a value containing characters
    outside ``[A-Za-z0-9._-]``, or the special path components ``.``/``..``.
    """

    if not subject_id or not _SAFE_SUBJECT_ID_PATTERN.match(subject_id):
        raise ValueError(f"Invalid subject_id for staging: {subject_id!r}")
    if subject_id in (".", ".."):
        raise ValueError(f"Invalid subject_id for staging: {subject_id!r}")
    return subject_id


def resolve_staging_subject_dir(staging_root: Path, subject_id: str) -> Path:
    """Return the validated, resolved ``staging_root / subject_id`` directory.

    Validates ``subject_id`` with :func:`validate_staging_subject_id` and
    additionally asserts the resolved path is actually contained within the
    resolved ``staging_root`` (guarding against, e.g., a pre-existing symlink
    at that location). Callers should call this immediately before an
    ``rmtree()`` of the returned path.
    """

    validate_staging_subject_id(subject_id)
    staging_root_resolved = staging_root.expanduser().resolve()
    candidate = (staging_root_resolved / subject_id).resolve()
    if candidate != staging_root_resolved and staging_root_resolved not in candidate.parents:
        raise ValueError(
            f"Resolved staging path {candidate} is not inside staging root {staging_root_resolved}"
        )
    return candidate
