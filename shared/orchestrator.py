"""Lightweight subject-root product orchestrator with resume support.

This is intentionally small: it gives the Slicer UI one backend entrypoint for
target-product execution while leaving each product pipeline responsible for its
own scientific details and manifest/QC files.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from shared.io_layout import (
    canonical_connectome_output_dir,
    materialize_canonical_output_tree,
    normalize_run_name,
    subject_layout,
)
from shared.validation import InputValidationConfig, validate_subject_inputs


SUPPORTED_TARGETS = {
    "validation",
    "preprocessing",
    "segmentation",
    "parcellation",
    "surface",
    "microstructure",
    "tractography",
    "bundles",
    "connectome",
    "saf",
    "wma",
    "tractcloud",
}


@dataclass(frozen=True)
class ProductOrchestratorConfig:
    subject_id: str
    subject_root: Path
    targets: tuple[str, ...]
    output_root: Optional[Path] = None
    run_name: str = "csd_act"
    tractography_backend: str = "csd_act"
    execute: bool = False
    resume: bool = True
    preprocessing_backend: str = "dipy"
    preprocessing_force: bool = False
    preprocessing_dipy_denoise_method: str = "mppca"
    preprocessing_dipy_run_gibbs: bool = True
    preprocessing_dipy_run_motion_correction: bool = True
    preprocessing_mrtrix_bin_dir: Optional[Path] = None
    preprocessing_fsl_bin_dir: Optional[Path] = None
    preprocessing_reverse_phase_b0: Optional[Path] = None
    preprocessing_phase_encoding_direction: Optional[str] = None
    preprocessing_readout_time: Optional[float] = None
    microstructure_fit_method: str = "wls"
    microstructure_run_free_water: bool = False
    microstructure_run_noddi: bool = False
    atlas_t2: Optional[Path] = None
    ddseg_device: str = "cpu"
    select_streamlines: int = 1000
    mrtrix_bin_dir: Optional[Path] = None
    tract_querier_root: Optional[Path] = None
    connectome_backend: str = "python"
    connectome_compress_mrtrix_dense: bool = False
    saf_fs_dir: Optional[Path] = None
    saf_pregenerated_tractogram: Optional[Path] = None
    saf_noregister: bool = False
    saf_mrtrix_prefix: str = ""
    wma_input_tractography: Optional[Path] = None
    wma_atlas_dir: Optional[Path] = None
    wma_root: Optional[Path] = None
    slicer_executable: Optional[Path] = None
    wma_use_virtual_x: bool = False
    wma_export_diffusion_measures: bool = False
    fiber_tract_measurements_cli: Optional[Path] = None
    tractcloud_input_tractography: Optional[Path] = None
    tractcloud_root: Optional[Path] = None
    tractcloud_python_executable: Optional[Path] = None
    tractcloud_data_dir: Optional[Path] = None
    tractcloud_device: str = "auto"
    tractcloud_batch_size: int = 2048


@dataclass(frozen=True)
class ProductTaskRecord:
    name: str
    status: str
    reason: str = ""
    manifest_path: Optional[Path] = None
    qc_path: Optional[Path] = None
    outputs: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductOrchestratorResult:
    subject_id: str
    subject_root: Path
    run_manifest_path: Path
    tasks: tuple[ProductTaskRecord, ...]


def _emit(message: str, log: Optional[Callable[[str], None]] = None) -> None:
    if log:
        log(message)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _qc_completed(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        return _read_json(path).get("status") == "completed"
    except Exception:
        return False


def _find_first_existing(candidates: list[Path]) -> Optional[Path]:
    return next((path for path in candidates if path.is_file()), None)


def _resolve_optional_path(path: Optional[Path]) -> Optional[Path]:
    return path.expanduser().resolve() if path is not None else None


def _resolve_slicer_executable(config: ProductOrchestratorConfig) -> Optional[Path]:
    explicit = _resolve_optional_path(config.slicer_executable)
    if explicit is not None:
        return explicit if explicit.is_file() else None
    env_value = Path(os.environ["SLICERDDSURFER_SLICER_EXECUTABLE"]).expanduser().resolve() if os.environ.get("SLICERDDSURFER_SLICER_EXECUTABLE") else None
    if env_value is not None and env_value.is_file():
        return env_value
    candidates = [
        Path("/data/chengjin/software/Slicer-5.10.0-linux-amd64/Slicer"),
        Path("/data/chengjin/software/Slicer/Slicer"),
    ]
    return _find_first_existing(candidates)


def _resolve_bundle_input_tractography(subject_root: Path, explicit_path: Optional[Path]) -> Optional[Path]:
    resolved_explicit = _resolve_optional_path(explicit_path)
    if resolved_explicit is not None:
        return resolved_explicit if resolved_explicit.is_file() else None
    candidates = sorted(subject_root.glob("tractography/**/*.vt*")) + sorted(subject_root.glob("tractography/*.vt*"))
    return next((path.resolve() for path in candidates if path.suffix.lower() in {".vtk", ".vtp"} and path.is_file()), None)


def _saf_output_dir(layout, run_name: str) -> Path:
    return layout.saf if run_name == "saf" else (layout.saf / run_name)


def _wma_output_dir(layout, run_name: str) -> Path:
    return layout.bundles_wma / run_name


def _tractcloud_output_dir(layout, run_name: str) -> Path:
    return layout.bundles_tractcloud / run_name


def _wma_anatomical_tract_count(output_dir: Path) -> int:
    return len(list(output_dir.glob("**/AnatomicalTracts/*.vtp"))) if output_dir.is_dir() else 0


def _normalize_targets(targets: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(target.strip().lower() for target in targets if target.strip()))
    unsupported = sorted(set(normalized) - SUPPORTED_TARGETS)
    if unsupported:
        raise ValueError(f"Unsupported orchestrator target(s): {', '.join(unsupported)}")
    return normalized


def _resolve_raw_inputs(subject_root: Path) -> dict[str, Path]:
    input_dir = subject_root / "input"
    return {
        "dwi": input_dir / "data.nii.gz",
        "bval": input_dir / "bvals",
        "bvec": input_dir / "bvecs",
        "mask": input_dir / "nodif_brain_mask.nii.gz",
    }


def _preprocessing_outputs(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> dict[str, Path]:
    layout = subject_layout(subject_root, output_root=output_root)
    preproc_dir = layout.preproc
    return {
        "dwi": preproc_dir / f"{subject_id}_dwi_final.nii.gz",
        "bval": preproc_dir / f"{subject_id}_dwi_final.bval",
        "bvec": preproc_dir / f"{subject_id}_dwi_final.bvec",
        "mask": preproc_dir / f"{subject_id}_brain_mask_final.nii.gz",
        "manifest": preproc_dir / f"{subject_id}_preproc_manifest.json",
        "qc": preproc_dir / "05_qc" / f"{subject_id}_preproc_qc.json",
    }


def _preprocessing_complete(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> bool:
    outputs = _preprocessing_outputs(subject_root, subject_id, output_root)
    return all(path.is_file() for key, path in outputs.items() if key != "qc") and _qc_completed(outputs["qc"])


def _resolve_segmentation(subject_root: Path) -> Optional[Path]:
    candidates = [
        subject_root / "outputs" / "03_structural" / "ddseg" / "SegmentationMap_GMWMCSF.nii.gz",
        subject_root / ".legacy_flat_outputs" / "ddseg" / "SegmentationMap_GMWMCSF.nii.gz",
        subject_root / "segmentation" / "SegmentationMap_GMWMCSF.nii.gz",
    ]
    return next((path for path in candidates if path.is_file()), None)


def _resolve_parcellation(subject_root: Path, subject_id: str) -> Optional[Path]:
    candidates = [
        subject_root / "outputs" / "03_structural" / "ddparcel" / f"{subject_id}_ddparcel_wmparc_labels.nii.gz",
        subject_root / "outputs" / "03_structural" / "ddparcel" / f"{subject_id}-DDSurfer-wmparc.nii.gz",
        subject_root / ".legacy_flat_outputs" / "ddparcel" / f"{subject_id}-DDSurfer-wmparc.nii.gz",
        subject_root / "parcellation" / "wmparc.nii.gz",
    ]
    return next((path for path in candidates if path.is_file()), None)


def _default_atlas_t2() -> Path:
    return Path(__file__).resolve().parent.parent / "Resources" / "Data" / "100HCP-population-mean-T2.nii.gz"


def _segmentation_outputs(subject_root: Path) -> dict[str, Path]:
    layout = subject_layout(subject_root)
    return {
        "segmentation": layout.ddseg / "SegmentationMap_GMWMCSF.nii.gz",
        "gm_probability": layout.ddseg / "ProbabilisticMap_GM.nii.gz",
        "wm_probability": layout.ddseg / "ProbabilisticMap_WM.nii.gz",
        "csf_probability": layout.ddseg / "ProbabilisticMap_CSF.nii.gz",
    }


def _segmentation_complete(subject_root: Path) -> bool:
    return all(path.is_file() for path in _segmentation_outputs(subject_root).values())


def _parcellation_outputs(subject_root: Path, subject_id: str) -> dict[str, Path]:
    layout = subject_layout(subject_root)
    return {
        "wmparc": layout.ddparcel / f"{subject_id}-DDSurfer-wmparc.nii.gz",
        "wmparc_reg": layout.ddparcel / f"{subject_id}-DDSurfer-wmparc-Reg.mgz",
        "fa_reg_norm": layout.ddparcel / f"{subject_id}-dti-FractionalAnisotropy-Reg-NormMasked.nii.gz",
        "trace_reg_norm": layout.ddparcel / f"{subject_id}-dti-Trace-Reg-NormMasked.nii.gz",
        "min_eig_reg_norm": layout.ddparcel / f"{subject_id}-dti-MinEigenvalue-Reg-NormMasked.nii.gz",
        "mid_eig_reg_norm": layout.ddparcel / f"{subject_id}-dti-MidEigenvalue-Reg-NormMasked.nii.gz",
    }


def _parcellation_complete(subject_root: Path, subject_id: str) -> bool:
    return all(path.is_file() for path in _parcellation_outputs(subject_root, subject_id).values())


def _surface_outputs(subject_root: Path, subject_id: str) -> dict[str, Path]:
    native_dir = subject_layout(subject_root).ddsurfer / "pred_results_SlicerDDSurfer" / "native" / subject_id
    return {
        "white_lh": native_dir / f"{subject_id}_predicted_wm_lh.stl",
        "white_rh": native_dir / f"{subject_id}_predicted_wm_rh.stl",
        "pial_lh": native_dir / f"{subject_id}_predicted_pial_lh.stl",
        "pial_rh": native_dir / f"{subject_id}_predicted_pial_rh.stl",
    }


def _surface_complete(subject_root: Path, subject_id: str) -> bool:
    return all(path.is_file() for path in _surface_outputs(subject_root, subject_id).values())


def _microstructure_dti_outputs(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> dict[str, Path]:
    layout = subject_layout(subject_root, output_root=output_root)
    dti_dir = layout.microstructure_dti
    return {
        "fa": dti_dir / f"{subject_id}_dti_FA.nii.gz",
        "md": dti_dir / f"{subject_id}_dti_MD.nii.gz",
        "ad": dti_dir / f"{subject_id}_dti_AD.nii.gz",
        "rd": dti_dir / f"{subject_id}_dti_RD.nii.gz",
        "l1": dti_dir / f"{subject_id}_dti_L1.nii.gz",
        "l2": dti_dir / f"{subject_id}_dti_L2.nii.gz",
        "l3": dti_dir / f"{subject_id}_dti_L3.nii.gz",
        "trace": dti_dir / f"{subject_id}_dti_Trace.nii.gz",
        "manifest": layout.microstructure / "manifest.json",
    }


def _microstructure_dti_complete(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> bool:
    return all(path.is_file() for path in _microstructure_dti_outputs(subject_root, subject_id, output_root).values())


def _microstructure_freewater_outputs(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> dict[str, Path]:
    layout = subject_layout(subject_root, output_root=output_root)
    freewater_dir = layout.microstructure_freewater
    return {
        "fwf": freewater_dir / f"{subject_id}_fw_fraction.nii.gz",
        "fw_fa": freewater_dir / f"{subject_id}_fw_FA.nii.gz",
        "fw_md": freewater_dir / f"{subject_id}_fw_MD.nii.gz",
        "manifest": freewater_dir / "freewater_manifest.json",
    }


def _microstructure_freewater_complete(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> bool:
    return all(path.is_file() for path in _microstructure_freewater_outputs(subject_root, subject_id, output_root).values())


def _microstructure_noddi_outputs(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> dict[str, Path]:
    layout = subject_layout(subject_root, output_root=output_root)
    noddi_dir = layout.microstructure_noddi
    return {
        "ndi": noddi_dir / f"{subject_id}_noddi_NDI.nii.gz",
        "odi": noddi_dir / f"{subject_id}_noddi_ODI.nii.gz",
        "isovf": noddi_dir / f"{subject_id}_noddi_IsoVF.nii.gz",
        "manifest": noddi_dir / "noddi_manifest.json",
    }


def _microstructure_noddi_complete(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> bool:
    return all(path.is_file() for path in _microstructure_noddi_outputs(subject_root, subject_id, output_root).values())


def _microstructure_requested_outputs_complete(
    subject_root: Path,
    subject_id: str,
    *,
    output_root: Optional[Path],
    run_free_water: bool,
    run_noddi: bool,
) -> bool:
    if not _microstructure_dti_complete(subject_root, subject_id, output_root):
        return False
    if run_free_water and not _microstructure_freewater_complete(subject_root, subject_id, output_root):
        return False
    if run_noddi and not _microstructure_noddi_complete(subject_root, subject_id, output_root):
        return False
    return True


def _task_from_result(name: str, result, *, status: str = "completed", reason: str = "") -> ProductTaskRecord:
    return ProductTaskRecord(
        name=name,
        status=status,
        reason=reason,
        manifest_path=getattr(result, "manifest_path", None),
        qc_path=getattr(result, "qc_path", None),
    )


def run_subject_products(
    config: ProductOrchestratorConfig,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> ProductOrchestratorResult:
    """Run or plan selected products from a shared subject root."""

    if not config.subject_id.strip():
        raise ValueError("subject_id is required.")
    if config.select_streamlines <= 0:
        raise ValueError("select_streamlines must be > 0.")
    if config.tractography_backend not in {"csd_act", "dti_det"}:
        raise ValueError("tractography_backend must be one of: csd_act, dti_det.")
    if config.connectome_backend not in {"python", "mrtrix"}:
        raise ValueError("connectome_backend must be one of: python, mrtrix.")

    targets = _normalize_targets(config.targets)
    subject_root = config.subject_root.expanduser().resolve()
    output_root = config.output_root.expanduser().resolve() if config.output_root is not None else None
    layout = subject_layout(subject_root, output_root=output_root)
    run_name = normalize_run_name(config.run_name)
    tasks: list[ProductTaskRecord] = []
    start = time.monotonic()

    materialize_canonical_output_tree(subject_root, output_root=output_root, mode="symlink", archive_legacy=False)
    raw = _resolve_raw_inputs(subject_root)

    if "validation" in targets:
        validation = validate_subject_inputs(
            InputValidationConfig(
                subject_id=config.subject_id,
                input_root=subject_root,
                output_dir=layout.run_metadata / "validation",
                dependency_groups=("core",),
            )
        )
        tasks.append(
            ProductTaskRecord(
                name="validation",
                status=validation.status,
                reason=f"errors={validation.error_count}; warnings={validation.warning_count}",
                manifest_path=validation.report_path,
                qc_path=validation.report_path,
            )
        )

    if "preprocessing" in targets:
        if config.resume and _preprocessing_complete(subject_root, config.subject_id, output_root):
            tasks.append(
                ProductTaskRecord(
                    name="preprocessing.dwi",
                    status="skipped",
                    reason="completed outputs found",
                    manifest_path=preprocessing_outputs["manifest"],
                    qc_path=preprocessing_outputs["qc"],
                    outputs={key: path.as_posix() for key, path in preprocessing_outputs.items() if key not in {"manifest", "qc"}},
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="preprocessing.dwi", status="planned", reason="execute=False"))
        elif any(not path.is_file() for path in raw.values()):
            missing = [label for label, path in raw.items() if not path.is_file()]
            tasks.append(ProductTaskRecord(name="preprocessing.dwi", status="blocked", reason="missing raw input: " + ", ".join(missing)))
        else:
            from preprocessing import DwiPreprocessingConfig, run_dwi_preprocessing

            _emit("[Orchestrator] Running DWI preprocessing", log)
            result = run_dwi_preprocessing(
                DwiPreprocessingConfig(
                    subject_id=config.subject_id,
                    input_root=subject_root,
                    output_dir=layout.preproc,
                    backend=config.preprocessing_backend,
                    execute=True,
                    skip=False,
                    force=config.preprocessing_force or (not config.resume),
                    dipy_denoise_method=config.preprocessing_dipy_denoise_method,
                    dipy_run_gibbs=config.preprocessing_dipy_run_gibbs,
                    dipy_run_motion_correction=config.preprocessing_dipy_run_motion_correction,
                    mrtrix_bin_dir=config.preprocessing_mrtrix_bin_dir,
                    fsl_bin_dir=config.preprocessing_fsl_bin_dir,
                    reverse_phase_b0=config.preprocessing_reverse_phase_b0,
                    phase_encoding_direction=config.preprocessing_phase_encoding_direction,
                    readout_time=config.preprocessing_readout_time,
                ),
                log=log,
            )
            tasks.append(
                ProductTaskRecord(
                    name="preprocessing.dwi",
                    status="completed" if result.status in {"completed", "cached"} else result.status,
                    reason="cached outputs reused" if result.status == "cached" else "",
                    manifest_path=result.manifest_path,
                    qc_path=result.qc_path,
                    outputs={
                        "dwi": result.final_dwi_path.as_posix(),
                        "bval": result.final_bval_path.as_posix(),
                        "bvec": result.final_bvec_path.as_posix(),
                        "mask": result.final_mask_path.as_posix(),
                    },
                )
            )

    preprocessing_outputs = _preprocessing_outputs(subject_root, config.subject_id, output_root)
    segmentation = _resolve_segmentation(subject_root)
    parcellation = _resolve_parcellation(subject_root, config.subject_id)
    atlas_t2 = config.atlas_t2.expanduser().resolve() if config.atlas_t2 is not None else _default_atlas_t2()
    segmentation_outputs = _segmentation_outputs(subject_root)
    parcellation_outputs = _parcellation_outputs(subject_root, config.subject_id)
    surface_outputs = _surface_outputs(subject_root, config.subject_id)
    micro_outputs = _microstructure_dti_outputs(subject_root, config.subject_id, output_root)
    csd_dir = layout.csd if run_name == "csd_act" else layout.csd / run_name
    tractogram_dir = layout.tractograms / run_name
    dti_tractogram_dir = layout.tractograms_dti_det / run_name
    wmql_dir = layout.bundles_wmql / run_name
    saf_dir = _saf_output_dir(layout, run_name)
    wma_dir = _wma_output_dir(layout, run_name)
    tractcloud_dir = _tractcloud_output_dir(layout, run_name)
    connectome_dir = canonical_connectome_output_dir(subject_root, run_name, "streamline_count", output_root=output_root)
    sift2_connectome_dir = canonical_connectome_output_dir(
        subject_root,
        run_name,
        "sift2_weighted_streamline_count",
        output_root=output_root,
    )
    csd_qc = csd_dir / "csd_act_qc.json"
    dti_stem = f"{config.subject_id}-dti-deterministic"
    dti_qc = dti_tractogram_dir / f"{dti_stem}_qc.json"
    dti_manifest = dti_tractogram_dir / f"{dti_stem}_manifest.json"
    csd_tractogram = tractogram_dir / f"{config.subject_id}_csd_act_ifod2.tck"
    csd_tractogram_trk = csd_tractogram.with_suffix(".trk")
    sift2_weights = csd_tractogram.with_name(f"{csd_tractogram.stem}_sift2_weights.txt")
    dti_tractogram_trk = dti_tractogram_dir / f"{dti_stem}.trk"
    tractogram = csd_tractogram if config.tractography_backend == "csd_act" else dti_tractogram_trk
    tractogram_trk = csd_tractogram_trk if config.tractography_backend == "csd_act" else dti_tractogram_trk
    saf_tractogram = saf_dir / "SAF.tck"
    wma_input_tractography = _resolve_bundle_input_tractography(subject_root, config.wma_input_tractography)
    tractcloud_input_tractography = _resolve_bundle_input_tractography(subject_root, config.tractcloud_input_tractography)
    slicer_executable = _resolve_slicer_executable(config)

    if "segmentation" in targets:
        if config.resume and _segmentation_complete(subject_root):
            tasks.append(
                ProductTaskRecord(
                    name="segmentation.ddseg",
                    status="skipped",
                    reason="completed outputs found",
                    outputs={key: path.as_posix() for key, path in segmentation_outputs.items()},
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="segmentation.ddseg", status="planned", reason="execute=False"))
        elif any(not path.is_file() for path in raw.values()):
            missing = [label for label, path in raw.items() if not path.is_file()]
            tasks.append(ProductTaskRecord(name="segmentation.ddseg", status="blocked", reason="missing raw input: " + ", ".join(missing)))
        else:
            from segmentation.config import DDSegConfig
            from segmentation.pipeline import run_ddseg
            from shared.pipeline import ensure_native_dti_bundle, find_subject_root

            _emit("[Orchestrator] Running DDSeg", log)
            raw_bundle = find_subject_root(subject_root, config.subject_id)
            native_bundle = ensure_native_dti_bundle(raw_bundle, fit_method="ls", reuse=bool(config.resume), log=log)
            run_ddseg(
                DDSegConfig(
                    input_mask_nii=raw_bundle.mask_path,
                    parameter_type="DTI",
                    output_folder=layout.ddseg,
                    weights_dir=Path(__file__).resolve().parent.parent / "segmentation" / "weights",
                    dti_feature_dir=native_bundle.bundle_dir,
                    device=config.ddseg_device,
                )
            )
            tasks.append(
                ProductTaskRecord(
                    name="segmentation.ddseg",
                    status="completed",
                    outputs={key: path.as_posix() for key, path in segmentation_outputs.items()},
                )
            )
            segmentation = _resolve_segmentation(subject_root)

    if "parcellation" in targets:
        if config.resume and _parcellation_complete(subject_root, config.subject_id):
            tasks.append(
                ProductTaskRecord(
                    name="parcellation.ddparcel",
                    status="skipped",
                    reason="completed outputs found",
                    outputs={key: path.as_posix() for key, path in parcellation_outputs.items()},
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="parcellation.ddparcel", status="planned", reason="execute=False"))
        elif not atlas_t2.is_file():
            tasks.append(ProductTaskRecord(name="parcellation.ddparcel", status="blocked", reason=f"missing atlas T2: {atlas_t2}"))
        elif any(not path.is_file() for path in raw.values()):
            missing = [label for label, path in raw.items() if not path.is_file()]
            tasks.append(ProductTaskRecord(name="parcellation.ddparcel", status="blocked", reason="missing raw input: " + ", ".join(missing)))
        else:
            from parcellation import DDParcelRegisteredConfig, run_ddparcel_from_registered_bundle
            from shared.pipeline import ensure_registered_dti_bundle, find_subject_root

            _emit("[Orchestrator] Running DDParcel", log)
            raw_bundle = find_subject_root(subject_root, config.subject_id)
            registered = ensure_registered_dti_bundle(
                raw_bundle,
                atlas_t2=atlas_t2,
                fit_method="wls",
                reuse=bool(config.resume),
                log=log,
            )
            run_ddparcel_from_registered_bundle(
                DDParcelRegisteredConfig(
                    subject_id=config.subject_id,
                    registered_bundle=registered,
                    output_dir=layout.ddparcel,
                    native_mask=raw_bundle.mask_path,
                ),
                log=log,
            )
            tasks.append(
                ProductTaskRecord(
                    name="parcellation.ddparcel",
                    status="completed",
                    outputs={key: path.as_posix() for key, path in parcellation_outputs.items()},
                )
            )
            parcellation = _resolve_parcellation(subject_root, config.subject_id)

    if "surface" in targets:
        if config.resume and _surface_complete(subject_root, config.subject_id):
            tasks.append(
                ProductTaskRecord(
                    name="surface.ddsurfer",
                    status="skipped",
                    reason="completed outputs found",
                    outputs={key: path.as_posix() for key, path in surface_outputs.items()},
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="surface.ddsurfer", status="planned", reason="execute=False"))
        else:
            from surface import SurfaceConfig, inspect_surface_resources, run_surface

            surface_config = SurfaceConfig(
                subject_id=config.subject_id,
                subject_root=subject_root,
                output_dir=layout.ddsurfer,
                predict_mode="all",
                device=config.ddseg_device,
                registration_atlas=atlas_t2,
                execute=True,
            )
            resources = inspect_surface_resources(surface_config)
            if not resources["available"]:
                missing = resources.get("missing", [])
                tasks.append(
                    ProductTaskRecord(
                        name="surface.ddsurfer",
                        status="blocked",
                        reason="missing DDSurfer resources: " + ", ".join(str(item) for item in missing),
                    )
                )
            elif any(not path.is_file() for path in raw.values()):
                missing = [label for label, path in raw.items() if not path.is_file()]
                tasks.append(ProductTaskRecord(name="surface.ddsurfer", status="blocked", reason="missing raw input: " + ", ".join(missing)))
            else:
                _emit("[Orchestrator] Running DDSurfer surface", log)
                result = run_surface(surface_config, log=log)
                tasks.append(
                    ProductTaskRecord(
                        name="surface.ddsurfer",
                        status="completed",
                        manifest_path=result.manifest_path,
                        qc_path=result.qc_path,
                        outputs={f"model_{index}": path.as_posix() for index, path in enumerate(result.generated_models, start=1)},
                    )
                )

    if "microstructure" in targets:
        micro_outputs = _microstructure_dti_outputs(subject_root, config.subject_id, output_root)
        freewater_outputs = _microstructure_freewater_outputs(subject_root, config.subject_id, output_root)
        noddi_outputs = _microstructure_noddi_outputs(subject_root, config.subject_id, output_root)
        if (
            config.resume
            and _microstructure_requested_outputs_complete(
                subject_root,
                config.subject_id,
                output_root=output_root,
                run_free_water=config.microstructure_run_free_water,
                run_noddi=config.microstructure_run_noddi,
            )
        ):
            outputs = {key: path.as_posix() for key, path in micro_outputs.items() if key != "manifest"}
            if config.microstructure_run_free_water:
                outputs.update({f"freewater_{key}": path.as_posix() for key, path in freewater_outputs.items() if key != "manifest"})
            if config.microstructure_run_noddi:
                outputs.update({f"noddi_{key}": path.as_posix() for key, path in noddi_outputs.items() if key != "manifest"})
            tasks.append(
                ProductTaskRecord(
                    name="microstructure.dti",
                    status="skipped",
                    reason="completed requested microstructure outputs found",
                    manifest_path=micro_outputs["manifest"],
                    outputs=outputs,
                )
            )
        elif not config.execute:
            reason = "execute=False"
            enabled = []
            if config.microstructure_run_free_water:
                enabled.append("Free Water")
            if config.microstructure_run_noddi:
                enabled.append("NODDI")
            if enabled:
                reason += "; gated stages enabled: " + ", ".join(enabled)
            tasks.append(ProductTaskRecord(name="microstructure.dti", status="planned", reason=reason))
        elif any(not path.is_file() for path in raw.values()):
            missing = [label for label, path in raw.items() if not path.is_file()]
            tasks.append(ProductTaskRecord(name="microstructure.dti", status="blocked", reason="missing raw input: " + ", ".join(missing)))
        else:
            from microstructure import MicrostructureConfig, run_microstructure
            from shared.pipeline import ensure_native_dti_bundle, find_subject_root

            _emit("[Orchestrator] Running Microstructure DTI", log)
            raw_bundle = find_subject_root(subject_root, config.subject_id)
            native_bundle = ensure_native_dti_bundle(
                raw_bundle,
                fit_method=config.microstructure_fit_method,
                reuse=bool(config.resume),
                log=log,
            )
            result = run_microstructure(
                MicrostructureConfig(
                    subject_id=config.subject_id,
                    raw_input_bundle=raw_bundle,
                    native_bundle=native_bundle,
                    output_dir=layout.microstructure,
                    roi_label_map=parcellation,
                    run_free_water=config.microstructure_run_free_water,
                    run_noddi=config.microstructure_run_noddi,
                    force_recompute=not config.resume,
                ),
                log=log,
            )
            tasks.append(
                ProductTaskRecord(
                    name="microstructure.dti",
                    status="completed",
                    manifest_path=layout.microstructure / "manifest.json",
                    outputs={
                        "fa": result.fa_path.as_posix(),
                        "md": result.md_path.as_posix(),
                        "ad": result.ad_path.as_posix(),
                        "rd": result.rd_path.as_posix(),
                        "l1": result.l1_path.as_posix(),
                        "l2": result.l2_path.as_posix(),
                        "l3": result.l3_path.as_posix(),
                        "trace": result.trace_path.as_posix(),
                        "roi_stats_csv": result.roi_stats_csv_path.as_posix() if result.roi_stats_csv_path else None,
                        "roi_stats_json": result.roi_stats_json_path.as_posix() if result.roi_stats_json_path else None,
                        "fwf": result.fwf_path.as_posix() if config.microstructure_run_free_water else None,
                        "fw_tissue_fa": result.fw_tissue_fa_path.as_posix() if config.microstructure_run_free_water else None,
                        "fw_tissue_md": result.fw_tissue_md_path.as_posix() if config.microstructure_run_free_water else None,
                        "noddi_ndi": result.noddi_ndi_path.as_posix() if config.microstructure_run_noddi else None,
                        "noddi_odi": result.noddi_odi_path.as_posix() if config.microstructure_run_noddi else None,
                        "noddi_fwf": result.noddi_fwf_path.as_posix() if config.microstructure_run_noddi else None,
                    },
                )
            )

    if "tractography" in targets:
        tractography_qc = csd_qc if config.tractography_backend == "csd_act" else dti_qc
        tractography_manifest = csd_dir / "csd_act_manifest.json" if config.tractography_backend == "csd_act" else dti_manifest
        tractography_task_name = "tractography.csd_act" if config.tractography_backend == "csd_act" else "tractography.dti_det"
        if config.resume and _qc_completed(tractography_qc) and tractogram_trk.is_file() and (
            config.tractography_backend != "csd_act" or csd_tractogram.is_file()
        ):
            tasks.append(
                ProductTaskRecord(
                    name=tractography_task_name,
                    status="skipped",
                    reason="completed outputs found",
                    qc_path=tractography_qc,
                    manifest_path=tractography_manifest,
                    outputs={"tractogram": tractogram.as_posix(), "tractogram_trk": tractogram_trk.as_posix()},
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name=tractography_task_name, status="planned", reason="execute=False"))
        elif any(not path.is_file() for path in raw.values()):
            missing = [label for label, path in raw.items() if not path.is_file()]
            tasks.append(ProductTaskRecord(name=tractography_task_name, status="blocked", reason="missing raw input: " + ", ".join(missing)))
        elif config.tractography_backend == "csd_act" and segmentation is None:
            tasks.append(ProductTaskRecord(name=tractography_task_name, status="blocked", reason="missing DDSeg segmentation"))
        else:
            if config.tractography_backend == "csd_act":
                from tractography.act_prep import ACTPrepConfig, run_act_prep
                from tractography.csd import CSDActConfig, run_csd_act

                _emit(f"[Orchestrator] Running CSD/ACT {run_name}", log)
                act_prep = run_act_prep(
                    ACTPrepConfig(
                        subject_id=config.subject_id,
                        segmentation_path=segmentation,
                        output_dir=layout.act_prep,
                        execute=True,
                    ),
                    log=log,
                )
                result = run_csd_act(
                    CSDActConfig(
                        subject_id=config.subject_id,
                        dwi_path=raw["dwi"],
                        bval_path=raw["bval"],
                        bvec_path=raw["bvec"],
                        mask_path=raw["mask"],
                        five_tt_path=act_prep.five_tt_path,
                        gmwmi_path=act_prep.gmwmi_path,
                        output_dir=csd_dir,
                        tractogram_dir=tractogram_dir,
                        select_streamlines=config.select_streamlines,
                        use_sift2=True,
                        export_trk=True,
                        mrtrix_bin_dir=config.mrtrix_bin_dir,
                        execute=True,
                    ),
                    log=log,
                )
                tasks.append(
                    ProductTaskRecord(
                        name=tractography_task_name,
                        status="completed",
                        manifest_path=result.manifest_path,
                        qc_path=result.qc_path,
                        outputs={
                            "tractogram": result.tractogram_path.as_posix(),
                            "tractogram_trk": result.tractogram_trk_path.as_posix() if result.tractogram_trk_path else None,
                            "sift2_weights": result.sift2_weights_path.as_posix() if result.sift2_weights_path else None,
                        },
                    )
                )
            else:
                from tractography.dti import DTITrackingConfig, run_dti_tracking

                _emit(f"[Orchestrator] Running DTI tractography {run_name}", log)
                result = run_dti_tracking(
                    DTITrackingConfig(
                        subject_id=config.subject_id,
                        input_root=subject_root,
                        output_dir=dti_tractogram_dir,
                        fit_method=config.microstructure_fit_method,
                        tracking_method="deterministic",
                        output_format="trk",
                        execute=True,
                    ),
                    log=log,
                )
                tasks.append(
                    ProductTaskRecord(
                        name=tractography_task_name,
                        status="completed",
                        manifest_path=result.manifest_path,
                        qc_path=result.qc_path,
                        outputs={"tractogram_trk": result.streamlines_path.as_posix()},
                    )
                )

    if "bundles" in targets:
        wmql_qc = wmql_dir / "wmql_qc.json"
        if config.resume and _qc_completed(wmql_qc):
            tasks.append(ProductTaskRecord(name="bundles.wmql", status="skipped", reason="completed outputs found", qc_path=wmql_qc, manifest_path=wmql_dir / "wmql_manifest.json"))
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="bundles.wmql", status="planned", reason="execute=False"))
        elif parcellation is None:
            tasks.append(ProductTaskRecord(name="bundles.wmql", status="blocked", reason="missing parcellation"))
        elif not tractogram_trk.is_file():
            tasks.append(ProductTaskRecord(name="bundles.wmql", status="blocked", reason="missing TRK tractogram"))
        else:
            from tractography.wmql import WMQLConfig, run_wmql_bundle_segmentation

            _emit(f"[Orchestrator] Running WMQL bundles {run_name}", log)
            result = run_wmql_bundle_segmentation(
                WMQLConfig(
                    subject_id=config.subject_id,
                    input_tractography=tractogram_trk,
                    atlas_path=parcellation,
                    output_dir=wmql_dir,
                    tract_querier_root=config.tract_querier_root,
                    execute=True,
                ),
                log=log,
            )
            tasks.append(_task_from_result("bundles.wmql", result))

    if "saf" in targets:
        saf_qc = saf_dir / "saf_qc.json"
        if config.resume and _qc_completed(saf_qc) and saf_tractogram.is_file():
            tasks.append(
                ProductTaskRecord(
                    name="tractography.saf",
                    status="skipped",
                    reason="completed outputs found",
                    qc_path=saf_qc,
                    manifest_path=saf_dir / "saf_manifest.json",
                    outputs={"tractogram": saf_tractogram.as_posix()},
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="tractography.saf", status="planned", reason="execute=False"))
        else:
            fod_candidate = csd_dir / f"{config.subject_id}_wmfod_norm.mif"
            fod_path = fod_candidate if fod_candidate.is_file() else (csd_dir / f"{config.subject_id}_wmfod.mif")
            fs_dir = _resolve_optional_path(config.saf_fs_dir)
            pregenerated_tractogram = _resolve_optional_path(config.saf_pregenerated_tractogram)
            if fs_dir is None:
                tasks.append(ProductTaskRecord(name="tractography.saf", status="blocked", reason="missing --saf-fs-dir"))
            elif not fod_path.is_file():
                tasks.append(ProductTaskRecord(name="tractography.saf", status="blocked", reason="missing CSD FOD output for SAF"))
            elif not config.saf_noregister and not micro_outputs["fa"].is_file():
                tasks.append(ProductTaskRecord(name="tractography.saf", status="blocked", reason="missing FA map for SAF registration"))
            else:
                from tractography import SAFConfig, run_saf

                _emit(f"[Orchestrator] Running SAF {run_name}", log)
                result = run_saf(
                    SAFConfig(
                        subject_id=config.subject_id,
                        input_root=subject_root,
                        fs_dir=fs_dir,
                        fod_path=fod_path,
                        output_dir=saf_dir,
                        fa_path=None if config.saf_noregister else micro_outputs["fa"],
                        pregenerated_tractogram=pregenerated_tractogram,
                        mrtrix_bin_dir=config.mrtrix_bin_dir,
                        mrtrix_prefix=config.saf_mrtrix_prefix,
                        noregister=config.saf_noregister,
                        execute=True,
                    ),
                    log=log,
                )
                tasks.append(
                    ProductTaskRecord(
                        name="tractography.saf",
                        status="completed",
                        qc_path=result.qc_path,
                        manifest_path=result.manifest_path,
                        outputs={"tractogram": result.saf_tractogram.as_posix()},
                    )
                )

    if "wma" in targets:
        wma_qc = wma_dir / "wma_org_atlas_qc.json"
        if config.resume and _qc_completed(wma_qc):
            anatomical_tract_count = _wma_anatomical_tract_count(wma_dir)
            if anatomical_tract_count > 0:
                tasks.append(
                    ProductTaskRecord(
                        name="bundles.wma",
                        status="skipped",
                        reason="completed outputs found",
                        qc_path=wma_qc,
                        manifest_path=wma_dir / "wma_org_atlas_manifest.json",
                        outputs={"anatomical_tract_count": str(anatomical_tract_count)},
                    )
                )
            else:
                tasks.append(ProductTaskRecord(name="bundles.wma", status="planned", reason="existing QC present but anatomical tracts missing"))
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="bundles.wma", status="planned", reason="execute=False"))
        elif wma_input_tractography is None:
            tasks.append(ProductTaskRecord(name="bundles.wma", status="blocked", reason="missing VTK/VTP input tractography for WMA"))
        elif config.wma_atlas_dir is None:
            tasks.append(ProductTaskRecord(name="bundles.wma", status="blocked", reason="missing --wma-atlas-dir"))
        elif slicer_executable is None:
            tasks.append(ProductTaskRecord(name="bundles.wma", status="blocked", reason="missing Slicer executable for WMA"))
        else:
            from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

            _emit(f"[Orchestrator] Running WMA {run_name}", log)
            result = run_wma_org_atlas(
                WMAOrgAtlasConfig(
                    subject_id=config.subject_id,
                    input_tractography=wma_input_tractography,
                    atlas_dir=config.wma_atlas_dir,
                    output_dir=wma_dir,
                    slicer_executable=slicer_executable,
                    wma_root=config.wma_root,
                    use_virtual_x=config.wma_use_virtual_x,
                    export_diffusion_measures=config.wma_export_diffusion_measures,
                    fiber_tract_measurements_cli=config.fiber_tract_measurements_cli,
                    execute=True,
                ),
                log=log,
            )
            tasks.append(_task_from_result("bundles.wma", result))

    if "tractcloud" in targets:
        tractcloud_qc = tractcloud_dir / "tractcloud_qc.json"
        if config.resume and _qc_completed(tractcloud_qc):
            from tractography.tractcloud import summarize_tractcloud_outputs

            output_summary = summarize_tractcloud_outputs(tractcloud_dir)
            if output_summary.get("bundle_count", 0) > 0:
                tasks.append(
                    ProductTaskRecord(
                        name="bundles.tractcloud",
                        status="skipped",
                        reason="completed outputs found",
                        qc_path=tractcloud_qc,
                        manifest_path=tractcloud_dir / "tractcloud_manifest.json",
                        outputs={"bundle_count": str(output_summary.get("bundle_count"))},
                    )
                )
            else:
                tasks.append(ProductTaskRecord(name="bundles.tractcloud", status="planned", reason="existing QC present but no bundle outputs found"))
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="bundles.tractcloud", status="planned", reason="execute=False"))
        elif tractcloud_input_tractography is None:
            tasks.append(ProductTaskRecord(name="bundles.tractcloud", status="blocked", reason="missing VTK/VTP input tractography for TractCloud"))
        else:
            from tractography import TractCloudConfig, run_tractcloud_parcellation

            _emit(f"[Orchestrator] Running TractCloud {run_name}", log)
            result = run_tractcloud_parcellation(
                TractCloudConfig(
                    subject_id=config.subject_id,
                    input_tractography=tractcloud_input_tractography,
                    output_dir=tractcloud_dir,
                    tractcloud_root=config.tractcloud_root,
                    python_executable=config.tractcloud_python_executable,
                    data_dir=config.tractcloud_data_dir,
                    device=config.tractcloud_device,
                    batch_size=config.tractcloud_batch_size,
                    execute=True,
                ),
                log=log,
            )
            tasks.append(_task_from_result("bundles.tractcloud", result))

    if "connectome" in targets:
        weighted_connectome_handled = False
        conn_qc = connectome_dir / f"{config.subject_id}-connectome-streamline_count_qc.json"
        if config.resume and _qc_completed(conn_qc):
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="skipped", reason="completed outputs found", qc_path=conn_qc, manifest_path=connectome_dir / f"{config.subject_id}-connectome-streamline_count_manifest.json"))
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="planned", reason="execute=False"))
        elif parcellation is None:
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="blocked", reason="missing parcellation"))
        elif config.tractography_backend == "csd_act" and not tractogram.is_file():
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="blocked", reason="missing TCK tractogram"))
        elif config.tractography_backend != "csd_act" and config.connectome_backend == "mrtrix":
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="blocked", reason="DTI tractography currently supports python connectome backend only"))
        elif not tractogram.is_file():
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="blocked", reason="missing tractogram"))
        else:
            from connectome import ConnectomeConfig, run_connectome

            _emit(f"[Orchestrator] Running connectome {run_name}", log)
            result = run_connectome(
                ConnectomeConfig(
                    subject_id=config.subject_id,
                    tractography_path=tractogram,
                    parcellation_path=parcellation,
                    output_dir=connectome_dir,
                    metric="streamline_count",
                    backend=config.connectome_backend,
                    mrtrix_bin_dir=config.mrtrix_bin_dir,
                    compress_mrtrix_dense=config.connectome_compress_mrtrix_dense,
                    execute=True,
                ),
                log=log,
            )
            tasks.append(_task_from_result("connectome.streamline_count", result))
            if sift2_weights.is_file():
                weighted = run_connectome(
                    ConnectomeConfig(
                        subject_id=config.subject_id,
                        tractography_path=tractogram,
                        parcellation_path=parcellation,
                        output_dir=sift2_connectome_dir,
                        metric="sift2_weighted_streamline_count",
                        sift2_weights_path=sift2_weights,
                        backend=config.connectome_backend,
                        mrtrix_bin_dir=config.mrtrix_bin_dir,
                        compress_mrtrix_dense=config.connectome_compress_mrtrix_dense,
                        execute=True,
                    ),
                    log=log,
                )
                tasks.append(_task_from_result("connectome.sift2_weighted", weighted))
                weighted_connectome_handled = True

        if not weighted_connectome_handled and sift2_weights.is_file():
            sift2_qc = sift2_connectome_dir / f"{config.subject_id}-connectome-sift2_weighted_streamline_count_qc.json"
            if config.resume and _qc_completed(sift2_qc):
                tasks.append(
                    ProductTaskRecord(
                        name="connectome.sift2_weighted",
                        status="skipped",
                        reason="completed outputs found",
                        qc_path=sift2_qc,
                        manifest_path=sift2_connectome_dir / f"{config.subject_id}-connectome-sift2_weighted_streamline_count_manifest.json",
                    )
                )
            elif not config.execute:
                tasks.append(ProductTaskRecord(name="connectome.sift2_weighted", status="planned", reason="execute=False"))
            elif parcellation is None:
                tasks.append(ProductTaskRecord(name="connectome.sift2_weighted", status="blocked", reason="missing parcellation"))
            elif not tractogram.is_file():
                tasks.append(ProductTaskRecord(name="connectome.sift2_weighted", status="blocked", reason="missing TCK tractogram"))
            else:
                from connectome import ConnectomeConfig, run_connectome

                weighted = run_connectome(
                    ConnectomeConfig(
                        subject_id=config.subject_id,
                        tractography_path=tractogram,
                        parcellation_path=parcellation,
                        output_dir=sift2_connectome_dir,
                        metric="sift2_weighted_streamline_count",
                        sift2_weights_path=sift2_weights,
                        backend=config.connectome_backend,
                        mrtrix_bin_dir=config.mrtrix_bin_dir,
                        compress_mrtrix_dense=config.connectome_compress_mrtrix_dense,
                        execute=True,
                    ),
                    log=log,
                )
                tasks.append(_task_from_result("connectome.sift2_weighted", weighted))

    manifest = {
        "kind": "slicerddsurfer_product_orchestration",
        "version": 1,
        "subject_id": config.subject_id,
        "subject_root": subject_root.as_posix(),
        "output_root": output_root.as_posix() if output_root is not None else layout.outputs.as_posix(),
        "targets": list(targets),
        "run_name": run_name,
        "tractography_backend": config.tractography_backend,
        "execute": config.execute,
        "resume": config.resume,
        "preprocessing_backend": config.preprocessing_backend,
        "preprocessing_force": config.preprocessing_force,
        "preprocessing_dipy_denoise_method": config.preprocessing_dipy_denoise_method,
        "preprocessing_dipy_run_gibbs": config.preprocessing_dipy_run_gibbs,
        "preprocessing_dipy_run_motion_correction": config.preprocessing_dipy_run_motion_correction,
        "preprocessing_mrtrix_bin_dir": config.preprocessing_mrtrix_bin_dir.as_posix() if config.preprocessing_mrtrix_bin_dir else None,
        "preprocessing_fsl_bin_dir": config.preprocessing_fsl_bin_dir.as_posix() if config.preprocessing_fsl_bin_dir else None,
        "preprocessing_reverse_phase_b0": config.preprocessing_reverse_phase_b0.as_posix() if config.preprocessing_reverse_phase_b0 else None,
        "preprocessing_phase_encoding_direction": config.preprocessing_phase_encoding_direction,
        "preprocessing_readout_time": config.preprocessing_readout_time,
        "microstructure_fit_method": config.microstructure_fit_method,
        "microstructure_run_free_water": config.microstructure_run_free_water,
        "microstructure_run_noddi": config.microstructure_run_noddi,
        "atlas_t2": atlas_t2.as_posix(),
        "ddseg_device": config.ddseg_device,
        "select_streamlines": config.select_streamlines,
        "connectome_backend": config.connectome_backend,
        "connectome_compress_mrtrix_dense": config.connectome_compress_mrtrix_dense,
        "saf_fs_dir": config.saf_fs_dir.expanduser().resolve().as_posix() if config.saf_fs_dir else None,
        "saf_pregenerated_tractogram": config.saf_pregenerated_tractogram.expanduser().resolve().as_posix() if config.saf_pregenerated_tractogram else None,
        "saf_noregister": config.saf_noregister,
        "saf_mrtrix_prefix": config.saf_mrtrix_prefix,
        "wma_input_tractography": wma_input_tractography.as_posix() if wma_input_tractography else None,
        "wma_atlas_dir": config.wma_atlas_dir.expanduser().resolve().as_posix() if config.wma_atlas_dir else None,
        "wma_root": config.wma_root.expanduser().resolve().as_posix() if config.wma_root else None,
        "slicer_executable": slicer_executable.as_posix() if slicer_executable else None,
        "wma_use_virtual_x": config.wma_use_virtual_x,
        "wma_export_diffusion_measures": config.wma_export_diffusion_measures,
        "fiber_tract_measurements_cli": config.fiber_tract_measurements_cli.expanduser().resolve().as_posix() if config.fiber_tract_measurements_cli else None,
        "tractcloud_input_tractography": tractcloud_input_tractography.as_posix() if tractcloud_input_tractography else None,
        "tractcloud_root": config.tractcloud_root.expanduser().resolve().as_posix() if config.tractcloud_root else None,
        "tractcloud_python_executable": config.tractcloud_python_executable.expanduser().resolve().as_posix() if config.tractcloud_python_executable else None,
        "tractcloud_data_dir": config.tractcloud_data_dir.expanduser().resolve().as_posix() if config.tractcloud_data_dir else None,
        "tractcloud_device": config.tractcloud_device,
        "tractcloud_batch_size": config.tractcloud_batch_size,
        "elapsed_seconds": time.monotonic() - start,
        "tasks": [
            {
                "name": task.name,
                "status": task.status,
                "reason": task.reason,
                "manifest_path": task.manifest_path.as_posix() if task.manifest_path else None,
                "qc_path": task.qc_path.as_posix() if task.qc_path else None,
                "outputs": task.outputs,
            }
            for task in tasks
        ],
    }
    manifest_path = layout.run_metadata / f"{run_name}_orchestration_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ProductOrchestratorResult(
        subject_id=config.subject_id,
        subject_root=subject_root,
        run_manifest_path=manifest_path,
        tasks=tuple(tasks),
    )
