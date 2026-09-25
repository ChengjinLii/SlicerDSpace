"""WMQL / Tract Querier integration for rule-based bundle extraction."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Optional

from shared.external_process import merged_startup_environment, text_subprocess_kwargs


TRACT_QUERIER_REPOSITORY = "https://github.com/demianw/tract_querier"
VALID_TRACT_EXTENSIONS = {".vtk", ".vtp", ".trk"}


def _file_info(path: Path) -> dict[str, object]:
    expanded = path.expanduser()
    if not expanded.exists():
        return {"path": expanded.as_posix(), "exists": False}
    stat = expanded.stat()
    return {
        "path": expanded.resolve().as_posix(),
        "exists": True,
        "is_file": expanded.is_file(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


@dataclass(frozen=True)
class WMQLConfig:
    subject_id: str
    input_tractography: Path
    atlas_path: Path
    output_dir: Path
    query_path: Optional[Path] = None
    query_selection: tuple[str, ...] = ("AF.left", "AF.right", "CST.left", "CST.right")
    tract_querier_root: Optional[Path] = None
    tract_querier_executable: Optional[Path] = None
    python_executable: Optional[Path] = None
    include_dirs: tuple[Path, ...] = ()
    threshold: float = 2.0
    length_threshold: float = 0.0
    execute: bool = False


@dataclass(frozen=True)
class WMQLResult:
    subject_id: str
    output_dir: Path
    manifest_path: Path
    qc_path: Path
    command: tuple[str, ...]
    executed: bool
    backend_status: dict[str, Any]
    return_code: Optional[int] = None


def bundled_wmql_query_path() -> Path:
    return Path(__file__).resolve().parent / "wmql_queries" / "AF_CST.qry"


def _default_query_data_dir() -> Optional[Path]:
    candidate = Path(__file__).resolve().parent.parent / "third_party" / "tract_querier" / "tract_querier" / "data"
    return candidate if candidate.is_dir() else None


def _resolve_python(python_executable: Optional[Path]) -> Path:
    if python_executable is not None:
        candidate = python_executable.expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"Python executable not found: {candidate}")
        return candidate
    for env_name in ("SLICERDDSURFER_WMQL_PYTHON", "TRACT_QUERIER_PYTHON"):
        env_value = os.environ.get(env_name)
        if env_value:
            candidate = Path(env_value).expanduser().resolve()
            if not candidate.is_file():
                raise FileNotFoundError(f"Python executable not found from {env_name}: {candidate}")
            return candidate
    return Path(sys.executable).resolve()


def _probe_python_package(python_path: Path, tract_querier_root: Optional[Path]) -> dict[str, Any]:
    env = merged_startup_environment()
    if tract_querier_root is not None:
        env["PYTHONPATH"] = tract_querier_root.expanduser().resolve().as_posix() + os.pathsep + env.get("PYTHONPATH", "")
    probe = (
        "import importlib.util, json; "
        "print(json.dumps({'tract_querier': importlib.util.find_spec('tract_querier') is not None, "
        "'nibabel': importlib.util.find_spec('nibabel') is not None, "
        "'numpy': importlib.util.find_spec('numpy') is not None}))"
    )
    try:
        completed = subprocess.run(
            [python_path.as_posix(), "-c", probe],
            check=True,
            capture_output=True,
            env=env,
            **text_subprocess_kwargs(),
        )
        return json.loads(completed.stdout.strip() or "{}")
    except Exception as exc:
        return {"error": str(exc), "tract_querier": False, "nibabel": False, "numpy": False}


def inspect_wmql_backend(
    *,
    tract_querier_root: Optional[Path] = None,
    tract_querier_executable: Optional[Path] = None,
    python_executable: Optional[Path] = None,
) -> dict[str, Any]:
    """Inspect Tract Querier availability without running WMQL."""

    python_path = _resolve_python(python_executable)
    root = tract_querier_root.expanduser().resolve() if tract_querier_root is not None else None
    explicit_cli = tract_querier_executable.expanduser().resolve() if tract_querier_executable is not None else None
    env_cli = os.environ.get("SLICERDDSURFER_WMQL_EXECUTABLE") or os.environ.get("TRACT_QUERIER_EXECUTABLE")
    cli_path: Optional[Path] = None
    if explicit_cli is not None:
        cli_path = explicit_cli
    elif env_cli:
        cli_path = Path(env_cli).expanduser().resolve()
    else:
        found = shutil.which("tract_querier")
        if found:
            cli_path = Path(found).resolve()

    root_script = root / "scripts" / "cli_tract_querier.py" if root is not None else None
    package_status = _probe_python_package(python_path, root)
    commands = {
        "tract_querier_executable": cli_path.as_posix() if cli_path and cli_path.is_file() else None,
        "root_script": root_script.as_posix() if root_script and root_script.is_file() else None,
        "python": python_path.as_posix(),
    }
    missing: list[str] = []
    has_runner = bool(commands["tract_querier_executable"] or commands["root_script"])
    if not has_runner:
        missing.append("tract_querier executable or tract_querier_root/scripts/cli_tract_querier.py")
    for package in ("tract_querier", "nibabel", "numpy"):
        if not package_status.get(package):
            missing.append(f"python package: {package}")

    return {
        "kind": "wmql_backend",
        "repository": TRACT_QUERIER_REPOSITORY,
        "available": not missing,
        "root": root.as_posix() if root else None,
        "commands": commands,
        "python_packages": package_status,
        "missing_required": missing,
    }


def _query_include_dirs(config: WMQLConfig, query_path: Path) -> list[Path]:
    dirs: list[Path] = [query_path.parent]
    dirs.extend(path.expanduser().resolve() for path in config.include_dirs)
    if config.tract_querier_root is not None:
        data_dir = config.tract_querier_root.expanduser().resolve() / "tract_querier" / "data"
        if data_dir.is_dir():
            dirs.append(data_dir)
    default_data = _default_query_data_dir()
    if default_data is not None:
        dirs.append(default_data.resolve())
    unique: list[Path] = []
    for path in dirs:
        if path not in unique:
            unique.append(path)
    return unique


def _requires_windows_query_staging() -> bool:
    """TractQuerier splits ``-I`` on ``:`` and therefore breaks drive paths."""

    return os.name == "nt"


def _stage_query_includes(include_dirs: list[Path], queries_dir: Path) -> None:
    """Stage query includes in one cwd that TractQuerier can search on Windows."""

    for include_dir in include_dirs:
        source_dir = include_dir.expanduser().resolve()
        if not source_dir.is_dir():
            raise FileNotFoundError(f"WMQL include directory not found: {source_dir}")
        for source in sorted(source_dir.glob("*.qry")):
            target = queries_dir / source.name
            if source.resolve() == target.resolve():
                continue
            if target.exists():
                # Include directories are ordered by precedence: the selected
                # query directory, explicit user paths, then bundled fallbacks.
                # Keep the first matching file, mirroring normal query lookup.
                continue
            shutil.copy2(source, target)


def build_wmql_command(config: WMQLConfig, backend_status: Optional[dict[str, Any]] = None) -> tuple[str, ...]:
    backend = backend_status or inspect_wmql_backend(
        tract_querier_root=config.tract_querier_root,
        tract_querier_executable=config.tract_querier_executable,
        python_executable=config.python_executable,
    )
    query_path = (config.query_path or bundled_wmql_query_path()).expanduser().resolve()
    output_prefix = config.output_dir.expanduser().resolve() / f"{config.subject_id}_desc-wmql"
    include_dirs = _query_include_dirs(config, query_path)
    query_selection = ",".join(name.lower() for name in config.query_selection if name.strip())

    cli = backend["commands"].get("tract_querier_executable")
    root_script = backend["commands"].get("root_script")
    if cli:
        cmd = [cli]
    elif root_script:
        cmd = [backend["commands"]["python"], root_script]
    else:
        cmd = [backend["commands"]["python"], "-m", "tract_querier.scripts.cli_tract_querier"]

    cmd.extend(
        [
            "-t",
            config.input_tractography.expanduser().resolve().as_posix(),
            "-a",
            config.atlas_path.expanduser().resolve().as_posix(),
            "-q",
            query_path.as_posix(),
            "-o",
            output_prefix.as_posix(),
        ]
    )
    if include_dirs and not _requires_windows_query_staging():
        # TractQuerier currently hard-codes ':' as its include separator.
        cmd.extend(["-I", ":".join(path.as_posix() for path in include_dirs)])
    cmd.extend(
        [
            "--threshold",
            str(config.threshold),
            "--length_threshold",
            str(config.length_threshold),
        ]
    )
    if query_selection:
        cmd.extend(["--query_selection", query_selection])
    return tuple(cmd)


def summarize_wmql_outputs(output_dir: Path) -> dict[str, Any]:
    root = output_dir.expanduser().resolve()
    bundle_files = sorted(
        path for path in root.glob("*") if path.suffix.lower() in VALID_TRACT_EXTENSIONS and "_desc-wmql_" in path.name
    ) if root.is_dir() else []
    bundle_details: list[dict[str, Any]] = []
    for path in bundle_files:
        detail: dict[str, Any] = {"path": path.as_posix(), "size": path.stat().st_size}
        if path.suffix.lower() in {".trk", ".tck"}:
            try:
                import nibabel as nib

                detail["streamline_count"] = len(nib.streamlines.load(path.as_posix()).streamlines)
            except Exception as exc:  # pragma: no cover - best-effort QC
                detail["streamline_count_error"] = str(exc)
        elif path.suffix.lower() in {".vtk", ".vtp"}:
            try:
                import re

                header = path.read_bytes()[: 64 * 1024]
                if path.suffix.lower() == ".vtp":
                    match = re.search(
                        rb'<Piece\b[^>]*\bNumberOfLines=["\'](\d+)["\']',
                        header,
                        flags=re.DOTALL,
                    )
                else:
                    match = re.search(rb"(?im)^\s*LINES\s+(\d+)\s+", header)
                if match is None:
                    raise ValueError("streamline count was not found in the VTK header")
                detail["streamline_count"] = int(match.group(1))
            except Exception as exc:  # pragma: no cover - best-effort QC
                detail["streamline_count_error"] = str(exc)
        bundle_details.append(detail)
    readable = [item for item in bundle_details if "streamline_count" in item]
    nonempty = [item for item in readable if int(item["streamline_count"]) > 0]
    return {
        "root": root.as_posix(),
        "root_exists": root.is_dir(),
        "bundle_count": len(bundle_files),
        "bundle_files": [path.as_posix() for path in bundle_files],
        "bundles": bundle_details,
        "bundle_readable_count": len(readable),
        "bundle_nonempty_count": len(nonempty),
        "streamline_count": sum(int(item["streamline_count"]) for item in readable),
        "unreadable_bundle_files": [
            str(item["path"]) for item in bundle_details if "streamline_count_error" in item
        ],
        "empty_bundle_files": [
            str(item["path"])
            for item in readable
            if int(item["streamline_count"]) == 0
        ],
    }


def _wmql_output_contract_error(
    output_summary: dict[str, Any],
    expected_bundle_count: int,
) -> Optional[str]:
    bundle_count = int(output_summary.get("bundle_count", 0) or 0)
    readable_count = int(output_summary.get("bundle_readable_count", 0) or 0)
    nonempty_count = int(output_summary.get("bundle_nonempty_count", 0) or 0)
    expected = max(1, expected_bundle_count)
    if bundle_count < expected:
        return f"WMQL produced {bundle_count} bundle files; at least {expected} were requested."
    if readable_count != bundle_count:
        return "WMQL produced one or more bundle files that could not be decoded."
    if nonempty_count < expected:
        return f"WMQL produced only {nonempty_count} non-empty bundles; at least {expected} were requested."
    return None


def _validate_wmql_config(config: WMQLConfig, backend_status: dict[str, Any]) -> None:
    if not config.subject_id.strip():
        raise ValueError("subject_id is required.")
    if config.input_tractography.suffix.lower() not in VALID_TRACT_EXTENSIONS:
        raise ValueError("WMQL input tractography must be .vtk, .vtp, or .trk.")
    if not config.input_tractography.expanduser().is_file():
        raise FileNotFoundError(f"Input tractography not found: {config.input_tractography}")
    if not config.atlas_path.expanduser().is_file():
        raise FileNotFoundError(f"WMQL atlas/parcellation not found: {config.atlas_path}")
    query_path = config.query_path or bundled_wmql_query_path()
    if not query_path.expanduser().is_file():
        raise FileNotFoundError(f"WMQL query file not found: {query_path}")
    if config.threshold < 0:
        raise ValueError("threshold must be non-negative.")
    if config.length_threshold < 0:
        raise ValueError("length_threshold must be non-negative.")
    if config.execute and not backend_status["available"]:
        raise RuntimeError("WMQL backend is incomplete. Missing: " + ", ".join(backend_status["missing_required"]))


def run_wmql_bundle_segmentation(
    config: WMQLConfig,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> WMQLResult:
    """Prepare or execute WMQL bundle extraction for one whole-brain tractogram."""

    backend_status = inspect_wmql_backend(
        tract_querier_root=config.tract_querier_root,
        tract_querier_executable=config.tract_querier_executable,
        python_executable=config.python_executable,
    )
    _validate_wmql_config(config, backend_status)
    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    queries_dir = output_dir / "queries"
    queries_dir.mkdir(parents=True, exist_ok=True)
    query_path = (config.query_path or bundled_wmql_query_path()).expanduser().resolve()
    staged_query = queries_dir / query_path.name
    if query_path.resolve() != staged_query.resolve():
        shutil.copy2(query_path, staged_query)
    if _requires_windows_query_staging():
        _stage_query_includes(_query_include_dirs(config, query_path), queries_dir)
    command_config = replace(config, query_path=staged_query)
    command = build_wmql_command(command_config, backend_status)

    manifest_path = output_dir / "wmql_manifest.json"
    qc_path = output_dir / "wmql_qc.json"
    output_summary = summarize_wmql_outputs(output_dir)
    manifest: dict[str, Any] = {
        "kind": "wmql_bundle_segmentation",
        "version": 2,
        "subject_id": config.subject_id,
        "input_tractography": config.input_tractography.expanduser().resolve().as_posix(),
        "atlas_path": config.atlas_path.expanduser().resolve().as_posix(),
        "query_path": query_path.as_posix(),
        "staged_query": staged_query.as_posix(),
        "query_selection": list(config.query_selection),
        "threshold": config.threshold,
        "length_threshold": config.length_threshold,
        "executed": bool(config.execute),
        "status": "planned" if not config.execute else "running",
        "command": list(command),
        "execution_cwd": queries_dir.as_posix() if _requires_windows_query_staging() else None,
        "backend": backend_status,
        "dependencies": {
            "input_tractography": _file_info(config.input_tractography),
            "atlas": _file_info(config.atlas_path),
            "query": _file_info(query_path),
        },
        "outputs": {"qc": qc_path.as_posix(), "summary": output_summary},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if log:
        mode = "Executing" if config.execute else "Prepared dry-run"
        log(f"[WMQL] {mode} command: {' '.join(command)}")
        log(f"[WMQL] Manifest: {manifest_path}")

    start_time = time.monotonic()
    return_code: Optional[int] = None
    execution_error: Optional[str] = None
    execution_exception: Optional[Exception] = None
    if config.execute:
        env = merged_startup_environment()
        if config.tract_querier_root is not None:
            root = config.tract_querier_root.expanduser().resolve()
            env["PYTHONPATH"] = root.as_posix() + os.pathsep + env.get("PYTHONPATH", "")
        try:
            output_prefix = f"{config.subject_id}_desc-wmql_"
            for stale_output in output_dir.glob(f"{output_prefix}*"):
                if stale_output.is_file() and stale_output.suffix.lower() in VALID_TRACT_EXTENSIONS:
                    stale_output.unlink()
            completed = subprocess.run(
                command,
                check=True,
                env=env,
                cwd=queries_dir if _requires_windows_query_staging() else None,
            )
            return_code = completed.returncode
        except subprocess.CalledProcessError as exc:
            return_code = exc.returncode
            execution_error = str(exc)
            execution_exception = exc
        except OSError as exc:
            # Preserve launch failures (missing/broken executables, permission
            # errors) in QC/manifest before surfacing the original exception.
            execution_error = f"{type(exc).__name__}: {exc}"
            execution_exception = exc
        finally:
            output_summary = summarize_wmql_outputs(output_dir)

    if config.execute and execution_error is None:
        execution_error = _wmql_output_contract_error(
            output_summary,
            len(config.query_selection),
        )

    elapsed_seconds = time.monotonic() - start_time
    qc = {
        "kind": "wmql_bundle_segmentation_qc",
        "version": 2,
        "subject_id": config.subject_id,
        "status": "failed" if execution_error else ("completed" if config.execute else "planned"),
        "executed": bool(config.execute),
        "return_code": return_code,
        "elapsed_seconds": elapsed_seconds,
        "backend_available": bool(backend_status["available"]),
        "output_summary": output_summary,
        "error": execution_error,
    }
    qc_path.write_text(json.dumps(qc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest["status"] = qc["status"]
    manifest["executed"] = bool(config.execute)
    manifest["return_code"] = return_code
    manifest["outputs"]["summary"] = output_summary
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if execution_exception is not None:
        raise execution_exception

    return WMQLResult(
        subject_id=config.subject_id,
        output_dir=output_dir,
        manifest_path=manifest_path,
        qc_path=qc_path,
        command=command,
        executed=bool(config.execute),
        backend_status=backend_status,
        return_code=return_code,
    )
