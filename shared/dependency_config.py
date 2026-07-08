"""Shared dependency-config schema and helpers.

The same external dependency profile is consumed by the Slicer UI, the subject
CLI, and the install planner. Keeping the key list here prevents drift between
entry points when a new runtime path is added.
"""

from __future__ import annotations

import json
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any


DEPENDENCY_CONFIG_KIND = "slicerdsurfer_dependency_config"
DEPENDENCY_PROFILE_KIND = "slicerdsurfer_dependency_profile"
DEPENDENCY_CONFIG_VERSION = 1

DEPENDENCY_CONFIG_KEYS = (
    "python_executable",
    "python_environment",
    "conda_executable",
    "model_assets_dir",
    "mrtrix_bin_dir",
    "preprocessing_mrtrix_bin_dir",
    "preprocessing_fsl_bin_dir",
    "postprocess_freesurfer_home",
    "wma_root",
    "wma_atlas_dir",
    "slicer_executable",
    "fiber_tract_measurements_cli",
    "tract_querier_root",
    "tractcloud_root",
    "tractcloud_python_executable",
    "tractcloud_data_dir",
)

DEPENDENCY_CONFIG_HELP = {
    "python_executable": "Python executable used for Python dependency checks and pip installs.",
    "python_environment": "Conda environment name or Python executable path used for Python dependency checks and pip installs.",
    "conda_executable": "conda or mamba executable used to resolve --python-environment names.",
    "model_assets_dir": "Directory containing downloaded SlicerDDSurfer model weights and templates.",
    "mrtrix_bin_dir": "Directory containing MRtrix3 commands for tractography/connectome routes.",
    "preprocessing_mrtrix_bin_dir": "Directory containing MRtrix3 commands for MRtrix/FSL preprocessing.",
    "preprocessing_fsl_bin_dir": "Directory containing FSL commands for MRtrix/FSL preprocessing.",
    "postprocess_freesurfer_home": "FreeSurfer installation root for DDSurfer post-processing.",
    "wma_root": "WhiteMatterAnalysis checkout or installation root.",
    "wma_atlas_dir": "ORG atlas directory used by WhiteMatterAnalysis.",
    "slicer_executable": "Slicer executable used by external bundle-analysis helpers.",
    "fiber_tract_measurements_cli": "FiberTractMeasurements CLI executable.",
    "tract_querier_root": "TractQuerier checkout root when not installed in the active Python.",
    "tractcloud_root": "TractCloud checkout or installation root.",
    "tractcloud_python_executable": "Python executable for TractCloud.",
    "tractcloud_data_dir": "TractCloud model/data directory.",
}

UI_DEPENDENCY_PATHS: tuple[dict[str, str], ...] = (
    {
        "id": "python_executable",
        "label": "Python executable",
        "section": "core-runtime",
        "mode": "file",
        "tooltip": "Optional. Python executable for dependency checks and Python package installation. Defaults to current Slicer Python.",
    },
    {
        "id": "python_environment",
        "label": "Python/conda environment",
        "section": "core-runtime",
        "mode": "file",
        "value_type": "text",
        "tooltip": "Optional. Conda environment name or Python executable path. Explicit Python executable takes precedence.",
    },
    {
        "id": "conda_executable",
        "label": "conda/mamba executable",
        "section": "core-runtime",
        "mode": "file",
        "tooltip": "Optional. conda or mamba executable used when Python/conda environment is an environment name.",
    },
    {
        "id": "model_assets_dir",
        "label": "Model assets root",
        "section": "model-assets",
        "mode": "dir",
        "tooltip": "Optional. Root directory for downloaded SlicerDDSurfer model assets. Defaults to SLICERDDSURFER_MODEL_ASSETS_DIR or a per-user data directory.",
    },
    {
        "id": "mrtrix_bin_dir",
        "label": "MRtrix3 bin dir",
        "section": "core-runtime",
        "mode": "dir",
        "tooltip": "Optional. Directory containing mrconvert, dwi2response, dwi2fod, tckgen, tcksift2.",
    },
    {
        "id": "preprocessing_fsl_bin_dir",
        "label": "FSL bin dir",
        "section": "core-runtime",
        "mode": "dir",
        "tooltip": "Optional. Directory containing eddy and topup for MRtrix/FSL preprocessing.",
    },
    {
        "id": "postprocess_freesurfer_home",
        "label": "FreeSurfer home",
        "section": "core-runtime",
        "mode": "dir",
        "tooltip": "Optional. FreeSurfer installation root. FREESURFER_HOME is also detected.",
    },
    {
        "id": "tract_querier_root",
        "label": "TractQuerier root",
        "section": "core-runtime",
        "mode": "dir",
        "tooltip": "Optional. Checkout root used by WMQL when tract_querier is not installed in Slicer Python.",
    },
    {
        "id": "wma_root",
        "label": "WMA root",
        "section": "bundle-backends",
        "mode": "dir",
        "tooltip": "Optional. External WhiteMatterAnalysis checkout root.",
    },
    {
        "id": "wma_atlas_dir",
        "label": "WMA ORG atlas dir",
        "section": "bundle-backends",
        "mode": "dir",
        "tooltip": "Optional. Directory containing ORG-RegAtlas-100HCP and ORG-800FC-100HCP.",
    },
    {
        "id": "slicer_executable",
        "label": "Slicer executable for WMA",
        "section": "bundle-backends",
        "mode": "file",
        "tooltip": "Optional. Slicer executable used by WMA/SlicerDMRI helper calls.",
    },
    {
        "id": "fiber_tract_measurements_cli",
        "label": "FiberTractMeasurements CLI",
        "section": "bundle-backends",
        "mode": "file",
        "tooltip": "Optional. SlicerDMRI FiberTractMeasurements CLI path.",
    },
    {
        "id": "tractcloud_root",
        "label": "TractCloud root",
        "section": "bundle-backends",
        "mode": "dir",
        "tooltip": "Optional. TractCloud package/check-out root.",
    },
    {
        "id": "tractcloud_python_executable",
        "label": "TractCloud Python",
        "section": "bundle-backends",
        "mode": "file",
        "tooltip": "Optional. Dedicated Python executable for TractCloud if not using Slicer Python.",
    },
    {
        "id": "tractcloud_data_dir",
        "label": "TractCloud data/model dir",
        "section": "bundle-backends",
        "mode": "dir",
        "tooltip": "Optional. TractCloud model/data directory.",
    },
)


def cli_flag_for_key(key: str) -> str:
    return "--" + key.replace("_", "-")


TEXT_CONFIG_KEYS = {"python_environment"}


def add_dependency_config_arguments(parser: ArgumentParser, *, exclude: tuple[str, ...] = ()) -> None:
    """Register external dependency path options on an argparse parser."""

    excluded = set(exclude)
    for key in DEPENDENCY_CONFIG_KEYS:
        if key in excluded:
            continue
        value_type = str if key in TEXT_CONFIG_KEYS else Path
        parser.add_argument(cli_flag_for_key(key), dest=key, type=value_type, help=DEPENDENCY_CONFIG_HELP.get(key))


def load_dependency_config(path: Path) -> dict[str, Any]:
    """Load a CLI/UI dependency config and return path-valued settings."""

    data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if "external_dependencies" in data and isinstance(data["external_dependencies"], dict):
        data = data["external_dependencies"]
    result: dict[str, Any] = {}
    for key in DEPENDENCY_CONFIG_KEYS:
        value = data.get(key)
        if value:
            result[key] = str(value).strip() if key in TEXT_CONFIG_KEYS else Path(str(value)).expanduser()
    return result


def apply_dependency_config(args: Namespace, path: Path | None) -> None:
    """Apply dependency config values to argparse args if not already set."""

    if not path:
        return
    config_path = path.expanduser()
    if not config_path.is_file():
        raise FileNotFoundError(f"Dependency config not found: {config_path}")
    for key, value in load_dependency_config(config_path).items():
        if getattr(args, key, None) is None:
            setattr(args, key, value)


def dependency_config_payload(args: Namespace) -> dict[str, object]:
    """Build the portable dependency config payload from argparse args."""

    return {
        "kind": DEPENDENCY_CONFIG_KIND,
        "version": DEPENDENCY_CONFIG_VERSION,
        "external_dependencies": {
            key: (
                str(getattr(args, key)).strip()
                if key in TEXT_CONFIG_KEYS
                else getattr(args, key).expanduser().as_posix()
            )
            for key in DEPENDENCY_CONFIG_KEYS
            if getattr(args, key, None) is not None
        },
    }


def write_dependency_config(args: Namespace, path: Path) -> Path:
    """Write a dependency config JSON for reuse by CLI, installer, or UI."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(dependency_config_payload(args), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return resolved
