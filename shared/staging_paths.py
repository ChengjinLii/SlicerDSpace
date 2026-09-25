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

# Rejects anything that could put a path separator into the joined
# ``staging_root / subject_id`` path. This alone is deliberately permissive:
# a subject id containing a space or non-ASCII characters (e.g. an accented
# name pulled from a DICOM header) is not itself a safety problem, since the
# actual guarantee against escaping ``staging_root`` is the containment
# check in :func:`resolve_staging_subject_dir`, not this character-level
# check.
_PATH_SEPARATOR_PATTERN = re.compile(r"[\\/]")

# Stricter allow-list applied only when the resolved directory may go on to
# be ``shutil.rmtree()``-ed (``for_delete=True``): Unicode word characters,
# dot, and hyphen. This is narrower than "whatever a filesystem can name" on
# purpose, so a value from an unexpected source cannot reach a destructive
# call at all -- e.g. control characters or a name that is entirely
# whitespace.
_SAFE_SUBJECT_ID_FOR_DELETE_PATTERN = re.compile(r"[\w.-]+", re.UNICODE)


def validate_staging_subject_id(subject_id: str, *, for_delete: bool = False) -> str:
    """Return ``subject_id`` if it is safe to use as a staging directory name.

    Always rejects an empty string, the special path components ``.``/
    ``..``, and any path separator -- these could make the joined path land
    outside ``staging_root`` regardless of what happens to it afterward.

    When ``for_delete`` is True (the caller is about to ``rmtree()`` the
    resolved directory), also requires ``subject_id`` to fully match the
    conservative ``[\\w.-]+`` allow-list. Callers that only need to read
    from or write into the directory should leave ``for_delete`` False, so
    a legitimate subject id containing a space or non-ASCII characters is
    not rejected when nothing is being deleted.
    """

    if not subject_id or subject_id in (".", ".."):
        raise ValueError(f"Invalid subject_id for staging: {subject_id!r}")
    if _PATH_SEPARATOR_PATTERN.search(subject_id):
        raise ValueError(f"Invalid subject_id for staging: {subject_id!r}")
    if for_delete and not _SAFE_SUBJECT_ID_FOR_DELETE_PATTERN.fullmatch(subject_id):
        raise ValueError(f"Invalid subject_id for staging deletion: {subject_id!r}")
    return subject_id


def resolve_staging_subject_dir(staging_root: Path, subject_id: str, *, for_delete: bool = False) -> Path:
    """Return the validated, resolved ``staging_root / subject_id`` directory.

    Validates ``subject_id`` with :func:`validate_staging_subject_id` and
    additionally asserts the resolved path is actually contained within the
    resolved ``staging_root`` (guarding against, e.g., a pre-existing symlink
    at that location). Pass ``for_delete=True`` when the returned path may go
    on to be ``rmtree()``-ed, so the stricter allow-list applies to exactly
    the case that matters.
    """

    validate_staging_subject_id(subject_id, for_delete=for_delete)
    staging_root_resolved = staging_root.expanduser().resolve()
    candidate = (staging_root_resolved / subject_id).resolve()
    if candidate != staging_root_resolved and staging_root_resolved not in candidate.parents:
        raise ValueError(
            f"Resolved staging path {candidate} is not inside staging root {staging_root_resolved}"
        )
    return candidate
