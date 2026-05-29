"""TractCloud integration for tractography parcellation.

This backend follows the SlicerDMRI TractCloud module design but keeps
dependency installation and execution explicit. It prepares a reproducible
``python -m tractcloud`` command, manifest, and QC record, and only runs when
``execute=True``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


TRACTCLOUD_REPOSITORY = "https://github.com/SlicerDMRI/TractCloud"
VALID_TRACTCLOUD_DEVICES = {"auto", "cpu", "cuda"}


@dataclass(frozen=True)
class TractCloudConfig:
    """Configuration for TractCloud whole-brain tractography parcellation."""

    subject_id: str
    input_tractography: Path
    output_dir: Path
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

    env_value = os.environ.get("SLICERDDSURFER_TRACTCLOUD_PYTHON") or os.environ.get("TRACTCLOUD_PYTHON")
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


def inspect_tractcloud_backend(python_executable: Optional[Path] = None) -> dict[str, Any]:
    """Inspect TractCloud package availability without importing torch in-process."""

    python_path = resolve_tractcloud_python(python_executable)
    status: dict[str, Any] = {
        "available": False,
        "python_executable": python_path.as_posix(),
        "repository": TRACTCLOUD_REPOSITORY,
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
        completed = subprocess.run(
            [python_path.as_posix(), "-c", probe],
            check=True,
            capture_output=True,
            text=True,
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
    backend_status = inspect_tractcloud_backend(config.python_executable)
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
    return {
        "root": root.as_posix(),
        "root_exists": root.is_dir(),
        "category_dirs": category_dirs,
        "bundle_count": len(bundle_files),
        "bundle_files": [path.as_posix() for path in bundle_files],
        "mrb_files": [path.as_posix() for path in mrb_files],
    }


def run_tractcloud_parcellation(
    config: TractCloudConfig,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> TractCloudResult:
    """Prepare or execute TractCloud parcellation for one tractogram."""

    validate_tractcloud_inputs(config)
    backend_status = inspect_tractcloud_backend(config.python_executable)
    command = build_tractcloud_command(config)
    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "tractcloud_manifest.json"
    qc_path = output_dir / "tractcloud_qc.json"
    output_summary = summarize_tractcloud_outputs(output_dir)

    manifest = {
        "kind": "tractcloud_parcellation",
        "version": 1,
        "name": "TractCloud registration-free tractography parcellation",
        "subject_id": config.subject_id,
        "input_tractography": config.input_tractography.expanduser().resolve().as_posix(),
        "output_dir": output_dir.as_posix(),
        "include_other": config.include_other,
        "device": config.device,
        "batch_size": config.batch_size,
        "data_dir": config.data_dir.expanduser().resolve().as_posix() if config.data_dir else None,
        "create_mrb": config.create_mrb,
        "executed": bool(config.execute),
        "status": "planned" if not config.execute else "running",
        "command": list(command),
        "backend": backend_status,
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
    if config.execute:
        env = os.environ.copy()
        if config.data_dir is not None:
            env["TRACTCLOUD_DATA_DIR"] = config.data_dir.expanduser().resolve().as_posix()
        try:
            completed = subprocess.run(command, check=True, env=env)
            return_code = completed.returncode
        except subprocess.CalledProcessError as exc:
            return_code = exc.returncode
            execution_error = str(exc)
            raise
        finally:
            output_summary = summarize_tractcloud_outputs(output_dir)

    elapsed_seconds = time.monotonic() - start_time
    qc = {
        "kind": "tractcloud_parcellation_qc",
        "version": 1,
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
