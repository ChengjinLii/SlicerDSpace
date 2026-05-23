"""DTI tractography scaffold.

The current implementation prepares stable inputs, output names, manifests, and
QC placeholders without launching long tractography jobs. Actual streamline
generation will be enabled in a later phase after the backend and thresholds are
validated on test data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from shared import NativeDTIBundle, find_subject_root


SUPPORTED_TRACKING_METHODS = {"deterministic", "probabilistic"}
SUPPORTED_OUTPUT_FORMATS = {"trk", "tck"}


@dataclass(frozen=True)
class DTITrackingConfig:
    subject_id: str
    input_root: Path
    output_dir: Optional[Path] = None
    fit_method: str = "wls"
    tracking_method: str = "deterministic"
    output_format: str = "trk"
    step_size_mm: float = 0.5
    max_angle_deg: float = 30.0
    seed_density: int = 1
    min_fa: float = 0.2
    force_recompute: bool = False
    execute: bool = False


@dataclass(frozen=True)
class DTITrackingResult:
    subject_id: str
    output_dir: Path
    streamlines_path: Path
    manifest_path: Path
    qc_path: Path
    native_bundle_dir: Path
    native_cache_available: bool
    executed: bool


def _emit(message: str, log: Optional[Callable[[str], None]] = None) -> None:
    if log:
        log(message)


def _file_info(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": path.as_posix(), "exists": False}
    stat = path.stat()
    return {
        "path": path.resolve().as_posix(),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _native_bundle_from_expected_cache(subject_root: Path, subject_id: str, fit_method: str) -> NativeDTIBundle:
    fit_key = fit_method.lower()
    bundle_dir = subject_root / "cache" / "native_dti" / fit_key
    return NativeDTIBundle(
        subject_root=subject_root,
        subject_id=subject_id,
        fit_method=fit_key,
        bundle_dir=bundle_dir,
        dwi_nhdr_path=bundle_dir / "DWI.nhdr",
        mask_nhdr_path=bundle_dir / "Mask.nhdr",
        dti_nrrd_path=bundle_dir / "DTI.nrrd",
        b0_nrrd_path=bundle_dir / "b0.nrrd",
        fa_nrrd_path=bundle_dir / "DTI_FA.nrrd",
        trace_nrrd_path=bundle_dir / "DTI_Trace.nrrd",
        mean_diffusivity_nrrd_path=bundle_dir / "DTI_MeanDiffusivity.nrrd",
        min_eig_nrrd_path=bundle_dir / "DTI_MinEigenvalue.nrrd",
        mid_eig_nrrd_path=bundle_dir / "DTI_MidEigenvalue.nrrd",
        max_eig_nrrd_path=bundle_dir / "DTI_MaxEigenvalue.nrrd",
        ddseg_md_nrrd_path=bundle_dir / "DTI_MD.nrrd",
        ddseg_e1_nrrd_path=bundle_dir / "DTI_E1.nrrd",
        ddseg_e2_nrrd_path=bundle_dir / "DTI_E2.nrrd",
        ddseg_e3_nrrd_path=bundle_dir / "DTI_E3.nrrd",
        fa_nii_path=bundle_dir / f"{subject_id}-dti-FractionalAnisotropy.nii.gz",
        trace_nii_path=bundle_dir / f"{subject_id}-dti-Trace.nii.gz",
        mean_diffusivity_nii_path=bundle_dir / f"{subject_id}-dti-MeanDiffusivity.nii.gz",
        min_eig_nii_path=bundle_dir / f"{subject_id}-dti-MinEigenvalue.nii.gz",
        mid_eig_nii_path=bundle_dir / f"{subject_id}-dti-MidEigenvalue.nii.gz",
        max_eig_nii_path=bundle_dir / f"{subject_id}-dti-MaxEigenvalue.nii.gz",
        manifest_path=bundle_dir / "manifest.json",
    )


def _native_cache_available(bundle: NativeDTIBundle) -> bool:
    required = [
        bundle.manifest_path,
        bundle.dti_nrrd_path,
        bundle.fa_nii_path,
        bundle.mean_diffusivity_nii_path,
    ]
    return all(path.is_file() for path in required)


def _validate_config(config: DTITrackingConfig) -> None:
    if not config.subject_id.strip():
        raise ValueError("subject_id is required.")
    if config.fit_method.lower() not in {"ls", "wls"}:
        raise ValueError("fit_method must be 'ls' or 'wls'.")
    if config.tracking_method.lower() not in SUPPORTED_TRACKING_METHODS:
        raise ValueError(f"tracking_method must be one of {sorted(SUPPORTED_TRACKING_METHODS)}.")
    if config.output_format.lower() not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(f"output_format must be one of {sorted(SUPPORTED_OUTPUT_FORMATS)}.")
    if config.step_size_mm <= 0:
        raise ValueError("step_size_mm must be > 0.")
    if config.max_angle_deg <= 0:
        raise ValueError("max_angle_deg must be > 0.")
    if config.seed_density < 1:
        raise ValueError("seed_density must be >= 1.")
    if config.min_fa < 0:
        raise ValueError("min_fa must be >= 0.")


def run_dti_tracking(config: DTITrackingConfig, *, log: Optional[Callable[[str], None]] = None) -> DTITrackingResult:
    """Prepare DTI tractography outputs and manifests.

    ``execute=False`` records a reproducible plan and can run in normal Python.
    ``execute=True`` is reserved for the future DIPY backend and currently raises
    ``NotImplementedError`` after validating inputs.
    """

    _validate_config(config)
    raw = find_subject_root(config.input_root.expanduser().resolve(), config.subject_id)
    fit_method = config.fit_method.lower()
    tracking_method = config.tracking_method.lower()
    output_format = config.output_format.lower()
    output_dir = (
        config.output_dir.expanduser().resolve()
        if config.output_dir is not None
        else raw.subject_root / "outputs" / "tractography"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    native_bundle = _native_bundle_from_expected_cache(raw.subject_root, raw.subject_id, fit_method)
    native_available = _native_cache_available(native_bundle)
    stem = f"{raw.subject_id}-dti-{tracking_method}"
    streamlines_path = output_dir / f"{stem}.{output_format}"
    manifest_path = output_dir / f"{stem}_manifest.json"
    qc_path = output_dir / f"{stem}_qc.json"

    if config.execute:
        raise NotImplementedError(
            "DTI tractography execution is not enabled yet. Use execute=False to prepare a manifest scaffold."
        )

    manifest = {
        "kind": "dti_tracking",
        "version": 1,
        "subject_id": raw.subject_id,
        "backend": "dipy",
        "executed": False,
        "status": "planned",
        "parameters": {
            "fit_method": fit_method,
            "tracking_method": tracking_method,
            "output_format": output_format,
            "step_size_mm": config.step_size_mm,
            "max_angle_deg": config.max_angle_deg,
            "seed_density": config.seed_density,
            "min_fa": config.min_fa,
            "force_recompute": bool(config.force_recompute),
        },
        "raw_inputs": {
            "dwi": _file_info(raw.dwi_path),
            "bval": _file_info(raw.bval_path),
            "bvec": _file_info(raw.bvec_path),
            "mask": _file_info(raw.mask_path),
        },
        "native_dti_cache": {
            "available": native_available,
            "bundle_dir": native_bundle.bundle_dir.as_posix(),
            "manifest": _file_info(native_bundle.manifest_path),
            "dti_nrrd": _file_info(native_bundle.dti_nrrd_path),
            "fa": _file_info(native_bundle.fa_nii_path),
            "md": _file_info(native_bundle.mean_diffusivity_nii_path),
        },
        "outputs": {
            "streamlines": streamlines_path.as_posix(),
            "qc": qc_path.as_posix(),
        },
    }
    qc = {
        "subject_id": raw.subject_id,
        "status": "planned",
        "executed": False,
        "native_cache_available": native_available,
        "streamline_count": None,
        "length_mean_mm": None,
        "length_min_mm": None,
        "length_max_mm": None,
        "mask_coverage": None,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    qc_path.write_text(json.dumps(qc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _emit(f"[Tractography] Prepared DTI tracking scaffold: {manifest_path}", log)

    return DTITrackingResult(
        subject_id=raw.subject_id,
        output_dir=output_dir,
        streamlines_path=streamlines_path,
        manifest_path=manifest_path,
        qc_path=qc_path,
        native_bundle_dir=native_bundle.bundle_dir,
        native_cache_available=native_available,
        executed=False,
    )
