"""Helpers for launching external commands safely from Slicer or headless CLI."""

from __future__ import annotations

import os
from typing import Mapping, Optional


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
