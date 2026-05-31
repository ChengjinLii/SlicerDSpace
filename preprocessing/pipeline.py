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
from shared.pipeline import RawInputBundle, find_subject_root


REQUIRED_COMMANDS = ("dwidenoise", "mrdegibbs", "dwifslpreproc")
DIAGNOSTIC_COMMANDS = ("eddy", "topup")


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


def _resolve_command(command: str, config: DwiPreprocessingConfig) -> Optional[str]:
    return shutil.which(command, path=_command_search_path(config))


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
    commands = {
        command: _resolve_command(command, config)
        for command in (*REQUIRED_COMMANDS, *DIAGNOSTIC_COMMANDS)
    }
    missing_required = [command for command in REQUIRED_COMMANDS if commands[command] is None]
    missing_diagnostic = [command for command in DIAGNOSTIC_COMMANDS if commands[command] is None]
    return {
        "kind": "dwi_preprocessing_backend",
        "backend": "mrtrix_fsl",
        "required_commands": list(REQUIRED_COMMANDS),
        "diagnostic_commands": list(DIAGNOSTIC_COMMANDS),
        "commands": commands,
        "missing_required": missing_required,
        "missing_diagnostic": missing_diagnostic,
        "available": not missing_required,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    }


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
    eddy_params = paths["motion_dir"] / f"{subject}_eddy_parameters.txt"
    eddy_rms = paths["motion_dir"] / f"{subject}_eddy_movement_rms.txt"
    outlier_map = paths["motion_dir"] / f"{subject}_eddy_outlier_map.nii.gz"

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
        "--cnr_maps --residuals",
    ]
    if config.reverse_phase_b0 is not None:
        dwifslpreproc_cmd.extend(["-rpe_pair", "-se_epi", config.reverse_phase_b0.expanduser().resolve().as_posix()])
        if config.phase_encoding_direction:
            dwifslpreproc_cmd.extend(["-pe_dir", config.phase_encoding_direction])
        if config.readout_time is not None:
            dwifslpreproc_cmd.extend(["-readout_time", str(config.readout_time)])
    else:
        dwifslpreproc_cmd.append("-rpe_none")

    return [
        [
            backend["commands"]["dwidenoise"] or "dwidenoise",
            raw.dwi_path.as_posix(),
            denoised.as_posix(),
            "-noise",
            noise.as_posix(),
        ],
        [
            backend["commands"]["mrdegibbs"] or "mrdegibbs",
            denoised.as_posix(),
            degibbs.as_posix(),
        ],
        dwifslpreproc_cmd,
        ["copy", raw.mask_path.as_posix(), paths["final_mask"].as_posix()],
        ["optional-output", eddy_params.as_posix(), eddy_rms.as_posix(), outlier_map.as_posix()],
    ]


def _materialize_dirs(paths: dict[str, Path]) -> None:
    for key in ("import_dir", "gradients_dir", "denoise_dir", "motion_dir", "mask_dir", "qc_dir"):
        paths[key].mkdir(parents=True, exist_ok=True)


def _copy_input_sidecars(raw: RawInputBundle, paths: dict[str, Path]) -> None:
    shutil.copy2(raw.dwi_path, paths["import_dir"] / raw.dwi_path.name)
    shutil.copy2(raw.bval_path, paths["import_dir"] / raw.bval_path.name)
    shutil.copy2(raw.bvec_path, paths["import_dir"] / raw.bvec_path.name)
    shutil.copy2(raw.mask_path, paths["import_dir"] / raw.mask_path.name)
    shutil.copy2(raw.bval_path, paths["gradients_dir"] / f"{raw.subject_id}_gradients_checked.bval")
    shutil.copy2(raw.bvec_path, paths["gradients_dir"] / f"{raw.subject_id}_gradients_checked.bvec")


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
    if affine_array.ndim != 3 or affine_array.shape[-2:] != (4, 4) or len(bvecs) != affine_array.shape[0]:
        shutil.copy2(raw_bvec_path, output_bvec_path)
        return {
            "status": "copied",
            "reason": "unexpected affine array shape or gradient count mismatch",
            "affine_shape": list(affine_array.shape),
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
    source_img = nib.load(str(raw.dwi_path))
    data = source_img.get_fdata(dtype=np.float32)
    if data.ndim != 4:
        raise ValueError(f"DIPY preprocessing expects a 4D DWI image, got shape {data.shape}")

    bvals = np.loadtxt(str(raw.bval_path), ndmin=1)
    bvecs = np.loadtxt(str(raw.bvec_path))
    if bvecs.ndim == 2 and bvecs.shape[0] == 3:
        bvecs = bvecs.T
    gtab = gradient_table(bvals, bvecs=bvecs, b0_threshold=config.b0_threshold)

    denoise_method = config.dipy_denoise_method.lower()
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


def run_dwi_preprocessing(
    config: DwiPreprocessingConfig,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> DwiPreprocessingResult:
    raw = find_subject_root(config.input_root, config.subject_id)
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
        "outputs": {key: value.as_posix() for key, value in paths.items() if key not in {"import_dir", "gradients_dir", "denoise_dir", "motion_dir", "mask_dir", "qc_dir"}},
        "commands": command_records,
    }

    if config.skip:
        _write_json(paths["manifest"], manifest)
        _write_json(paths["qc"], {"kind": "dwi_preprocessing_qc", "status": "skipped", "subject_id": raw.subject_id, "checks": []})
        return DwiPreprocessingResult(raw.subject_id, "skipped", output_dir, paths["manifest"], paths["qc"], paths["final_dwi"], paths["final_bval"], paths["final_bvec"], paths["final_mask"])

    if not config.execute:
        _write_json(paths["manifest"], manifest)
        _write_json(paths["qc"], {"kind": "dwi_preprocessing_qc", "status": "planned", "subject_id": raw.subject_id, "backend_available": backend["available"]})
        return DwiPreprocessingResult(raw.subject_id, "planned", output_dir, paths["manifest"], paths["qc"], paths["final_dwi"], paths["final_bval"], paths["final_bvec"], paths["final_mask"])

    if not backend["available"]:
        missing = ", ".join(backend.get("missing_required", backend.get("missing_python", [])))
        raise RuntimeError(f"DWI preprocessing backend is unavailable ({config.backend}): {missing}")

    if not config.force and paths["final_dwi"].is_file() and paths["final_bval"].is_file() and paths["final_bvec"].is_file():
        manifest["status"] = "cached"
        _write_json(paths["manifest"], manifest)
        _write_json(paths["qc"], {"kind": "dwi_preprocessing_qc", "status": "cached", "subject_id": raw.subject_id})
        return DwiPreprocessingResult(raw.subject_id, "cached", output_dir, paths["manifest"], paths["qc"], paths["final_dwi"], paths["final_bval"], paths["final_bvec"], paths["final_mask"])

    _materialize_dirs(paths)
    _copy_input_sidecars(raw, paths)

    backend_details: dict[str, Any] = {}
    if backend.get("backend") == "dipy":
        backend_details = _run_dipy_backend(raw, config, paths, log=log)
    else:
        env = os.environ.copy()
        env["PATH"] = _command_search_path(config)
        for command in commands:
            if command[0] == "copy":
                shutil.copy2(command[1], command[2])
                continue
            if command[0] == "optional-output":
                continue
            _run_command(command, env=env, log=log)

    if not paths["final_bval"].exists():
        shutil.copy2(raw.bval_path, paths["final_bval"])
    if not paths["final_bvec"].exists():
        shutil.copy2(raw.bvec_path, paths["final_bvec"])
    if not paths["final_mask"].exists():
        shutil.copy2(raw.mask_path, paths["final_mask"])

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
            "eddy_parameters": _file_record(paths["motion_dir"] / f"{raw.subject_id}_eddy_parameters.txt"),
            "eddy_movement_rms": _file_record(paths["motion_dir"] / f"{raw.subject_id}_eddy_movement_rms.txt"),
        },
        "warnings": [
            f"Diagnostic command not found: {command}"
            for command in backend.get("missing_diagnostic", [])
        ],
        "backend_details": backend_details,
    }
    _write_json(paths["manifest"], manifest)
    _write_json(paths["qc"], qc_payload)

    return DwiPreprocessingResult(raw.subject_id, "completed", output_dir, paths["manifest"], paths["qc"], paths["final_dwi"], paths["final_bval"], paths["final_bvec"], paths["final_mask"])
