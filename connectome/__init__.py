"""Connectome workflow package for SlicerDDSurfer."""

from __future__ import annotations

from .pipeline import (
    ConnectomeConfig,
    ConnectomeResult,
    build_tck2connectome_command,
    inspect_connectome_backends,
    run_connectome,
)

PLANNED_WORKFLOWS: tuple[str, ...] = (
    "Tractography-driven connectome construction",
    "Parcel-node reuse from DDParcel",
)

__all__ = [
    "PLANNED_WORKFLOWS",
    "ConnectomeConfig",
    "ConnectomeResult",
    "build_tck2connectome_command",
    "inspect_connectome_backends",
    "run_connectome",
]
