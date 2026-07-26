"""WhiteMatterAnalysis integration for tractography post-processing.

This module intentionally keeps WMA execution behind an explicit ``execute``
flag so the extension can construct reproducible commands and manifests before
running long tractography clustering jobs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import re
import traceback
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Optional

from shared.external_process import external_python_environment, merged_startup_environment


WMA_APPLY_ORG_SCRIPT = Path("bin") / "wm_apply_ORG_atlas_to_subject.sh"
WMA_APPLY_ORG_SCRIPT_NAME = "wm_apply_ORG_atlas_to_subject.sh"
WMA_REPOSITORY = "https://github.com/SlicerDMRI/whitematteranalysis.git"
EXPECTED_ORG_ATLAS_DIRS = ("ORG-RegAtlas-100HCP", "ORG-800FC-100HCP")
MIN_ANATOMICAL_TRACT_COUNT = 73
REQUIRED_WMA_COMMANDS = (
    "wm_append_clusters_to_anatomical_tracts.py",
    "wm_assess_cluster_location_by_hemisphere.py",
    "wm_cluster_from_atlas.py",
    "wm_cluster_remove_outliers.py",
    "wm_harden_transform.py",
    "wm_register_to_atlas_new.py",
    "wm_separate_clusters_by_hemisphere.py",
)
OPTIONAL_WMA_COMMANDS = ("wm_diffusion_measurements.py", "xvfb-run")
EXTRA_TOOL_DIRS = (
    Path("/data/chengjin/software/xvfb/usr/bin"),
)
EXTRA_LIBRARY_DIRS = (
    Path("/data/chengjin/software/libpcre2-16-0/usr/lib/x86_64-linux-gnu"),
    Path("/data/chengjin/software/libxcb-xinerama0/usr/lib/x86_64-linux-gnu"),
)


@dataclass(frozen=True)
class WMAOrgAtlasConfig:
    """Configuration for applying the WMA ORG atlas to one tractogram."""

    subject_id: str
    input_tractography: Path
    atlas_dir: Path
    output_dir: Path
    slicer_executable: Path
    wma_root: Optional[Path] = None
    mrtrix_bin_dir: Optional[Path] = None
    transform_path: Optional[Path] = None
    registration_mode: str = "rig"
    num_threads: int = 1
    use_virtual_x: bool = False
    export_diffusion_measures: bool = False
    fiber_tract_measurements_cli: Optional[Path] = None
    clean_files: int = 0
    execute: bool = False


@dataclass(frozen=True)
class WMAOrgAtlasResult:
    """Prepared or completed WMA ORG atlas run."""

    subject_id: str
    status: str
    output_dir: Path
    manifest_path: Path
    qc_path: Path
    command: tuple[str, ...]
    executed: bool
    backend_status: dict[str, Any]
    atlas_status: dict[str, Any]
    return_code: Optional[int] = None


def resolve_configured_wma_root() -> Path:
    """Resolve WMA from environment variables or PATH."""

    for env_name in ("SLICERDDSURFER_WMA_ROOT", "WMA_ROOT"):
        env_value = os.environ.get(env_name)
        if env_value:
            return Path(env_value).expanduser().resolve()

    script_on_path = shutil.which(WMA_APPLY_ORG_SCRIPT_NAME)
    if script_on_path:
        script_path = Path(script_on_path).resolve()
        if script_path.parent.name == "bin":
            return script_path.parent.parent
        return script_path.parent

    raise FileNotFoundError(
        "WMA ORG atlas script was not found. Configure WMA by passing wma_root, "
        "setting SLICERDDSURFER_WMA_ROOT or WMA_ROOT, or adding "
        f"{WMA_APPLY_ORG_SCRIPT_NAME} to PATH. WMA is an optional external backend; "
        "it is not bundled inside SlicerDDSurfer."
    )


def resolve_wma_root(wma_root: Optional[Path] = None, module_dir: Optional[Path] = None) -> Path:
    del module_dir  # Backward-compatible signature; WMA discovery is no longer repo-relative.
    candidate = (wma_root.expanduser().resolve() if wma_root is not None else resolve_configured_wma_root())
    script = candidate / WMA_APPLY_ORG_SCRIPT
    if not script.is_file():
        raise FileNotFoundError(
            f"WMA ORG atlas script not found: {script}. "
            "Configure an external WhiteMatterAnalysis checkout with wma_root, "
            "SLICERDDSURFER_WMA_ROOT, WMA_ROOT, or PATH."
        )
    return candidate


def wma_source_info(wma_root: Path) -> dict[str, str]:
    git_dir = wma_root / ".git"
    info = {
        "root": wma_root.as_posix(),
        "repository": WMA_REPOSITORY,
    }
    if git_dir.exists():
        try:
            commit = subprocess.check_output(
                ["git", "-C", wma_root.as_posix(), "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            info["commit"] = commit
        except Exception:
            pass
    source_record = wma_root / "VENDORED_SOURCE.md"
    if source_record.is_file():
        for line in source_record.read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.removeprefix("- ").partition(":")
            if not separator or not value.strip():
                continue
            normalized_key = key.strip().lower().replace(" ", "_")
            if normalized_key in {"commit", "date_added"}:
                info[normalized_key] = value.strip()
        info["source_record"] = source_record.as_posix()
    return info


def _command_path(command_name: str, wma_root: Path) -> Optional[Path]:
    local_candidates = [
        wma_root / "bin" / command_name,
        wma_root / "utilities" / command_name,
    ]
    local_candidates.extend(tool_dir / command_name for tool_dir in EXTRA_TOOL_DIRS)
    for candidate in local_candidates:
        if candidate.is_file():
            return candidate.resolve()
    found = shutil.which(command_name)
    return Path(found).resolve() if found else None


def _slicerdmri_module_paths(slicer_executable: Path) -> tuple[Path, ...]:
    slicer_root = slicer_executable.expanduser().resolve().parent
    candidates = sorted((slicer_root / "slicer.org").glob("Extensions-*/SlicerDMRI"))
    if not candidates:
        return ()
    slicerdmri_root = candidates[-1]
    module_roots = sorted((slicerdmri_root / "lib").glob("Slicer-*"))
    paths: list[Path] = []
    for module_root in module_roots:
        paths.extend(
            (
                module_root / "qt-loadable-modules",
                module_root / "qt-scripted-modules",
                module_root / "cli-modules",
            )
        )
    return tuple(path for path in paths if path.is_dir())


def _slicer_runtime_library_paths(slicer_executable: Path) -> tuple[Path, ...]:
    """Return library directories needed by Slicer/PythonSlicer shims."""

    slicer_root = slicer_executable.expanduser().resolve().parent
    candidates = sorted((slicer_root / "lib").glob("Slicer-*"))
    candidates.append(slicer_root / "lib")
    slicerdmri_paths = _slicerdmri_module_paths(slicer_executable)
    for path in slicerdmri_paths:
        candidates.append(path)
        candidates.append(path.parent)
    candidates.extend(path for path in EXTRA_LIBRARY_DIRS)
    unique: list[Path] = []
    for path in candidates:
        if path.is_dir():
            resolved = path.resolve()
            if resolved not in unique:
                unique.append(resolved)
    return tuple(unique)


def _resolve_slicer_launcher(slicer_executable: Path) -> Path:
    slicer_executable = slicer_executable.expanduser().resolve()
    launcher = slicer_executable.parent.parent / "run-slicer.sh"
    return launcher if launcher.is_file() else slicer_executable


def _resolve_runtime_display() -> Optional[str]:
    for env_name in ("SLICERDDSURFER_DISPLAY", "DISPLAY"):
        value = os.environ.get(env_name)
        if value:
            return value
    return None


def inspect_wma_backend(
    wma_root: Optional[Path] = None,
    *,
    require_virtual_x: bool = False,
    require_diffusion_measurements: bool = False,
) -> dict[str, Any]:
    """Inspect the external WhiteMatterAnalysis backend without running WMA."""

    status: dict[str, Any] = {
        "available": False,
        "root": None,
        "script": None,
        "missing_required": [],
        "missing_optional": [],
        "commands": {},
        "source": None,
    }
    root = resolve_wma_root(wma_root)
    status["root"] = root.as_posix()
    script = root / WMA_APPLY_ORG_SCRIPT
    status["script"] = script.as_posix()
    status["source"] = wma_source_info(root)

    required = list(REQUIRED_WMA_COMMANDS)
    optional = list(OPTIONAL_WMA_COMMANDS)
    if require_diffusion_measurements and "wm_diffusion_measurements.py" not in required:
        required.append("wm_diffusion_measurements.py")
    if require_virtual_x and "xvfb-run" not in required:
        required.append("xvfb-run")
    for command_name in required:
        command_path = _command_path(command_name, root)
        status["commands"][command_name] = command_path.as_posix() if command_path else None
        if command_path is None:
            status["missing_required"].append(command_name)
    for command_name in optional:
        if command_name in required:
            continue
        command_path = _command_path(command_name, root)
        status["commands"][command_name] = command_path.as_posix() if command_path else None
        if command_path is None:
            status["missing_optional"].append(command_name)

    status["script_executable"] = os.access(script, os.X_OK)
    status["available"] = not status["missing_required"] and bool(status["script_executable"])
    return status


def inspect_wma_org_atlas(atlas_dir: Path) -> dict[str, Any]:
    """Inspect the expected ORG atlas directory layout."""

    root = atlas_dir.expanduser().resolve()
    status: dict[str, Any] = {
        "available": False,
        "root": root.as_posix(),
        "exists": root.is_dir(),
        "missing_required_dirs": [],
        "required_dirs": {},
    }
    if not root.is_dir():
        status["missing_required_dirs"] = list(EXPECTED_ORG_ATLAS_DIRS)
        return status

    for dirname in EXPECTED_ORG_ATLAS_DIRS:
        path = root / dirname
        file_count = sum(1 for item in path.rglob("*") if item.is_file()) if path.is_dir() else 0
        status["required_dirs"][dirname] = {
            "path": path.as_posix(),
            "exists": path.is_dir(),
            "file_count": file_count,
        }
        if not path.is_dir():
            status["missing_required_dirs"].append(dirname)
    status["available"] = not status["missing_required_dirs"]
    return status


def summarize_wma_outputs(output_dir: Path, input_tractography: Path) -> dict[str, Any]:
    """Summarize expected WMA output products for manifest/QC."""

    case_id = input_tractography.stem
    case_dir = output_dir / case_id
    anatomical_dir = case_dir / "AnatomicalTracts"
    cluster_dir = case_dir / "FiberClustering"
    initial_dir = cluster_dir / "InitialClusters" / f"{case_id}_reg"
    outlier_dir = cluster_dir / "OutlierRemovedClusters" / f"{case_id}_reg_outlier_removed"
    transformed_dir = cluster_dir / "TransformedClusters" / case_id
    separated_dir = cluster_dir / "SeparatedClusters"
    tracts = sorted(anatomical_dir.glob("*.vtp")) if anatomical_dir.is_dir() else []
    registration_dir = case_dir / "TractRegistration" / case_id
    progress_file = registration_dir / "progress.txt"
    iteration_dirs = sorted(path.name for path in registration_dir.glob("iteration_*") if path.is_dir())

    def _count_vtp(path: Path) -> int:
        return len(list(path.glob("*.vtp"))) if path.is_dir() else 0

    def _vtp_line_count(path: Path) -> Optional[int]:
        """Read a VTP Piece line count without importing VTK or loading points."""

        try:
            with path.open("rb") as stream:
                header = stream.read(64 * 1024)
        except OSError:
            return None
        match = re.search(
            rb'<Piece\b[^>]*\bNumberOfLines=["\'](\d+)["\']',
            header,
            flags=re.DOTALL,
        )
        return int(match.group(1)) if match else None

    anatomical_line_counts = {tract.name: _vtp_line_count(tract) for tract in tracts}
    readable_anatomical_line_counts = {
        name: count for name, count in anatomical_line_counts.items() if count is not None
    }

    progress_summary = _parse_wma_progress(progress_file)

    commissural_dir = separated_dir / "tracts_commissural"
    left_hemi_dir = separated_dir / "tracts_left_hemisphere"
    right_hemi_dir = separated_dir / "tracts_right_hemisphere"
    return {
        "case_id": case_id,
        "case_dir": case_dir.as_posix(),
        "case_dir_exists": case_dir.is_dir(),
        "anatomical_tracts_dir": anatomical_dir.as_posix(),
        "anatomical_tracts_dir_exists": anatomical_dir.is_dir(),
        "anatomical_tract_count": len(tracts),
        "anatomical_tract_readable_count": len(readable_anatomical_line_counts),
        "anatomical_tract_nonempty_count": sum(
            count > 0 for count in readable_anatomical_line_counts.values()
        ),
        "anatomical_streamline_count": sum(readable_anatomical_line_counts.values()),
        "anatomical_empty_tracts": sorted(
            name for name, count in readable_anatomical_line_counts.items() if count == 0
        ),
        "fiber_clustering_dir": cluster_dir.as_posix(),
        "fiber_clustering_dir_exists": cluster_dir.is_dir(),
        "initial_clusters_dir": initial_dir.as_posix(),
        "initial_clusters_dir_exists": initial_dir.is_dir(),
        "initial_cluster_count": _count_vtp(initial_dir),
        "outlier_removed_dir": outlier_dir.as_posix(),
        "outlier_removed_dir_exists": outlier_dir.is_dir(),
        "outlier_removed_cluster_count": _count_vtp(outlier_dir),
        "transformed_clusters_dir": transformed_dir.as_posix(),
        "transformed_clusters_dir_exists": transformed_dir.is_dir(),
        "transformed_cluster_count": _count_vtp(transformed_dir),
        "separated_clusters_dir": separated_dir.as_posix(),
        "separated_clusters_dir_exists": separated_dir.is_dir(),
        "separated_commissural_dir": commissural_dir.as_posix(),
        "separated_commissural_count": _count_vtp(commissural_dir),
        "separated_left_hemisphere_dir": left_hemi_dir.as_posix(),
        "separated_left_hemisphere_count": _count_vtp(left_hemi_dir),
        "separated_right_hemisphere_dir": right_hemi_dir.as_posix(),
        "separated_right_hemisphere_count": _count_vtp(right_hemi_dir),
        "diffusion_measurements_csv": (anatomical_dir / "diffusion_measurements_anatomical_tracts.csv").as_posix(),
        "diffusion_measurements_csv_exists": (anatomical_dir / "diffusion_measurements_anatomical_tracts.csv").is_file(),
        "registration_dir": registration_dir.as_posix(),
        "registration_dir_exists": registration_dir.is_dir(),
        "registration_iteration_dir_count": len(iteration_dirs),
        "registration_iteration_dirs": iteration_dirs,
        "progress_file": progress_file.as_posix(),
        "progress_file_exists": progress_file.is_file(),
        "progress": progress_summary,
    }


def _parse_wma_progress(progress_file: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "exists": progress_file.is_file(),
        "last_nonempty_line": None,
        "completed_iterations": 0,
        "total_iterations": None,
        "latest_percent_finished": None,
        "latest_elapsed_minutes": None,
    }
    if not progress_file.is_file():
        return summary
    text = progress_file.read_text(encoding="utf-8", errors="replace")
    last_line = _last_nonempty_line(text)
    summary["last_nonempty_line"] = last_line
    matches = list(
        re.finditer(
            r"Done iteration\s+(\d+)\s*/\s*(\d+)\.\s*Percent finished approx:\s*([0-9.]+)\.\s*Time:.*Minutes Elapsed:\s*([0-9.]+)",
            text,
        )
    )
    if not matches:
        return summary
    latest = matches[-1]
    summary["completed_iterations"] = int(latest.group(1))
    summary["total_iterations"] = int(latest.group(2))
    summary["latest_percent_finished"] = float(latest.group(3))
    summary["latest_elapsed_minutes"] = float(latest.group(4))
    return summary


def _last_nonempty_line(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _derive_wma_status(output_summary: dict[str, Any], execution_error: Optional[str], executed: bool) -> str:
    if not executed:
        return "planned"
    anatomical_tract_count = int(output_summary.get("anatomical_tract_count", 0) or 0)
    if execution_error and (
        anatomical_tract_count > 0
        or output_summary.get("transformed_cluster_count", 0) > 0
        or output_summary.get("outlier_removed_cluster_count", 0) > 0
        or output_summary.get("initial_cluster_count", 0) > 0
    ):
        return "partial_failed"
    if execution_error:
        return "failed"
    if anatomical_tract_count >= MIN_ANATOMICAL_TRACT_COUNT:
        return "completed"
    if anatomical_tract_count > 0:
        return "partial_failed"
    if output_summary.get("transformed_cluster_count", 0) > 0:
        return "partial_failed"
    if output_summary.get("outlier_removed_cluster_count", 0) > 0:
        return "partial_failed"
    if output_summary.get("initial_cluster_count", 0) > 0:
        return "partial_failed"
    return "failed"


def build_wma_org_atlas_command(config: WMAOrgAtlasConfig) -> tuple[str, ...]:
    wma_root = resolve_wma_root(config.wma_root)
    script = wma_root / WMA_APPLY_ORG_SCRIPT
    if config.registration_mode not in {"rig", "nonrig"}:
        raise ValueError("registration_mode must be 'rig' or 'nonrig'.")
    if config.num_threads < 1:
        raise ValueError("num_threads must be >= 1.")
    if config.clean_files not in {0, 1, 2}:
        raise ValueError("clean_files must be 0, 1, or 2.")

    cmd: list[str] = [
        script.as_posix(),
        "-i",
        config.input_tractography.expanduser().resolve().as_posix(),
        "-o",
        config.output_dir.expanduser().resolve().as_posix(),
        "-a",
        config.atlas_dir.expanduser().resolve().as_posix(),
        "-s",
        config.slicer_executable.expanduser().resolve().as_posix(),
        "-r",
        config.registration_mode,
        "-n",
        str(config.num_threads),
        "-x",
        "1" if config.use_virtual_x else "0",
        "-c",
        str(config.clean_files),
    ]
    if config.transform_path is not None:
        cmd.extend(["-t", config.transform_path.expanduser().resolve().as_posix()])
    if config.export_diffusion_measures:
        if config.fiber_tract_measurements_cli is None:
            raise ValueError("fiber_tract_measurements_cli is required when export_diffusion_measures=True.")
        cmd.extend(
            [
                "-d",
                "1",
                "-m",
                config.fiber_tract_measurements_cli.expanduser().resolve().as_posix(),
            ]
        )
    return tuple(cmd)


def _resolve_tckconvert(config: WMAOrgAtlasConfig) -> Optional[Path]:
    configured_dirs: list[Path] = []
    if config.mrtrix_bin_dir is not None:
        configured_dirs.append(config.mrtrix_bin_dir.expanduser())
    for env_name in ("SLICERDDSURFER_MRTRIX_BIN_DIR", "MRTRIX_BIN_DIR"):
        value = os.environ.get(env_name)
        if value:
            configured_dirs.append(Path(value).expanduser())
    executable_names = ("tckconvert.exe", "tckconvert") if os.name == "nt" else ("tckconvert",)
    for bin_dir in configured_dirs:
        for executable_name in executable_names:
            candidate = bin_dir / executable_name
            if candidate.is_file():
                return candidate.resolve()
    resolved = shutil.which("tckconvert")
    return Path(resolved).resolve() if resolved else None


def validate_wma_org_inputs(config: WMAOrgAtlasConfig) -> None:
    if not config.subject_id.strip():
        raise ValueError("subject_id is required.")
    input_suffix = config.input_tractography.suffix.lower()
    if input_suffix not in {".vtk", ".vtp", ".tck"}:
        raise ValueError("WMA ORG atlas input must be a whole-brain VTK/VTP/TCK tractography file.")
    if not config.input_tractography.expanduser().is_file():
        raise FileNotFoundError(f"Input tractography not found: {config.input_tractography}")
    if input_suffix == ".tck" and _resolve_tckconvert(config) is None:
        raise RuntimeError(
            "TCK input requires MRtrix3 tckconvert. Configure mrtrix_bin_dir, "
            "SLICERDDSURFER_MRTRIX_BIN_DIR, MRTRIX_BIN_DIR, or PATH."
        )
    if not config.atlas_dir.expanduser().is_dir():
        raise FileNotFoundError(f"WMA ORG atlas directory not found: {config.atlas_dir}")
    atlas_status = inspect_wma_org_atlas(config.atlas_dir)
    if not atlas_status["available"]:
        missing = ", ".join(atlas_status["missing_required_dirs"])
        raise FileNotFoundError(f"WMA ORG atlas directory is incomplete. Missing: {missing}")
    if not config.slicer_executable.expanduser().is_file():
        raise FileNotFoundError(f"Slicer executable not found: {config.slicer_executable}")
    if config.transform_path is not None and not config.transform_path.expanduser().is_file():
        raise FileNotFoundError(f"Transform file not found: {config.transform_path}")
    if (
        config.fiber_tract_measurements_cli is not None
        and not config.fiber_tract_measurements_cli.expanduser().is_file()
    ):
        raise FileNotFoundError(f"FiberTractMeasurements CLI not found: {config.fiber_tract_measurements_cli}")
    backend_status = inspect_wma_backend(
        config.wma_root,
        require_virtual_x=config.use_virtual_x,
        require_diffusion_measurements=config.export_diffusion_measures,
    )
    if not backend_status["available"]:
        missing = ", ".join(backend_status["missing_required"])
        raise RuntimeError(f"WMA backend is incomplete. Missing required command(s): {missing}")


def run_wma_org_atlas(
    config: WMAOrgAtlasConfig,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> WMAOrgAtlasResult:
    """Prepare or execute WMA ORG atlas clustering for one tractogram."""

    validate_wma_org_inputs(config)
    wma_root = resolve_wma_root(config.wma_root)
    backend_status = inspect_wma_backend(
        wma_root,
        require_virtual_x=config.use_virtual_x,
        require_diffusion_measurements=config.export_diffusion_measures,
    )
    atlas_status = inspect_wma_org_atlas(config.atlas_dir)
    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_tractography = config.input_tractography.expanduser().resolve()
    prepared_tractography = source_tractography
    conversion_command: tuple[str, ...] = ()
    if source_tractography.suffix.lower() == ".tck":
        prepared_tractography = output_dir / "input" / f"{source_tractography.stem}.vtk"
        tckconvert = _resolve_tckconvert(config)
        if tckconvert is None:  # Defensive: validate_wma_org_inputs already checks this.
            raise RuntimeError("MRtrix3 tckconvert was not found.")
        conversion_command = (
            tckconvert.as_posix(),
            source_tractography.as_posix(),
            prepared_tractography.as_posix(),
            "-force",
        )
    runtime_config = replace(config, input_tractography=prepared_tractography)
    command = build_wma_org_atlas_command(runtime_config)
    manifest_path = output_dir / "wma_org_atlas_manifest.json"
    qc_path = output_dir / "wma_org_atlas_qc.json"
    log_dir = output_dir / "logs"
    stdout_log = log_dir / "wma_stdout.log"
    stderr_log = log_dir / "wma_stderr.log"
    conversion_stdout_log = log_dir / "tckconvert_stdout.log"
    conversion_stderr_log = log_dir / "tckconvert_stderr.log"
    output_summary = summarize_wma_outputs(output_dir, prepared_tractography)

    manifest = {
        "kind": "wma_org_atlas",
        "version": 3,
        "name": "WMA ORG atlas clustering",
        "subject_id": config.subject_id,
        "input_tractography": source_tractography.as_posix(),
        "prepared_input_tractography": prepared_tractography.as_posix(),
        "input_conversion": {
            "required": bool(conversion_command),
            "command": list(conversion_command),
            "stdout_log": conversion_stdout_log.as_posix(),
            "stderr_log": conversion_stderr_log.as_posix(),
        },
        "atlas_dir": config.atlas_dir.expanduser().resolve().as_posix(),
        "output_dir": output_dir.as_posix(),
        "registration_mode": config.registration_mode,
        "num_threads": config.num_threads,
        "use_virtual_x": config.use_virtual_x,
        "export_diffusion_measures": config.export_diffusion_measures,
        "clean_files": config.clean_files,
        "executed": bool(config.execute),
        "status": "planned" if not config.execute else "running",
        "command": list(command),
        "backend": backend_status,
        "atlas": atlas_status,
        "outputs": {
            "qc": qc_path.as_posix(),
            "stdout_log": stdout_log.as_posix(),
            "stderr_log": stderr_log.as_posix(),
            "summary": output_summary,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if log:
        mode = "Executing" if config.execute else "Prepared dry-run"
        log(f"[WMA] {mode} ORG atlas command: {' '.join(command)}")
        log(f"[WMA] Manifest: {manifest_path}")

    start_time = time.monotonic()
    return_code: Optional[int] = None
    execution_error: Optional[str] = None
    if config.execute:
        log_dir.mkdir(parents=True, exist_ok=True)
        env = merged_startup_environment()
        python_path = wma_root.as_posix()
        env["PYTHONPATH"] = (
            python_path if not env.get("PYTHONPATH") else python_path + os.pathsep + env["PYTHONPATH"]
        )
        slicer_executable = config.slicer_executable.expanduser().resolve()
        slicer_python_candidates = (
            slicer_executable.parent / "PythonSlicer",
            slicer_executable.parent / "bin" / "PythonSlicer",
        )
        slicer_python = next((candidate for candidate in slicer_python_candidates if candidate.is_file()), None)
        path_entries = [
            (wma_root / "bin").as_posix(),
            (wma_root / "utilities").as_posix(),
        ]
        path_entries.extend(tool_dir.as_posix() for tool_dir in EXTRA_TOOL_DIRS if tool_dir.is_dir())
        library_entries = [path.as_posix() for path in _slicer_runtime_library_paths(slicer_executable)]
        runtime_display = _resolve_runtime_display()
        temp_python_dir: Optional[tempfile.TemporaryDirectory[str]] = None
        try:
            if conversion_command:
                prepared_tractography.parent.mkdir(parents=True, exist_ok=True)
                if log:
                    log("[WMA] Converting TCK input: " + " ".join(conversion_command))
                conversion_env = external_python_environment(
                    path_prepend=(config.mrtrix_bin_dir,) if config.mrtrix_bin_dir is not None else (),
                )
                converted = subprocess.run(
                    conversion_command,
                    check=True,
                    env=conversion_env,
                    capture_output=True,
                    text=True,
                )
                conversion_stdout_log.write_text(converted.stdout or "", encoding="utf-8")
                conversion_stderr_log.write_text(converted.stderr or "", encoding="utf-8")
            slicerdmri_paths = _slicerdmri_module_paths(slicer_executable)
            if slicer_python is not None or config.use_virtual_x or slicerdmri_paths:
                temp_python_dir = tempfile.TemporaryDirectory(prefix="slicerdds_wma_python_")
                if slicer_python is not None:
                    shim = Path(temp_python_dir.name) / "python"
                    shim.symlink_to(slicer_python)
                if config.use_virtual_x:
                    real_xvfb = _command_path("xvfb-run", wma_root)
                    if real_xvfb is not None:
                        xvfb_shim = Path(temp_python_dir.name) / "xvfb-run"
                        xvfb_shim.write_text(
                            f"#!/bin/sh\nexec {real_xvfb.as_posix()} -a \"$@\"\n",
                            encoding="utf-8",
                        )
                        xvfb_shim.chmod(0o755)
                if slicerdmri_paths:
                    slicer_shim = Path(temp_python_dir.name) / "Slicer"
                    slicer_launcher = _resolve_slicer_launcher(slicer_executable)
                    module_args = " ".join(
                        f"--additional-module-paths '{path.as_posix()}'" for path in slicerdmri_paths
                    )
                    slicer_shim.write_text(
                        f"#!/bin/sh\nexec '{slicer_launcher.as_posix()}' {module_args} \"$@\"\n",
                        encoding="utf-8",
                    )
                    slicer_shim.chmod(0o755)
                    runtime_command = list(command)
                    if "-s" in runtime_command:
                        runtime_command[runtime_command.index("-s") + 1] = slicer_shim.as_posix()
                    if runtime_display and "-x" in runtime_command:
                        runtime_command[runtime_command.index("-x") + 1] = "0"
                    command_to_run = tuple(runtime_command)
                else:
                    command_to_run = command
                path_entries.insert(0, temp_python_dir.name)
            else:
                command_to_run = command
            env["PATH"] = os.pathsep.join(path_entries + ([env["PATH"]] if env.get("PATH") else []))
            if library_entries:
                env["LD_LIBRARY_PATH"] = os.pathsep.join(
                    library_entries + ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else [])
                )
            if runtime_display:
                env["DISPLAY"] = runtime_display
            completed = subprocess.run(
                command_to_run,
                check=True,
                cwd=wma_root.as_posix(),
                env=env,
                capture_output=True,
                text=True,
            )
            stdout_log.write_text(completed.stdout or "", encoding="utf-8")
            stderr_log.write_text(completed.stderr or "", encoding="utf-8")
            return_code = completed.returncode
        except subprocess.CalledProcessError as exc:
            return_code = exc.returncode
            failed_stdout = conversion_stdout_log if conversion_command and not prepared_tractography.is_file() else stdout_log
            failed_stderr = conversion_stderr_log if conversion_command and not prepared_tractography.is_file() else stderr_log
            failed_stdout.write_text(exc.stdout or "", encoding="utf-8")
            failed_stderr.write_text(exc.stderr or "", encoding="utf-8")
            execution_error = str(exc)
        except KeyboardInterrupt:
            return_code = 130
            execution_error = "Interrupted by user."
            stderr_log.write_text(execution_error + "\n", encoding="utf-8")
        except Exception as exc:
            return_code = None
            execution_error = f"{type(exc).__name__}: {exc}"
            stderr_log.write_text(traceback.format_exc(), encoding="utf-8")
        finally:
            if temp_python_dir is not None:
                temp_python_dir.cleanup()
            output_summary = summarize_wma_outputs(output_dir, prepared_tractography)
            if (
                execution_error is None
                and config.execute
                and int(output_summary.get("anatomical_tract_count", 0) or 0)
                < MIN_ANATOMICAL_TRACT_COUNT
            ):
                log_hint = _last_nonempty_line(stderr_log.read_text(encoding="utf-8") if stderr_log.is_file() else "")
                if log_hint is None:
                    log_hint = _last_nonempty_line(stdout_log.read_text(encoding="utf-8") if stdout_log.is_file() else "")
                execution_error = (
                    "WMA command returned without a complete AnatomicalTracts output "
                    f"(expected at least {MIN_ANATOMICAL_TRACT_COUNT}, found "
                    f"{output_summary.get('anatomical_tract_count', 0)})."
                )
                if log_hint:
                    execution_error += f" Last log line: {log_hint}"

    elapsed_seconds = time.monotonic() - start_time
    status = _derive_wma_status(output_summary, execution_error, bool(config.execute))
    qc = {
        "kind": "wma_org_atlas_qc",
        "version": 1,
        "subject_id": config.subject_id,
        "status": status,
        "executed": bool(config.execute),
        "return_code": return_code,
        "elapsed_seconds": elapsed_seconds,
        "backend_available": bool(backend_status["available"]),
        "atlas_available": bool(atlas_status["available"]),
        "output_summary": output_summary,
        "acceptance_criteria": {
            "minimum_anatomical_tract_count": MIN_ANATOMICAL_TRACT_COUNT,
        },
        "logs": {
            "stdout": stdout_log.as_posix(),
            "stderr": stderr_log.as_posix(),
            "stdout_exists": stdout_log.is_file(),
            "stderr_exists": stderr_log.is_file(),
            "tckconvert_stdout": conversion_stdout_log.as_posix(),
            "tckconvert_stderr": conversion_stderr_log.as_posix(),
        },
        "error": execution_error,
    }
    qc_path.write_text(json.dumps(qc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest["status"] = status
    manifest["executed"] = bool(config.execute)
    manifest["return_code"] = return_code
    manifest["runtime_seconds"] = elapsed_seconds
    manifest["error"] = execution_error
    manifest["environment"] = {
        "use_virtual_x": config.use_virtual_x,
        "runtime_display": _resolve_runtime_display(),
        "resolved_wma_root": wma_root.as_posix(),
        "resolved_tckconvert": _resolve_tckconvert(config).as_posix() if conversion_command else None,
        "resolved_slicer_executable": config.slicer_executable.expanduser().resolve().as_posix(),
        "resolved_slicer_launcher": _resolve_slicer_launcher(config.slicer_executable).as_posix(),
    }
    manifest["outputs"]["summary"] = output_summary
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return WMAOrgAtlasResult(
        subject_id=config.subject_id,
        status=status,
        output_dir=output_dir,
        manifest_path=manifest_path,
        qc_path=qc_path,
        command=command,
        executed=bool(config.execute),
        backend_status=backend_status,
        atlas_status=atlas_status,
        return_code=return_code,
    )
