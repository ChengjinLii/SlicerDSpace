"""MRtrix3 CSD/FOD/ACT tractography backend.

The implementation intentionally treats MRtrix3 as an external backend. It
records dependency status and the exact command chain in dry-run mode, then runs
the same commands when ``execute=True`` and MRtrix3 is available on PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from shared.external_process import external_python_environment


REQUIRED_MRTRIX_COMMANDS = (
    "mrconvert",
    "dwi2response",
    "dwi2fod",
    "mtnormalise",
    "tckgen",
    "tcksift2",
)


@dataclass(frozen=True)
class CSDActConfig:
    subject_id: str
    dwi_path: Path
    bval_path: Path
    bvec_path: Path
    mask_path: Path
    five_tt_path: Path
    gmwmi_path: Path
    output_dir: Path
    tractogram_dir: Optional[Path] = None
    algorithm: str = "iFOD2"
    select_streamlines: int = 1_000_000
    min_length_mm: float = 10.0
    max_length_mm: float = 250.0
    step_size_mm: Optional[float] = None
    cutoff: Optional[float] = None
    random_seed: int = 12345
    use_sift2: bool = True
    export_trk: bool = False
    export_vtk: bool = False
    mrtrix_bin_dir: Optional[Path] = None
    execute: bool = False


@dataclass(frozen=True)
class CSDActResult:
    subject_id: str
    output_dir: Path
    wm_fod_path: Path
    wm_fod_norm_path: Path
    tractogram_path: Path
    tractogram_trk_path: Optional[Path]
    tractogram_vtk_path: Optional[Path]
    sift2_weights_path: Optional[Path]
    manifest_path: Path
    qc_path: Path
    commands: tuple[tuple[str, ...], ...]
    backend_status: dict[str, object]
    executed: bool
    return_code: Optional[int] = None


def _emit(message: str, log: Optional[Callable[[str], None]] = None) -> None:
    if log:
        log(message)


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


def _resolve_command(name: str, bin_dir: Optional[Path] = None) -> Optional[str]:
    if bin_dir is not None:
        candidate = bin_dir.expanduser() / name
        if candidate.is_file():
            return candidate.resolve().as_posix()
    return shutil.which(name)


def inspect_mrtrix_csd_backend(
    bin_dir: Optional[Path] = None,
    *,
    require_tckconvert: bool = False,
) -> dict[str, object]:
    commands: dict[str, Optional[str]] = {}
    missing: list[str] = []
    required_commands = (*REQUIRED_MRTRIX_COMMANDS, "tckconvert") if require_tckconvert else REQUIRED_MRTRIX_COMMANDS
    for command in required_commands:
        resolved = _resolve_command(command, bin_dir)
        commands[command] = resolved
        if resolved is None:
            missing.append(command)
    return {
        "name": "mrtrix3",
        "bin_dir": bin_dir.expanduser().resolve().as_posix() if bin_dir is not None else None,
        "available": not missing,
        "commands": commands,
        "missing_commands": missing,
    }


def _cmd(name: str, bin_dir: Optional[Path] = None) -> str:
    return _resolve_command(name, bin_dir) or name


def _validate_config(config: CSDActConfig) -> None:
    if not config.subject_id.strip():
        raise ValueError("subject_id is required.")
    if config.select_streamlines <= 0:
        raise ValueError("select_streamlines must be > 0.")
    if config.min_length_mm <= 0 or config.max_length_mm <= config.min_length_mm:
        raise ValueError("CSD/ACT streamline lengths require 0 < min_length_mm < max_length_mm.")
    if config.random_seed < 0:
        raise ValueError("random_seed must be >= 0.")
    for label, path in (
        ("dwi_path", config.dwi_path),
        ("bval_path", config.bval_path),
        ("bvec_path", config.bvec_path),
        ("mask_path", config.mask_path),
        ("five_tt_path", config.five_tt_path),
        ("gmwmi_path", config.gmwmi_path),
    ):
        if not path.expanduser().is_file():
            raise FileNotFoundError(f"{label} does not exist: {path}")


def build_csd_act_commands(config: CSDActConfig) -> tuple[tuple[str, ...], ...]:
    output_dir = config.output_dir.expanduser().resolve()
    tractogram_dir = (
        config.tractogram_dir.expanduser().resolve()
        if config.tractogram_dir is not None
        else output_dir.parent / "tractograms" / "csd_act"
    )
    dwi_mif = output_dir / f"{config.subject_id}_dwi.mif"
    mask_mif = output_dir / f"{config.subject_id}_mask.mif"
    wm_response = output_dir / f"{config.subject_id}_response_wm.txt"
    gm_response = output_dir / f"{config.subject_id}_response_gm.txt"
    csf_response = output_dir / f"{config.subject_id}_response_csf.txt"
    wm_fod = output_dir / f"{config.subject_id}_wmfod.mif"
    gm = output_dir / f"{config.subject_id}_gm.mif"
    csf = output_dir / f"{config.subject_id}_csf.mif"
    wm_fod_norm = output_dir / f"{config.subject_id}_wmfod_norm.mif"
    gm_norm = output_dir / f"{config.subject_id}_gm_norm.mif"
    csf_norm = output_dir / f"{config.subject_id}_csf_norm.mif"
    tractogram = tractogram_dir / f"{config.subject_id}_csd_act_{config.algorithm.lower()}.tck"
    weights = tractogram.with_name(f"{tractogram.stem}_sift2_weights.txt")

    commands: list[tuple[str, ...]] = [
        (
            _cmd("mrconvert", config.mrtrix_bin_dir),
            config.dwi_path.expanduser().resolve().as_posix(),
            dwi_mif.as_posix(),
            "-fslgrad",
            config.bvec_path.expanduser().resolve().as_posix(),
            config.bval_path.expanduser().resolve().as_posix(),
            "-force",
        ),
        (
            _cmd("mrconvert", config.mrtrix_bin_dir),
            config.mask_path.expanduser().resolve().as_posix(),
            mask_mif.as_posix(),
            "-force",
        ),
        (
            _cmd("dwi2response", config.mrtrix_bin_dir),
            "dhollander",
            dwi_mif.as_posix(),
            wm_response.as_posix(),
            gm_response.as_posix(),
            csf_response.as_posix(),
            "-mask",
            mask_mif.as_posix(),
            "-force",
        ),
        (
            _cmd("dwi2fod", config.mrtrix_bin_dir),
            "msmt_csd",
            dwi_mif.as_posix(),
            wm_response.as_posix(),
            wm_fod.as_posix(),
            gm_response.as_posix(),
            gm.as_posix(),
            csf_response.as_posix(),
            csf.as_posix(),
            "-mask",
            mask_mif.as_posix(),
            "-force",
        ),
        (
            _cmd("mtnormalise", config.mrtrix_bin_dir),
            wm_fod.as_posix(),
            wm_fod_norm.as_posix(),
            gm.as_posix(),
            gm_norm.as_posix(),
            csf.as_posix(),
            csf_norm.as_posix(),
            "-mask",
            mask_mif.as_posix(),
            "-force",
        ),
    ]
    tckgen = [
        _cmd("tckgen", config.mrtrix_bin_dir),
        wm_fod_norm.as_posix(),
        tractogram.as_posix(),
        "-algorithm",
        config.algorithm,
        "-act",
        config.five_tt_path.expanduser().resolve().as_posix(),
        "-seed_gmwmi",
        config.gmwmi_path.expanduser().resolve().as_posix(),
        "-backtrack",
        "-crop_at_gmwmi",
        "-select",
        str(config.select_streamlines),
        "-minlength",
        str(config.min_length_mm),
        "-maxlength",
        str(config.max_length_mm),
        "-force",
    ]
    if config.step_size_mm is not None:
        tckgen.extend(["-step", str(config.step_size_mm)])
    if config.cutoff is not None:
        tckgen.extend(["-cutoff", str(config.cutoff)])
    commands.append(tuple(tckgen))
    if config.use_sift2:
        commands.append(
            (
                _cmd("tcksift2", config.mrtrix_bin_dir),
                tractogram.as_posix(),
                wm_fod_norm.as_posix(),
                weights.as_posix(),
                "-act",
                config.five_tt_path.expanduser().resolve().as_posix(),
                "-force",
            )
        )
    if config.export_vtk:
        commands.append(
            (
                _cmd("tckconvert", config.mrtrix_bin_dir),
                tractogram.as_posix(),
                tractogram.with_suffix(".vtk").as_posix(),
                "-force",
            )
        )
    return tuple(commands)


def _tractogram_summary(path: Path) -> dict[str, object]:
    """Decode every streamline and return the evidence used by CSD/ACT QC."""

    import nibabel as nib
    import numpy as np

    lengths: list[float] = []
    all_points_finite = True
    for streamline in nib.streamlines.load(str(path), lazy_load=True).streamlines:
        points = np.asarray(streamline, dtype=np.float64)
        if points.ndim != 2 or points.shape[0] < 2 or points.shape[1] != 3:
            all_points_finite = False
            continue
        if not np.isfinite(points).all():
            all_points_finite = False
            continue
        lengths.append(float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum()))
    values = np.asarray(lengths, dtype=np.float64)
    summary: dict[str, object] = {
        "file": _file_info(path),
        "streamline_count": int(values.size),
        "all_points_finite": bool(all_points_finite),
    }
    if values.size:
        summary["length_mm"] = {
            "min": float(np.min(values)),
            "p05": float(np.percentile(values, 5)),
            "median": float(np.median(values)),
            "p95": float(np.percentile(values, 95)),
            "max": float(np.max(values)),
        }
    return summary


def _sift2_summary(path: Path, expected_count: int) -> dict[str, object]:
    import numpy as np

    values = np.asarray(np.loadtxt(path, ndmin=1), dtype=np.float64).reshape(-1)
    return {
        "file": _file_info(path),
        "weight_count": int(values.size),
        "expected_count": int(expected_count),
        "all_finite": bool(np.isfinite(values).all()),
        "all_nonnegative": bool(np.all(values >= 0.0)),
        "positive_count": int(np.count_nonzero(values > 0.0)),
        "sum": float(np.sum(values)) if values.size else 0.0,
    }


def _vtk_streamline_summary(path: Path) -> dict[str, object]:
    import re

    match = None
    with path.open("rb") as stream:
        for line in stream:
            match = re.match(rb"(?i)^\s*LINES\s+(\d+)\s+", line)
            if match is not None:
                break
    if match is None:
        raise ValueError("VTK LINES count was not found")
    return {
        "file": _file_info(path),
        "streamline_count": int(match.group(1)),
    }


def _validate_generated_outputs(
    config: CSDActConfig,
    tractogram: Path,
    tractogram_trk: Optional[Path],
    tractogram_vtk: Optional[Path],
    weights: Optional[Path],
) -> tuple[dict[str, object], Optional[str]]:
    """Validate generated tractography before a run can report completion."""

    try:
        tck_summary = _tractogram_summary(tractogram)
        summaries: dict[str, object] = {"tck": tck_summary}
        expected_count = int(config.select_streamlines)
        count = int(tck_summary["streamline_count"])
        length_summary = dict(tck_summary.get("length_mm") or {})
        valid = (
            bool(tck_summary["all_points_finite"])
            and count == expected_count
            and bool(length_summary)
            and float(length_summary["min"]) + 1e-3 >= float(config.min_length_mm)
            and float(length_summary["max"]) - 1e-3 <= float(config.max_length_mm)
        )
        if tractogram_trk is not None:
            trk_summary = _tractogram_summary(tractogram_trk)
            summaries["trk"] = trk_summary
            valid = valid and int(trk_summary["streamline_count"]) == count and bool(
                trk_summary["all_points_finite"]
            )
        if tractogram_vtk is not None:
            vtk_summary = _vtk_streamline_summary(tractogram_vtk)
            summaries["vtk"] = vtk_summary
            valid = valid and int(vtk_summary["streamline_count"]) == count
        if weights is not None:
            weight_summary = _sift2_summary(weights, count)
            summaries["sift2"] = weight_summary
            valid = valid and (
                int(weight_summary["weight_count"]) == count
                and bool(weight_summary["all_finite"])
                and bool(weight_summary["all_nonnegative"])
                and int(weight_summary["positive_count"]) > 0
            )
        if not valid:
            return summaries, "Generated CSD/ACT tractography failed its scientific output contract."
        return summaries, None
    except Exception as exc:
        return {}, f"Unable to validate generated CSD/ACT outputs: {type(exc).__name__}: {exc}"


def export_tck_to_trk(tck_path: Path, reference_image_path: Path, trk_path: Path) -> Path:
    """Export an MRtrix TCK tractogram as TRK for TractQuerier/WMQL users.

    MRtrix is the preferred backend for ACT, but TractQuerier reads TRK in the
    current Python environment. Keeping this conversion inside the CSD/ACT
    backend avoids hidden one-off shell steps between ACT and WMQL.
    """

    try:
        import nibabel as nib
        from nibabel.streamlines import Field
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("TCK to TRK export requires nibabel.") from exc

    tck = tck_path.expanduser().resolve()
    reference = reference_image_path.expanduser().resolve()
    trk = trk_path.expanduser().resolve()
    if not tck.is_file():
        raise FileNotFoundError(f"TCK tractogram does not exist: {tck}")
    if not reference.is_file():
        raise FileNotFoundError(f"Reference image does not exist: {reference}")
    trk.parent.mkdir(parents=True, exist_ok=True)

    reference_image = nib.load(reference.as_posix())
    tractogram = nib.streamlines.load(tck.as_posix()).tractogram
    header = nib.streamlines.trk.TrkFile.create_empty_header()
    header[Field.VOXEL_TO_RASMM] = reference_image.affine
    header[Field.VOXEL_SIZES] = reference_image.header.get_zooms()[:3]
    header[Field.DIMENSIONS] = reference_image.shape[:3]
    header[Field.VOXEL_ORDER] = "RAS"
    nib.streamlines.save(nib.streamlines.TrkFile(tractogram, header), trk.as_posix())
    return trk


def run_csd_act(config: CSDActConfig, *, log: Optional[Callable[[str], None]] = None) -> CSDActResult:
    _validate_config(config)
    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    tractogram_dir = (
        config.tractogram_dir.expanduser().resolve()
        if config.tractogram_dir is not None
        else output_dir.parent / "tractograms" / "csd_act"
    )
    tractogram_dir.mkdir(parents=True, exist_ok=True)

    wm_fod = output_dir / f"{config.subject_id}_wmfod.mif"
    wm_fod_norm = output_dir / f"{config.subject_id}_wmfod_norm.mif"
    tractogram = tractogram_dir / f"{config.subject_id}_csd_act_{config.algorithm.lower()}.tck"
    weights = tractogram.with_name(f"{tractogram.stem}_sift2_weights.txt") if config.use_sift2 else None
    manifest_path = output_dir / "csd_act_manifest.json"
    qc_path = output_dir / "csd_act_qc.json"
    tractogram_trk = tractogram.with_suffix(".trk") if config.export_trk else None
    tractogram_vtk = tractogram.with_suffix(".vtk") if config.export_vtk else None
    backend_status = inspect_mrtrix_csd_backend(
        config.mrtrix_bin_dir,
        require_tckconvert=config.export_vtk,
    )
    commands = build_csd_act_commands(config)

    manifest: dict[str, object] = {
        "kind": "mrtrix_csd_act",
        "version": 2,
        "subject_id": config.subject_id,
        "executed": bool(config.execute),
        "status": "running" if config.execute else "planned",
        "backend": backend_status,
        "parameters": {
            "algorithm": config.algorithm,
            "select_streamlines": config.select_streamlines,
            "min_length_mm": config.min_length_mm,
            "max_length_mm": config.max_length_mm,
            "step_size_mm": config.step_size_mm,
            "cutoff": config.cutoff,
            "random_seed": config.random_seed,
            "use_sift2": config.use_sift2,
            "export_trk": config.export_trk,
            "export_vtk": config.export_vtk,
            "tractogram_dir": tractogram_dir.as_posix(),
            "mrtrix_bin_dir": config.mrtrix_bin_dir.expanduser().resolve().as_posix()
            if config.mrtrix_bin_dir is not None
            else None,
        },
        "dependencies": {
            "dwi": _file_info(config.dwi_path),
            "bval": _file_info(config.bval_path),
            "bvec": _file_info(config.bvec_path),
            "mask": _file_info(config.mask_path),
            "five_tt": _file_info(config.five_tt_path),
            "gmwmi": _file_info(config.gmwmi_path),
        },
        "outputs": {
            "wm_fod": wm_fod.as_posix(),
            "wm_fod_norm": wm_fod_norm.as_posix(),
            "tractogram": tractogram.as_posix(),
            "tractogram_trk": tractogram_trk.as_posix() if tractogram_trk else None,
            "tractogram_vtk": tractogram_vtk.as_posix() if tractogram_vtk else None,
            "sift2_weights": weights.as_posix() if weights else None,
            "qc": qc_path.as_posix(),
        },
        "commands": [list(command) for command in commands],
    }
    qc: dict[str, object] = {
        "kind": "mrtrix_csd_act_qc",
        "version": 2,
        "subject_id": config.subject_id,
        "status": "planned",
        "executed": False,
        "backend_available": bool(backend_status["available"]),
        "missing_commands": backend_status["missing_commands"],
        "wm_fod_exists": wm_fod.is_file(),
        "wm_fod_norm_exists": wm_fod_norm.is_file(),
        "tractogram_exists": tractogram.is_file(),
        "tractogram_trk_exists": tractogram_trk.is_file() if tractogram_trk else None,
        "tractogram_vtk_exists": tractogram_vtk.is_file() if tractogram_vtk else None,
        "sift2_weights_exists": weights.is_file() if weights else None,
        "return_code": None,
        "elapsed_seconds": 0.0,
        "error": None,
        "scientific_output_summary": {},
    }

    return_code: Optional[int] = None
    error: Optional[str] = None
    start = time.monotonic()
    if config.execute:
        if not backend_status["available"]:
            missing = ", ".join(str(item) for item in backend_status["missing_commands"])
            raise RuntimeError(f"MRtrix3 CSD/ACT backend is incomplete. Missing command(s): {missing}")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # MRtrix3 ignores "-config RandomSeed <n>" on the command line; the
        # seed must be provided via the MRTRIX_RNG_SEED environment variable.
        command_env = external_python_environment(
            extra_env={"MRTRIX_RNG_SEED": str(config.random_seed)},
            path_prepend=[config.mrtrix_bin_dir] if config.mrtrix_bin_dir is not None else None,
        )
        try:
            for command in commands:
                _emit(f"[Tractography] Running MRtrix CSD/ACT command: {' '.join(command)}", log)
                completed = subprocess.run(command, check=True, env=command_env)
                return_code = completed.returncode
            if config.export_trk and tractogram_trk is not None:
                _emit(f"[Tractography] Exporting ACT TCK to TRK for WMQL: {tractogram_trk}", log)
                export_tck_to_trk(tractogram, config.dwi_path, tractogram_trk)
            scientific_summary, validation_error = _validate_generated_outputs(
                config,
                tractogram,
                tractogram_trk,
                tractogram_vtk,
                weights,
            )
            qc["scientific_output_summary"] = scientific_summary
            if validation_error is not None:
                error = validation_error
        except subprocess.CalledProcessError as exc:
            return_code = exc.returncode
            error = str(exc)
        except Exception as exc:
            return_code = 1
            error = str(exc)
        qc.update(
            {
                "status": "failed" if error else "completed",
                "executed": True,
                "return_code": return_code,
                "elapsed_seconds": time.monotonic() - start,
                "wm_fod_exists": wm_fod.is_file(),
                "wm_fod_norm_exists": wm_fod_norm.is_file(),
                "tractogram_exists": tractogram.is_file(),
                "tractogram_trk_exists": tractogram_trk.is_file() if tractogram_trk else None,
                "tractogram_vtk_exists": tractogram_vtk.is_file() if tractogram_vtk else None,
                "sift2_weights_exists": weights.is_file() if weights else None,
                "error": error,
            }
        )
        manifest["status"] = qc["status"]
        manifest["return_code"] = return_code
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    qc_path.write_text(json.dumps(qc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if error is not None:
        raise RuntimeError(f"MRtrix CSD/ACT execution failed: {error}")

    return CSDActResult(
        subject_id=config.subject_id,
        output_dir=output_dir,
        wm_fod_path=wm_fod,
        wm_fod_norm_path=wm_fod_norm,
        tractogram_path=tractogram,
        tractogram_trk_path=tractogram_trk,
        tractogram_vtk_path=tractogram_vtk,
        sift2_weights_path=weights,
        manifest_path=manifest_path,
        qc_path=qc_path,
        commands=commands,
        backend_status=backend_status,
        executed=bool(config.execute),
        return_code=return_code,
    )
