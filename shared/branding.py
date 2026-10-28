"""Canonical product identity and non-destructive legacy settings compatibility."""

import os
from pathlib import Path

PRODUCT_NAME = 'SlicerDSpace'
LEGACY_NAME = 'Slicer' + 'DDSurfer'
ENV_PREFIX = 'SLICERDSPACE_'
LEGACY_ENV_PREFIX = 'SLICER' + 'DDSURFER_'


def mirror_environment(environ=None):
    """Prefer canonical options while supporting existing launchers/backends."""
    env = os.environ if environ is None else environ
    for key, value in list(env.items()):
        if key.startswith(ENV_PREFIX):
            env[LEGACY_ENV_PREFIX + key[len(ENV_PREFIX):]] = value
    for key, value in list(env.items()):
        if key.startswith(LEGACY_ENV_PREFIX):
            env.setdefault(ENV_PREFIX + key[len(LEGACY_ENV_PREFIX):], value)


def reuse_legacy_path(path):
    """Reuse an existing user directory without moving or redownloading assets."""
    path = Path(path)
    if path.exists() or PRODUCT_NAME not in path.parts:
        return path
    parts = list(path.parts)
    parts[parts.index(PRODUCT_NAME)] = LEGACY_NAME
    previous = Path(*parts)
    return previous if previous.exists() else path


def migrate_qsettings(settings):
    """Copy old preferences only where no canonical preference exists."""
    prefix = LEGACY_NAME + '/'
    for key in settings.allKeys():
        key = str(key)
        if key.startswith(prefix):
            canonical = PRODUCT_NAME + key[len(LEGACY_NAME):]
            if not settings.contains(canonical):
                settings.setValue(canonical, settings.value(key))
