"""Portable filesystem operations used by the translated SAF backend."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def remove_matching(directory, pattern):
    """Remove entries matching *pattern* below *directory* without a shell."""

    removed = []
    for path in Path(directory).glob(pattern):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(path)
    return removed


def link_or_copy(source, destination):
    """Create a convenience symlink, copying when links are unavailable.

    Windows can deny unprivileged symbolic-link creation, and WSL links stored
    on mounted Windows drives are not portable to native Windows readers. SAF
    only uses these links for convenience files, so a copy is equivalent.
    """

    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Use the lexical destination rather than ``resolve()`` here: resolving an
    # existing WSL symlink follows it to the source and hides where the link is
    # physically stored.
    destination_parts = destination.absolute().parts
    windows_backed = os.name == "nt" or (
        len(destination_parts) >= 3
        and destination_parts[0] == os.sep
        and destination_parts[1].lower() == "mnt"
        and len(destination_parts[2]) == 1
    )

    if destination.exists() or destination.is_symlink():
        # Replace legacy WSL-on-NTFS symlinks with real files even when they
        # already resolve to the requested source.
        if not (windows_backed and destination.is_symlink()):
            try:
                if os.path.samefile(source, destination):
                    return destination
            except (FileNotFoundError, OSError):
                pass
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()

    # A symlink created by Linux on a WSL-mounted Windows drive is usable from
    # WSL but appears as a zero-byte reparse point to native Windows tools.
    # SAF outputs are intended to remain self-contained and readable from
    # Slicer on Windows, so materialize convenience files on those mounts.
    if windows_backed:
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        return destination

    try:
        destination.symlink_to(source.resolve(), target_is_directory=source.is_dir())
    except (NotImplementedError, OSError):
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
    return destination
