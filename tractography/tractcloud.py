"""TractCloud integration for tractography parcellation.

This backend follows the SlicerDMRI TractCloud module design but keeps
dependency installation and execution explicit. It prepares a reproducible
``python -m tractcloud`` command, manifest, and QC record, and only runs when
``execute=True``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from shared.external_process import merged_startup_environment
from shared.output_contracts import vtp_streamline_count


TRACTCLOUD_REPOSITORY = "https://github.com/SlicerDMRI/TractCloud"
VALID_TRACTCLOUD_DEVICES = {"auto", "cpu", "cuda"}


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
class TractCloudConfig:
    """Configuration for TractCloud whole-brain tractography parcellation."""

    subject_id: str
    input_tractography: Path
    output_dir: Path
    tractcloud_root: Optional[Path] = None
    python_executable: Optional[Path] = None
    include_other: bool = False
    device: str = "auto"
    batch_size: int = 2048
    data_dir: Optional[Path] = None
    create_mrb: bool = False
    execute: bool = False


@dataclass(frozen=True)
class TractCloudResult:
    """Prepared or completed TractCloud parcellation run."""

    subject_id: str
    output_dir: Path
    manifest_path: Path
    qc_path: Path
    command: tuple[str, ...]
    executed: bool
    backend_status: dict[str, Any]
    return_code: Optional[int] = None


def resolve_tractcloud_python(python_executable: Optional[Path] = None) -> Path:
    """Resolve the Python executable used to invoke ``python -m tractcloud``."""

    if python_executable is not None:
        candidate = python_executable.expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"TractCloud Python executable not found: {candidate}")
        return candidate

    env_value = (
        os.environ.get("SLICERDDSURFER_TRACTCLOUD_PYTHON_EXECUTABLE")
        or os.environ.get("TRACTCLOUD_PYTHON_EXECUTABLE")
        or os.environ.get("SLICERDDSURFER_TRACTCLOUD_PYTHON")
        or os.environ.get("TRACTCLOUD_PYTHON")
    )
    if env_value:
        candidate = Path(env_value).expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"TractCloud Python executable not found: {candidate}")
        return candidate

    for executable_name in ("PythonSlicer", "python3", "python"):
        found = shutil.which(executable_name)
        if found:
            return Path(found).resolve()

    return Path(sys.executable).resolve()


def resolve_tractcloud_root(tractcloud_root: Optional[Path] = None) -> Optional[Path]:
    """Resolve an optional TractCloud source checkout."""

    candidate_value = tractcloud_root
    if candidate_value is None:
        env_value = os.environ.get("SLICERDDSURFER_TRACTCLOUD_ROOT") or os.environ.get("TRACTCLOUD_ROOT")
        candidate_value = Path(env_value) if env_value else None
    if candidate_value is None:
        return None

    candidate = candidate_value.expanduser().resolve()
    package_candidates = [
        candidate / "tractcloud",
        candidate / "src" / "tractcloud",
    ]
    if not any(path.is_dir() for path in package_candidates):
        raise FileNotFoundError(
            f"TractCloud source checkout not found at {candidate}. Expected tractcloud/ or src/tractcloud/."
        )
    return candidate


def _tractcloud_pythonpath(root: Optional[Path]) -> Optional[str]:
    if root is None:
        return None
    src_dir = root / "src"
    return src_dir.as_posix() if (src_dir / "tractcloud").is_dir() else root.as_posix()


def _tractcloud_source_info(root: Optional[Path]) -> dict[str, Any] | None:
    if root is None:
        return None
    info: dict[str, Any] = {
        "root": root.as_posix(),
        "repository": TRACTCLOUD_REPOSITORY,
        "pythonpath": _tractcloud_pythonpath(root),
    }
    if (root / ".git").is_dir():
        try:
            commit = subprocess.check_output(
                ["git", "-C", root.as_posix(), "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            info["commit"] = commit
        except Exception:
            pass
    return info


def _tractcloud_env(config: "TractCloudConfig", backend_status: Optional[dict[str, Any]] = None) -> dict[str, str]:
    env: dict[str, str] = {}
    source = backend_status.get("source") if backend_status else None
    root_value = source.get("pythonpath") if isinstance(source, dict) else None
    if root_value:
        env["PYTHONPATH"] = root_value
    if config.data_dir is not None:
        env["TRACTCLOUD_DATA_DIR"] = config.data_dir.expanduser().resolve().as_posix()
    return env


def inspect_tractcloud_backend(
    python_executable: Optional[Path] = None,
    tractcloud_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Inspect TractCloud package availability without importing torch in-process."""

    python_path = resolve_tractcloud_python(python_executable)
    root = resolve_tractcloud_root(tractcloud_root)
    status: dict[str, Any] = {
        "available": False,
        "python_executable": python_path.as_posix(),
        "repository": TRACTCLOUD_REPOSITORY,
        "source": _tractcloud_source_info(root),
        "packages": {
            "tractcloud": False,
            "torch": False,
        },
        "error": None,
    }
    probe = (
        "import importlib.util, json; "
        "print(json.dumps({"
        "'tractcloud': importlib.util.find_spec('tractcloud') is not None, "
        "'torch': importlib.util.find_spec('torch') is not None"
        "}))"
    )
    try:
        env = merged_startup_environment()
        source_pythonpath = _tractcloud_pythonpath(root)
        if source_pythonpath:
            env["PYTHONPATH"] = source_pythonpath + os.pathsep + env.get("PYTHONPATH", "")
        completed = subprocess.run(
            [python_path.as_posix(), "-c", probe],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        packages = json.loads(completed.stdout.strip() or "{}")
        status["packages"].update({key: bool(packages.get(key)) for key in status["packages"]})
        status["available"] = bool(status["packages"]["tractcloud"] and status["packages"]["torch"])
    except Exception as exc:
        status["error"] = str(exc)
    return status


def validate_tractcloud_inputs(config: TractCloudConfig) -> None:
    if not config.subject_id.strip():
        raise ValueError("subject_id is required.")
    if config.input_tractography.suffix.lower() not in {".vtk", ".vtp"}:
        raise ValueError("TractCloud input must be a VTK/VTP tractography file.")
    if not config.input_tractography.expanduser().is_file():
        raise FileNotFoundError(f"Input tractography not found: {config.input_tractography}")
    if config.device not in VALID_TRACTCLOUD_DEVICES:
        raise ValueError("device must be one of: auto, cpu, cuda.")
    if config.batch_size < 64:
        raise ValueError("batch_size must be >= 64.")
    if config.data_dir is not None and not config.data_dir.expanduser().is_dir():
        raise FileNotFoundError(f"TractCloud data directory not found: {config.data_dir}")
    backend_status = inspect_tractcloud_backend(config.python_executable, config.tractcloud_root)
    if config.execute and not backend_status["available"]:
        missing = [name for name, available in backend_status["packages"].items() if not available]
        raise RuntimeError(f"TractCloud backend is incomplete. Missing package(s): {', '.join(missing)}")


def build_tractcloud_command(config: TractCloudConfig) -> tuple[str, ...]:
    python_path = resolve_tractcloud_python(config.python_executable)
    output_dir = config.output_dir.expanduser().resolve()
    cmd: list[str] = [
        python_path.as_posix(),
        "-m",
        "tractcloud",
        "--input",
        config.input_tractography.expanduser().resolve().as_posix(),
        "--output-dir",
        output_dir.as_posix(),
        "--device",
        config.device,
        "--batch-size",
        str(config.batch_size),
    ]
    if config.include_other:
        cmd.append("--include-other")
    if config.create_mrb:
        cmd.append("--mrb")
    if config.data_dir is not None:
        cmd.extend(["--data-dir", config.data_dir.expanduser().resolve().as_posix()])
    return tuple(cmd)


def summarize_tractcloud_outputs(output_dir: Path) -> dict[str, Any]:
    root = output_dir.expanduser().resolve()
    bundle_files = sorted(root.rglob("*.vtp")) if root.is_dir() else []
    category_dirs = sorted(
        item.name for item in root.iterdir() if item.is_dir()
    ) if root.is_dir() else []
    mrb_files = sorted(root.glob("*.mrb")) if root.is_dir() else []

    line_counts: dict[str, Optional[int]] = {}
    for path in bundle_files:
        relative = path.relative_to(root).as_posix()
        line_counts[relative] = vtp_streamline_count(path)
    readable_line_counts = {
        name: count for name, count in line_counts.items() if count is not None
    }
    return {
        "root": root.as_posix(),
        "root_exists": root.is_dir(),
        "category_dirs": category_dirs,
        "bundle_count": len(bundle_files),
        "bundle_readable_count": len(readable_line_counts),
        "bundle_nonempty_count": sum(count > 0 for count in readable_line_counts.values()),
        "assigned_streamline_count": sum(readable_line_counts.values()),
        "empty_bundle_files": sorted(
            name for name, count in readable_line_counts.items() if count == 0
        ),
        "unreadable_bundle_files": sorted(
            name for name, count in line_counts.items() if count is None
        ),
        "bundle_files": [path.as_posix() for path in bundle_files],
        "mrb_files": [path.as_posix() for path in mrb_files],
    }


def _tractcloud_output_contract_error(output_summary: dict[str, Any]) -> Optional[str]:
    bundle_count = int(output_summary.get("bundle_count", 0) or 0)
    readable_count = int(output_summary.get("bundle_readable_count", 0) or 0)
    nonempty_count = int(output_summary.get("bundle_nonempty_count", 0) or 0)
    assigned_count = int(output_summary.get("assigned_streamline_count", 0) or 0)
    if bundle_count <= 0:
        return "TractCloud did not produce any bundle files."
    if readable_count != bundle_count:
        return "TractCloud produced one or more VTP files that could not be decoded."
    if nonempty_count != bundle_count or assigned_count <= 0:
        return "TractCloud produced empty bundle outputs or assigned no streamlines."
    return None


def run_tractcloud_parcellation(
    config: TractCloudConfig,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> TractCloudResult:
    """Prepare or execute TractCloud parcellation for one tractogram."""

    validate_tractcloud_inputs(config)
    backend_status = inspect_tractcloud_backend(config.python_executable, config.tractcloud_root)
    command = build_tractcloud_command(config)
    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "tractcloud_manifest.json"
    qc_path = output_dir / "tractcloud_qc.json"
    output_summary = summarize_tractcloud_outputs(output_dir)
    resolved_root = resolve_tractcloud_root(config.tractcloud_root)

    manifest = {
        "kind": "tractcloud_parcellation",
        "version": 2,
        "name": "TractCloud registration-free tractography parcellation",
        "subject_id": config.subject_id,
        "input_tractography": config.input_tractography.expanduser().resolve().as_posix(),
        "output_dir": output_dir.as_posix(),
        "tractcloud_root": resolved_root.as_posix() if resolved_root else None,
        "include_other": config.include_other,
        "device": config.device,
        "batch_size": config.batch_size,
        "data_dir": config.data_dir.expanduser().resolve().as_posix() if config.data_dir else None,
        "create_mrb": config.create_mrb,
        "executed": bool(config.execute),
        "status": "planned" if not config.execute else "running",
        "command": list(command),
        "backend": backend_status,
        "dependencies": {
            "input_tractography": _file_info(config.input_tractography),
            "data_dir": _file_info(config.data_dir) if config.data_dir else None,
        },
        "outputs": {
            "qc": qc_path.as_posix(),
            "summary": output_summary,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if log:
        mode = "Executing" if config.execute else "Prepared dry-run"
        log(f"[TractCloud] {mode} command: {' '.join(command)}")
        log(f"[TractCloud] Manifest: {manifest_path}")

    start_time = time.monotonic()
    return_code: Optional[int] = None
    execution_error: Optional[str] = None
    execution_exception: Optional[Exception] = None
    if config.execute:
        env = merged_startup_environment(_tractcloud_env(config, backend_status))
        try:
            completed = subprocess.run(command, check=True, env=env)
            return_code = completed.returncode
        except subprocess.CalledProcessError as exc:
            return_code = exc.returncode
            execution_error = str(exc)
            execution_exception = exc
        except OSError as exc:
            execution_error = f"{type(exc).__name__}: {exc}"
            execution_exception = exc
        finally:
            output_summary = summarize_tractcloud_outputs(output_dir)

    if config.execute and execution_error is None:
        execution_error = _tractcloud_output_contract_error(output_summary)

    elapsed_seconds = time.monotonic() - start_time
    qc = {
        "kind": "tractcloud_parcellation_qc",
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

    return TractCloudResult(
        subject_id=config.subject_id,
        output_dir=output_dir,
        manifest_path=manifest_path,
        qc_path=qc_path,
        command=command,
        executed=bool(config.execute),
        backend_status=backend_status,
        return_code=return_code,
    )
