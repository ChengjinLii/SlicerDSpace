"""Helpers for launching external commands safely from Slicer or headless CLI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Mapping, Optional


def startup_environment(extra_env: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Return an environment suitable for external tools.

    When running inside Slicer, ``slicer.util.startupEnvironment()`` strips
    Slicer's runtime library-path overrides that can break external tools.
    Outside Slicer we fall back to the current process environment.
    """

    env: dict[str, str]
    try:
        import slicer  # type: ignore[import-not-found]

        env = dict(slicer.util.startupEnvironment())
    except Exception:
        env = os.environ.copy()

    if extra_env:
        env.update({str(key): str(value) for key, value in extra_env.items() if value is not None})
    return env


def merged_startup_environment(extra_env: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Alias used at call sites where an existing env dict is extended."""

    return startup_environment(extra_env)


def _path_parts(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [part for part in value.split(os.pathsep) if part]


def _looks_like_slicer_runtime_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return any(
        marker in normalized
        for marker in (
            "/slicer-",
            "/slicer.app/",
            "/slicer.org/extensions",
            "/lib/slicer-",
            "/qt-scripted-modules",
            "/qt-loadable-modules",
            "/cli-modules",
            "/pythonqt",
        )
    )


def _dedupe_paths(paths: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        if not path:
            continue
        key = os.path.normpath(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def external_python_environment(
    extra_env: Optional[Mapping[str, str]] = None,
    *,
    path_prepend: Optional[Iterable[Path | str]] = None,
    strip_slicer_paths: bool = True,
) -> dict[str, str]:
    """Return an environment for external Python-based command-line tools.

    Slicer and ``PythonSlicer`` export ``PYTHONHOME``/``PYTHONPATH`` and prepend
    Slicer runtime directories to ``PATH``. Python scripts launched via
    ``#!/usr/bin/env python`` can then import Slicer's stdlib with a different
    interpreter and fail with errors such as ``SRE module mismatch``. This
    helper keeps the user's normal environment shape but removes Slicer Python
    overrides before launching external Python tools such as MRtrix scripts.
    """

    env = startup_environment()
    for key in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONNOUSERSITE",
        "PYTHONEXECUTABLE",
        "PYTHONUSERBASE",
    ):
        env.pop(key, None)

    prepend = [Path(path).expanduser().as_posix() for path in (path_prepend or [])]
    for key in ("PATH", "LD_LIBRARY_PATH"):
        parts = _path_parts(env.get(key))
        if strip_slicer_paths:
            parts = [part for part in parts if not _looks_like_slicer_runtime_path(part)]
        if key == "PATH":
            parts = prepend + parts
        env[key] = os.pathsep.join(_dedupe_paths(parts))

    if extra_env:
        env.update({str(key): str(value) for key, value in extra_env.items() if value is not None})
    return env
