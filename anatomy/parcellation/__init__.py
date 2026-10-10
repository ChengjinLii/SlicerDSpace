"""Parcellation workflow package for SlicerDDSurfer."""

from __future__ import annotations

__all__ = [
    "DDParcelConfig",
    "DDParcelRegisteredConfig",
    "ParcellationConfig",
    "RegisteredParcellationConfig",
    "run_ddparcel",
    "run_ddparcel_from_registered_bundle",
    "run_parcellation",
    "run_parcellation_from_registered_bundle",
]


def __getattr__(name):
    if name in __all__:
        from .pipeline import (
            DDParcelConfig,
            DDParcelRegisteredConfig,
            run_ddparcel,
            run_ddparcel_from_registered_bundle,
        )

        namespace = {
            "DDParcelConfig": DDParcelConfig,
            "DDParcelRegisteredConfig": DDParcelRegisteredConfig,
            "ParcellationConfig": DDParcelConfig,
            "RegisteredParcellationConfig": DDParcelRegisteredConfig,
            "run_ddparcel": run_ddparcel,
            "run_ddparcel_from_registered_bundle": run_ddparcel_from_registered_bundle,
            "run_parcellation": run_ddparcel,
            "run_parcellation_from_registered_bundle": run_ddparcel_from_registered_bundle,
        }
        return namespace[name]
    raise AttributeError(name)
