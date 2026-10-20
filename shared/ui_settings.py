"""User-settings helpers for the SlicerDDSurfer widget."""

from __future__ import annotations

from typing import Any


COMMON_USER_SETTING_SPECS: tuple[tuple[str, type], ...] = (
    ("subjectId", str),
    ("inputDirectory", str),
    ("outputDirectory", str),
    ("orchestrationRunName", str),
    ("orchestrationTractographyBackend", str),
    ("ukfParameters", str),
    ("orchestrationBundleBackend", str),
    ("orchestrationWmqlPreset", str),
    ("maxParallelModels", int),
    ("orchestrationSelectStreamlines", int),
    ("orchestrationMicrostructureStages", str),
    ("connectomeBackend", str),
    ("connectomeCompressMrtrixDense", bool),
    ("autoInstallPythonDependencies", bool),
    ("batchMode", bool),
    ("batchRoot", str),
    ("batchSize", int),
    ("batchArrangeInputs", str),
    ("targetPreprocessing", bool),
    ("targetSurface", bool),
    ("targetSurfacePostprocess", bool),
    ("targetParcellation", bool),
    ("targetSegmentation", bool),
    ("targetMicrostructure", bool),
    ("targetTractography", bool),
    ("targetBundles", bool),
    ("targetConnectome", bool),
)


def common_user_setting_specs() -> tuple[tuple[str, type], ...]:
    """Return persisted parameter-node attributes and their value types."""

    return COMMON_USER_SETTING_SPECS


def coerce_user_setting_value(value: Any, value_type: type) -> Any:
    """Coerce a Slicer user-settings value to the expected parameter-node type."""

    if value_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if value_type is int:
        return int(value)
    return str(value or "")
