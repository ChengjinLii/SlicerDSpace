"""Connectome workflow package for SlicerDDSurfer."""

from __future__ import annotations

from .pipeline import (
    ConnectomeConfig,
    ConnectomeResult,
    build_tck2connectome_command,
    inspect_connectome_backends,
    run_connectome,
)

SUPPORTED_WORKFLOWS: tuple[str, ...] = (
    "Python tractography-to-parcel connectomes",
    "MRtrix tractography-to-parcel connectomes",
    "Scalar, length, and SIFT2 edge weighting",
)

# Compatibility alias retained for downstream imports from earlier releases.
PLANNED_WORKFLOWS = SUPPORTED_WORKFLOWS

__all__ = [
    "PLANNED_WORKFLOWS",
    "SUPPORTED_WORKFLOWS",
    "ConnectomeConfig",
    "ConnectomeResult",
    "build_tck2connectome_command",
    "inspect_connectome_backends",
    "run_connectome",
]
