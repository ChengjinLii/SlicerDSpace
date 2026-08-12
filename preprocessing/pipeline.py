"""Optional DWI preprocessing wrapper around DIPY or MRtrix3/FSL commands.

This stage is intentionally optional. Product pipelines may consume raw
``input/data.nii.gz`` directly, or users may run this stage first to generate a
shared corrected DWI under ``outputs/01_preproc``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from shared.io_layout import default_task_output_dir
from shared.external_process import external_python_environment
from shared.pipeline import RawInputBundle, find_subject_root


REQUIRED_COMMANDS = ("dwidenoise", "mrdegibbs", "dwifslpreproc", "dwi2mask")
REVERSE_PHASE_COMMANDS = ("mrconvert", "dwiextract", "mrcat")
DIAGNOSTIC_COMMANDS = ("eddy", "topup")


def _default_eddy_threads() -> int:
    process_cpu_count = getattr(os, "process_cpu_count", None)
    if callable(process_cpu_count):
        count = process_cpu_count()
    elif hasattr(os, "sched_getaffinity"):
        count = len(os.sched_getaffinity(0))
    else:
        count = os.cpu_count()
    return max(1, min(8, int(count or 1)))


@dataclass(frozen=True)
class DwiPreprocessingConfig:
    subject_id: str
    input_root: Path
    output_dir: Optional[Path] = None
    backend: str = "dipy"
    execute: bool = False
    skip: bool = False
    force: bool = False
    dipy_denoise_method: str = "mppca"
    dipy_run_gibbs: bool = True
    dipy_run_motion_correction: bool = True
    b0_threshold: float = 50.0
    mrtrix_bin_dir: Optional[Path] = None
    fsl_bin_dir: Optional[Path] = None
    reverse_phase_b0: Optional[Path] = None
    phase_encoding_direction: Optional[str] = None
    readout_time: Optional[float] = None
    eddy_threads: Optional[int] = None
    eddy_second_level_model: Optional[str] = None


@dataclass(frozen=True)
class DwiPreprocessingResult:
    subject_id: str
    status: str
    output_dir: Path
    manifest_path: Path
    qc_path: Path
    final_dwi_path: Path
    final_bval_path: Path
    final_bvec_path: Path
    final_mask_path: Path


def _resolve_output_dir(raw: RawInputBundle, output_dir: Optional[Path]) -> Path:
    if output_dir is not None:
        return output_dir.expanduser().resolve()
    return default_task_output_dir(raw.subject_root, "preproc")


def _command_search_path(config: DwiPreprocessingConfig) -> str:
    entries: list[str] = []
    for candidate in (config.mrtrix_bin_dir, config.fsl_bin_dir):
        if candidate is not None:
            entries.append(candidate.expanduser().resolve().as_posix())
    existing = os.environ.get("PATH", "")
    if existing:
        entries.append(existing)
    return os.pathsep.join(entries)


def _fsl_root_from_bin_dir(bin_dir: Path) -> Path:
    """Return ``FSLDIR`` for either ``$FSLDIR/bin`` or ``share/fsl/bin``."""

    resolved = bin_dir.expanduser().resolve()
    if (
        resolved.name == "bin"
        and resolved.parent.name == "fsl"
        and resolved.parent.parent.name == "share"
    ):
        return resolved.parent.parent.parent
    return resolved.parent


def _resolve_command(command: str, config: DwiPreprocessingConfig) -> Optional[str]:
    return shutil.which(command, path=_command_search_path(config))


def _resolved_eddy_threads(config: DwiPreprocessingConfig) -> int:
    if config.eddy_threads is None:
        return _default_eddy_threads()
    if config.eddy_threads < 1:
        raise ValueError("eddy_threads must be >= 1.")
    return int(config.eddy_threads)


def _resolved_eddy_options(config: DwiPreprocessingConfig) -> str:
    options = ["--cnr_maps", "--residuals", f"--nthr={_resolved_eddy_threads(config)}"]
    if config.eddy_second_level_model is not None:
        model = config.eddy_second_level_model.strip().lower()
        if model not in {"none", "linear", "quadratic"}:
            raise ValueError(
                "eddy_second_level_model must be one of: none, linear, quadratic."
            )
        options.append(f"--slm={model}")
    return " ".join(options)


def _external_command_environment(config: DwiPreprocessingConfig) -> dict[str, str]:
    path_prepend = [
        candidate.expanduser().resolve()
        for candidate in (config.mrtrix_bin_dir, config.fsl_bin_dir)
        if candidate is not None
    ]
    extra_env: dict[str, str] = {}
    if config.fsl_bin_dir is not None:
        extra_env["FSLDIR"] = _fsl_root_from_bin_dir(config.fsl_bin_dir).as_posix()
        extra_env["FSLOUTPUTTYPE"] = os.environ.get("FSLOUTPUTTYPE", "NIFTI_GZ")
    return external_python_environment(extra_env, path_prepend=path_prepend)


def inspect_preprocessing_backend(config: DwiPreprocessingConfig) -> dict[str, Any]:
    backend_name = config.backend.lower()
    if backend_name == "dipy":
        python_modules = ("nibabel", "numpy", "dipy")
        python_status = {
            module: importlib.util.find_spec(module) is not None
            for module in python_modules
        }
        missing_python = [module for module, available in python_status.items() if not available]
        return {
            "kind": "dwi_preprocessing_backend",
            "backend": "dipy",
            "python": python_status,
            "missing_python": missing_python,
            "available": not missing_python,
            "capabilities": {
                "denoise": config.dipy_denoise_method,
                "gibbs_removal": bool(config.dipy_run_gibbs),
                "between_volume_motion_correction": bool(config.dipy_run_motion_correction),
                "susceptibility_distortion_correction": False,
                "eddy_current_modeling": False,
            },
        }
    if backend_name not in {"mrtrix_fsl", "mrtrix", "fsl"}:
        return {
            "kind": "dwi_preprocessing_backend",
            "backend": backend_name,
            "available": False,
            "missing_required": [f"unsupported backend: {config.backend}"],
        }
    required_commands = list(REQUIRED_COMMANDS)
    if config.reverse_phase_b0 is not None:
        required_commands.extend(REVERSE_PHASE_COMMANDS)
    commands = {
        command: _resolve_command(command, config)
        for command in (*required_commands, *DIAGNOSTIC_COMMANDS)
    }
    missing_required = [command for command in required_commands if commands[command] is None]
    missing_diagnostic = [command for command in DIAGNOSTIC_COMMANDS if commands[command] is None]
    return {
        "kind": "dwi_preprocessing_backend",
        "backend": "mrtrix_fsl",
        "required_commands": required_commands,
        "diagnostic_commands": list(DIAGNOSTIC_COMMANDS),
        "commands": commands,
        "missing_required": missing_required,
        "missing_diagnostic": missing_diagnostic,
        "available": not missing_required,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _link_or_copy(src: Path, dest: Path) -> None:
    src = src.expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    try:
        dest.symlink_to(src)
        return
    except OSError:
        pass
    try:
        os.link(src, dest)
        return
    except OSError:
        pass
    shutil.copy2(src, dest)


def _file_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": path.as_posix(), "exists": False}
    stat = path.stat()
    return {
        "path": path.resolve().as_posix(),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _run_command(cmd: list[str], *, env: dict[str, str], log: Optional[Callable[[str], None]]) -> None:
    if log:
        log("[Preproc] Running: " + " ".join(cmd))
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if process.stdout:
        for line in process.stdout:
            if log:
                log("[Preproc] " + line.rstrip())
        process.stdout.close()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"Preprocessing command failed with exit code {return_code}: {' '.join(cmd)}")


def _planned_paths(output_dir: Path, subject: str) -> dict[str, Path]:
    return {
        "import_dir": output_dir / "00_import",
        "gradients_dir": output_dir / "01_gradients",
        "denoise_dir": output_dir / "02_denoise_degibbs",
        "motion_dir": output_dir / "03_distortion_motion",
        "mask_dir": output_dir / "04_bias_normalize",
        "qc_dir": output_dir / "05_qc",
        "final_dwi": output_dir / f"{subject}_dwi_final.nii.gz",
        "final_bval": output_dir / f"{subject}_dwi_final.bval",
        "final_bvec": output_dir / f"{subject}_dwi_final.bvec",
        "final_mask": output_dir / f"{subject}_brain_mask_final.nii.gz",
        "manifest": output_dir / f"{subject}_preproc_manifest.json",
        "qc": output_dir / "05_qc" / f"{subject}_preproc_qc.json",
        "eddy_parameters": output_dir / "05_qc" / f"{subject}_eddy_parameters.txt",
        "eddy_movement_rms": output_dir / "05_qc" / f"{subject}_eddy_movement_rms.txt",
        "eddy_outlier_map": output_dir / "05_qc" / f"{subject}_eddy_outlier_map.txt",
        "eddy_outlier_report": output_dir / "05_qc" / f"{subject}_eddy_outlier_report.txt",
        "eddy_cnr_maps": output_dir / "05_qc" / f"{subject}_eddy_cnr_maps.nii.gz",
        "eddy_residuals": output_dir / "05_qc" / f"{subject}_eddy_residuals.nii.gz",
    }


def _collect_dwifslpreproc_diagnostics(paths: dict[str, Path], subject: str) -> dict[str, dict[str, Any]]:
    scratch_dir = paths["motion_dir"] / "dwifslpreproc_tmp"
    destinations = {
        "eddy_parameters": (
            scratch_dir / "dwi_post_eddy.eddy_parameters",
            paths["eddy_parameters"],
        ),
        "eddy_movement_rms": (
            scratch_dir / "dwi_post_eddy.eddy_movement_rms",
            paths["eddy_movement_rms"],
        ),
        "eddy_restricted_movement_rms": (
            scratch_dir / "dwi_post_eddy.eddy_restricted_movement_rms",
            paths["motion_dir"] / f"{subject}_eddy_restricted_movement_rms.txt",
        ),
        "eddy_outlier_map": (
            scratch_dir / "dwi_post_eddy.eddy_outlier_map",
            paths["eddy_outlier_map"],
        ),
        "eddy_outlier_report": (
            scratch_dir / "dwi_post_eddy.eddy_outlier_report",
            paths["eddy_outlier_report"],
        ),
        "eddy_cnr_maps": (
            scratch_dir / "dwi_post_eddy.eddy_cnr_maps.nii.gz",
            paths["eddy_cnr_maps"],
        ),
        "eddy_residuals": (
            scratch_dir / "dwi_post_eddy.eddy_residuals.nii.gz",
            paths["eddy_residuals"],
        ),
        "topup_field_coefficients": (
            scratch_dir / "field_fieldcoef.nii.gz",
            paths["motion_dir"] / f"{subject}_topup_fieldcoef.nii.gz",
        ),
        "topup_field_map": (
            scratch_dir / "field_map.nii.gz",
            paths["motion_dir"] / f"{subject}_topup_field_map.nii.gz",
        ),
        "topup_motion_parameters": (
            scratch_dir / "field_movpar.txt",
            paths["motion_dir"] / f"{subject}_topup_motion_parameters.txt",
        ),
        "topup_log": (
            scratch_dir / "topup_in.topup_log",
            paths["qc_dir"] / f"{subject}_topup.log",
        ),
    }
    records: dict[str, dict[str, Any]] = {}
    for name, (source, destination) in destinations.items():
        if source.is_file():
            shutil.copy2(source, destination)
        records[name] = _file_record(destination)
    return records


def _build_commands(raw: RawInputBundle, config: DwiPreprocessingConfig, paths: dict[str, Path], backend: dict[str, Any]) -> list[list[str]]:
    if backend.get("backend") == "dipy":
        return [
            ["dipy", "denoise", config.dipy_denoise_method, raw.dwi_path.as_posix(), (paths["denoise_dir"] / f"{raw.subject_id}_dwi_denoised.nii.gz").as_posix()],
            ["dipy", "gibbs_removal", (paths["denoise_dir"] / f"{raw.subject_id}_dwi_degibbs.nii.gz").as_posix()]
            if config.dipy_run_gibbs
            else ["dipy", "skip_gibbs_removal"],
            ["dipy", "motion_correction", (paths["motion_dir"] / f"{raw.subject_id}_dwi_preproc.nii.gz").as_posix()]
            if config.dipy_run_motion_correction
            else ["dipy", "skip_motion_correction"],
            ["copy", raw.mask_path.as_posix(), paths["final_mask"].as_posix()],
        ]

    subject = raw.subject_id
    denoised = paths["denoise_dir"] / f"{subject}_dwi_denoised.nii.gz"
    noise = paths["denoise_dir"] / f"{subject}_dwi_noise.nii.gz"
    degibbs = paths["denoise_dir"] / f"{subject}_dwi_degibbs.nii.gz"
    reverse_phase_commands: list[list[str]] = []
    reverse_phase_b0 = (
        config.reverse_phase_b0.expanduser().resolve()
        if config.reverse_phase_b0 is not None
        else None
    )
    if reverse_phase_b0 is not None:
        if not reverse_phase_b0.is_file():
            raise FileNotFoundError(f"Reverse phase-encoded b=0 image not found: {reverse_phase_b0}")
        import nibabel as nib

        try:
            reverse_shape = nib.load(str(reverse_phase_b0)).shape
        except Exception as exc:
            raise ValueError(f"Unable to read reverse phase-encoded b=0 image: {reverse_phase_b0}") from exc
        reverse_ndim = len(reverse_shape)
        if reverse_ndim not in {3, 4}:
            raise ValueError(
                "reverse_phase_b0 must be a 3D image or a single-volume 4D image; "
                f"received shape {reverse_shape}."
            )
        reverse_volume_count = int(reverse_shape[3]) if reverse_ndim == 4 else 1
        if reverse_volume_count != 1:
            raise ValueError(
                "reverse_phase_b0 must contain exactly one reverse phase-encoded b=0 volume; "
                f"received shape {reverse_shape}."
            )
        if reverse_ndim == 3:
            normalized_reverse = paths["motion_dir"] / f"{subject}_reverse_phase_b0_4d.nii.gz"
            normalize_cmd = [
                backend["commands"]["mrconvert"] or "mrconvert",
                reverse_phase_b0.as_posix(),
                normalized_reverse.as_posix(),
                "-axes",
                "0,1,2,-1",
            ]
            if config.force:
                normalize_cmd.append("-force")
            reverse_phase_commands.append(normalize_cmd)
            reverse_phase_b0 = normalized_reverse
        forward_b0s = paths["motion_dir"] / f"{subject}_forward_b0s.mif"
        forward_b0 = paths["motion_dir"] / f"{subject}_forward_b0_4d.nii.gz"
        se_epi_pair = paths["motion_dir"] / f"{subject}_se_epi_pair.mif"
        reverse_phase_commands.extend(
            [
                [
                    backend["commands"]["dwiextract"] or "dwiextract",
                    degibbs.as_posix(),
                    forward_b0s.as_posix(),
                    "-fslgrad",
                    raw.bvec_path.as_posix(),
                    raw.bval_path.as_posix(),
                    "-bzero",
                ],
                [
                    backend["commands"]["mrconvert"] or "mrconvert",
                    forward_b0s.as_posix(),
                    forward_b0.as_posix(),
                    "-coord",
                    "3",
                    "0",
                    "-axes",
                    "0,1,2,-1",
                ],
                [
                    backend["commands"]["mrcat"] or "mrcat",
                    forward_b0.as_posix(),
                    reverse_phase_b0.as_posix(),
                    se_epi_pair.as_posix(),
                    "-axis",
                    "3",
                ],
            ]
        )
        if config.force:
            for command in reverse_phase_commands:
                if "-force" not in command:
                    command.append("-force")
        reverse_phase_b0 = se_epi_pair

    dwifslpreproc_cmd = [
        backend["commands"]["dwifslpreproc"] or "dwifslpreproc",
        degibbs.as_posix(),
        paths["final_dwi"].as_posix(),
        "-fslgrad",
        raw.bvec_path.as_posix(),
        raw.bval_path.as_posix(),
        "-export_grad_fsl",
        paths["final_bvec"].as_posix(),
        paths["final_bval"].as_posix(),
        "-scratch",
        (paths["motion_dir"] / "dwifslpreproc_tmp").as_posix(),
        "-nocleanup",
        "-eddy_options",
        _resolved_eddy_options(config),
    ]
    if config.force:
        dwifslpreproc_cmd.append("-force")
    if reverse_phase_b0 is not None:
        dwifslpreproc_cmd.extend(["-rpe_pair", "-se_epi", reverse_phase_b0.as_posix()])
    else:
        dwifslpreproc_cmd.append("-rpe_none")
    if config.phase_encoding_direction:
        dwifslpreproc_cmd.extend(["-pe_dir", config.phase_encoding_direction])
    if config.readout_time is not None:
        dwifslpreproc_cmd.extend(["-readout_time", str(config.readout_time)])

    dwidenoise_cmd = [
        backend["commands"]["dwidenoise"] or "dwidenoise",
        raw.dwi_path.as_posix(),
        denoised.as_posix(),
        "-noise",
        noise.as_posix(),
    ]
    mrdegibbs_cmd = [
        backend["commands"]["mrdegibbs"] or "mrdegibbs",
        denoised.as_posix(),
        degibbs.as_posix(),
    ]
    if config.force:
        dwidenoise_cmd.append("-force")
        mrdegibbs_cmd.append("-force")

    final_mask_cmd = [
        backend["commands"]["dwi2mask"] or "dwi2mask",
        paths["final_dwi"].as_posix(),
        paths["final_mask"].as_posix(),
        "-fslgrad",
        paths["final_bvec"].as_posix(),
        paths["final_bval"].as_posix(),
    ]
    if config.force or paths["final_mask"].exists():
        final_mask_cmd.append("-force")

    return [
        dwidenoise_cmd,
        mrdegibbs_cmd,
        *reverse_phase_commands,
        dwifslpreproc_cmd,
        final_mask_cmd,
        [
            "optional-output",
            paths["eddy_parameters"].as_posix(),
            paths["eddy_movement_rms"].as_posix(),
            paths["eddy_outlier_map"].as_posix(),
            paths["eddy_outlier_report"].as_posix(),
            paths["eddy_cnr_maps"].as_posix(),
            paths["eddy_residuals"].as_posix(),
        ],
    ]


def _collect_eddy_qc_artifacts(paths: dict[str, Path]) -> dict[str, Any]:
    """Copy Eddy products retained by ``dwifslpreproc -nocleanup`` into QC.

    MRtrix writes these files below its scratch directory with the fixed
    ``dwi_post_eddy`` prefix.  They are useful pipeline outputs, but are not
    copied by ``dwifslpreproc`` itself.  In particular, Eddy's outlier map is
    a text matrix rather than a NIfTI image, so preserve it as ``.txt``.
    """

    scratch_dir = paths["motion_dir"] / "dwifslpreproc_tmp"
    source_prefix = scratch_dir / "dwi_post_eddy"
    specifications = {
        "eddy_parameters": (".eddy_parameters", "text/eddy-parameters"),
        "eddy_movement_rms": (".eddy_movement_rms", "text/eddy-movement-rms"),
        "eddy_outlier_map": (".eddy_outlier_map", "text/eddy-outlier-map"),
        "eddy_outlier_report": (".eddy_outlier_report", "text/eddy-outlier-report"),
        "eddy_cnr_maps": (".eddy_cnr_maps.nii.gz", "application/nifti+gzip"),
        "eddy_residuals": (".eddy_residuals.nii.gz", "application/nifti+gzip"),
    }
    artifact_records: dict[str, Any] = {}
    for key, (suffix, content_type) in specifications.items():
        source = Path(f"{source_prefix}{suffix}")
        destination = paths[key]
        record = {
            "source": source.as_posix(),
            "destination": destination.as_posix(),
            "content_type": content_type,
            "status": "missing",
        }
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            record.update({"status": "copied", "size": destination.stat().st_size})
        artifact_records[key] = record
    return {
        "scratch_dir": scratch_dir.as_posix(),
        "artifacts": artifact_records,
    }


def _materialize_dirs(paths: dict[str, Path]) -> None:
    for key in ("import_dir", "gradients_dir", "denoise_dir", "motion_dir", "mask_dir", "qc_dir"):
        paths[key].mkdir(parents=True, exist_ok=True)


def _copy_input_sidecars(raw: RawInputBundle, paths: dict[str, Path]) -> None:
    _link_or_copy(raw.dwi_path, paths["import_dir"] / raw.dwi_path.name)
    _link_or_copy(raw.bval_path, paths["import_dir"] / raw.bval_path.name)
    _link_or_copy(raw.bvec_path, paths["import_dir"] / raw.bvec_path.name)
    _link_or_copy(raw.mask_path, paths["import_dir"] / raw.mask_path.name)
    _link_or_copy(raw.bval_path, paths["gradients_dir"] / f"{raw.subject_id}_gradients_checked.bval")
    _link_or_copy(raw.bvec_path, paths["gradients_dir"] / f"{raw.subject_id}_gradients_checked.bvec")


def _load_bvecs(path: Path) -> list[list[float]]:
    rows = [[float(token) for token in line.split()] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) == 3:
        return [list(vector) for vector in zip(*rows)]
    return rows


def _write_bvecs(path: Path, vectors: list[list[float]]) -> None:
    if not vectors:
        path.write_text("", encoding="utf-8")
        return
    rows = list(zip(*vectors))
    text = "\n".join(" ".join(f"{float(value):.10g}" for value in row) for row in rows) + "\n"
    path.write_text(text, encoding="utf-8")


def _rotate_bvecs_best_effort(raw_bvec_path: Path, output_bvec_path: Path, affines: Any) -> dict[str, Any]:
    try:
        import numpy as np
    except Exception as exc:  # pragma: no cover
        shutil.copy2(raw_bvec_path, output_bvec_path)
        return {"status": "copied", "reason": f"numpy unavailable: {exc}"}

    bvecs = _load_bvecs(raw_bvec_path)
    affine_array = np.asarray(affines)
    input_affine_shape = list(affine_array.shape)
    affine_layout: Optional[str] = None
    if (
        affine_array.ndim == 3
        and affine_array.shape[:2] == (4, 4)
        and affine_array.shape[-1] == len(bvecs)
    ):
        # DIPY 1.12 returns one affine per volume with shape (4, 4, N).
        # Move the volume axis first so the rotation loop below also remains
        # compatible with the historical/list-derived (N, 4, 4) layout.
        affine_array = np.moveaxis(affine_array, -1, 0)
        affine_layout = "4x4xN"
    elif (
        affine_array.ndim == 3
        and affine_array.shape[-2:] == (4, 4)
        and affine_array.shape[0] == len(bvecs)
    ):
        affine_layout = "Nx4x4"

    if affine_layout is None:
        shutil.copy2(raw_bvec_path, output_bvec_path)
        return {
            "status": "copied",
            "reason": "unexpected affine array shape or gradient count mismatch",
            "affine_shape": input_affine_shape,
            "gradient_count": len(bvecs),
        }

    rotated: list[list[float]] = []
    for vector, affine in zip(bvecs, affine_array):
        vec = np.asarray(vector, dtype=float)
        norm = float(np.linalg.norm(vec))
        if norm < 1e-8:
            rotated.append([0.0, 0.0, 0.0])
            continue
        linear = affine[:3, :3]
        try:
            u, _, vt = np.linalg.svd(linear)
            rotation = u @ vt
        except np.linalg.LinAlgError:
            rotation = np.eye(3)
        new_vec = rotation @ vec
        new_norm = float(np.linalg.norm(new_vec))
        if new_norm > 1e-8:
            new_vec = new_vec / new_norm
        rotated.append([float(new_vec[0]), float(new_vec[1]), float(new_vec[2])])
    _write_bvecs(output_bvec_path, rotated)
    return {
        "status": "rotated",
        "method": "best_effort_polar_decomposition_of_dipy_affines",
        "gradient_count": len(rotated),
        "affine_layout": affine_layout,
        "affine_shape": input_affine_shape,
    }


def _run_dipy_backend(
    raw: RawInputBundle,
    config: DwiPreprocessingConfig,
    paths: dict[str, Path],
    *,
    log: Optional[Callable[[str], None]],
) -> dict[str, Any]:
    try:
        import nibabel as nib
        import numpy as np
        from dipy.align import motion_correction
        from dipy.core.gradients import gradient_table
        from dipy.denoise.gibbs import gibbs_removal
        from dipy.denoise.localpca import localpca, mppca
        try:
            from dipy.denoise.patch2self import patch2self
        except Exception:  # pragma: no cover - version-dependent optional path
            patch2self = None
    except Exception as exc:
        raise RuntimeError("DIPY preprocessing backend requires nibabel, numpy, and dipy.") from exc

    def emit(message: str) -> None:
        if log:
            log("[Preproc:DIPY] " + message)

    subject = raw.subject_id
    denoise_method = config.dipy_denoise_method.lower()
    if denoise_method in {"none", "skip", ""} and not config.dipy_run_gibbs and not config.dipy_run_motion_correction:
        emit("Fast path: linking raw DWI/gradients directly to final preprocessing outputs")
        denoised_path = paths["denoise_dir"] / f"{subject}_dwi_denoised.nii.gz"
        degibbs_path = paths["denoise_dir"] / f"{subject}_dwi_degibbs.nii.gz"
        corrected_path = paths["motion_dir"] / f"{subject}_dwi_preproc.nii.gz"
        _link_or_copy(raw.dwi_path, denoised_path)
        _link_or_copy(denoised_path, degibbs_path)
        _link_or_copy(degibbs_path, corrected_path)
        _link_or_copy(corrected_path, paths["final_dwi"])
        _link_or_copy(raw.bval_path, paths["final_bval"])
        _link_or_copy(raw.bvec_path, paths["final_bvec"])
        _link_or_copy(raw.mask_path, paths["final_mask"])
        return {
            "denoise": {"method": denoise_method, "status": "skipped"},
            "gibbs": {"status": "skipped"},
            "motion": {"status": "skipped", "bvec_rotation": {"status": "copied"}},
            "bias_correction": {
                "status": "not_run",
                "reason": "fast path requested with no denoise/gibbs/motion operations",
            },
            "susceptibility_distortion_correction": {
                "status": "not_supported_by_dipy_backend",
                "recommended_backend": "mrtrix_fsl",
            },
            "files": {
                "denoised": denoised_path.as_posix(),
                "degibbs": degibbs_path.as_posix(),
                "motion_corrected": corrected_path.as_posix(),
            },
            "fast_path": True,
        }

    emit(f"Loading source DWI from {raw.dwi_path}")
    source_img = nib.load(str(raw.dwi_path))
    emit("Materializing DWI array into memory")
    data = source_img.get_fdata(dtype=np.float32)
    if data.ndim != 4:
        raise ValueError(f"DIPY preprocessing expects a 4D DWI image, got shape {data.shape}")
    emit(f"Loaded DWI shape={data.shape}")

    emit("Loading gradients")
    bvals = np.loadtxt(str(raw.bval_path), ndmin=1)
    bvecs = np.loadtxt(str(raw.bvec_path))
    if bvecs.ndim == 2 and bvecs.shape[0] == 3:
        bvecs = bvecs.T
    gtab = gradient_table(bvals, bvecs=bvecs, b0_threshold=config.b0_threshold)
    emit(f"Gradient table prepared with {int(len(bvals))} volumes")

    denoised = data
    noise_path = paths["denoise_dir"] / f"{subject}_dwi_noise.nii.gz"
    denoise_status: dict[str, Any] = {"method": denoise_method}
    if denoise_method in {"none", "skip", ""}:
        emit("Skipping denoise")
        denoise_status["status"] = "skipped"
    elif denoise_method == "mppca":
        emit("Running mppca denoise")
        denoised, sigma = mppca(data, patch_radius=2, return_sigma=True)
        nib.save(nib.Nifti1Image(np.asarray(sigma, dtype=np.float32), source_img.affine, source_img.header), str(noise_path))
        denoise_status["status"] = "completed"
        denoise_status["noise_map"] = noise_path.as_posix()
    elif denoise_method == "localpca":
        emit("Running localpca denoise")
        denoised = localpca(data, sigma=None, patch_radius=2)
        denoise_status["status"] = "completed"
    elif denoise_method == "patch2self":
        if patch2self is None:
            raise RuntimeError("DIPY patch2self is not available in this environment.")
        emit("Running patch2self denoise")
        denoised = patch2self(data, bvals, b0_threshold=config.b0_threshold, verbose=False)
        denoise_status["status"] = "completed"
    else:
        raise ValueError(f"Unsupported DIPY denoise method: {config.dipy_denoise_method}")

    denoised_path = paths["denoise_dir"] / f"{subject}_dwi_denoised.nii.gz"
    nib.save(nib.Nifti1Image(np.asarray(denoised, dtype=np.float32), source_img.affine, source_img.header), str(denoised_path))

    if config.dipy_run_gibbs:
        emit("Running Gibbs removal")
        degibbs = gibbs_removal(np.asarray(denoised, dtype=np.float32), slice_axis=2, inplace=False, num_processes=1)
        gibbs_status = {"status": "completed"}
    else:
        emit("Skipping Gibbs removal")
        degibbs = np.asarray(denoised, dtype=np.float32)
        gibbs_status = {"status": "skipped"}
    degibbs_path = paths["denoise_dir"] / f"{subject}_dwi_degibbs.nii.gz"
    nib.save(nib.Nifti1Image(np.asarray(degibbs, dtype=np.float32), source_img.affine, source_img.header), str(degibbs_path))

    if config.dipy_run_motion_correction:
        emit("Running between-volume motion correction")
        corrected_img, affine_array = motion_correction(
            nib.Nifti1Image(np.asarray(degibbs, dtype=np.float32), source_img.affine, source_img.header),
            gtab,
            b0_ref=0,
        )
        corrected_path = paths["motion_dir"] / f"{subject}_dwi_preproc.nii.gz"
        nib.save(corrected_img, str(corrected_path))
        affine_path = paths["motion_dir"] / f"{subject}_dipy_motion_affines.npy"
        np.save(str(affine_path), np.asarray(affine_array))
        rotation_status = _rotate_bvecs_best_effort(raw.bvec_path, paths["final_bvec"], affine_array)
        motion_status = {
            "status": "completed",
            "affines": affine_path.as_posix(),
            "bvec_rotation": rotation_status,
        }
    else:
        emit("Skipping motion correction")
        corrected_path = paths["motion_dir"] / f"{subject}_dwi_preproc.nii.gz"
        shutil.copy2(degibbs_path, corrected_path)
        shutil.copy2(raw.bvec_path, paths["final_bvec"])
        motion_status = {"status": "skipped", "bvec_rotation": {"status": "copied"}}

    shutil.copy2(corrected_path, paths["final_dwi"])
    shutil.copy2(raw.bval_path, paths["final_bval"])
    shutil.copy2(raw.mask_path, paths["final_mask"])

    return {
        "denoise": denoise_status,
        "gibbs": gibbs_status,
        "motion": motion_status,
        "bias_correction": {
            "status": "not_available",
            "reason": "DIPY bias_correction module is not available in the tested 1.11.0 environment.",
        },
        "susceptibility_distortion_correction": {
            "status": "not_supported_by_dipy_backend",
            "recommended_backend": "mrtrix_fsl",
        },
        "files": {
            "denoised": denoised_path.as_posix(),
            "degibbs": degibbs_path.as_posix(),
            "motion_corrected": corrected_path.as_posix(),
        },
    }


def _execute_preprocessing_backend(
    raw: RawInputBundle,
    config: DwiPreprocessingConfig,
    paths: dict[str, Path],
    backend: dict[str, Any],
    commands: list[list[str]],
    *,
    log: Optional[Callable[[str], None]],
) -> dict[str, Any]:
    if backend.get("backend") == "dipy":
        return _run_dipy_backend(raw, config, paths, log=log)

    env = _external_command_environment(config)
    for command in commands:
        if command[0] == "copy":
            shutil.copy2(command[1], command[2])
            continue
        if command[0] == "optional-output":
            continue
        _run_command(command, env=env, log=log)
    diagnostics = _collect_dwifslpreproc_diagnostics(paths, raw.subject_id)
    eddy_qc_collection = _collect_eddy_qc_artifacts(paths)
    return {
        "fsl_environment": {
            "FSLDIR": env.get("FSLDIR"),
            "FSLOUTPUTTYPE": env.get("FSLOUTPUTTYPE"),
        },
        "diagnostics": diagnostics,
        "eddy_qc_collection": eddy_qc_collection,
        "scratch_dir": (paths["motion_dir"] / "dwifslpreproc_tmp").as_posix(),
    }


def run_dwi_preprocessing(
    config: DwiPreprocessingConfig,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> DwiPreprocessingResult:
    raw = find_subject_root(
        config.input_root,
        config.subject_id,
        mrtrix_bin_dir=config.mrtrix_bin_dir,
    )
    output_dir = _resolve_output_dir(raw, config.output_dir)
    paths = _planned_paths(output_dir, raw.subject_id)
    backend = inspect_preprocessing_backend(config)
    commands = _build_commands(raw, config, paths, backend)
    command_records = [{"argv": command} for command in commands]

    output_dir.mkdir(parents=True, exist_ok=True)
    status = "skipped" if config.skip else ("planned" if not config.execute else "completed")

    manifest: dict[str, Any] = {
        "kind": "dwi_preprocessing",
        "version": 1,
        "subject_id": raw.subject_id,
        "status": status,
        "optional": True,
        "execute": config.execute,
        "skip": config.skip,
        "backend": backend,
        "inputs": {
            "subject_root": raw.subject_root.as_posix(),
            "dwi": raw.dwi_path.as_posix(),
            "bval": raw.bval_path.as_posix(),
            "bvec": raw.bvec_path.as_posix(),
            "mask": raw.mask_path.as_posix(),
            "reverse_phase_b0": config.reverse_phase_b0.as_posix() if config.reverse_phase_b0 else None,
        },
        "parameters": {
            "eddy_threads": _resolved_eddy_threads(config)
            if backend.get("backend") == "mrtrix_fsl"
            else None,
            "eddy_second_level_model": (
                config.eddy_second_level_model.strip().lower()
                if backend.get("backend") == "mrtrix_fsl"
                and config.eddy_second_level_model is not None
                else None
            ),
            "final_mask_method": (
                "dwi2mask_corrected_dwi"
                if backend.get("backend") == "mrtrix_fsl"
                else "input_mask"
            ),
        },
        "outputs": {key: value.as_posix() for key, value in paths.items() if key not in {"import_dir", "gradients_dir", "denoise_dir", "motion_dir", "mask_dir", "qc_dir"}},
        "commands": command_records,
    }
    _write_json(paths["manifest"], manifest)

    if config.skip:
        _write_json(paths["qc"], {"kind": "dwi_preprocessing_qc", "status": "skipped", "subject_id": raw.subject_id, "checks": []})
        return DwiPreprocessingResult(raw.subject_id, "skipped", output_dir, paths["manifest"], paths["qc"], paths["final_dwi"], paths["final_bval"], paths["final_bvec"], paths["final_mask"])

    if not config.execute:
        _write_json(paths["qc"], {"kind": "dwi_preprocessing_qc", "status": "planned", "subject_id": raw.subject_id, "backend_available": backend["available"]})
        return DwiPreprocessingResult(raw.subject_id, "planned", output_dir, paths["manifest"], paths["qc"], paths["final_dwi"], paths["final_bval"], paths["final_bvec"], paths["final_mask"])

    if not backend["available"]:
        missing = ", ".join(backend.get("missing_required", backend.get("missing_python", [])))
        raise RuntimeError(f"DWI preprocessing backend is unavailable ({config.backend}): {missing}")

    cached_core_ready = (
        not config.force
        and paths["final_dwi"].is_file()
        and paths["final_bval"].is_file()
        and paths["final_bvec"].is_file()
    )
    mask_refresh_status = "not_needed"
    if cached_core_ready and backend.get("backend") == "mrtrix_fsl":
        mask_is_stale = (
            not paths["final_mask"].is_file()
            or paths["final_mask"].stat().st_mtime_ns
            < paths["final_dwi"].stat().st_mtime_ns
        )
        if mask_is_stale:
            _materialize_dirs(paths)
            mask_command = [
                backend["commands"]["dwi2mask"] or "dwi2mask",
                paths["final_dwi"].as_posix(),
                paths["final_mask"].as_posix(),
                "-fslgrad",
                paths["final_bvec"].as_posix(),
                paths["final_bval"].as_posix(),
            ]
            if paths["final_mask"].exists():
                mask_command.append("-force")
            _run_command(
                mask_command,
                env=_external_command_environment(config),
                log=log,
            )
            mask_refresh_status = "regenerated_from_corrected_dwi"

    if cached_core_ready and paths["final_mask"].is_file():
        manifest["status"] = "cached"
        _write_json(paths["manifest"], manifest)
        backend_details: dict[str, Any] = {}
        if backend.get("backend") == "mrtrix_fsl":
            backend_details = {
                "diagnostics": _collect_dwifslpreproc_diagnostics(paths, raw.subject_id),
                "eddy_qc_collection": _collect_eddy_qc_artifacts(paths),
                "scratch_dir": (paths["motion_dir"] / "dwifslpreproc_tmp").as_posix(),
            }
        _write_json(
            paths["qc"],
            {
                "kind": "dwi_preprocessing_qc",
                "version": 1,
                "status": "completed",
                "reuse_status": "cached",
                "mask_refresh_status": mask_refresh_status,
                "subject_id": raw.subject_id,
                "files": {
                    "final_dwi": _file_record(paths["final_dwi"]),
                    "final_bval": _file_record(paths["final_bval"]),
                    "final_bvec": _file_record(paths["final_bvec"]),
                    "final_mask": _file_record(paths["final_mask"]),
                    "eddy_parameters": _file_record(paths["eddy_parameters"]),
                    "eddy_movement_rms": _file_record(paths["eddy_movement_rms"]),
                    "eddy_outlier_map": _file_record(paths["eddy_outlier_map"]),
                    "eddy_outlier_report": _file_record(paths["eddy_outlier_report"]),
                    "eddy_cnr_maps": _file_record(paths["eddy_cnr_maps"]),
                    "eddy_residuals": _file_record(paths["eddy_residuals"]),
                },
                "backend_details": backend_details,
            },
        )
        return DwiPreprocessingResult(raw.subject_id, "cached", output_dir, paths["manifest"], paths["qc"], paths["final_dwi"], paths["final_bval"], paths["final_bvec"], paths["final_mask"])

    _materialize_dirs(paths)
    if config.force:
        shutil.rmtree(paths["motion_dir"] / "dwifslpreproc_tmp", ignore_errors=True)
    _copy_input_sidecars(raw, paths)
    manifest["status"] = "running"
    _write_json(paths["manifest"], manifest)
    _write_json(
        paths["qc"],
        {
            "kind": "dwi_preprocessing_qc",
            "status": "running",
            "subject_id": raw.subject_id,
            "backend_available": backend["available"],
        },
    )

    try:
        backend_details = _execute_preprocessing_backend(
            raw,
            config,
            paths,
            backend,
            commands,
            log=log,
        )

        if not paths["final_bval"].exists():
            shutil.copy2(raw.bval_path, paths["final_bval"])
        if not paths["final_bvec"].exists():
            shutil.copy2(raw.bvec_path, paths["final_bvec"])
        if not paths["final_mask"].exists():
            shutil.copy2(raw.mask_path, paths["final_mask"])

        required_outputs = (
            paths["final_dwi"],
            paths["final_bval"],
            paths["final_bvec"],
            paths["final_mask"],
        )
        missing_outputs = [path.as_posix() for path in required_outputs if not path.is_file()]
        if missing_outputs:
            raise RuntimeError(
                "DWI preprocessing finished without required output(s): " + ", ".join(missing_outputs)
            )
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(paths["manifest"], manifest)
        _write_json(
            paths["qc"],
            {
                "kind": "dwi_preprocessing_qc",
                "version": 1,
                "subject_id": raw.subject_id,
                "status": "failed",
                "backend_available": backend["available"],
                "error": manifest["error"],
            },
        )
        raise

    qc_payload = {
        "kind": "dwi_preprocessing_qc",
        "version": 1,
        "subject_id": raw.subject_id,
        "status": "completed",
        "files": {
            "final_dwi": _file_record(paths["final_dwi"]),
            "final_bval": _file_record(paths["final_bval"]),
            "final_bvec": _file_record(paths["final_bvec"]),
            "final_mask": _file_record(paths["final_mask"]),
            "eddy_parameters": _file_record(paths["eddy_parameters"]),
            "eddy_movement_rms": _file_record(paths["eddy_movement_rms"]),
            "eddy_outlier_map": _file_record(paths["eddy_outlier_map"]),
            "eddy_outlier_report": _file_record(paths["eddy_outlier_report"]),
            "eddy_cnr_maps": _file_record(paths["eddy_cnr_maps"]),
            "eddy_residuals": _file_record(paths["eddy_residuals"]),
        },
        "warnings": [
            f"Diagnostic command not found: {command}"
            for command in backend.get("missing_diagnostic", [])
        ],
        "mask_generation": {
            "method": (
                "dwi2mask_corrected_dwi"
                if backend.get("backend") == "mrtrix_fsl"
                else "input_mask"
            ),
            "source": (
                paths["final_dwi"].as_posix()
                if backend.get("backend") == "mrtrix_fsl"
                else raw.mask_path.as_posix()
            ),
        },
        "backend_details": backend_details,
    }
    manifest["status"] = "completed"
    _write_json(paths["manifest"], manifest)
    _write_json(paths["qc"], qc_payload)

    return DwiPreprocessingResult(raw.subject_id, "completed", output_dir, paths["manifest"], paths["qc"], paths["final_dwi"], paths["final_bval"], paths["final_bvec"], paths["final_mask"])
