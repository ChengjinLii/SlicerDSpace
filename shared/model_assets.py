"""Shared model-asset root resolution.

Model weights and templates are intentionally treated as user data, not as
files that must live inside the Slicer extension checkout.  Legacy checkout-
relative locations remain fallback candidates so older local installations do
not break.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path


MODEL_ASSETS_ENV = "SLICERDDSURFER_MODEL_ASSETS_DIR"


def default_user_model_assets_root() -> Path:
    """Return the per-user default model-asset root."""

    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "SlicerDDSurfer" / "model-assets"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "SlicerDDSurfer" / "model-assets"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "SlicerDDSurfer" / "model-assets"


def configured_model_assets_root(explicit: Path | None = None) -> Path:
    """Return the explicit/env/default user asset root without legacy fallback."""

    if explicit is not None:
        return explicit.expanduser().resolve()
    env_root = os.environ.get(MODEL_ASSETS_ENV)
    if env_root:
        return Path(env_root).expanduser().resolve()
    return default_user_model_assets_root().expanduser().resolve()


def legacy_repo_asset_roots(repo_root: Path) -> tuple[Path, ...]:
    """Return checkout-relative roots used by older SlicerDDSurfer installs."""

    root = repo_root.expanduser().resolve()
    return (root,)


def common_model_asset_roots() -> tuple[Path, ...]:
    """Return common user/shared model-asset roots to scan before reporting missing assets."""

    system = platform.system()
    home = Path.home()
    candidates = [
        default_user_model_assets_root(),
        home / "SlicerDDSurfer-model-assets",
        home / "SlicerDDSurfer-models",
        home / ".cache" / "SlicerDDSurfer" / "model-assets",
        Path("/data/shared/SlicerDDSurfer-model-assets"),
        Path("/data/shared/SlicerDDSurfer-models"),
        Path("/data/chengjin/SlicerDDSurfer-model-assets"),
        Path("/data/chengjin/SlicerDDSurfer-models"),
        Path("/opt/SlicerDDSurfer/model-assets"),
        Path("/usr/local/share/SlicerDDSurfer/model-assets"),
    ]
    if system == "Darwin":
        candidates.extend(
            [
                home / "Library" / "Application Support" / "SlicerDDSurfer" / "model-assets",
                Path("/Users/Shared/SlicerDDSurfer/model-assets"),
            ]
        )
    if system == "Windows":
        program_data = os.environ.get("PROGRAMDATA")
        if program_data:
            candidates.append(Path(program_data) / "SlicerDDSurfer" / "model-assets")
        candidates.extend(
            [
                Path("C:/SlicerDDSurfer/model-assets"),
                Path("D:/SlicerDDSurfer/model-assets"),
            ]
        )
    return tuple(dict.fromkeys(path.expanduser() for path in candidates if path))


def _has_any_required_asset(root: Path, required_paths: tuple[str, ...]) -> bool:
    return any((root / relative).is_file() for relative in required_paths)


def resolve_model_assets_root(
    *,
    explicit: Path | None = None,
    repo_root: Path | None = None,
    required_paths: tuple[str, ...] = (),
    prefer_existing_legacy: bool = True,
) -> Path:
    """Return the asset root used for download/verify operations."""

    if explicit is not None or os.environ.get(MODEL_ASSETS_ENV):
        return configured_model_assets_root(explicit)
    for candidate in common_model_asset_roots():
        if _has_any_required_asset(candidate, required_paths):
            return candidate.expanduser().resolve()
    if prefer_existing_legacy and repo_root is not None:
        for legacy in legacy_repo_asset_roots(repo_root):
            if _has_any_required_asset(legacy, required_paths):
                return legacy
    return configured_model_assets_root()


def model_asset_path(relative: str, *, repo_root: Path, explicit_root: Path | None = None) -> Path:
    """Return the best existing path for one model asset or its default target."""

    root = resolve_model_assets_root(explicit=explicit_root, repo_root=repo_root, required_paths=(relative,))
    candidate = root / relative
    if candidate.exists():
        return candidate
    for legacy_root in legacy_repo_asset_roots(repo_root):
        legacy = legacy_root / relative
        if legacy.exists():
            return legacy
    return candidate


def model_asset_candidates(relative: str, *, repo_root: Path, explicit_root: Path | None = None) -> tuple[Path, ...]:
    """Return ordered candidate paths for diagnostics."""

    primary = resolve_model_assets_root(explicit=explicit_root, repo_root=repo_root, required_paths=(relative,))
    candidates = [primary / relative]
    for common_root in common_model_asset_roots():
        common = common_root / relative
        if common not in candidates:
            candidates.append(common)
    for legacy_root in legacy_repo_asset_roots(repo_root):
        legacy = legacy_root / relative
        if legacy not in candidates:
            candidates.append(legacy)
    return tuple(candidates)
