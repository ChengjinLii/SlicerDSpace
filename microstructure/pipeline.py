"""Phase-3 microstructure workflow: DTI maps, Free Water, and AMICO NODDI."""

from __future__ import annotations

import csv
import json
import logging
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from shared.pipeline import NativeDTIBundle, RawInputBundle

LOGGER = logging.getLogger(__name__)
FREE_WATER_ENGINES = {"serial", "joblib", "dask", "ray"}
# DIPY's free-water model assumes an isotropic free-water diffusivity of
# 3e-3 mm^2/s. Tissue MD estimates above that value are numerically invalid
# (typically caused by ill-conditioned low-signal voxel fits) and must not be
# propagated into regional statistics.
FREE_WATER_MAX_TISSUE_MD = 3.0e-3
# DIPY's reference free-water example excludes tissue metrics when the fitted
# free-water fraction exceeds 0.7 because tissue FA becomes unstable there.
FREE_WATER_MAX_FRACTION_FOR_TISSUE = 0.7
# NODDI's NDI and ODI are conditional tissue parameters. In voxels dominated
# by the fitted isotropic compartment they are not interpretable and AMICO can
# legitimately return a dictionary-boundary value. Public maps retain bounded
# brain estimates for continuous display; this threshold defines the separate
# validity mask used by quantitative summaries.
NODDI_MAX_ISOTROPIC_FRACTION_FOR_TISSUE = 0.7
NODDI_UPPER_BOUND = 0.99

try:
    import nibabel as nib
    import numpy as np
except ImportError as exc:  # pragma: no cover - handled at runtime inside Slicer
    nib = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

try:
    from dipy.core.gradients import gradient_table
    from dipy.reconst.fwdti import FreeWaterTensorModel
except ImportError as exc:  # pragma: no cover - optional runtime dependency
    gradient_table = None  # type: ignore[assignment]
    FreeWaterTensorModel = None  # type: ignore[assignment]
    DIPY_IMPORT_ERROR = exc
else:
    DIPY_IMPORT_ERROR = None

try:
    import amico
    from amico.util import fsl2scheme
except ImportError as exc:  # pragma: no cover - optional runtime dependency
    amico = None  # type: ignore[assignment]
    fsl2scheme = None  # type: ignore[assignment]
    AMICO_IMPORT_ERROR = exc
else:
    AMICO_IMPORT_ERROR = None


@dataclass(frozen=True)
class MicrostructureConfig:
    subject_id: str
    raw_input_bundle: RawInputBundle
    native_bundle: NativeDTIBundle
    output_dir: Path
    roi_label_map: Path | None = None
    lut_path: Path | None = None
    free_water_fit_method: str = "WLS"
    free_water_chunk_size: int = 2
    free_water_engine: str = "serial"
    free_water_n_jobs: int | None = None
    free_water_vox_per_chunk: int | None = None
    free_water_max_fraction_for_tissue: float = FREE_WATER_MAX_FRACTION_FOR_TISSUE
    run_free_water: bool = True
    run_noddi: bool = True
    force_recompute: bool = False
    noddi_directional_average: bool = False
    noddi_b0_threshold: int = 50
    noddi_lmax: int = 12
    noddi_ndirs: int = 500
    noddi_nthreads: int = 1
    noddi_solver_lambda1: float = 0.5
    noddi_solver_lambda2: float = 0.001
    noddi_max_isotropic_fraction_for_tissue: float = NODDI_MAX_ISOTROPIC_FRACTION_FOR_TISSUE


@dataclass(frozen=True)
class MicrostructureResult:
    subject_id: str
    output_dir: Path
    fa_path: Path
    md_path: Path
    ad_path: Path
    rd_path: Path
    l1_path: Path
    l2_path: Path
    l3_path: Path
    trace_path: Path
    fwf_path: Path
    fw_tissue_fa_path: Path
    fw_tissue_md_path: Path
    fw_tissue_valid_mask_path: Path
    free_water_qc_path: Path
    noddi_ndi_path: Path
    noddi_odi_path: Path
    noddi_fwf_path: Path
    noddi_tissue_valid_mask_path: Path
    noddi_rmse_path: Path
    noddi_nrmse_path: Path
    noddi_qc_path: Path
    roi_label_map: Path | None
    roi_stats_csv_path: Path | None
    roi_stats_json_path: Path | None


def _emit(message: str, log: Optional[Callable[[str], None]] = None) -> None:
    LOGGER.info(message)
    if log:
        log(message)


def _ensure_base_imports_ready() -> None:
    if IMPORT_ERROR is not None:
        raise RuntimeError(
            "Microstructure output generation requires nibabel and numpy."
        ) from IMPORT_ERROR


def _ensure_dipy_ready() -> None:
    if DIPY_IMPORT_ERROR is not None:
        raise RuntimeError(
            "Free Water modeling requires DIPY. Install it in the active Python environment first."
        ) from DIPY_IMPORT_ERROR


def _ensure_amico_ready() -> None:
    if AMICO_IMPORT_ERROR is not None:
        raise RuntimeError(
            "NODDI modeling requires AMICO (dmri-amico). Install it in the active Python environment first."
        ) from AMICO_IMPORT_ERROR


def _file_signature(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _read_json(path: Path) -> Optional[dict[str, object]]:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - corrupt manifest fallback
        LOGGER.warning("Unable to parse JSON file: %s", path)
        return None


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_progress(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    enriched = {
        **payload,
        "updated_at": _utc_now(),
    }
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(enriched, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _copy_if_needed(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dest.resolve():
        return
    shutil.copy2(src, dest)


def _link_or_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        return
    try:
        dest.symlink_to(src.resolve())
    except OSError:
        shutil.copy2(src, dest)


def _default_lut_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "parcellation"
        / "conversion"
        / "data"
        / "FreeSurferColorLUT.txt"
    )


def _resolve_roi_label_map(config: MicrostructureConfig) -> Path | None:
    if config.roi_label_map is not None:
        roi_path = config.roi_label_map.expanduser().resolve()
        if not roi_path.is_file():
            raise FileNotFoundError(f"ROI label map not found: {roi_path}")
        return roi_path

    default_candidates = [
        config.native_bundle.subject_root
        / "outputs"
        / "03_structural"
        / "ddparcel"
        / f"{config.subject_id}_ddparcel_wmparc_labels.nii.gz",
        config.native_bundle.subject_root
        / "outputs"
        / "03_structural"
        / "ddparcel"
        / f"{config.subject_id}-DDSurfer-wmparc.nii.gz",
        config.native_bundle.subject_root
        / "outputs"
        / "ddparcel"
        / f"{config.subject_id}-DDSurfer-wmparc.nii.gz",
    ]
    for default_path in default_candidates:
        if default_path.is_file():
            return default_path
    return None


def _resolve_lut_path(config: MicrostructureConfig) -> Path | None:
    lut_path = config.lut_path.expanduser().resolve() if config.lut_path is not None else _default_lut_path()
    if lut_path.is_file():
        return lut_path
    return None


def _parse_label_names(labels: list[int], lut_path: Path | None) -> dict[int, str]:
    if lut_path is None:
        return {}

    label_set = set(labels)
    names: dict[int, str] = {}
    with lut_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 2:
                continue
            try:
                label_id = int(parts[0])
            except ValueError:
                continue
            if label_id in label_set:
                names[label_id] = parts[1]
    return names


def _output_paths(
    subject_id: str,
    output_dir: Path,
) -> dict[str, Path]:
    dti_dir = output_dir / "dti"
    freewater_dir = output_dir / "freewater"
    noddi_dir = output_dir / "noddi"
    if output_dir.name == "02_microstructure":
        roi_dir = output_dir.parent / "05_statistics" / "regional_microstructure"
    else:
        roi_dir = output_dir / "regional_microstructure"
    return {
        "fa": dti_dir / f"{subject_id}_dti_FA.nii.gz",
        "md": dti_dir / f"{subject_id}_dti_MD.nii.gz",
        "ad": dti_dir / f"{subject_id}_dti_AD.nii.gz",
        "rd": dti_dir / f"{subject_id}_dti_RD.nii.gz",
        "l1": dti_dir / f"{subject_id}_dti_L1.nii.gz",
        "l2": dti_dir / f"{subject_id}_dti_L2.nii.gz",
        "l3": dti_dir / f"{subject_id}_dti_L3.nii.gz",
        "trace": dti_dir / f"{subject_id}_dti_Trace.nii.gz",
        "fwf": freewater_dir / f"{subject_id}_fw_fraction.nii.gz",
        "fw_tissue_fa": freewater_dir / f"{subject_id}_fw_FA.nii.gz",
        "fw_tissue_md": freewater_dir / f"{subject_id}_fw_MD.nii.gz",
        "fw_tissue_valid_mask": freewater_dir / f"{subject_id}_fw_tissue_valid_mask.nii.gz",
        "free_water_qc": freewater_dir / "freewater_qc.json",
        "noddi_ndi": noddi_dir / f"{subject_id}_noddi_NDI.nii.gz",
        "noddi_odi": noddi_dir / f"{subject_id}_noddi_ODI.nii.gz",
        "noddi_fwf": noddi_dir / f"{subject_id}_noddi_IsoVF.nii.gz",
        "noddi_tissue_valid_mask": noddi_dir / f"{subject_id}_noddi_tissue_valid_mask.nii.gz",
        "noddi_rmse": noddi_dir / f"{subject_id}_noddi_RMSE.nii.gz",
        "noddi_nrmse": noddi_dir / f"{subject_id}_noddi_NRMSE.nii.gz",
        "noddi_qc": noddi_dir / "noddi_qc.json",
        "roi_stats_csv": roi_dir / f"{subject_id}_ROIWise-Microstructure.csv",
        "roi_stats_json": roi_dir / f"{subject_id}_ROIWise-Microstructure.json",
        "free_water_manifest": freewater_dir / "freewater_manifest.json",
        "free_water_progress": freewater_dir / "freewater_progress.json",
        "noddi_manifest": noddi_dir / "noddi_manifest.json",
        "noddi_progress": noddi_dir / "noddi_progress.json",
        "manifest": output_dir / "manifest.json",
    }


def _expected_manifest(
    config: MicrostructureConfig,
    roi_label_map: Path | None,
    *,
    free_water_available: bool | None = None,
    noddi_available: bool | None = None,
) -> dict[str, object]:
    free_water_available = bool(config.run_free_water) if free_water_available is None else bool(free_water_available)
    noddi_available = bool(config.run_noddi) if noddi_available is None else bool(noddi_available)
    roi_metrics = ["FA", "MD", "AD", "RD", "L1", "L2", "L3", "TRACE"]
    if free_water_available:
        roi_metrics.extend(["FWF", "FW_TISSUE_FA", "FW_TISSUE_MD"])
    if noddi_available:
        roi_metrics.extend(["NODDI_NDI", "NODDI_ODI", "NODDI_FWF"])
    return {
        "kind": "microstructure_phase3",
        "version": 3,
        "subject_id": config.subject_id,
        "fit_method": config.native_bundle.fit_method,
        "roi_metrics": roi_metrics,
        "native_bundle": {
            "dir": str(config.native_bundle.bundle_dir.resolve()),
            "manifest": _read_json(config.native_bundle.manifest_path),
        },
        "raw_input_bundle": {
            "dwi": _file_signature(config.raw_input_bundle.dwi_path),
            "bval": _file_signature(config.raw_input_bundle.bval_path),
            "bvec": _file_signature(config.raw_input_bundle.bvec_path),
            "mask": _file_signature(config.raw_input_bundle.mask_path),
        },
        "free_water_model": {
            "fit_method": config.free_water_fit_method.upper(),
            "chunk_size": int(config.free_water_chunk_size),
            "engine": config.free_water_engine,
            "n_jobs": config.free_water_n_jobs,
            "vox_per_chunk": config.free_water_vox_per_chunk,
            "max_tissue_md_mm2_s": FREE_WATER_MAX_TISSUE_MD,
            "max_free_water_fraction_for_tissue": float(config.free_water_max_fraction_for_tissue),
            "run_enabled": bool(config.run_free_water),
            "outputs_available": free_water_available,
        },
        "noddi_model": {
            "name": "NODDI",
            "library": "AMICO",
            "run_enabled": bool(config.run_noddi),
            "outputs_available": noddi_available,
            "directional_average": bool(config.noddi_directional_average),
            "b0_threshold": int(config.noddi_b0_threshold),
            "lmax": int(config.noddi_lmax),
            "ndirs": int(config.noddi_ndirs),
            "nthreads": int(config.noddi_nthreads),
            "solver": {
                "lambda1": float(config.noddi_solver_lambda1),
                "lambda2": float(config.noddi_solver_lambda2),
            },
            "max_isotropic_fraction_for_tissue": float(config.noddi_max_isotropic_fraction_for_tissue),
        },
        "roi_label_map": _file_signature(roi_label_map) if roi_label_map is not None else None,
    }


def _expected_free_water_manifest(config: MicrostructureConfig) -> dict[str, object]:
    return {
        "kind": "microstructure_freewater_stage",
        "version": 2,
        "subject_id": config.subject_id,
        "raw_input_bundle": {
            "dwi": _file_signature(config.raw_input_bundle.dwi_path),
            "bval": _file_signature(config.raw_input_bundle.bval_path),
            "bvec": _file_signature(config.raw_input_bundle.bvec_path),
            "mask": _file_signature(config.raw_input_bundle.mask_path),
        },
        "free_water_model": {
            "fit_method": config.free_water_fit_method.upper(),
            "chunk_size": int(config.free_water_chunk_size),
            "engine": config.free_water_engine,
            "n_jobs": config.free_water_n_jobs,
            "vox_per_chunk": config.free_water_vox_per_chunk,
            "max_tissue_md_mm2_s": FREE_WATER_MAX_TISSUE_MD,
            "max_free_water_fraction_for_tissue": float(config.free_water_max_fraction_for_tissue),
        },
    }


def _expected_noddi_manifest(config: MicrostructureConfig) -> dict[str, object]:
    return {
        "kind": "microstructure_noddi_stage",
        "version": 2,
        "subject_id": config.subject_id,
        "raw_input_bundle": {
            "dwi": _file_signature(config.raw_input_bundle.dwi_path),
            "bval": _file_signature(config.raw_input_bundle.bval_path),
            "bvec": _file_signature(config.raw_input_bundle.bvec_path),
            "mask": _file_signature(config.raw_input_bundle.mask_path),
        },
        "noddi_model": {
            "name": "NODDI",
            "library": "AMICO",
            "directional_average": bool(config.noddi_directional_average),
            "b0_threshold": int(config.noddi_b0_threshold),
            "lmax": int(config.noddi_lmax),
            "ndirs": int(config.noddi_ndirs),
            "nthreads": int(config.noddi_nthreads),
            "solver": {
                "lambda1": float(config.noddi_solver_lambda1),
                "lambda2": float(config.noddi_solver_lambda2),
            },
            "max_isotropic_fraction_for_tissue": float(config.noddi_max_isotropic_fraction_for_tissue),
            "residual_maps": ["RMSE", "NRMSE"],
        },
    }


def _outputs_complete(
    paths: dict[str, Path],
    *,
    roi_enabled: bool,
    free_water_enabled: bool,
    noddi_enabled: bool,
) -> bool:
    required = [
        paths["fa"],
        paths["md"],
        paths["ad"],
        paths["rd"],
        paths["l1"],
        paths["l2"],
        paths["l3"],
        paths["trace"],
        paths["manifest"],
    ]
    if free_water_enabled:
        required.extend(
            [
                paths["fwf"],
                paths["fw_tissue_fa"],
                paths["fw_tissue_md"],
                paths["fw_tissue_valid_mask"],
                paths["free_water_qc"],
                paths["free_water_manifest"],
            ]
        )
    if noddi_enabled:
        required.extend(
            [
                paths["noddi_ndi"],
                paths["noddi_odi"],
                paths["noddi_fwf"],
                paths["noddi_tissue_valid_mask"],
                paths["noddi_rmse"],
                paths["noddi_nrmse"],
                paths["noddi_qc"],
                paths["noddi_manifest"],
            ]
        )
    if roi_enabled:
        required.extend([paths["roi_stats_csv"], paths["roi_stats_json"]])
    return all(path.is_file() for path in required)


def _free_water_outputs_complete(paths: dict[str, Path]) -> bool:
    return _free_water_maps_complete(paths) and paths["free_water_qc"].is_file() and (
        _read_json(paths["free_water_qc"]).get("status") == "completed"
    )


def _free_water_maps_complete(paths: dict[str, Path]) -> bool:
    return all(
        paths[key].is_file()
        for key in ("fwf", "fw_tissue_fa", "fw_tissue_md", "fw_tissue_valid_mask")
    )


def _noddi_outputs_complete(paths: dict[str, Path]) -> bool:
    return all(
        paths[key].is_file()
        for key in (
            "noddi_ndi",
            "noddi_odi",
            "noddi_fwf",
            "noddi_tissue_valid_mask",
            "noddi_rmse",
            "noddi_nrmse",
            "noddi_qc",
        )
    )


def _free_water_outputs_current(config: MicrostructureConfig, paths: dict[str, Path]) -> bool:
    """Return whether reusable Free Water maps match the current input/config."""

    return (
        _free_water_outputs_complete(paths)
        and _read_json(paths["free_water_manifest"]) == _expected_free_water_manifest(config)
    )


def _noddi_outputs_current(config: MicrostructureConfig, paths: dict[str, Path]) -> bool:
    """Return whether reusable NODDI maps match the current input/config."""

    return (
        _noddi_outputs_complete(paths)
        and _read_json(paths["noddi_manifest"]) == _expected_noddi_manifest(config)
    )


def _compute_rd_map(l2_path: Path, l3_path: Path, output_path: Path) -> None:
    _ensure_base_imports_ready()
    l2_img = nib.load(str(l2_path))
    l3_img = nib.load(str(l3_path))
    l2 = np.asarray(l2_img.get_fdata(dtype=np.float32), dtype=np.float32)
    l3 = np.asarray(l3_img.get_fdata(dtype=np.float32), dtype=np.float32)
    rd = (l2 + l3) / np.float32(2.0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(rd, l2_img.affine, l2_img.header), str(output_path))


def _export_dti_scalar_maps(config: MicrostructureConfig, paths: dict[str, Path]) -> None:
    native = config.native_bundle
    _copy_if_needed(native.fa_nii_path, paths["fa"])
    _copy_if_needed(native.mean_diffusivity_nii_path, paths["md"])
    _copy_if_needed(native.max_eig_nii_path, paths["l1"])
    _copy_if_needed(native.mid_eig_nii_path, paths["l2"])
    _copy_if_needed(native.min_eig_nii_path, paths["l3"])
    _copy_if_needed(native.trace_nii_path, paths["trace"])
    _copy_if_needed(native.max_eig_nii_path, paths["ad"])
    if config.force_recompute or not paths["rd"].is_file():
        _compute_rd_map(paths["l2"], paths["l3"], paths["rd"])


def _remove_legacy_roi_outputs(output_dir: Path, subject_id: str) -> None:
    legacy_paths = [
        output_dir / f"{subject_id}-ROIWise-FA.csv",
        output_dir / f"{subject_id}-ROIWise-FA.json",
    ]
    for path in legacy_paths:
        path.unlink(missing_ok=True)


def _load_bvals_bvecs(raw_input_bundle: RawInputBundle) -> tuple[np.ndarray, np.ndarray]:
    bvals = np.loadtxt(raw_input_bundle.bval_path)
    bvecs = np.loadtxt(raw_input_bundle.bvec_path)

    bvals = np.atleast_1d(np.asarray(bvals, dtype=np.float64)).reshape(-1)
    bvecs = np.asarray(bvecs, dtype=np.float64)
    if bvecs.ndim == 1:
        bvecs = bvecs.reshape(1, -1)
    if bvecs.shape[0] == 3 and bvecs.shape[1] == bvals.shape[0]:
        bvecs = bvecs.T
    if bvecs.shape != (bvals.shape[0], 3):
        raise ValueError(
            f"Unexpected bvec shape {bvecs.shape}; expected ({bvals.shape[0]}, 3)."
        )
    return bvals, bvecs


def _save_scalar_nifti(data: np.ndarray, reference_img: nib.Nifti1Image, output_path: Path) -> None:
    header = reference_img.header.copy()
    header.set_data_dtype(np.float32)
    image = nib.Nifti1Image(data.astype(np.float32), reference_img.affine, header)
    nib.save(image, str(output_path))


def _save_mask_nifti(data: np.ndarray, reference_img: nib.Nifti1Image, output_path: Path) -> None:
    header = reference_img.header.copy()
    header.set_data_dtype(np.uint8)
    image = nib.Nifti1Image(data.astype(np.uint8), reference_img.affine, header)
    nib.save(image, str(output_path))


def _sanitize_free_water_scalars(
    fwf: np.ndarray,
    tissue_fa: np.ndarray,
    tissue_md: np.ndarray,
    tissue_evals: np.ndarray,
    *,
    max_tissue_md: float = FREE_WATER_MAX_TISSUE_MD,
    max_free_water_fraction: float = FREE_WATER_MAX_FRACTION_FOR_TISSUE,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    """Return free-water maps and an explicit tissue-fit validity mask.

    Tissue FA and MD are unavailable when free water dominates the voxel or
    when DIPY's tensor decomposition reaches a non-positive boundary. The
    original FWF estimate remains available; unavailable tissue metrics are
    zeroed and accompanied by a machine-readable validity mask.
    """

    raw_fwf = np.asarray(fwf, dtype=np.float32)
    raw_fa = np.asarray(tissue_fa, dtype=np.float32)
    raw_md = np.asarray(tissue_md, dtype=np.float32)
    raw_evals = np.asarray(tissue_evals, dtype=np.float32)
    if raw_evals.shape != raw_fa.shape + (3,):
        raise ValueError(
            f"Expected tissue eigenvalues with shape {raw_fa.shape + (3,)}, got {raw_evals.shape}."
        )
    valid_tissue = (
        np.isfinite(raw_fwf)
        & (raw_fwf >= 0.0)
        & (raw_fwf <= float(max_free_water_fraction))
        & np.isfinite(raw_fa)
        & np.isfinite(raw_md)
        & np.all(np.isfinite(raw_evals), axis=-1)
        & np.all(raw_evals > 0.0, axis=-1)
        & (raw_fa >= 0.0)
        & (raw_fa <= 1.0)
        & (raw_md >= 0.0)
        & (raw_md <= float(max_tissue_md))
    )
    invalid_count = int(np.count_nonzero(~valid_tissue))
    clean_fwf = np.clip(
        np.nan_to_num(raw_fwf, nan=0.0, posinf=1.0, neginf=0.0),
        0.0,
        1.0,
    ).astype(np.float32, copy=False)
    clean_fa = np.where(valid_tissue, raw_fa, 0.0).astype(np.float32, copy=False)
    clean_md = np.where(valid_tissue, raw_md, 0.0).astype(np.float32, copy=False)
    return clean_fwf, clean_fa, clean_md, valid_tissue, invalid_count


def _write_free_water_qc(config: MicrostructureConfig, paths: dict[str, Path]) -> dict[str, object]:
    """Validate saved Free Water maps and persist a reusable scientific QC record."""

    _ensure_base_imports_ready()
    mask_image = nib.load(str(config.raw_input_bundle.mask_path))
    mask = np.asarray(mask_image.dataobj) > 0
    images = {
        "fwf": nib.load(str(paths["fwf"])),
        "fw_tissue_fa": nib.load(str(paths["fw_tissue_fa"])),
        "fw_tissue_md": nib.load(str(paths["fw_tissue_md"])),
        "valid_mask": nib.load(str(paths["fw_tissue_valid_mask"])),
    }
    arrays = {key: np.asarray(image.dataobj, dtype=np.float64) for key, image in images.items()}
    valid = arrays["valid_mask"] > 0.0
    brain_voxels = int(np.count_nonzero(mask))
    valid_voxels = int(np.count_nonzero(valid))
    checks = {
        "shape_matches_mask": all(array.shape == mask.shape for array in arrays.values()),
        "affine_matches_mask": all(
            bool(np.allclose(image.affine, mask_image.affine, atol=1e-4))
            for image in images.values()
        ),
        "all_values_finite": all(bool(np.isfinite(array).all()) for array in arrays.values()),
        "valid_mask_binary": bool(np.all(np.isin(arrays["valid_mask"], (0.0, 1.0)))),
        "valid_mask_within_brain": bool(np.all(~valid | mask)),
        "fwf_in_range": bool(
            np.all((arrays["fwf"][mask] >= 0.0) & (arrays["fwf"][mask] <= 1.0))
        ),
        "tissue_fa_in_range": bool(
            np.all((arrays["fw_tissue_fa"][valid] >= 0.0) & (arrays["fw_tissue_fa"][valid] <= 1.0))
        ),
        "tissue_md_in_range": bool(
            np.all(
                (arrays["fw_tissue_md"][valid] >= 0.0)
                & (arrays["fw_tissue_md"][valid] <= FREE_WATER_MAX_TISSUE_MD)
            )
        ),
        "invalid_tissue_metrics_zero": bool(
            np.allclose(arrays["fw_tissue_fa"][~valid], 0.0, atol=1e-7)
            and np.allclose(arrays["fw_tissue_md"][~valid], 0.0, atol=1e-9)
        ),
        "maps_zero_outside_brain": bool(
            all(np.allclose(array[~mask], 0.0, atol=1e-7) for array in arrays.values())
        ),
        "nonempty_valid_tissue": valid_voxels > 0,
    }
    payload: dict[str, object] = {
        "kind": "freewater_qc",
        "version": 1,
        "status": "completed" if all(checks.values()) else "failed",
        "subject_id": config.subject_id,
        "model": "DIPY FreeWaterTensorModel",
        "input": {
            "dwi": str(config.raw_input_bundle.dwi_path.resolve()),
            "bval": str(config.raw_input_bundle.bval_path.resolve()),
            "bvec": str(config.raw_input_bundle.bvec_path.resolve()),
            "mask": str(config.raw_input_bundle.mask_path.resolve()),
        },
        "public_maps": {
            "fwf": str(paths["fwf"].resolve()),
            "tissue_fa": str(paths["fw_tissue_fa"].resolve()),
            "tissue_md": str(paths["fw_tissue_md"].resolve()),
            "tissue_valid_mask": str(paths["fw_tissue_valid_mask"].resolve()),
        },
        "parameters": {
            "max_free_water_fraction_for_tissue": float(config.free_water_max_fraction_for_tissue),
            "max_tissue_md_mm2_s": FREE_WATER_MAX_TISSUE_MD,
        },
        "checks": checks,
        "validity": {
            "brain_mask_voxels": brain_voxels,
            "valid_tissue_voxels": valid_voxels,
            "valid_tissue_fraction": float(valid_voxels / max(1, brain_voxels)),
            "excluded_tissue_voxels": int(np.count_nonzero(mask & ~valid)),
        },
        "summary": {
            "fwf_brain_mask": _scalar_summary(arrays["fwf"], mask),
            "tissue_fa_valid": _scalar_summary(arrays["fw_tissue_fa"], valid),
            "tissue_md_valid": _scalar_summary(arrays["fw_tissue_md"], valid),
        },
        "warnings": [
            "Tissue FA and MD are interpreted only where the tissue-validity mask is non-zero."
        ],
    }
    _write_json(paths["free_water_qc"], payload)
    if payload["status"] != "completed":
        failed = ", ".join(name for name, passed in checks.items() if not passed)
        raise RuntimeError(f"Free Water outputs failed scientific QC: {failed}")
    return payload


def _compute_free_water_maps(
    *,
    config: MicrostructureConfig,
    paths: dict[str, Path],
    log: Optional[Callable[[str], None]] = None,
) -> None:
    raw = config.raw_input_bundle
    fit_method = config.free_water_fit_method.upper()
    chunk_size = max(1, int(config.free_water_chunk_size))
    engine = (config.free_water_engine or "serial").lower()
    n_jobs = config.free_water_n_jobs
    vox_per_chunk = config.free_water_vox_per_chunk
    progress_path = paths["free_water_progress"]
    started = time.monotonic()

    bvals, bvecs = _load_bvals_bvecs(raw)
    gtab = gradient_table(bvals, bvecs=bvecs, b0_threshold=50)
    fw_model = FreeWaterTensorModel(gtab, fit_method=fit_method)

    rounded_shells = np.unique(np.round(bvals / 100.0) * 100.0).astype(int).tolist()
    _emit(
        f"[Microstructure] Free Water model: fit={fit_method}, chunk_size={chunk_size}, "
        f"engine={engine}, n_jobs={n_jobs}, vox_per_chunk={vox_per_chunk}, shells={rounded_shells}",
        log,
    )

    dwi_img = nib.load(str(raw.dwi_path))
    mask_img = nib.load(str(raw.mask_path))
    mask = mask_img.get_fdata(dtype=np.float32) > 0

    if dwi_img.shape[:3] != mask.shape:
        raise ValueError(
            f"DWI shape {dwi_img.shape[:3]} does not match mask shape {mask.shape}."
        )

    fwf_map = np.zeros(mask.shape, dtype=np.float32)
    fw_tissue_fa_map = np.zeros(mask.shape, dtype=np.float32)
    fw_tissue_md_map = np.zeros(mask.shape, dtype=np.float32)
    fw_tissue_valid_mask = np.zeros(mask.shape, dtype=bool)

    z_size = mask.shape[2]
    chunk_count = (z_size + chunk_size - 1) // chunk_size
    gradient_count = dwi_img.shape[3]
    total_voxels = int(mask.sum())
    completed_chunks = 0
    completed_voxels = 0
    invalid_tissue_voxels = 0

    progress_base: dict[str, object] = {
        "kind": "microstructure_stage_progress",
        "version": 1,
        "subject_id": config.subject_id,
        "stage": "freewater",
        "status": "running",
        "fit_method": fit_method,
        "chunk_size": chunk_size,
        "engine": engine,
        "n_jobs": n_jobs,
        "vox_per_chunk": vox_per_chunk,
        "chunk_count": chunk_count,
        "total_voxels": total_voxels,
        "gradient_count": int(gradient_count),
        "shells": rounded_shells,
        "max_free_water_fraction_for_tissue": float(config.free_water_max_fraction_for_tissue),
    }
    _write_progress(
        progress_path,
        {
            **progress_base,
            "completed_chunks": completed_chunks,
            "completed_voxels": completed_voxels,
            "current_chunk": None,
            "elapsed_seconds": 0.0,
        },
    )

    for chunk_index, z_start in enumerate(range(0, z_size, chunk_size), start=1):
        z_stop = min(z_size, z_start + chunk_size)
        mask_chunk = mask[:, :, z_start:z_stop]
        voxel_count = int(mask_chunk.sum())
        if voxel_count == 0:
            completed_chunks += 1
            _write_progress(
                progress_path,
                {
                    **progress_base,
                    "completed_chunks": completed_chunks,
                    "completed_voxels": completed_voxels,
                    "current_chunk": chunk_index,
                    "z_start": z_start,
                    "z_stop": z_stop,
                    "voxel_count": voxel_count,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                },
            )
            continue

        _emit(
            f"[Microstructure] Free Water chunk {chunk_index}/{chunk_count}: z={z_start}:{z_stop}, voxels={voxel_count}",
            log,
        )
        _write_progress(
            progress_path,
            {
                **progress_base,
                "completed_chunks": completed_chunks,
                "completed_voxels": completed_voxels,
                "current_chunk": chunk_index,
                "z_start": z_start,
                "z_stop": z_stop,
                "voxel_count": voxel_count,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
        )

        data_chunk = np.asarray(dwi_img.dataobj[:, :, z_start:z_stop, :], dtype=np.float32)
        voxel_signals = data_chunk.reshape(-1, gradient_count)[mask_chunk.reshape(-1)]
        fit_kwargs: dict[str, object] = {"engine": engine}
        if n_jobs is not None:
            fit_kwargs["n_jobs"] = int(n_jobs)
        if vox_per_chunk is not None:
            fit_kwargs["vox_per_chunk"] = int(vox_per_chunk)
        fit = fw_model.fit(voxel_signals, **fit_kwargs)

        fwf, fw_fa, fw_md, valid_tissue, invalid_count = _sanitize_free_water_scalars(
            fit.f,
            fit.fa,
            fit.md,
            fit.evals,
            max_free_water_fraction=config.free_water_max_fraction_for_tissue,
        )
        invalid_tissue_voxels += invalid_count

        fwf_chunk = np.zeros(mask_chunk.shape, dtype=np.float32)
        fw_fa_chunk = np.zeros(mask_chunk.shape, dtype=np.float32)
        fw_md_chunk = np.zeros(mask_chunk.shape, dtype=np.float32)
        valid_chunk = np.zeros(mask_chunk.shape, dtype=bool)

        flat_mask = mask_chunk.reshape(-1)
        fwf_chunk.reshape(-1)[flat_mask] = fwf
        fw_fa_chunk.reshape(-1)[flat_mask] = fw_fa
        fw_md_chunk.reshape(-1)[flat_mask] = fw_md
        valid_chunk.reshape(-1)[flat_mask] = valid_tissue

        fwf_map[:, :, z_start:z_stop] = fwf_chunk
        fw_tissue_fa_map[:, :, z_start:z_stop] = fw_fa_chunk
        fw_tissue_md_map[:, :, z_start:z_stop] = fw_md_chunk
        fw_tissue_valid_mask[:, :, z_start:z_stop] = valid_chunk
        completed_chunks += 1
        completed_voxels += voxel_count
        _write_progress(
            progress_path,
            {
                **progress_base,
                "completed_chunks": completed_chunks,
                "completed_voxels": completed_voxels,
                "current_chunk": chunk_index,
                "z_start": z_start,
                "z_stop": z_stop,
                "voxel_count": voxel_count,
                "invalid_tissue_voxels": invalid_tissue_voxels,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
        )

    _save_scalar_nifti(fwf_map, mask_img, paths["fwf"])
    _save_scalar_nifti(fw_tissue_fa_map, mask_img, paths["fw_tissue_fa"])
    _save_scalar_nifti(fw_tissue_md_map, mask_img, paths["fw_tissue_md"])
    _save_mask_nifti(fw_tissue_valid_mask, mask_img, paths["fw_tissue_valid_mask"])
    _write_free_water_qc(config, paths)
    _write_progress(
        progress_path,
        {
            **progress_base,
            "status": "completed",
            "completed_chunks": completed_chunks,
            "completed_voxels": completed_voxels,
            "invalid_tissue_voxels": invalid_tissue_voxels,
            "max_tissue_md_mm2_s": FREE_WATER_MAX_TISSUE_MD,
            "max_free_water_fraction_for_tissue": float(config.free_water_max_fraction_for_tissue),
            "current_chunk": None,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "outputs": {
                "fwf": paths["fwf"].as_posix(),
                "fw_tissue_fa": paths["fw_tissue_fa"].as_posix(),
                "fw_tissue_md": paths["fw_tissue_md"].as_posix(),
                "fw_tissue_valid_mask": paths["fw_tissue_valid_mask"].as_posix(),
            },
        },
    )


def _amico_cache_root(config: MicrostructureConfig) -> Path:
    return config.raw_input_bundle.subject_root / "cache" / "microstructure" / "amico"


def _amico_subject_dir(config: MicrostructureConfig) -> Path:
    return _amico_cache_root(config) / config.subject_id


def _amico_output_dir(config: MicrostructureConfig) -> Path:
    return config.output_dir / "noddi" / "_amico_noddi"


def _prepare_amico_inputs(
    *,
    config: MicrostructureConfig,
    log: Optional[Callable[[str], None]] = None,
) -> tuple[Path, Path, Path, Path, Path]:
    if fsl2scheme is None:
        raise RuntimeError("AMICO is unavailable; cannot prepare NODDI inputs.")

    study_dir = _amico_subject_dir(config)
    study_dir.mkdir(parents=True, exist_ok=True)

    raw = config.raw_input_bundle
    dwi_path = study_dir / raw.dwi_path.name
    bval_path = study_dir / raw.bval_path.name
    bvec_path = study_dir / raw.bvec_path.name
    mask_path = study_dir / raw.mask_path.name
    scheme_path = study_dir / "DWI.scheme"

    _link_or_copy(raw.dwi_path, dwi_path)
    _link_or_copy(raw.bval_path, bval_path)
    _link_or_copy(raw.bvec_path, bvec_path)
    _link_or_copy(raw.mask_path, mask_path)
    fsl2scheme(str(bval_path), str(bvec_path), schemeFilename=str(scheme_path))

    _emit(
        f"[Microstructure] AMICO study cache prepared at {study_dir}",
        log,
    )
    return study_dir, dwi_path, mask_path, bval_path, scheme_path


def _sanitize_noddi_maps(
    ndi: np.ndarray,
    odi: np.ndarray,
    isovf: np.ndarray,
    brain_mask: np.ndarray,
    *,
    max_isotropic_fraction: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    """Sanitize public NODDI maps and derive a separate tissue-validity mask.

    AMICO preserves its raw estimates in ``_amico_noddi``. The public NDI/ODI
    maps retain finite, bounded estimates throughout the brain mask so that
    display does not create artificial holes. Quantitative summaries use the
    separate tissue-validity mask because conditional tissue fractions are not
    interpreted in voxels dominated by the isotropic component.
    """
    raw_ndi = np.asarray(ndi, dtype=np.float32)
    raw_odi = np.asarray(odi, dtype=np.float32)
    raw_isovf = np.asarray(isovf, dtype=np.float32)
    mask = np.asarray(brain_mask, dtype=bool)
    if not (raw_ndi.shape == raw_odi.shape == raw_isovf.shape == mask.shape):
        raise ValueError("NODDI maps and brain mask must have identical shapes.")

    finite_and_bounded = (
        np.isfinite(raw_ndi)
        & np.isfinite(raw_odi)
        & np.isfinite(raw_isovf)
        & (raw_ndi >= 0.0)
        & (raw_ndi <= 1.0)
        & (raw_odi >= 0.0)
        & (raw_odi <= 1.0)
        & (raw_isovf >= 0.0)
        & (raw_isovf <= 1.0)
    )
    high_isotropic = raw_isovf > float(max_isotropic_fraction)
    valid_tissue = mask & finite_and_bounded & ~high_isotropic
    valid_brain_estimate = mask & finite_and_bounded
    clean_ndi = np.where(valid_brain_estimate, raw_ndi, 0.0).astype(np.float32, copy=False)
    clean_odi = np.where(valid_brain_estimate, raw_odi, 0.0).astype(np.float32, copy=False)
    clean_isovf = np.where(
        mask,
        np.clip(np.nan_to_num(raw_isovf, nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0),
        0.0,
    ).astype(np.float32, copy=False)
    valid_count = int(np.count_nonzero(valid_tissue))
    valid_ndi = raw_ndi[valid_tissue]
    qc = {
        "brain_mask_voxels": int(np.count_nonzero(mask)),
        "valid_tissue_voxels": valid_count,
        "valid_tissue_fraction": float(valid_count / max(1, int(np.count_nonzero(mask)))),
        "excluded_high_isotropic_voxels": int(np.count_nonzero(mask & high_isotropic)),
        "excluded_nonfinite_or_out_of_range_voxels": int(np.count_nonzero(mask & ~finite_and_bounded)),
        "max_isotropic_fraction_for_tissue": float(max_isotropic_fraction),
        "ndi_upper_boundary_voxels_in_valid_tissue": int(
            np.count_nonzero(valid_ndi >= NODDI_UPPER_BOUND)
        ),
        "ndi_upper_boundary_fraction_in_valid_tissue": float(
            np.count_nonzero(valid_ndi >= NODDI_UPPER_BOUND) / max(1, valid_ndi.size)
        ),
    }
    return clean_ndi, clean_odi, clean_isovf, valid_tissue, qc


def _scalar_summary(data: np.ndarray, mask: np.ndarray) -> dict[str, float | int]:
    values = np.asarray(data, dtype=np.float32)[np.asarray(mask, dtype=bool)]
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"count": 0, "min": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    return {
        "count": int(values.size),
        "min": float(np.min(values)),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "max": float(np.max(values)),
    }


def _compute_noddi_maps(
    *,
    config: MicrostructureConfig,
    paths: dict[str, Path],
    log: Optional[Callable[[str], None]] = None,
) -> None:
    if amico is None:
        raise RuntimeError("AMICO is required for NODDI modeling.")
    progress_path = paths["noddi_progress"]
    started = time.monotonic()

    def write_noddi_progress(status: str, step: str, **extra: object) -> None:
        _write_progress(
            progress_path,
            {
                "kind": "microstructure_stage_progress",
                "version": 1,
                "subject_id": config.subject_id,
                "stage": "noddi",
                "status": status,
                "current_step": step,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "directional_average": bool(config.noddi_directional_average),
                "b0_threshold": int(config.noddi_b0_threshold),
                "lmax": int(config.noddi_lmax),
                "ndirs": int(config.noddi_ndirs),
                "nthreads": int(config.noddi_nthreads),
                **extra,
            },
        )

    write_noddi_progress("running", "checking_shells")

    bvals, _ = _load_bvals_bvecs(config.raw_input_bundle)
    nonzero_shells = sorted(
        {
            int(shell)
            for shell in np.unique(np.round(bvals / 100.0) * 100.0)
            if int(shell) > int(config.noddi_b0_threshold)
        }
    )
    if len(nonzero_shells) < 2:
        raise ValueError(
            "NODDI requires multi-shell diffusion data with at least two non-zero shells."
        )

    write_noddi_progress("running", "preparing_amico_inputs", nonzero_shells=nonzero_shells)
    study_dir, dwi_path, mask_path, _, scheme_path = _prepare_amico_inputs(config=config, log=log)
    amico_output_dir = _amico_output_dir(config)
    amico_output_dir.mkdir(parents=True, exist_ok=True)

    _emit(
        "[Microstructure] AMICO NODDI: "
        f"directional_average={config.noddi_directional_average}, "
        f"b0_thr={config.noddi_b0_threshold}, "
        f"shells={nonzero_shells}",
        log,
    )
    amico.set_verbose(2)
    write_noddi_progress(
        "running",
        "loading_data",
        nonzero_shells=nonzero_shells,
        study_dir=study_dir.as_posix(),
        amico_output_dir=amico_output_dir.as_posix(),
    )
    evaluation = amico.Evaluation(
        study_path=str(_amico_cache_root(config)),
        subject=config.subject_id,
        output_path=str(amico_output_dir),
    )
    evaluation.set_config("doDirectionalAverage", bool(config.noddi_directional_average))
    evaluation.set_config("doSaveModulatedMaps", False)
    evaluation.set_config("doComputeRMSE", True)
    evaluation.set_config("doComputeNRMSE", True)
    evaluation.set_config("nthreads", int(config.noddi_nthreads))
    evaluation.set_config("BLAS_nthreads", 1)
    evaluation.load_data(
        dwi_filename=dwi_path.name,
        scheme_filename=scheme_path.name,
        mask_filename=mask_path.name,
        b0_thr=int(config.noddi_b0_threshold),
    )
    evaluation.set_model("NODDI")
    evaluation.set_solver(
        lambda1=float(config.noddi_solver_lambda1),
        lambda2=float(config.noddi_solver_lambda2),
    )
    write_noddi_progress("running", "generating_kernels", nonzero_shells=nonzero_shells)
    try:
        evaluation.generate_kernels(
            regenerate=False,
            lmax=int(config.noddi_lmax),
            ndirs=int(config.noddi_ndirs),
        )
    except Exception as exc:
        message = str(exc)
        if "Auxiliary matrices not found" not in message and "amico.setup()" not in message:
            raise
        _emit("[Microstructure] AMICO kernels missing; running amico.setup() once and retrying.", log)
        amico.setup(lmax=int(config.noddi_lmax))
        evaluation.generate_kernels(
            regenerate=False,
            lmax=int(config.noddi_lmax),
            ndirs=int(config.noddi_ndirs),
        )
    write_noddi_progress("running", "loading_kernels", nonzero_shells=nonzero_shells)
    evaluation.load_kernels()
    write_noddi_progress("running", "fitting_model", nonzero_shells=nonzero_shells)
    evaluation.fit()
    write_noddi_progress("running", "saving_results", nonzero_shells=nonzero_shells)
    evaluation.save_results()

    source_dir = amico_output_dir
    noddi_sources = {
        "noddi_ndi": source_dir / "fit_NDI.nii.gz",
        "noddi_odi": source_dir / "fit_ODI.nii.gz",
        "noddi_fwf": source_dir / "fit_FWF.nii.gz",
        "noddi_rmse": source_dir / "fit_RMSE.nii.gz",
        "noddi_nrmse": source_dir / "fit_NRMSE.nii.gz",
    }
    for key, src in noddi_sources.items():
        if not src.is_file():
            raise FileNotFoundError(f"AMICO did not produce expected NODDI map: {src}")

    mask_img = nib.load(str(config.raw_input_bundle.mask_path))
    mask = mask_img.get_fdata(dtype=np.float32) > 0.0
    source_images = {key: nib.load(str(src)) for key, src in noddi_sources.items()}
    source_arrays = {
        key: image.get_fdata(dtype=np.float32)
        for key, image in source_images.items()
    }
    for key, image in source_images.items():
        if image.shape != mask.shape or not np.allclose(image.affine, mask_img.affine, atol=1e-4):
            raise ValueError(f"AMICO {key} output does not match the NODDI input mask grid.")
    clean_ndi, clean_odi, clean_isovf, valid_tissue, validity_qc = _sanitize_noddi_maps(
        source_arrays["noddi_ndi"],
        source_arrays["noddi_odi"],
        source_arrays["noddi_fwf"],
        mask,
        max_isotropic_fraction=config.noddi_max_isotropic_fraction_for_tissue,
    )
    _save_scalar_nifti(clean_ndi, mask_img, paths["noddi_ndi"])
    _save_scalar_nifti(clean_odi, mask_img, paths["noddi_odi"])
    _save_scalar_nifti(clean_isovf, mask_img, paths["noddi_fwf"])
    _save_mask_nifti(valid_tissue, mask_img, paths["noddi_tissue_valid_mask"])
    shutil.copy2(noddi_sources["noddi_rmse"], paths["noddi_rmse"])
    shutil.copy2(noddi_sources["noddi_nrmse"], paths["noddi_nrmse"])
    qc_payload = {
        "kind": "noddi_qc",
        "version": 1,
        "status": "completed",
        "subject_id": config.subject_id,
        "model": "AMICO NODDI",
        "input": {
            "dwi": str(config.raw_input_bundle.dwi_path.resolve()),
            "bval": str(config.raw_input_bundle.bval_path.resolve()),
            "bvec": str(config.raw_input_bundle.bvec_path.resolve()),
            "mask": str(config.raw_input_bundle.mask_path.resolve()),
        },
        "source_maps": {key: str(path.resolve()) for key, path in noddi_sources.items()},
        "public_maps": {
            "ndi": str(paths["noddi_ndi"].resolve()),
            "odi": str(paths["noddi_odi"].resolve()),
            "isovf": str(paths["noddi_fwf"].resolve()),
            "tissue_valid_mask": str(paths["noddi_tissue_valid_mask"].resolve()),
            "rmse": str(paths["noddi_rmse"].resolve()),
            "nrmse": str(paths["noddi_nrmse"].resolve()),
        },
        "validity": validity_qc,
        "summary": {
            "ndi_valid_tissue": _scalar_summary(source_arrays["noddi_ndi"], valid_tissue),
            "odi_valid_tissue": _scalar_summary(source_arrays["noddi_odi"], valid_tissue),
            "isovf_brain_mask": _scalar_summary(source_arrays["noddi_fwf"], mask),
            "rmse_valid_tissue": _scalar_summary(source_arrays["noddi_rmse"], valid_tissue),
            "nrmse_valid_tissue": _scalar_summary(source_arrays["noddi_nrmse"], valid_tissue),
        },
        "warnings": [
            "NDI and ODI are displayed within the brain mask; quantitative summaries additionally exclude voxels where NODDI IsoVF exceeds the tissue-validity threshold."
        ],
    }
    _write_json(paths["noddi_qc"], qc_payload)
    write_noddi_progress(
        "completed",
        "completed",
        nonzero_shells=nonzero_shells,
        outputs={
            "noddi_ndi": paths["noddi_ndi"].as_posix(),
            "noddi_odi": paths["noddi_odi"].as_posix(),
            "noddi_fwf": paths["noddi_fwf"].as_posix(),
            "noddi_tissue_valid_mask": paths["noddi_tissue_valid_mask"].as_posix(),
            "noddi_rmse": paths["noddi_rmse"].as_posix(),
            "noddi_nrmse": paths["noddi_nrmse"].as_posix(),
            "noddi_qc": paths["noddi_qc"].as_posix(),
        },
    )


def _compute_roi_stats(
    *,
    metric_paths: dict[str, Path],
    roi_label_map: Path,
    lut_path: Path | None,
    csv_path: Path,
    json_path: Path,
    validity_masks: dict[str, np.ndarray] | None = None,
) -> int:
    roi_img = nib.load(str(roi_label_map))
    roi_data = roi_img.get_fdata(dtype=np.float32)
    metric_arrays: dict[str, np.ndarray] = {}
    metric_fieldnames: list[str] = []

    for metric_key, metric_path in metric_paths.items():
        metric_img = nib.load(str(metric_path))
        metric_data = metric_img.get_fdata(dtype=np.float32)
        if metric_data.shape != roi_data.shape:
            raise ValueError(
                f"ROI label map shape {roi_data.shape} does not match {metric_key} shape {metric_data.shape}."
            )
        if not np.allclose(metric_img.affine, roi_img.affine, atol=1e-4):
            raise ValueError(f"ROI label map affine does not match the {metric_key} image affine.")
        metric_arrays[metric_key] = metric_data
        metric_fieldnames.extend(
            [
                f"{metric_key}_mean",
                f"{metric_key}_std",
                f"{metric_key}_min",
                f"{metric_key}_max",
            ]
        )

    metric_validity_masks: dict[str, np.ndarray] = dict(validity_masks or {})
    for metric_key, valid_mask in metric_validity_masks.items():
        if metric_key not in metric_arrays:
            raise ValueError(f"Validity mask supplied for unknown metric: {metric_key}.")
        if np.asarray(valid_mask).shape != roi_data.shape:
            raise ValueError(f"Validity mask shape does not match ROI label map for {metric_key}.")
        metric_validity_masks[metric_key] = np.asarray(valid_mask, dtype=bool)
    if {"fw_tissue_fa", "fw_tissue_md"}.issubset(metric_arrays):
        tissue_fa = metric_arrays["fw_tissue_fa"]
        tissue_md = metric_arrays["fw_tissue_md"]
        valid_tissue_pair = np.isfinite(tissue_fa) & np.isfinite(tissue_md) & (
            (tissue_fa != 0.0) | (tissue_md != 0.0)
        )
        metric_validity_masks["fw_tissue_fa"] = valid_tissue_pair
        metric_validity_masks["fw_tissue_md"] = valid_tissue_pair

    rounded_roi = np.rint(roi_data)
    non_integer_mask = np.logical_and(roi_data > 0, np.abs(roi_data - rounded_roi) > 1e-3)
    if np.any(non_integer_mask):
        raise ValueError("ROI label map must contain discrete integer labels.")

    roi_labels = rounded_roi.astype(np.int64)
    unique_labels = sorted(int(label) for label in np.unique(roi_labels) if int(label) > 0)
    label_names = _parse_label_names(unique_labels, lut_path)

    rows: list[dict[str, object]] = []
    for label in unique_labels:
        row: dict[str, object] = {
            "label_id": label,
            "label_name": label_names.get(label, ""),
        }
        label_mask = roi_labels == label
        voxel_count: int | None = None

        for metric_key, metric_data in metric_arrays.items():
            metric_valid_mask = np.logical_and(label_mask, np.isfinite(metric_data))
            if metric_key in metric_validity_masks:
                metric_valid_mask = np.logical_and(metric_valid_mask, metric_validity_masks[metric_key])
            voxels = metric_data[metric_valid_mask]
            if voxels.size == 0:
                voxel_count = 0 if voxel_count is None else voxel_count
                for suffix in ("mean", "std", "min", "max"):
                    row[f"{metric_key}_{suffix}"] = 0.0
                continue
            if voxel_count is None:
                voxel_count = int(voxels.size)
            row[f"{metric_key}_mean"] = float(np.mean(voxels))
            row[f"{metric_key}_std"] = float(np.std(voxels))
            row[f"{metric_key}_min"] = float(np.min(voxels))
            row[f"{metric_key}_max"] = float(np.max(voxels))

        if not voxel_count:
            continue
        row["voxel_count"] = int(voxel_count)
        rows.append(row)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["label_id", "label_name", "voxel_count", *metric_fieldnames],
        )
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "subject_id": next(iter(metric_paths.values())).name.split("_")[0],
        "roi_label_map": str(roi_label_map.resolve()),
        "lut_path": str(lut_path.resolve()) if lut_path is not None else None,
        "feature_maps": {metric_key: str(metric_path.resolve()) for metric_key, metric_path in metric_paths.items()},
        "roi_count": len(rows),
        "rows": rows,
    }
    _write_json(json_path, payload)
    return len(rows)


def run_microstructure(
    config: MicrostructureConfig,
    log: Optional[Callable[[str], None]] = None,
) -> MicrostructureResult:
    """Export native DTI maps, Free Water maps, and ROI-wise statistics."""

    subject_id = config.subject_id.strip()
    if not subject_id:
        raise ValueError("Subject ID must be provided.")
    if subject_id != config.raw_input_bundle.subject_id:
        raise ValueError("Subject ID does not match the provided raw input bundle.")
    if subject_id != config.native_bundle.subject_id:
        raise ValueError("Subject ID does not match the provided native DTI bundle.")
    if config.raw_input_bundle.subject_root != config.native_bundle.subject_root:
        raise ValueError("Raw input bundle and native DTI bundle must belong to the same subject root.")
    if config.free_water_chunk_size <= 0:
        raise ValueError("free_water_chunk_size must be > 0.")
    if (config.free_water_engine or "serial").lower() not in FREE_WATER_ENGINES:
        raise ValueError("free_water_engine must be one of: serial, joblib, dask, ray.")
    if config.free_water_vox_per_chunk is not None and config.free_water_vox_per_chunk <= 0:
        raise ValueError("free_water_vox_per_chunk must be > 0 when provided.")
    if not 0.0 < float(config.free_water_max_fraction_for_tissue) < 1.0:
        raise ValueError("free_water_max_fraction_for_tissue must be between 0 and 1.")
    if not 0.0 < float(config.noddi_max_isotropic_fraction_for_tissue) < 1.0:
        raise ValueError("noddi_max_isotropic_fraction_for_tissue must be between 0 and 1.")
    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = _output_paths(subject_id, output_dir)
    expected_free_water_manifest = _expected_free_water_manifest(config)
    if (
        bool(config.run_free_water)
        and _read_json(paths["free_water_manifest"]) == expected_free_water_manifest
        and _free_water_maps_complete(paths)
        and not _free_water_outputs_complete(paths)
    ):
        _emit("[Microstructure] Backfilling scientific QC for reusable Free Water outputs", log)
        _write_free_water_qc(config, paths)
    roi_label_map = _resolve_roi_label_map(config)
    free_water_available = bool(config.run_free_water) or _free_water_outputs_current(config, paths)
    noddi_available = bool(config.run_noddi) or _noddi_outputs_current(config, paths)
    expected_manifest = _expected_manifest(
        config,
        roi_label_map,
        free_water_available=free_water_available,
        noddi_available=noddi_available,
    )
    actual_manifest = _read_json(paths["manifest"])
    roi_enabled = roi_label_map is not None
    force_recompute = bool(config.force_recompute)

    if (
        not force_recompute
        and actual_manifest == expected_manifest
        and _outputs_complete(
            paths,
            roi_enabled=roi_enabled,
            free_water_enabled=bool(config.run_free_water),
            noddi_enabled=bool(config.run_noddi),
        )
    ):
        _emit(f"[Microstructure] Reusing outputs in {output_dir}", log)
        return MicrostructureResult(
            subject_id=subject_id,
            output_dir=output_dir,
            fa_path=paths["fa"],
            md_path=paths["md"],
            ad_path=paths["ad"],
            rd_path=paths["rd"],
            l1_path=paths["l1"],
            l2_path=paths["l2"],
            l3_path=paths["l3"],
            trace_path=paths["trace"],
            fwf_path=paths["fwf"],
            fw_tissue_fa_path=paths["fw_tissue_fa"],
            fw_tissue_md_path=paths["fw_tissue_md"],
            fw_tissue_valid_mask_path=paths["fw_tissue_valid_mask"],
            free_water_qc_path=paths["free_water_qc"],
            noddi_ndi_path=paths["noddi_ndi"],
            noddi_odi_path=paths["noddi_odi"],
            noddi_fwf_path=paths["noddi_fwf"],
            noddi_tissue_valid_mask_path=paths["noddi_tissue_valid_mask"],
            noddi_rmse_path=paths["noddi_rmse"],
            noddi_nrmse_path=paths["noddi_nrmse"],
            noddi_qc_path=paths["noddi_qc"],
            roi_label_map=roi_label_map,
            roi_stats_csv_path=paths["roi_stats_csv"] if roi_enabled else None,
            roi_stats_json_path=paths["roi_stats_json"] if roi_enabled else None,
        )

    _emit(
        f"[Microstructure] Exporting DTI scalar maps from native DTI bundle ({config.native_bundle.fit_method})",
        log,
    )
    _export_dti_scalar_maps(config, paths)
    _remove_legacy_roi_outputs(output_dir, subject_id)

    actual_free_water_manifest = _read_json(paths["free_water_manifest"])
    if bool(config.run_free_water):
        if (
            not force_recompute
            and actual_free_water_manifest == expected_free_water_manifest
            and _free_water_outputs_complete(paths)
        ):
            _emit("[Microstructure] Reusing Free Water stage outputs", log)
        else:
            _ensure_base_imports_ready()
            _ensure_dipy_ready()
            _emit("[Microstructure] Running Free Water stage", log)
            try:
                _compute_free_water_maps(config=config, paths=paths, log=log)
            except Exception as exc:
                _write_progress(
                    paths["free_water_progress"],
                    {
                        "kind": "microstructure_stage_progress",
                        "version": 1,
                        "subject_id": subject_id,
                        "stage": "freewater",
                        "status": "failed",
                        "error": str(exc),
                    },
                )
                raise
            _write_json(paths["free_water_manifest"], expected_free_water_manifest)
    else:
        _emit("[Microstructure] Free Water stage disabled; DTI-only outputs will not include Free Water maps", log)

    expected_noddi_manifest = _expected_noddi_manifest(config)
    actual_noddi_manifest = _read_json(paths["noddi_manifest"])
    if bool(config.run_noddi):
        if (
            not force_recompute
            and actual_noddi_manifest == expected_noddi_manifest
            and _noddi_outputs_complete(paths)
        ):
            _emit("[Microstructure] Reusing NODDI stage outputs", log)
        else:
            _ensure_base_imports_ready()
            _ensure_amico_ready()
            _emit("[Microstructure] Running NODDI stage", log)
            try:
                _compute_noddi_maps(config=config, paths=paths, log=log)
            except Exception as exc:
                _write_progress(
                    paths["noddi_progress"],
                    {
                        "kind": "microstructure_stage_progress",
                        "version": 1,
                        "subject_id": subject_id,
                        "stage": "noddi",
                        "status": "failed",
                        "error": str(exc),
                    },
                )
                raise
            _write_json(paths["noddi_manifest"], expected_noddi_manifest)
    else:
        _emit("[Microstructure] NODDI stage disabled; DTI-only outputs will not include NODDI maps", log)

    if roi_label_map is not None:
        _ensure_base_imports_ready()
        lut_path = _resolve_lut_path(config)
        metric_paths = {
            "fa": paths["fa"],
            "md": paths["md"],
            "ad": paths["ad"],
            "rd": paths["rd"],
            "l1": paths["l1"],
            "l2": paths["l2"],
            "l3": paths["l3"],
            "trace": paths["trace"],
        }
        if _free_water_outputs_current(config, paths):
            metric_paths.update(
                {
                    "fwf": paths["fwf"],
                    "fw_tissue_fa": paths["fw_tissue_fa"],
                    "fw_tissue_md": paths["fw_tissue_md"],
                }
            )
        if _noddi_outputs_current(config, paths):
            metric_paths.update(
                {
                    "noddi_ndi": paths["noddi_ndi"],
                    "noddi_odi": paths["noddi_odi"],
                    "noddi_fwf": paths["noddi_fwf"],
                }
            )
        validity_masks: dict[str, np.ndarray] = {}
        if _noddi_outputs_current(config, paths):
            noddi_valid_mask = nib.load(str(paths["noddi_tissue_valid_mask"])).get_fdata(dtype=np.float32) > 0.0
            validity_masks = {
                "noddi_ndi": noddi_valid_mask,
                "noddi_odi": noddi_valid_mask,
            }
        _emit(f"[Microstructure] Computing ROI-wise statistics from {roi_label_map}", log)
        roi_count = _compute_roi_stats(
            metric_paths=metric_paths,
            roi_label_map=roi_label_map,
            lut_path=lut_path,
            csv_path=paths["roi_stats_csv"],
            json_path=paths["roi_stats_json"],
            validity_masks=validity_masks,
        )
        _emit(
            f"[Microstructure] ROI-wise statistics written for {roi_count} labels",
            log,
        )
    else:
        _emit(
            "[Microstructure] ROI label map not found. Wrote DTI, Free Water, and NODDI maps only and skipped ROI-wise statistics.",
            log,
        )
        paths["roi_stats_csv"].unlink(missing_ok=True)
        paths["roi_stats_json"].unlink(missing_ok=True)

    _write_json(paths["manifest"], expected_manifest)
    return MicrostructureResult(
        subject_id=subject_id,
        output_dir=output_dir,
        fa_path=paths["fa"],
        md_path=paths["md"],
        ad_path=paths["ad"],
        rd_path=paths["rd"],
        l1_path=paths["l1"],
        l2_path=paths["l2"],
        l3_path=paths["l3"],
        trace_path=paths["trace"],
        fwf_path=paths["fwf"],
        fw_tissue_fa_path=paths["fw_tissue_fa"],
        fw_tissue_md_path=paths["fw_tissue_md"],
        fw_tissue_valid_mask_path=paths["fw_tissue_valid_mask"],
        free_water_qc_path=paths["free_water_qc"],
        noddi_ndi_path=paths["noddi_ndi"],
        noddi_odi_path=paths["noddi_odi"],
        noddi_fwf_path=paths["noddi_fwf"],
        noddi_tissue_valid_mask_path=paths["noddi_tissue_valid_mask"],
        noddi_rmse_path=paths["noddi_rmse"],
        noddi_nrmse_path=paths["noddi_nrmse"],
        noddi_qc_path=paths["noddi_qc"],
        roi_label_map=roi_label_map,
        roi_stats_csv_path=paths["roi_stats_csv"] if roi_label_map is not None else None,
        roi_stats_json_path=paths["roi_stats_json"] if roi_label_map is not None else None,
    )
