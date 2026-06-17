"""Lightweight subject-root product orchestrator with resume support.

This is intentionally small: it gives the Slicer UI one backend entrypoint for
target-product execution while leaving each product pipeline responsible for its
own scientific details and manifest/QC files.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from shared.io_layout import (
    archive_development_outputs,
    canonical_connectome_output_dir,
    materialize_canonical_output_tree,
    normalize_run_name,
    subject_layout,
)
from shared.validation import InputValidationConfig, validate_subject_inputs
from shared.environment import resolve_auto_torch_device


SUPPORTED_TARGETS = {
    "validation",
    "preprocessing",
    "segmentation",
    "parcellation",
    "surface",
    "surface_postprocess",
    "microstructure",
    "microstructure_freewater",
    "microstructure_noddi",
    "tractography",
    "bundles",
    "connectome",
    "saf",
    "wma",
    "tractcloud",
}

TRACTOGRAPHY_BACKENDS = {"csd_act", "dti_det", "saf"}
BUNDLE_BACKENDS = {"wmql", "wma", "tractcloud"}

TARGET_ORDER = (
    "validation",
    "preprocessing",
    "segmentation",
    "parcellation",
    "surface",
    "surface_postprocess",
    "microstructure",
    "microstructure_freewater",
    "microstructure_noddi",
    "tractography",
    "bundles",
    "saf",
    "wma",
    "tractcloud",
    "connectome",
)


@dataclass(frozen=True)
class ProductOrchestratorConfig:
    subject_id: str
    subject_root: Path
    targets: tuple[str, ...]
    output_root: Optional[Path] = None
    run_name: str = "csd_act"
    tractography_backend: str = "csd_act"
    bundle_backend: str = "wmql"
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
    microstructure_free_water_chunk_size: int = 2
    microstructure_free_water_engine: str = "serial"
    microstructure_free_water_n_jobs: Optional[int] = None
    microstructure_free_water_vox_per_chunk: Optional[int] = None
    postprocess_native_dir: Optional[Path] = None
    postprocess_mri_dir: Optional[Path] = None
    postprocess_backend_root: Optional[Path] = None
    postprocess_mode: str = "whole"
    postprocess_python_bin: Optional[Path] = None
    postprocess_freesurfer_home: Optional[Path] = None
    postprocess_atlases: Optional[tuple[str, ...]] = None
    postprocess_force: bool = False
    atlas_t2: Optional[Path] = None
    ddseg_device: str = "auto"
    surface_device: str = "auto"
    select_streamlines: int = 100000
    mrtrix_bin_dir: Optional[Path] = None
    tract_querier_root: Optional[Path] = None
    connectome_backend: str = "python"
    connectome_compress_mrtrix_dense: bool = False
    saf_fs_dir: Optional[Path] = None
    saf_pregenerated_tractogram: Optional[Path] = None
    saf_tckgen_options: str = ""
    saf_noregister: bool = True
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
    preflight_blocked_targets: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductTaskRecord:
    name: str
    status: str
    reason: str = ""
    manifest_path: Optional[Path] = None
    qc_path: Optional[Path] = None
    outputs: dict[str, str | None] = field(default_factory=dict)
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    runtime_seconds: Optional[float] = None
    logs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunPlanItem:
    target: str
    task_name: str
    status: str
    reason: str = ""
    reason_category: str = ""
    runnable: bool = False
    will_run: bool = False
    reused: bool = False
    inputs: dict[str, str | None] = field(default_factory=dict)
    outputs: dict[str, str | None] = field(default_factory=dict)
    dependencies: dict[str, str | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "task_name": self.task_name,
            "status": self.status,
            "reason": self.reason,
            "reason_category": self.reason_category,
            "runnable": self.runnable,
            "will_run": self.will_run,
            "reused": self.reused,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "dependencies": self.dependencies,
        }


@dataclass(frozen=True)
class RunPlanResult:
    subject_id: str
    subject_root: Path
    output_root: Path
    run_name: str
    targets: tuple[str, ...]
    run_plan_path: Path
    items: tuple[RunPlanItem, ...]

    @property
    def blocked_items(self) -> tuple[RunPlanItem, ...]:
        return tuple(item for item in self.items if item.status == "blocked")

    @property
    def will_run_items(self) -> tuple[RunPlanItem, ...]:
        return tuple(item for item in self.items if item.will_run)

    @property
    def skipped_items(self) -> tuple[RunPlanItem, ...]:
        return tuple(item for item in self.items if item.status == "skipped")

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "slicerddsurfer_run_plan",
            "version": 1,
            "subject_id": self.subject_id,
            "subject_root": self.subject_root.as_posix(),
            "output_root": self.output_root.as_posix(),
            "run_name": self.run_name,
            "targets": list(self.targets),
            "summary": {
                "will_run": len(self.will_run_items),
                "skipped": len(self.skipped_items),
                "blocked": len(self.blocked_items),
            },
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class ProductOrchestratorResult:
    subject_id: str
    subject_root: Path
    run_manifest_path: Path
    tasks: tuple[ProductTaskRecord, ...]
    run_plan_path: Optional[Path] = None


def _emit(message: str, log: Optional[Callable[[str], None]] = None) -> None:
    if log:
        log(message)


def _start_task_timer(label: str, log: Optional[Callable[[str], None]] = None) -> float:
    started = time.monotonic()
    _emit(f"[Orchestrator] {label} started", log)
    return started


def _finish_task_timer(label: str, started: float, log: Optional[Callable[[str], None]] = None) -> None:
    _emit(f"[Orchestrator] {label} completed in {time.monotonic() - started:0.1f}s", log)


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


def _resolved_device_for_execution(requested: str, *, execute: bool, target_will_run: bool) -> str:
    normalized = (requested or "auto").strip().lower() or "auto"
    if normalized not in {"", "auto"}:
        return resolve_auto_torch_device(normalized)
    if not target_will_run:
        return "not_resolved_target_not_run"
    if not execute:
        return "not_resolved_execute_false"
    return resolve_auto_torch_device(normalized)


def _resolved_tractcloud_device_for_execution(requested: str, *, execute: bool, target_will_run: bool) -> str:
    normalized = (requested or "auto").strip().lower() or "auto"
    if normalized not in {"", "auto"}:
        return normalized
    resolved = _resolved_device_for_execution(normalized, execute=execute, target_will_run=target_will_run)
    if resolved.startswith("cuda"):
        return "cuda"
    if resolved == "cpu":
        return "cpu"
    return resolved


def _normalize_bundle_backends(bundle_backend: str) -> tuple[str, ...]:
    value = (bundle_backend or "wmql").strip().lower()
    if value in {"", "default"}:
        value = "wmql"
    value = value.replace("+", ",").replace(";", ",")
    tokens: list[str] = []
    for token in (part.strip() for part in value.split(",")):
        if not token:
            continue
        if token == "all":
            tokens.extend(("wmql", "wma", "tractcloud"))
        elif token in {"none", "off", "skip"}:
            continue
        else:
            tokens.append(token)
    unknown = sorted(set(tokens) - BUNDLE_BACKENDS)
    if unknown:
        raise ValueError("bundle_backend must contain only: all, wmql, wma, tractcloud.")
    return tuple(dict.fromkeys(tokens))


def _primary_tractography_backend(config: ProductOrchestratorConfig) -> str:
    return "csd_act" if config.tractography_backend == "saf" else config.tractography_backend


def normalize_orchestrator_targets(
    targets: tuple[str, ...],
    *,
    tractography_backend: str = "csd_act",
    bundle_backend: str = "wmql",
    microstructure_run_free_water: bool = False,
    microstructure_run_noddi: bool = False,
) -> tuple[str, ...]:
    """Expand product-level targets according to selected backend parameters."""

    requested = tuple(dict.fromkeys(target.strip().lower() for target in targets if target.strip()))
    bundle_backends = _normalize_bundle_backends(bundle_backend)
    expanded: list[str] = []
    for target in requested:
        if target == "microstructure":
            expanded.append("microstructure")
            if microstructure_run_free_water:
                expanded.append("microstructure_freewater")
            if microstructure_run_noddi:
                expanded.append("microstructure_noddi")
            continue
        if target == "bundles":
            for backend in bundle_backends:
                expanded.append("bundles" if backend == "wmql" else backend)
            continue
        expanded.append(target)
        if target == "tractography" and tractography_backend == "saf":
            expanded.append("surface_postprocess")
            expanded.append("saf")

    requested_set = set(expanded)
    normalized = tuple(target for target in TARGET_ORDER if target in requested_set)
    unsupported = sorted(set(normalized) - SUPPORTED_TARGETS)
    if unsupported:
        raise ValueError(f"Unsupported orchestrator target(s): {', '.join(unsupported)}")
    missing_from_order = sorted(requested_set - set(TARGET_ORDER))
    if missing_from_order:
        raise ValueError(f"Unsupported orchestrator target(s): {', '.join(missing_from_order)}")
    return normalized


def _resolve_bundle_input_tractography(
    subject_root: Path,
    explicit_path: Optional[Path],
    *,
    output_root: Optional[Path] = None,
    run_name: Optional[str] = None,
) -> Optional[Path]:
    resolved_explicit = _resolve_optional_path(explicit_path)
    if resolved_explicit is not None:
        return resolved_explicit if resolved_explicit.is_file() else None
    layout = subject_layout(subject_root, output_root=output_root)
    candidates: list[Path] = []
    if run_name:
        normalized_run = normalize_run_name(run_name)
        candidates.extend(
            [
                _saf_output_dir(layout, normalized_run) / "SAF.vtk",
                _saf_output_dir(layout, normalized_run) / "SAF.vtp",
            ]
        )
    candidates.extend(sorted(layout.saf.glob("**/*.vt*")))
    candidates.extend(sorted(layout.tractography.glob("**/*.vt*")))
    candidates.extend(sorted(subject_root.glob("tractography/**/*.vt*")) + sorted(subject_root.glob("tractography/*.vt*")))
    return next((path.resolve() for path in candidates if path.suffix.lower() in {".vtk", ".vtp"} and path.is_file()), None)


def _resolve_best_saf_pregenerated_tractogram(subject_root: Path, explicit_path: Optional[Path], output_root: Optional[Path] = None) -> Optional[Path]:
    resolved_explicit = _resolve_optional_path(explicit_path)
    if resolved_explicit is not None:
        return resolved_explicit if resolved_explicit.is_file() else None
    layout = subject_layout(subject_root, output_root=output_root)
    candidates = sorted(layout.tractograms.glob("csd_act*/**/*.tck"))
    if not candidates:
        return None
    candidates = [path.resolve() for path in candidates if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_size, path.as_posix()))


def _saf_output_dir(layout, run_name: str) -> Path:
    return layout.saf if run_name == "saf" else (layout.saf / run_name)


def _wma_output_dir(layout, run_name: str) -> Path:
    return layout.bundles_wma / run_name


def _tractcloud_output_dir(layout, run_name: str) -> Path:
    return layout.bundles_tractcloud / run_name


def _wma_anatomical_tract_count(output_dir: Path) -> int:
    return len(list(output_dir.glob("**/AnatomicalTracts/*.vtp"))) if output_dir.is_dir() else 0


def _normalize_targets(config: ProductOrchestratorConfig) -> tuple[str, ...]:
    return normalize_orchestrator_targets(
        config.targets,
        tractography_backend=config.tractography_backend,
        bundle_backend=config.bundle_backend,
        microstructure_run_free_water=config.microstructure_run_free_water,
        microstructure_run_noddi=config.microstructure_run_noddi,
    )


def _task_name_for_target(target: str, config: ProductOrchestratorConfig) -> str:
    if target == "preprocessing":
        return "preprocessing.dwi"
    if target == "segmentation":
        return "segmentation.ddseg"
    if target == "parcellation":
        return "parcellation.ddparcel"
    if target == "surface":
        return "surface.ddsurfer"
    if target == "surface_postprocess":
        return "surface.ddsurfer_postprocess"
    if target == "microstructure":
        return "microstructure.dti"
    if target == "microstructure_freewater":
        return "microstructure.freewater"
    if target == "microstructure_noddi":
        return "microstructure.noddi"
    if target == "tractography":
        return "tractography.csd_act" if _primary_tractography_backend(config) == "csd_act" else "tractography.dti_det"
    if target == "bundles":
        return "bundles.wmql"
    if target == "connectome":
        return "connectome.streamline_count"
    if target == "saf":
        return "tractography.saf"
    if target == "wma":
        return "bundles.wma"
    if target == "tractcloud":
        return "bundles.tractcloud"
    return target


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


def _resolve_segmentation(subject_root: Path, output_root: Optional[Path] = None) -> Optional[Path]:
    layout = subject_layout(subject_root, output_root=output_root)
    candidates = [
        layout.ddseg / "SegmentationMap_GMWMCSF.nii.gz",
        subject_root / ".legacy_flat_outputs" / "ddseg" / "SegmentationMap_GMWMCSF.nii.gz",
        subject_root / "segmentation" / "SegmentationMap_GMWMCSF.nii.gz",
    ]
    return next((path for path in candidates if path.is_file()), None)


def _resolve_parcellation(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> Optional[Path]:
    layout = subject_layout(subject_root, output_root=output_root)
    candidates = [
        layout.ddparcel / f"{subject_id}_ddparcel_wmparc_labels.nii.gz",
        layout.ddparcel / f"{subject_id}-DDSurfer-wmparc.nii.gz",
        subject_root / ".legacy_flat_outputs" / "ddparcel" / f"{subject_id}-DDSurfer-wmparc.nii.gz",
        subject_root / "parcellation" / "wmparc.nii.gz",
    ]
    return next((path for path in candidates if path.is_file()), None)


def _default_atlas_t2() -> Path:
    return Path(__file__).resolve().parent.parent / "Resources" / "Data" / "100HCP-population-mean-T2.nii.gz"


def _segmentation_outputs(subject_root: Path, output_root: Optional[Path] = None) -> dict[str, Path]:
    layout = subject_layout(subject_root, output_root=output_root)
    return {
        "segmentation": layout.ddseg / "SegmentationMap_GMWMCSF.nii.gz",
        "gm_probability": layout.ddseg / "ProbabilisticMap_GM.nii.gz",
        "wm_probability": layout.ddseg / "ProbabilisticMap_WM.nii.gz",
        "csf_probability": layout.ddseg / "ProbabilisticMap_CSF.nii.gz",
    }


def _segmentation_complete(subject_root: Path, output_root: Optional[Path] = None) -> bool:
    return all(path.is_file() for path in _segmentation_outputs(subject_root, output_root).values())


def _parcellation_outputs(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> dict[str, Path]:
    layout = subject_layout(subject_root, output_root=output_root)
    return {
        "wmparc": layout.ddparcel / f"{subject_id}-DDSurfer-wmparc.nii.gz",
        "wmparc_reg": layout.ddparcel / f"{subject_id}-DDSurfer-wmparc-Reg.mgz",
        "fa_reg_norm": layout.ddparcel / f"{subject_id}-dti-FractionalAnisotropy-Reg-NormMasked.nii.gz",
        "trace_reg_norm": layout.ddparcel / f"{subject_id}-dti-Trace-Reg-NormMasked.nii.gz",
        "min_eig_reg_norm": layout.ddparcel / f"{subject_id}-dti-MinEigenvalue-Reg-NormMasked.nii.gz",
        "mid_eig_reg_norm": layout.ddparcel / f"{subject_id}-dti-MidEigenvalue-Reg-NormMasked.nii.gz",
    }


def _parcellation_complete(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> bool:
    return all(path.is_file() for path in _parcellation_outputs(subject_root, subject_id, output_root).values())


def _surface_outputs(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> dict[str, Path]:
    native_dir = subject_layout(subject_root, output_root=output_root).ddsurfer / "pred_results_SlicerDDSurfer" / "native" / subject_id
    return {
        "white_lh": native_dir / f"{subject_id}_predicted_wm_lh.stl",
        "white_rh": native_dir / f"{subject_id}_predicted_wm_rh.stl",
        "pial_lh": native_dir / f"{subject_id}_predicted_pial_lh.stl",
        "pial_rh": native_dir / f"{subject_id}_predicted_pial_rh.stl",
    }


def _surface_complete(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> bool:
    return all(path.is_file() for path in _surface_outputs(subject_root, subject_id, output_root).values())


def _surface_postprocess_outputs(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> dict[str, Path]:
    layout = subject_layout(subject_root, output_root=output_root)
    structural_root = layout.ddsurfer_postprocess
    stats_root = layout.ddsurfer_postprocess_stats
    return {
        "manifest": structural_root / "manifest.json",
        "qc": structural_root / "qc.json",
        "surf": structural_root / "surf",
        "label": structural_root / "label",
        "stats": stats_root / "stats",
    }


def _surface_postprocess_complete(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> bool:
    outputs = _surface_postprocess_outputs(subject_root, subject_id, output_root)
    return outputs["manifest"].is_file() and outputs["surf"].exists() and _qc_completed(outputs["qc"])


def _surface_postprocess_saf_fs_dir(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> Optional[Path]:
    """Return a SAF-compatible postprocess root when whole-surface outputs are complete."""

    outputs = _surface_postprocess_outputs(subject_root, subject_id, output_root)
    structural_root = outputs["manifest"].parent
    if not _surface_postprocess_complete(subject_root, subject_id, output_root):
        return None
    required_files = [
        structural_root / "mri" / "brain.mgz",
        structural_root / "surf" / "lh.white",
        structural_root / "surf" / "rh.white",
        structural_root / "surf" / "lh.pial",
        structural_root / "surf" / "rh.pial",
        structural_root / "surf" / "lh.inflated",
        structural_root / "surf" / "rh.inflated",
        structural_root / "surf" / "lh.sphere",
        structural_root / "surf" / "rh.sphere",
        structural_root / "surf" / "lh.curv",
        structural_root / "surf" / "rh.curv",
    ]
    return structural_root if all(path.is_file() for path in required_files) else None


def _act_prep_outputs(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> dict[str, Path]:
    layout = subject_layout(subject_root, output_root=output_root)
    return {
        "five_tt": layout.act_prep / f"{subject_id}_5tt_from_labels.nii.gz",
        "gmwmi": layout.act_prep / f"{subject_id}_gmwmi_from_labels.nii.gz",
        "manifest": layout.act_prep / "act_prep_manifest.json",
        "qc": layout.act_prep / "act_prep_qc.json",
    }


def _act_prep_complete(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> bool:
    outputs = _act_prep_outputs(subject_root, subject_id, output_root)
    return outputs["five_tt"].is_file() and outputs["gmwmi"].is_file() and _qc_completed(outputs["qc"])


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
        "progress": freewater_dir / "freewater_progress.json",
    }


def _microstructure_freewater_complete(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> bool:
    outputs = _microstructure_freewater_outputs(subject_root, subject_id, output_root)
    return all(outputs[key].is_file() for key in ("fwf", "fw_fa", "fw_md", "manifest"))


def _microstructure_noddi_outputs(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> dict[str, Path]:
    layout = subject_layout(subject_root, output_root=output_root)
    noddi_dir = layout.microstructure_noddi
    return {
        "ndi": noddi_dir / f"{subject_id}_noddi_NDI.nii.gz",
        "odi": noddi_dir / f"{subject_id}_noddi_ODI.nii.gz",
        "isovf": noddi_dir / f"{subject_id}_noddi_IsoVF.nii.gz",
        "manifest": noddi_dir / "noddi_manifest.json",
        "progress": noddi_dir / "noddi_progress.json",
    }


def _microstructure_noddi_complete(subject_root: Path, subject_id: str, output_root: Optional[Path] = None) -> bool:
    outputs = _microstructure_noddi_outputs(subject_root, subject_id, output_root)
    return all(outputs[key].is_file() for key in ("ndi", "odi", "isovf", "manifest"))


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


def _path_dict(paths: dict[str, Path | None]) -> dict[str, str | None]:
    return {key: value.as_posix() if isinstance(value, Path) else None for key, value in paths.items()}


def _missing_file_labels(paths: dict[str, Path]) -> list[str]:
    return [label for label, path in paths.items() if not path.is_file()]


def _run_plan_path(layout, run_name: str) -> Path:
    return layout.run_metadata / f"{run_name}_run_plan.json"


def _write_run_plan(plan: RunPlanResult) -> Path:
    plan.run_plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan.run_plan_path.write_text(json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan.run_plan_path


def plan_subject_products(config: ProductOrchestratorConfig, *, write: bool = True) -> RunPlanResult:
    """Build a target-level run plan without executing product algorithms."""

    if not config.subject_id.strip():
        raise ValueError("subject_id is required.")
    if config.select_streamlines <= 0:
        raise ValueError("select_streamlines must be > 0.")
    if config.microstructure_free_water_chunk_size <= 0:
        raise ValueError("microstructure_free_water_chunk_size must be > 0.")
    if config.microstructure_free_water_engine not in {"serial", "joblib", "dask", "ray"}:
        raise ValueError("microstructure_free_water_engine must be one of: serial, joblib, dask, ray.")
    if config.microstructure_free_water_vox_per_chunk is not None and config.microstructure_free_water_vox_per_chunk <= 0:
        raise ValueError("microstructure_free_water_vox_per_chunk must be > 0.")
    if config.tractography_backend not in TRACTOGRAPHY_BACKENDS:
        raise ValueError("tractography_backend must be one of: csd_act, dti_det, saf.")
    bundle_backends = _normalize_bundle_backends(config.bundle_backend)
    if config.connectome_backend not in {"python", "mrtrix"}:
        raise ValueError("connectome_backend must be one of: python, mrtrix.")

    targets = _normalize_targets(config)
    selected = set(targets)
    preflight_blocked_targets = {
        target: reason
        for target, reason in (config.preflight_blocked_targets or {}).items()
        if target in selected and reason
    }
    subject_root = config.subject_root.expanduser().resolve()
    output_root = config.output_root.expanduser().resolve() if config.output_root is not None else None
    layout = subject_layout(subject_root, output_root=output_root)
    run_name = normalize_run_name(config.run_name)
    primary_tractography_backend = _primary_tractography_backend(config)
    raw = _resolve_raw_inputs(subject_root)
    raw_missing = _missing_file_labels(raw)
    atlas_t2 = config.atlas_t2.expanduser().resolve() if config.atlas_t2 is not None else _default_atlas_t2()

    preprocessing_outputs = _preprocessing_outputs(subject_root, config.subject_id, output_root)
    segmentation_outputs = _segmentation_outputs(subject_root, output_root)
    parcellation_outputs = _parcellation_outputs(subject_root, config.subject_id, output_root)
    surface_outputs = _surface_outputs(subject_root, config.subject_id, output_root)
    micro_outputs = _microstructure_dti_outputs(subject_root, config.subject_id, output_root)
    freewater_outputs = _microstructure_freewater_outputs(subject_root, config.subject_id, output_root)
    noddi_outputs = _microstructure_noddi_outputs(subject_root, config.subject_id, output_root)
    postprocess_outputs = _surface_postprocess_outputs(subject_root, config.subject_id, output_root)

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
    tractogram = csd_tractogram if primary_tractography_backend == "csd_act" else dti_tractogram_trk
    tractogram_trk = csd_tractogram_trk if primary_tractography_backend == "csd_act" else dti_tractogram_trk
    saf_tractogram = saf_dir / "SAF.tck"
    wma_input_tractography = _resolve_bundle_input_tractography(subject_root, config.wma_input_tractography, output_root=output_root, run_name=run_name)
    tractcloud_input_tractography = _resolve_bundle_input_tractography(subject_root, config.tractcloud_input_tractography, output_root=output_root, run_name=run_name)
    slicer_executable = _resolve_slicer_executable(config)
    segmentation = _resolve_segmentation(subject_root, output_root)
    parcellation = _resolve_parcellation(subject_root, config.subject_id, output_root)

    items: list[RunPlanItem] = []
    available: dict[str, bool] = {}

    def target_completed(target: str) -> bool:
        if target == "preprocessing":
            return _preprocessing_complete(subject_root, config.subject_id, output_root)
        if target == "segmentation":
            return _segmentation_complete(subject_root, output_root)
        if target == "parcellation":
            return _parcellation_complete(subject_root, config.subject_id, output_root)
        if target == "surface":
            return _surface_complete(subject_root, config.subject_id, output_root)
        if target == "surface_postprocess":
            return _surface_postprocess_complete(subject_root, config.subject_id, output_root)
        if target == "microstructure":
            return _microstructure_dti_complete(subject_root, config.subject_id, output_root)
        if target == "microstructure_freewater":
            return _microstructure_freewater_complete(subject_root, config.subject_id, output_root)
        if target == "microstructure_noddi":
            return _microstructure_noddi_complete(subject_root, config.subject_id, output_root)
        if target == "tractography":
            return _qc_completed(csd_qc if primary_tractography_backend == "csd_act" else dti_qc) and tractogram_trk.is_file() and (
                primary_tractography_backend != "csd_act" or tractogram.is_file()
            )
        if target == "bundles":
            return _qc_completed(wmql_dir / "wmql_qc.json")
        if target == "saf":
            return _qc_completed(saf_dir / "saf_qc.json") and saf_tractogram.is_file()
        if target == "wma":
            return _qc_completed(wma_dir / "wma_org_atlas_qc.json") and _wma_anatomical_tract_count(wma_dir) > 0
        if target == "tractcloud":
            if not _qc_completed(tractcloud_dir / "tractcloud_qc.json"):
                return False
            try:
                from tractography.tractcloud import summarize_tractcloud_outputs

                return int(summarize_tractcloud_outputs(tractcloud_dir).get("bundle_count", 0) or 0) > 0
            except Exception:
                return False
        if target == "connectome":
            return _qc_completed(connectome_dir / f"{config.subject_id}-connectome-streamline_count_qc.json")
        return False

    def add(
        target: str,
        status: str,
        reason: str = "",
        reason_category: str = "",
        *,
        inputs: dict[str, Path | None] | None = None,
        outputs: dict[str, Path | None] | None = None,
        dependencies: dict[str, str | None] | None = None,
        provides: bool = True,
    ) -> None:
        item = RunPlanItem(
            target=target,
            task_name=_task_name_for_target(target, config),
            status=status,
            reason=reason,
            reason_category=reason_category,
            runnable=status != "blocked",
            will_run=status == "will_run",
            reused=status == "skipped",
            inputs=_path_dict(inputs or {}),
            outputs=_path_dict(outputs or {}),
            dependencies=dependencies or {},
        )
        items.append(item)
        available[target] = provides and status in {"will_run", "skipped"}

    def raw_input_block(target: str, outputs: dict[str, Path | None] | None = None) -> bool:
        if raw_missing:
            add(
                target,
                "blocked",
                "missing raw input: " + ", ".join(raw_missing),
                "data",
                inputs=raw,
                outputs=outputs,
                provides=False,
            )
            return True
        return False

    for target in targets:
        if target in preflight_blocked_targets and not target_completed(target):
            add(
                target,
                "blocked",
                preflight_blocked_targets[target],
                "environment",
                provides=False,
            )
            continue

        if target == "validation":
            add(
                target,
                "will_run",
                "validate subject inputs and write QC report",
                "runnable",
                inputs=raw,
                outputs={"report": layout.run_metadata / "validation" / f"{config.subject_id}_input_validation.json"},
                provides=False,
            )
            continue

        if target == "preprocessing":
            if config.resume and _preprocessing_complete(subject_root, config.subject_id, output_root):
                add(target, "skipped", "completed outputs found", "reuse", inputs=raw, outputs=preprocessing_outputs)
            elif not raw_input_block(target, preprocessing_outputs):
                add(target, "will_run", "ready to run DWI preprocessing", "runnable", inputs=raw, outputs=preprocessing_outputs)
            continue

        if target == "segmentation":
            if config.resume and _segmentation_complete(subject_root, output_root):
                add(target, "skipped", "completed outputs found", "reuse", inputs=raw, outputs=segmentation_outputs)
            elif not raw_input_block(target, segmentation_outputs):
                add(target, "will_run", "ready to run DDSeg", "runnable", inputs=raw, outputs=segmentation_outputs)
            continue

        if target == "parcellation":
            if config.resume and _parcellation_complete(subject_root, config.subject_id, output_root):
                add(target, "skipped", "completed outputs found", "reuse", inputs=raw, outputs=parcellation_outputs)
            elif not atlas_t2.is_file():
                add(
                    target,
                    "blocked",
                    f"missing atlas T2: {atlas_t2}",
                    "data",
                    inputs={**raw, "atlas_t2": atlas_t2},
                    outputs=parcellation_outputs,
                    provides=False,
                )
            elif not raw_input_block(target, parcellation_outputs):
                add(target, "will_run", "ready to run DDParcel", "runnable", inputs={**raw, "atlas_t2": atlas_t2}, outputs=parcellation_outputs)
            continue

        if target == "surface":
            if config.resume and _surface_complete(subject_root, config.subject_id, output_root):
                add(target, "skipped", "completed outputs found", "reuse", inputs=raw, outputs=surface_outputs)
            elif not raw_input_block(target, surface_outputs):
                add(target, "will_run", "ready to run DDSurfer surface", "runnable", inputs=raw, outputs=surface_outputs)
            continue

        if target == "surface_postprocess":
            native_dir = _resolve_optional_path(config.postprocess_native_dir)
            mri_dir = _resolve_optional_path(config.postprocess_mri_dir)
            if config.resume and _surface_postprocess_complete(subject_root, config.subject_id, output_root):
                add(target, "skipped", "completed outputs found", "reuse", outputs=postprocess_outputs)
            elif native_dir is not None and not native_dir.is_dir():
                add(target, "blocked", "invalid explicit postprocess inputs: postprocess_native_dir", "data", inputs={"native_dir": native_dir}, outputs=postprocess_outputs, provides=False)
            elif mri_dir is not None and not mri_dir.is_dir():
                add(target, "blocked", "invalid explicit postprocess inputs: postprocess_mri_dir", "data", inputs={"mri_dir": mri_dir}, outputs=postprocess_outputs, provides=False)
            else:
                add(target, "will_run", "ready to run DDSurfer postprocess", "runnable", inputs={"native_dir": native_dir, "mri_dir": mri_dir}, outputs=postprocess_outputs)
            continue

        if target == "microstructure":
            outputs = {**micro_outputs}
            if config.resume and _microstructure_dti_complete(subject_root, config.subject_id, output_root):
                add(target, "skipped", "completed DTI microstructure outputs found", "reuse", inputs=raw, outputs=outputs)
            elif not raw_input_block(target, outputs):
                add(target, "will_run", "ready to run Microstructure DTI", "runnable", inputs=raw, outputs=outputs, dependencies={"parcellation": "optional ROI stats"})
            continue

        if target == "microstructure_freewater":
            dti_ready = _microstructure_dti_complete(subject_root, config.subject_id, output_root) or available.get("microstructure", False)
            if config.resume and _microstructure_freewater_complete(subject_root, config.subject_id, output_root):
                add(target, "skipped", "completed Free Water outputs found", "reuse", inputs=raw, outputs=freewater_outputs, dependencies={"microstructure": "available" if dti_ready else None})
            elif not dti_ready:
                add(target, "blocked", "missing Microstructure DTI outputs; select microstructure or provide existing output", "upstream", inputs=raw, outputs=freewater_outputs, dependencies={"microstructure": "missing"}, provides=False)
            elif not raw_input_block(target, freewater_outputs):
                add(target, "will_run", "ready to run Microstructure Free Water", "runnable", inputs=raw, outputs=freewater_outputs, dependencies={"microstructure": "available" if _microstructure_dti_complete(subject_root, config.subject_id, output_root) else "will_run"})
            continue

        if target == "microstructure_noddi":
            dti_ready = _microstructure_dti_complete(subject_root, config.subject_id, output_root) or available.get("microstructure", False)
            if config.resume and _microstructure_noddi_complete(subject_root, config.subject_id, output_root):
                add(target, "skipped", "completed NODDI outputs found", "reuse", inputs=raw, outputs=noddi_outputs, dependencies={"microstructure": "available" if dti_ready else None})
            elif not dti_ready:
                add(target, "blocked", "missing Microstructure DTI outputs; select microstructure or provide existing output", "upstream", inputs=raw, outputs=noddi_outputs, dependencies={"microstructure": "missing"}, provides=False)
            elif not raw_input_block(target, noddi_outputs):
                add(target, "will_run", "ready to run Microstructure NODDI", "runnable", inputs=raw, outputs=noddi_outputs, dependencies={"microstructure": "available" if _microstructure_dti_complete(subject_root, config.subject_id, output_root) else "will_run"})
            continue

        if target == "tractography":
            tractography_qc = csd_qc if primary_tractography_backend == "csd_act" else dti_qc
            tractography_outputs = {
                "tractogram": tractogram,
                "tractogram_trk": tractogram_trk,
                "qc": tractography_qc,
                "manifest": csd_dir / "csd_act_manifest.json" if primary_tractography_backend == "csd_act" else dti_manifest,
            }
            complete = config.resume and _qc_completed(tractography_qc) and tractogram_trk.is_file() and (
                primary_tractography_backend != "csd_act" or tractogram.is_file()
            )
            segmentation_ready = segmentation is not None or available.get("segmentation", False)
            if complete:
                add(target, "skipped", "completed outputs found", "reuse", inputs=raw, outputs=tractography_outputs, dependencies={"segmentation": "available" if segmentation_ready else None})
            elif raw_input_block(target, tractography_outputs):
                pass
            elif primary_tractography_backend == "csd_act" and not segmentation_ready:
                add(target, "blocked", "missing DDSeg segmentation; select segmentation or provide existing output", "upstream", inputs=raw, outputs=tractography_outputs, dependencies={"segmentation": "missing"}, provides=False)
            else:
                add(target, "will_run", f"ready to run tractography backend {config.tractography_backend}", "runnable", inputs=raw, outputs=tractography_outputs, dependencies={"segmentation": "available" if segmentation is not None else ("will_run" if available.get("segmentation", False) else None)})
            continue

        if target == "bundles":
            wmql_outputs = {"qc": wmql_dir / "wmql_qc.json", "manifest": wmql_dir / "wmql_manifest.json", "bundle_dir": wmql_dir}
            parcellation_ready = parcellation is not None or available.get("parcellation", False)
            tractogram_ready = tractogram_trk.is_file() or available.get("tractography", False)
            if config.resume and _qc_completed(wmql_outputs["qc"]):
                add(target, "skipped", "completed outputs found", "reuse", outputs=wmql_outputs, dependencies={"parcellation": "available", "tractogram": "available"})
            elif not parcellation_ready:
                add(target, "blocked", "missing parcellation; select parcellation or provide existing output", "upstream", outputs=wmql_outputs, dependencies={"parcellation": "missing"}, provides=False)
            elif not tractogram_ready:
                add(target, "blocked", "missing TRK tractogram; select tractography or provide existing output", "upstream", outputs=wmql_outputs, dependencies={"tractogram": "missing"}, provides=False)
            else:
                add(target, "will_run", "ready to run WMQL bundles", "runnable", inputs={"tractogram_trk": tractogram_trk, "parcellation": parcellation}, outputs=wmql_outputs, dependencies={"parcellation": "available" if parcellation is not None else "will_run", "tractogram": "available" if tractogram_trk.is_file() else "will_run"})
            continue

        if target == "saf":
            saf_outputs = {"tractogram": saf_tractogram, "tractogram_vtk": saf_dir / "SAF.vtk", "qc": saf_dir / "saf_qc.json", "manifest": saf_dir / "saf_manifest.json"}
            if config.resume and _qc_completed(saf_outputs["qc"]) and saf_tractogram.is_file():
                add(target, "skipped", "completed outputs found", "reuse", outputs=saf_outputs)
            else:
                fod_candidate = csd_dir / f"{config.subject_id}_wmfod_norm.mif"
                fod_path = fod_candidate if fod_candidate.is_file() else (csd_dir / f"{config.subject_id}_wmfod.mif")
                fs_dir = _resolve_optional_path(config.saf_fs_dir) or _surface_postprocess_saf_fs_dir(subject_root, config.subject_id, output_root)
                if fs_dir is None and not available.get("surface_postprocess", False):
                    add(target, "blocked", "missing --saf-fs-dir or completed DDSurfer postprocess outputs", "upstream", outputs=saf_outputs, provides=False)
                elif not fod_path.is_file() and not available.get("tractography", False):
                    add(target, "blocked", "missing CSD FOD output for SAF", "upstream", outputs=saf_outputs, dependencies={"fod": "missing"}, provides=False)
                else:
                    add(target, "will_run", "ready to run SAF", "runnable", inputs={"fs_dir": fs_dir, "fod": fod_path}, outputs=saf_outputs, dependencies={"surface_postprocess": "available" if fs_dir else "will_run", "fod": "available" if fod_path.is_file() else "will_run"})
            continue

        if target == "wma":
            wma_outputs = {"qc": wma_dir / "wma_org_atlas_qc.json", "manifest": wma_dir / "wma_org_atlas_manifest.json", "output_dir": wma_dir}
            if config.resume and _qc_completed(wma_outputs["qc"]) and _wma_anatomical_tract_count(wma_dir) > 0:
                add(target, "skipped", "completed outputs found", "reuse", outputs=wma_outputs)
            elif wma_input_tractography is None and not available.get("saf", False):
                add(target, "blocked", "missing VTK/VTP input tractography for WMA", "data", outputs=wma_outputs, provides=False)
            elif config.wma_atlas_dir is None:
                add(target, "blocked", "missing --wma-atlas-dir", "data", inputs={"input_tractography": wma_input_tractography}, outputs=wma_outputs, provides=False)
            elif slicer_executable is None:
                add(target, "blocked", "missing Slicer executable for WMA", "environment", inputs={"input_tractography": wma_input_tractography}, outputs=wma_outputs, provides=False)
            else:
                add(target, "will_run", "ready to run WMA ORG atlas", "runnable", inputs={"input_tractography": wma_input_tractography, "atlas_dir": config.wma_atlas_dir}, outputs=wma_outputs, dependencies={"input_tractography": "available" if wma_input_tractography else "will_run:saf"})
            continue

        if target == "tractcloud":
            tractcloud_outputs = {"qc": tractcloud_dir / "tractcloud_qc.json", "manifest": tractcloud_dir / "tractcloud_manifest.json", "output_dir": tractcloud_dir}
            tractcloud_bundle_count = 0
            if config.resume and _qc_completed(tractcloud_outputs["qc"]):
                try:
                    from tractography.tractcloud import summarize_tractcloud_outputs

                    tractcloud_bundle_count = int(summarize_tractcloud_outputs(tractcloud_dir).get("bundle_count", 0) or 0)
                except Exception:
                    tractcloud_bundle_count = 0
            if tractcloud_bundle_count > 0:
                add(target, "skipped", "completed outputs found", "reuse", outputs=tractcloud_outputs)
            elif tractcloud_input_tractography is None and not available.get("saf", False):
                add(target, "blocked", "missing VTK/VTP input tractography for TractCloud", "data", outputs=tractcloud_outputs, provides=False)
            else:
                add(target, "will_run", "ready to run TractCloud", "runnable", inputs={"input_tractography": tractcloud_input_tractography}, outputs=tractcloud_outputs, dependencies={"input_tractography": "available" if tractcloud_input_tractography else "will_run:saf"})
            continue

        if target == "connectome":
            conn_qc = connectome_dir / f"{config.subject_id}-connectome-streamline_count_qc.json"
            conn_outputs = {
                "qc": conn_qc,
                "manifest": connectome_dir / f"{config.subject_id}-connectome-streamline_count_manifest.json",
                "output_dir": connectome_dir,
                "sift2_output_dir": sift2_connectome_dir,
            }
            parcellation_ready = parcellation is not None or available.get("parcellation", False)
            tractogram_ready = tractogram.is_file() or available.get("tractography", False)
            if config.resume and _qc_completed(conn_qc):
                add(target, "skipped", "completed outputs found", "reuse", outputs=conn_outputs)
            elif not parcellation_ready:
                add(target, "blocked", "missing parcellation; select parcellation or provide existing output", "upstream", outputs=conn_outputs, dependencies={"parcellation": "missing"}, provides=False)
            elif not tractogram_ready:
                add(target, "blocked", "missing tractogram; select tractography or provide existing output", "upstream", outputs=conn_outputs, dependencies={"tractogram": "missing"}, provides=False)
            elif primary_tractography_backend != "csd_act" and config.connectome_backend == "mrtrix":
                add(target, "blocked", "DTI tractography currently supports python connectome backend only", "configuration", outputs=conn_outputs, provides=False)
            else:
                add(
                    target,
                    "will_run",
                    "ready to run connectome",
                    "runnable",
                    inputs={"tractogram": tractogram, "parcellation": parcellation, "sift2_weights": sift2_weights if sift2_weights.is_file() else None},
                    outputs=conn_outputs,
                    dependencies={"parcellation": "available" if parcellation is not None else "will_run", "tractogram": "available" if tractogram.is_file() else "will_run"},
                )
            continue

    plan = RunPlanResult(
        subject_id=config.subject_id,
        subject_root=subject_root,
        output_root=layout.outputs,
        run_name=run_name,
        targets=targets,
        run_plan_path=_run_plan_path(layout, run_name),
        items=tuple(items),
    )
    if write:
        _write_run_plan(plan)
    return plan


def _safe_task_dir_name(name: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name).strip("_") or "task"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class _TimedTaskList(list):
    def __init__(self, start_monotonic: float) -> None:
        super().__init__()
        self._last_monotonic = start_monotonic
        self._last_wall = datetime.now(timezone.utc)

    def append(self, task: ProductTaskRecord) -> None:  # type: ignore[override]
        now = time.monotonic()
        now_wall = datetime.now(timezone.utc)
        runtime = max(0.0, now - self._last_monotonic)
        ended_at = now_wall.isoformat(timespec="seconds")
        started_at = task.started_at or self._last_wall.isoformat(timespec="seconds")
        timed_task = replace(
            task,
            started_at=started_at,
            ended_at=task.ended_at or ended_at,
            runtime_seconds=task.runtime_seconds if task.runtime_seconds is not None else runtime,
            logs=task.logs
            or (
                f"{task.name} {task.status}" + (f": {task.reason}" if task.reason else ""),
            ),
        )
        super().append(timed_task)
        self._last_monotonic = now
        self._last_wall = now_wall


def _write_normalized_task_records(
    *,
    layout,
    run_name: str,
    config: ProductOrchestratorConfig,
    tasks: list[ProductTaskRecord],
    plan: RunPlanResult,
    orchestration_manifest_path: Path,
) -> dict[str, dict[str, str]]:
    """Write one stable manifest/qc/logs directory per task.

    Product-specific pipelines keep their native manifest/QC paths. This layer
    gives the Slicer UI, CLI, and regression scripts one schema to inspect.
    """

    task_root = layout.run_metadata / "tasks" / run_name
    task_root.mkdir(parents=True, exist_ok=True)
    plan_by_task = {item.task_name: item for item in plan.items}
    normalized: dict[str, dict[str, str]] = {}
    for task in tasks:
        task_dir = task_root / _safe_task_dir_name(task.name)
        logs_dir = task_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        plan_item = plan_by_task.get(task.name)
        reused = task.status == "skipped" or bool(plan_item.reused if plan_item else False)
        normalized_manifest_path = task_dir / "manifest.json"
        normalized_qc_path = task_dir / "qc.json"
        log_path = logs_dir / "task.log"
        record = {
            "kind": "slicerddsurfer_task_manifest",
            "version": 1,
            "schema": "slicerddsurfer.task.v1",
            "subject_id": config.subject_id,
            "subject_root": config.subject_root.expanduser().resolve().as_posix(),
            "output_root": layout.outputs.as_posix(),
            "run_name": run_name,
            "target": plan_item.target if plan_item else task.name.split(".", 1)[0],
            "task_name": task.name,
            "status": task.status,
            "reason": task.reason,
            "reason_category": plan_item.reason_category if plan_item else "",
            "reused": reused,
            "started_at": task.started_at,
            "ended_at": task.ended_at,
            "runtime_seconds": task.runtime_seconds,
            "created_at": _now_utc(),
            "inputs": plan_item.inputs if plan_item else {},
            "outputs": task.outputs or (plan_item.outputs if plan_item else {}),
            "dependencies": plan_item.dependencies if plan_item else {},
            "native_manifest_path": task.manifest_path.as_posix() if task.manifest_path else None,
            "native_qc_path": task.qc_path.as_posix() if task.qc_path else None,
            "orchestration_manifest_path": orchestration_manifest_path.as_posix(),
            "run_plan_path": plan.run_plan_path.as_posix(),
            "qc_path": normalized_qc_path.as_posix(),
            "logs_dir": logs_dir.as_posix(),
        }
        qc = {
            "kind": "slicerddsurfer_task_qc",
            "version": 1,
            "schema": "slicerddsurfer.task_qc.v1",
            "subject_id": config.subject_id,
            "run_name": run_name,
            "task_name": task.name,
            "status": task.status,
            "reason": task.reason,
            "reason_category": plan_item.reason_category if plan_item else "",
            "reused": reused,
            "started_at": task.started_at,
            "ended_at": task.ended_at,
            "runtime_seconds": task.runtime_seconds,
            "checks": {
                "normalized_manifest_written": True,
                "native_manifest_exists": bool(task.manifest_path and task.manifest_path.is_file()),
                "native_qc_exists": bool(task.qc_path and task.qc_path.is_file()),
                "declared_output_count": len(task.outputs),
            },
            "created_at": record["created_at"],
        }
        normalized_manifest_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        normalized_qc_path.write_text(json.dumps(qc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        log_path.write_text(
            f"{record['created_at']} {task.name} {task.status}"
            + (f" ({task.reason})" if task.reason else "")
            + "\n"
            + "\n".join(task.logs)
            + ("\n" if task.logs else ""),
            encoding="utf-8",
        )
        normalized[task.name] = {
            "manifest_path": normalized_manifest_path.as_posix(),
            "qc_path": normalized_qc_path.as_posix(),
            "logs_dir": logs_dir.as_posix(),
        }
    return normalized


def _expected_output_top_dirs(targets: tuple[str, ...]) -> set[str]:
    expected = {"00_run_metadata"}
    selected = set(targets)
    if "preprocessing" in selected:
        expected.add("01_preproc")
    if selected & {"microstructure", "microstructure_freewater", "microstructure_noddi"}:
        expected.update({"02_microstructure", "05_statistics"})
    if selected & {"segmentation", "parcellation", "surface", "surface_postprocess"}:
        expected.add("03_structural")
    if selected & {"tractography", "bundles", "saf", "wma", "tractcloud", "connectome"}:
        expected.add("04_tractography")
    expected.add("06_slicer_scene_report")
    return expected


def _audit_output_tree(layout, *, subject_id: str, selected_targets: tuple[str, ...] = ()) -> dict[str, object]:
    expected_top_dirs = _expected_output_top_dirs(selected_targets)
    optional_missing = {"06_slicer_scene_report"}
    warnings: list[str] = []
    outputs = layout.outputs
    present_top_dirs = sorted(path.name for path in outputs.iterdir() if path.is_dir()) if outputs.is_dir() else []
    missing = sorted(name for name in expected_top_dirs - optional_missing if not (outputs / name).exists())
    for name in missing:
        warnings.append(f"missing canonical output directory: {name}")
    nested_outputs = outputs / subject_id / "outputs"
    if nested_outputs.exists():
        warnings.append(f"unexpected nested subject outputs: {nested_outputs.as_posix()}")
    legacy_names = {
        "microstructure",
        "ddseg",
        "ddparcel",
        "ddsurfer",
        "tractography",
        "connectome",
        "validation",
    }
    legacy_present = sorted(name for name in legacy_names if (outputs / name).exists())
    for name in legacy_present:
        warnings.append(f"legacy top-level output should be moved under canonical tree or cache: {name}")
    audit = {
        "kind": "slicerddsurfer_output_tree_audit",
        "version": 1,
        "schema": "slicerddsurfer.output_tree_audit.v1",
        "subject_id": subject_id,
        "output_root": outputs.as_posix(),
        "present_top_dirs": present_top_dirs,
        "expected_top_dirs": sorted(expected_top_dirs),
        "warnings": warnings,
        "status": "warning" if warnings else "passed",
        "created_at": _now_utc(),
    }
    audit_path = layout.run_metadata / "output_tree_audit.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit["path"] = audit_path.as_posix()
    return audit


def _write_output_tree_semantics(
    *,
    layout,
    subject_id: str,
    requested_targets: tuple[str, ...],
    run_targets: tuple[str, ...],
    tasks: list[ProductTaskRecord],
) -> dict[str, object]:
    """Write user-facing reasons for canonical output directory state."""

    task_status_by_target = {
        task.name.split(".", 1)[0]: {
            "task_name": task.name,
            "status": task.status,
            "reason": task.reason,
        }
        for task in tasks
    }
    requested = set(requested_targets)
    runnable = set(run_targets)
    entries: list[dict[str, Any]] = []
    directory_targets: list[tuple[str, tuple[str, ...], str]] = [
        ("00_run_metadata", ("validation",), "Run metadata, validation, environment and task records."),
        ("01_preproc", ("preprocessing",), "DWI preprocessing outputs."),
        ("02_microstructure", ("microstructure", "microstructure_freewater", "microstructure_noddi"), "Microstructure model outputs."),
        ("03_structural", ("segmentation", "parcellation", "surface", "surface_postprocess"), "Segmentation, parcellation and surface products."),
        ("04_tractography", ("tractography", "bundles", "saf", "wma", "tractcloud", "connectome"), "Tractography, bundle extraction, SAF and connectome products."),
        ("05_statistics", ("microstructure", "microstructure_freewater", "microstructure_noddi", "surface_postprocess"), "Regional summaries and post-process statistics."),
        ("06_slicer_scene_report", tuple(TARGET_ORDER), "HTML/Markdown reports and output tree views."),
    ]
    for relative, targets, description in directory_targets:
        path = layout.outputs / relative
        selected_here = bool(requested & set(targets)) or relative == "00_run_metadata"
        runnable_here = bool(runnable & set(targets)) or relative == "00_run_metadata"
        file_count, size_bytes = _path_stats(path)
        if not selected_here:
            state = "not_selected_existing" if path.exists() else "not_selected_absent"
        elif not runnable_here:
            state = "blocked_existing" if path.exists() else "blocked_absent"
        elif path.exists() and file_count:
            state = "selected_has_outputs"
        elif path.exists():
            state = "selected_empty"
        else:
            state = "selected_not_created_yet"
        related_tasks = [
            task_status_by_target[target]
            for target in targets
            if target in task_status_by_target
        ]
        entries.append(
            {
                "path": relative,
                "absolute_path": path.as_posix(),
                "state": state,
                "selected": selected_here,
                "runnable": runnable_here,
                "exists": path.exists(),
                "file_count": file_count,
                "size_bytes": size_bytes,
                "related_targets": list(targets),
                "related_tasks": related_tasks,
                "description": description,
            }
        )
    payload = {
        "kind": "slicerddsurfer_output_tree_semantics",
        "version": 1,
        "schema": "slicerddsurfer.output_tree_semantics.v1",
        "subject_id": subject_id,
        "output_root": layout.outputs.as_posix(),
        "requested_targets": list(requested_targets),
        "run_targets": list(run_targets),
        "entries": entries,
        "created_at": _now_utc(),
    }
    path = layout.run_metadata / "output_tree_semantics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload["path"] = path.as_posix()
    return payload


def _path_stats(path: Path) -> tuple[int, int]:
    """Return (file_count, size_bytes) for an existing file or directory."""

    if not path.exists():
        return 0, 0
    if path.is_file():
        try:
            return 1, path.stat().st_size
        except OSError:
            return 1, 0
    if not path.is_dir():
        return 0, 0
    file_count = 0
    size_bytes = 0
    for child in path.rglob("*"):
        if not child.is_file():
            continue
        file_count += 1
        try:
            size_bytes += child.stat().st_size
        except OSError:
            pass
    return file_count, size_bytes


def _path_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _declared_task_output_stats(task: ProductTaskRecord) -> tuple[int, int]:
    candidates: list[Path] = []
    for value in (task.outputs or {}).values():
        if not value:
            continue
        path = Path(str(value)).expanduser()
        if not path.exists():
            continue
        try:
            normalized_path = path.resolve()
        except OSError:
            normalized_path = path
        candidates.append(normalized_path)

    roots: list[Path] = []
    for path in candidates:
        if any(path == existing or _path_within(path, existing) for existing in roots):
            continue
        if path.is_dir():
            roots = [existing for existing in roots if not _path_within(existing, path)]
        roots.append(path)

    total_files = 0
    total_bytes = 0
    for path in roots:
        file_count, size_bytes = _path_stats(path)
        total_files += file_count
        total_bytes += size_bytes
    return total_files, total_bytes


def _top_dir_stats(output_root: Path) -> list[dict[str, object]]:
    stats: dict[str, dict[str, object]] = {}
    if not output_root.is_dir():
        return []
    for path in output_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            top_name = path.relative_to(output_root).parts[0]
        except (IndexError, ValueError):
            continue
        row = stats.setdefault(top_name, {"path": top_name, "file_count": 0, "size_bytes": 0})
        row["file_count"] = int(row["file_count"]) + 1
        try:
            row["size_bytes"] = int(row["size_bytes"]) + path.stat().st_size
        except OSError:
            pass
    return [stats[name] for name in sorted(stats)]


def _build_performance_profile(
    *,
    layout,
    run_name: str,
    tasks: list[ProductTaskRecord],
    orchestration_elapsed_seconds: float,
) -> dict[str, object]:
    task_rows = []
    for task in tasks:
        output_files, output_bytes = _declared_task_output_stats(task)
        task_rows.append(
            {
                "name": task.name,
                "status": task.status,
                "runtime_seconds": float(task.runtime_seconds or 0.0),
                "declared_output_files": output_files,
                "declared_output_bytes": output_bytes,
                "reason": task.reason,
            }
        )

    output_root = layout.outputs
    top_dirs = _top_dir_stats(output_root)

    profile = {
        "kind": "slicerddsurfer_performance_profile",
        "version": 1,
        "schema": "slicerddsurfer.performance_profile.v1",
        "run_name": run_name,
        "output_root": output_root.as_posix(),
        "created_at": _now_utc(),
        "orchestration_elapsed_seconds": orchestration_elapsed_seconds,
        "task_runtime_seconds_total": sum(float(row["runtime_seconds"]) for row in task_rows),
        "profile_notes": [
            "Task runtime_seconds are measured by the product orchestrator around each task append.",
            "Skipped task runtimes measure resume detection overhead, not the original compute runtime.",
            "Declared output sizes are computed from task output paths that exist when the manifest is written.",
        ],
        "slowest_tasks": sorted(task_rows, key=lambda row: float(row["runtime_seconds"]), reverse=True)[:8],
        "largest_task_outputs": sorted(task_rows, key=lambda row: int(row["declared_output_bytes"]), reverse=True)[:8],
        "largest_top_dirs": sorted(top_dirs, key=lambda row: int(row["size_bytes"]), reverse=True)[:8],
        "top_dirs": top_dirs,
    }
    profile_path = layout.run_metadata / f"{run_name}_performance_profile.json"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile["path"] = profile_path.as_posix()
    profile_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return profile


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
    if config.microstructure_free_water_chunk_size <= 0:
        raise ValueError("microstructure_free_water_chunk_size must be > 0.")
    if config.microstructure_free_water_engine not in {"serial", "joblib", "dask", "ray"}:
        raise ValueError("microstructure_free_water_engine must be one of: serial, joblib, dask, ray.")
    if config.microstructure_free_water_vox_per_chunk is not None and config.microstructure_free_water_vox_per_chunk <= 0:
        raise ValueError("microstructure_free_water_vox_per_chunk must be > 0.")
    if config.tractography_backend not in TRACTOGRAPHY_BACKENDS:
        raise ValueError("tractography_backend must be one of: csd_act, dti_det, saf.")
    bundle_backends = _normalize_bundle_backends(config.bundle_backend)
    if config.connectome_backend not in {"python", "mrtrix"}:
        raise ValueError("connectome_backend must be one of: python, mrtrix.")

    targets = _normalize_targets(config)
    subject_root = config.subject_root.expanduser().resolve()
    output_root = config.output_root.expanduser().resolve() if config.output_root is not None else None
    layout = subject_layout(subject_root, output_root=output_root)
    run_name = normalize_run_name(config.run_name)
    primary_tractography_backend = _primary_tractography_backend(config)
    start = time.monotonic()
    tasks: list[ProductTaskRecord] = _TimedTaskList(start)
    plan = plan_subject_products(config, write=True)
    plan_by_target = {item.target: item for item in plan.items}
    preflight_blocked_targets = {
        target: reason
        for target, reason in (config.preflight_blocked_targets or {}).items()
        if target in targets and reason and plan_by_target.get(target) is not None and plan_by_target[target].status == "blocked"
    }
    run_targets = tuple(target for target in targets if target not in preflight_blocked_targets)

    materialize_canonical_output_tree(subject_root, output_root=output_root, mode="symlink", archive_legacy=False)
    raw = _resolve_raw_inputs(subject_root)

    for target in targets:
        if target in preflight_blocked_targets:
            tasks.append(
                ProductTaskRecord(
                    name=_task_name_for_target(target, config),
                    status="blocked",
                    reason=preflight_blocked_targets[target],
                )
            )

    if "validation" in run_targets:
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

    if "preprocessing" in run_targets:
        preprocessing_outputs = _preprocessing_outputs(subject_root, config.subject_id, output_root)
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
    segmentation = _resolve_segmentation(subject_root, output_root)
    parcellation = _resolve_parcellation(subject_root, config.subject_id, output_root)
    atlas_t2 = config.atlas_t2.expanduser().resolve() if config.atlas_t2 is not None else _default_atlas_t2()
    segmentation_outputs = _segmentation_outputs(subject_root, output_root)
    parcellation_outputs = _parcellation_outputs(subject_root, config.subject_id, output_root)
    surface_outputs = _surface_outputs(subject_root, config.subject_id, output_root)
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
    tractogram = csd_tractogram if primary_tractography_backend == "csd_act" else dti_tractogram_trk
    tractogram_trk = csd_tractogram_trk if primary_tractography_backend == "csd_act" else dti_tractogram_trk
    saf_tractogram = saf_dir / "SAF.tck"
    wma_input_tractography = _resolve_bundle_input_tractography(subject_root, config.wma_input_tractography, output_root=output_root, run_name=run_name)
    tractcloud_input_tractography = _resolve_bundle_input_tractography(subject_root, config.tractcloud_input_tractography, output_root=output_root, run_name=run_name)
    slicer_executable = _resolve_slicer_executable(config)
    ddseg_device = _resolved_device_for_execution(
        config.ddseg_device,
        execute=config.execute,
        target_will_run="segmentation" in run_targets,
    )
    surface_device = _resolved_device_for_execution(
        config.surface_device,
        execute=config.execute,
        target_will_run="surface" in run_targets,
    )
    tractcloud_device = _resolved_tractcloud_device_for_execution(
        config.tractcloud_device,
        execute=config.execute,
        target_will_run="tractcloud" in run_targets,
    )

    if "segmentation" in run_targets:
        if config.resume and _segmentation_complete(subject_root, output_root):
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
            task_started = _start_task_timer("DDSeg", log)
            raw_bundle = find_subject_root(subject_root, config.subject_id)
            native_bundle = ensure_native_dti_bundle(raw_bundle, fit_method="ls", reuse=bool(config.resume), log=log)
            run_ddseg(
                DDSegConfig(
                    input_mask_nii=raw_bundle.mask_path,
                    parameter_type="DTI",
                    output_folder=layout.ddseg,
                    weights_dir=Path(__file__).resolve().parent.parent / "segmentation" / "weights",
                    dti_feature_dir=native_bundle.bundle_dir,
                    device=ddseg_device,
                )
            )
            _finish_task_timer("DDSeg", task_started, log)
            tasks.append(
                ProductTaskRecord(
                    name="segmentation.ddseg",
                    status="completed",
                    outputs={key: path.as_posix() for key, path in segmentation_outputs.items()},
                )
            )
            segmentation = _resolve_segmentation(subject_root, output_root)

    if "parcellation" in run_targets:
        if config.resume and _parcellation_complete(subject_root, config.subject_id, output_root):
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
            task_started = _start_task_timer("DDParcel", log)
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
            _finish_task_timer("DDParcel", task_started, log)
            tasks.append(
                ProductTaskRecord(
                    name="parcellation.ddparcel",
                    status="completed",
                    outputs={key: path.as_posix() for key, path in parcellation_outputs.items()},
                )
            )
            parcellation = _resolve_parcellation(subject_root, config.subject_id, output_root)

    if "surface" in run_targets:
        if config.resume and _surface_complete(subject_root, config.subject_id, output_root):
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
                device=surface_device,
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
                task_started = _start_task_timer("DDSurfer surface", log)
                result = run_surface(surface_config, log=log)
                _finish_task_timer("DDSurfer surface", task_started, log)
                tasks.append(
                    ProductTaskRecord(
                        name="surface.ddsurfer",
                        status="completed",
                        manifest_path=result.manifest_path,
                        qc_path=result.qc_path,
                        outputs={f"model_{index}": path.as_posix() for index, path in enumerate(result.generated_models, start=1)},
                    )
                )

    if "surface_postprocess" in run_targets:
        postprocess_outputs = _surface_postprocess_outputs(subject_root, config.subject_id, output_root)
        if config.resume and _surface_postprocess_complete(subject_root, config.subject_id, output_root):
            tasks.append(
                ProductTaskRecord(
                    name="surface.ddsurfer_postprocess",
                    status="skipped",
                    reason="completed outputs found",
                    manifest_path=postprocess_outputs["manifest"],
                    qc_path=postprocess_outputs["qc"],
                    outputs={key: path.as_posix() for key, path in postprocess_outputs.items()},
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="surface.ddsurfer_postprocess", status="planned", reason="execute=False"))
        else:
            from surface import DDSurferPostprocessConfig, run_ddsurfer_postprocess

            native_dir = _resolve_optional_path(config.postprocess_native_dir)
            mri_dir = _resolve_optional_path(config.postprocess_mri_dir)
            if native_dir is not None and not native_dir.is_dir():
                tasks.append(
                    ProductTaskRecord(
                        name="surface.ddsurfer_postprocess",
                        status="blocked",
                        reason="invalid explicit postprocess inputs: postprocess_native_dir",
                    )
                )
            elif mri_dir is not None and not mri_dir.is_dir():
                tasks.append(
                    ProductTaskRecord(
                        name="surface.ddsurfer_postprocess",
                        status="blocked",
                        reason="invalid explicit postprocess inputs: postprocess_mri_dir",
                    )
                )
            else:
                _emit("[Orchestrator] Running DDSurfer postprocess", log)
                result = run_ddsurfer_postprocess(
                    DDSurferPostprocessConfig(
                        subject_id=config.subject_id,
                        subject_root=subject_root,
                        native_dir=native_dir,
                        mri_dir=mri_dir,
                        output_root=subject_layout(subject_root, output_root=output_root).outputs,
                        backend_root=_resolve_optional_path(config.postprocess_backend_root),
                        mode=config.postprocess_mode,
                        python_bin=_resolve_optional_path(config.postprocess_python_bin),
                        freesurfer_home=_resolve_optional_path(config.postprocess_freesurfer_home),
                        atlases=config.postprocess_atlases,
                        force=bool(config.postprocess_force),
                    ),
                    log=log,
                )
                tasks.append(
                    ProductTaskRecord(
                        name="surface.ddsurfer_postprocess",
                        status="completed",
                        manifest_path=result.manifest_path,
                        qc_path=result.qc_path,
                        outputs={
                            "structural_root": result.structural_root.as_posix(),
                            "stats_root": result.stats_root.as_posix(),
                            "staged_input_dir": result.staged_input_dir.as_posix(),
                        },
                    )
                )

    if "microstructure" in run_targets:
        micro_outputs = _microstructure_dti_outputs(subject_root, config.subject_id, output_root)
        freewater_outputs = _microstructure_freewater_outputs(subject_root, config.subject_id, output_root)
        noddi_outputs = _microstructure_noddi_outputs(subject_root, config.subject_id, output_root)
        if config.resume and _microstructure_dti_complete(subject_root, config.subject_id, output_root):
            outputs = {key: path.as_posix() for key, path in micro_outputs.items() if key != "manifest"}
            tasks.append(
                ProductTaskRecord(
                    name="microstructure.dti",
                    status="skipped",
                    reason="completed DTI microstructure outputs found",
                    manifest_path=micro_outputs["manifest"],
                    outputs=outputs,
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="microstructure.dti", status="planned", reason="execute=False"))
        elif any(not path.is_file() for path in raw.values()):
            missing = [label for label, path in raw.items() if not path.is_file()]
            tasks.append(ProductTaskRecord(name="microstructure.dti", status="blocked", reason="missing raw input: " + ", ".join(missing)))
        else:
            from microstructure import MicrostructureConfig, run_microstructure
            from shared.pipeline import ensure_native_dti_bundle, find_subject_root

            _emit("[Orchestrator] Running Microstructure DTI", log)
            task_started = _start_task_timer("Microstructure DTI", log)
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
                    run_free_water=False,
                    run_noddi=False,
                    free_water_chunk_size=config.microstructure_free_water_chunk_size,
                    free_water_engine=config.microstructure_free_water_engine,
                    free_water_n_jobs=config.microstructure_free_water_n_jobs,
                    free_water_vox_per_chunk=config.microstructure_free_water_vox_per_chunk,
                    force_recompute=not config.resume,
                ),
                log=log,
            )
            _finish_task_timer("Microstructure DTI", task_started, log)
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
                    },
                )
            )

    if "microstructure_freewater" in run_targets:
        freewater_outputs = _microstructure_freewater_outputs(subject_root, config.subject_id, output_root)
        if config.resume and _microstructure_freewater_complete(subject_root, config.subject_id, output_root):
            tasks.append(
                ProductTaskRecord(
                    name="microstructure.freewater",
                    status="skipped",
                    reason="completed Free Water outputs found",
                    manifest_path=freewater_outputs["manifest"],
                    outputs={key: path.as_posix() for key, path in freewater_outputs.items() if key != "manifest"},
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="microstructure.freewater", status="planned", reason="execute=False"))
        elif any(not path.is_file() for path in raw.values()):
            missing = [label for label, path in raw.items() if not path.is_file()]
            tasks.append(ProductTaskRecord(name="microstructure.freewater", status="blocked", reason="missing raw input: " + ", ".join(missing)))
        else:
            from microstructure import MicrostructureConfig, run_microstructure
            from shared.pipeline import ensure_native_dti_bundle, find_subject_root

            _emit("[Orchestrator] Running Microstructure Free Water", log)
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
                    run_free_water=True,
                    run_noddi=False,
                    free_water_chunk_size=config.microstructure_free_water_chunk_size,
                    free_water_engine=config.microstructure_free_water_engine,
                    free_water_n_jobs=config.microstructure_free_water_n_jobs,
                    free_water_vox_per_chunk=config.microstructure_free_water_vox_per_chunk,
                    force_recompute=not config.resume,
                ),
                log=log,
            )
            tasks.append(
                ProductTaskRecord(
                    name="microstructure.freewater",
                    status="completed",
                    manifest_path=freewater_outputs["manifest"],
                    outputs={
                        "fwf": result.fwf_path.as_posix(),
                        "fw_tissue_fa": result.fw_tissue_fa_path.as_posix(),
                        "fw_tissue_md": result.fw_tissue_md_path.as_posix(),
                    },
                )
            )

    if "microstructure_noddi" in run_targets:
        noddi_outputs = _microstructure_noddi_outputs(subject_root, config.subject_id, output_root)
        if config.resume and _microstructure_noddi_complete(subject_root, config.subject_id, output_root):
            tasks.append(
                ProductTaskRecord(
                    name="microstructure.noddi",
                    status="skipped",
                    reason="completed NODDI outputs found",
                    manifest_path=noddi_outputs["manifest"],
                    outputs={key: path.as_posix() for key, path in noddi_outputs.items() if key != "manifest"},
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="microstructure.noddi", status="planned", reason="execute=False"))
        elif any(not path.is_file() for path in raw.values()):
            missing = [label for label, path in raw.items() if not path.is_file()]
            tasks.append(ProductTaskRecord(name="microstructure.noddi", status="blocked", reason="missing raw input: " + ", ".join(missing)))
        else:
            from microstructure import MicrostructureConfig, run_microstructure
            from shared.pipeline import ensure_native_dti_bundle, find_subject_root

            _emit("[Orchestrator] Running Microstructure NODDI", log)
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
                    run_noddi=True,
                    free_water_chunk_size=config.microstructure_free_water_chunk_size,
                    free_water_engine=config.microstructure_free_water_engine,
                    free_water_n_jobs=config.microstructure_free_water_n_jobs,
                    free_water_vox_per_chunk=config.microstructure_free_water_vox_per_chunk,
                    force_recompute=not config.resume,
                ),
                log=log,
            )
            tasks.append(
                ProductTaskRecord(
                    name="microstructure.noddi",
                    status="completed",
                    manifest_path=noddi_outputs["manifest"],
                    outputs={
                        "noddi_ndi": result.noddi_ndi_path.as_posix(),
                        "noddi_odi": result.noddi_odi_path.as_posix(),
                        "noddi_fwf": result.noddi_fwf_path.as_posix(),
                    },
                )
            )

    if "tractography" in run_targets:
        tractography_qc = csd_qc if primary_tractography_backend == "csd_act" else dti_qc
        tractography_manifest = csd_dir / "csd_act_manifest.json" if primary_tractography_backend == "csd_act" else dti_manifest
        tractography_task_name = "tractography.csd_act" if primary_tractography_backend == "csd_act" else "tractography.dti_det"
        if config.resume and _qc_completed(tractography_qc) and tractogram_trk.is_file() and (
            primary_tractography_backend != "csd_act" or csd_tractogram.is_file()
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
        elif primary_tractography_backend == "csd_act" and segmentation is None:
            tasks.append(ProductTaskRecord(name=tractography_task_name, status="blocked", reason="missing DDSeg segmentation"))
        else:
            if primary_tractography_backend == "csd_act":
                from tractography.act_prep import ACTPrepConfig, run_act_prep
                from tractography.csd import CSDActConfig, run_csd_act

                _emit(f"[Orchestrator] Running CSD/ACT {run_name}", log)
                task_started = _start_task_timer(f"CSD/ACT {run_name}", log)
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
                _finish_task_timer(f"CSD/ACT {run_name}", task_started, log)
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
                task_started = _start_task_timer(f"DTI tractography {run_name}", log)
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
                _finish_task_timer(f"DTI tractography {run_name}", task_started, log)
                tasks.append(
                    ProductTaskRecord(
                        name=tractography_task_name,
                        status="completed",
                        manifest_path=result.manifest_path,
                        qc_path=result.qc_path,
                        outputs={"tractogram_trk": result.streamlines_path.as_posix()},
                    )
                )

    if "bundles" in run_targets:
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
            task_started = _start_task_timer(f"WMQL bundles {run_name}", log)
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
            _finish_task_timer(f"WMQL bundles {run_name}", task_started, log)
            tasks.append(_task_from_result("bundles.wmql", result))

    if "saf" in run_targets:
        saf_qc = saf_dir / "saf_qc.json"
        if config.resume and _qc_completed(saf_qc) and saf_tractogram.is_file():
            saf_qc_data = _read_json(saf_qc)
            saf_vtk = saf_dir / "SAF.vtk"
            streamline_count = saf_qc_data.get("streamline_count")
            tasks.append(
                ProductTaskRecord(
                    name="tractography.saf",
                    status="skipped",
                    reason="completed outputs found",
                    qc_path=saf_qc,
                    manifest_path=saf_dir / "saf_manifest.json",
                    outputs={
                        "tractogram": saf_tractogram.as_posix(),
                        "tractogram_vtk": saf_vtk.as_posix() if saf_vtk.is_file() else None,
                        "streamline_count": str(streamline_count) if streamline_count is not None else None,
                    },
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="tractography.saf", status="planned", reason="execute=False"))
        else:
            fod_candidate = csd_dir / f"{config.subject_id}_wmfod_norm.mif"
            fod_path = fod_candidate if fod_candidate.is_file() else (csd_dir / f"{config.subject_id}_wmfod.mif")
            fs_dir = _resolve_optional_path(config.saf_fs_dir)
            if fs_dir is None:
                fs_dir = _surface_postprocess_saf_fs_dir(subject_root, config.subject_id, output_root)
            pregenerated_tractogram = _resolve_optional_path(config.saf_pregenerated_tractogram)
            saf_tckgen_options = config.saf_tckgen_options
            saf_maxlen = 40.0
            if pregenerated_tractogram is None:
                preproc_outputs = _preprocessing_outputs(subject_root, config.subject_id, output_root)
                seed_mask = preproc_outputs["mask"] if preproc_outputs["mask"].is_file() else raw["mask"]
                if not seed_mask.is_file():
                    tasks.append(
                        ProductTaskRecord(
                            name="tractography.saf",
                            status="blocked",
                            reason="missing pregenerated tractogram and no brain mask available for SAF tckgen",
                        )
                    )
                    seed_mask = None
                elif not saf_tckgen_options.strip():
                    saf_tckgen_options = (
                        f"-seed_image {seed_mask.expanduser().resolve().as_posix()} "
                        "-cutoff 0.05 -select 1000000 -maxlength 40"
                    )
            if fs_dir is None:
                tasks.append(
                    ProductTaskRecord(
                        name="tractography.saf",
                        status="blocked",
                        reason="missing --saf-fs-dir or completed whole DDSurfer postprocess outputs",
                    )
                )
            elif not fod_path.is_file():
                tasks.append(ProductTaskRecord(name="tractography.saf", status="blocked", reason="missing CSD FOD output for SAF"))
            elif pregenerated_tractogram is None and 'seed_mask' in locals() and seed_mask is None:
                pass
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
                        tckgen_options=saf_tckgen_options,
                        mrtrix_bin_dir=config.mrtrix_bin_dir,
                        mrtrix_prefix=config.saf_mrtrix_prefix,
                        noregister=config.saf_noregister,
                        maxlen=saf_maxlen,
                        force_recompute=not config.resume,
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
                        outputs={
                            "tractogram": result.saf_tractogram.as_posix(),
                            "tractogram_vtk": result.saf_vtk_path.as_posix() if result.saf_vtk_path else None,
                            "streamline_count": str(result.streamline_count) if result.streamline_count is not None else None,
                        },
                    )
                )

    if "wma" in run_targets:
        wma_qc = wma_dir / "wma_org_atlas_qc.json"
        anatomical_tract_count = _wma_anatomical_tract_count(wma_dir) if config.resume and _qc_completed(wma_qc) else 0
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
        elif not config.execute:
            reason = "execute=False"
            if config.resume and _qc_completed(wma_qc):
                reason = "execute=False; existing QC present but anatomical tracts missing"
            tasks.append(ProductTaskRecord(name="bundles.wma", status="planned", reason=reason))
        else:
            wma_input_tractography = _resolve_bundle_input_tractography(
                subject_root,
                config.wma_input_tractography,
                output_root=output_root,
                run_name=run_name,
            )
            if anatomical_tract_count > 0:
                tasks.append(ProductTaskRecord(name="bundles.wma", status="skipped", reason="completed outputs found", qc_path=wma_qc, manifest_path=wma_dir / "wma_org_atlas_manifest.json", outputs={"anatomical_tract_count": str(anatomical_tract_count)}))
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

    if "tractcloud" in run_targets:
        tractcloud_qc = tractcloud_dir / "tractcloud_qc.json"
        output_summary = {"bundle_count": 0}
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
        elif not config.execute:
            reason = "execute=False"
            if config.resume and _qc_completed(tractcloud_qc):
                reason = "execute=False; existing QC present but no bundle outputs found"
            tasks.append(ProductTaskRecord(name="bundles.tractcloud", status="planned", reason=reason))
        else:
            tractcloud_input_tractography = _resolve_bundle_input_tractography(
                subject_root,
                config.tractcloud_input_tractography,
                output_root=output_root,
                run_name=run_name,
            )
            if tractcloud_input_tractography is None:
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
                        device=tractcloud_device,
                        batch_size=config.tractcloud_batch_size,
                        execute=True,
                    ),
                    log=log,
                )
                tasks.append(_task_from_result("bundles.tractcloud", result))

    if "connectome" in run_targets:
        weighted_connectome_handled = False
        conn_qc = connectome_dir / f"{config.subject_id}-connectome-streamline_count_qc.json"
        if config.resume and _qc_completed(conn_qc):
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="skipped", reason="completed outputs found", qc_path=conn_qc, manifest_path=connectome_dir / f"{config.subject_id}-connectome-streamline_count_manifest.json"))
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="planned", reason="execute=False"))
        elif parcellation is None:
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="blocked", reason="missing parcellation"))
        elif primary_tractography_backend == "csd_act" and not tractogram.is_file():
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="blocked", reason="missing TCK tractogram"))
        elif primary_tractography_backend != "csd_act" and config.connectome_backend == "mrtrix":
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="blocked", reason="DTI tractography currently supports python connectome backend only"))
        elif not tractogram.is_file():
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="blocked", reason="missing tractogram"))
        else:
            from connectome import ConnectomeConfig, run_connectome

            _emit(f"[Orchestrator] Running connectome {run_name}", log)
            task_started = _start_task_timer(f"connectome {run_name}", log)
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
            _finish_task_timer(f"connectome {run_name}", task_started, log)
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

    manifest_path = layout.run_metadata / f"{run_name}_orchestration_manifest.json"
    normalized_task_records = _write_normalized_task_records(
        layout=layout,
        run_name=run_name,
        config=config,
        tasks=tasks,
        plan=plan,
        orchestration_manifest_path=manifest_path,
    )
    archived_outputs = archive_development_outputs(
        subject_root,
        output_root=output_root,
        current_run_name=run_name,
        current_tractography_backend=primary_tractography_backend,
    )
    output_tree_audit = _audit_output_tree(layout, subject_id=config.subject_id, selected_targets=targets)
    output_tree_semantics = _write_output_tree_semantics(
        layout=layout,
        subject_id=config.subject_id,
        requested_targets=targets,
        run_targets=run_targets,
        tasks=tasks,
    )
    task_payloads = []
    for task in tasks:
        payload = {
            "name": task.name,
            "status": task.status,
            "reason": task.reason,
            "manifest_path": task.manifest_path.as_posix() if task.manifest_path else None,
            "qc_path": task.qc_path.as_posix() if task.qc_path else None,
            "outputs": task.outputs,
            "started_at": task.started_at,
            "ended_at": task.ended_at,
            "runtime_seconds": task.runtime_seconds,
        }
        payload.update(
            {
                f"normalized_{key}": value
                for key, value in normalized_task_records.get(task.name, {}).items()
            }
        )
        task_payloads.append(payload)

    elapsed_seconds = time.monotonic() - start
    performance_profile = _build_performance_profile(
        layout=layout,
        run_name=run_name,
        tasks=tasks,
        orchestration_elapsed_seconds=elapsed_seconds,
    )

    manifest = {
        "kind": "slicerddsurfer_product_orchestration",
        "version": 1,
        "subject_id": config.subject_id,
        "subject_root": subject_root.as_posix(),
        "output_root": output_root.as_posix() if output_root is not None else layout.outputs.as_posix(),
        "targets": list(targets),
        "run_targets": list(run_targets),
        "run_plan_path": plan.run_plan_path.as_posix(),
        "run_plan_summary": plan.to_dict()["summary"],
        "output_tree_audit_path": output_tree_audit.get("path"),
        "output_tree_warnings": output_tree_audit.get("warnings", []),
        "output_tree_semantics_path": output_tree_semantics.get("path"),
        "output_tree_semantics_summary": {
            "states": {
                state: sum(1 for entry in output_tree_semantics.get("entries", []) if entry.get("state") == state)
                for state in sorted({entry.get("state") for entry in output_tree_semantics.get("entries", [])})
            }
        },
        "archived_development_outputs": {key: value.as_posix() for key, value in archived_outputs.items()},
        "preflight_blocked_targets": preflight_blocked_targets,
        "run_name": run_name,
        "tractography_backend": config.tractography_backend,
        "primary_tractography_backend": primary_tractography_backend,
        "bundle_backend": config.bundle_backend,
        "bundle_backends": list(bundle_backends),
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
        "microstructure_free_water_chunk_size": config.microstructure_free_water_chunk_size,
        "microstructure_free_water_engine": config.microstructure_free_water_engine,
        "microstructure_free_water_n_jobs": config.microstructure_free_water_n_jobs,
        "microstructure_free_water_vox_per_chunk": config.microstructure_free_water_vox_per_chunk,
        "microstructure_stages": [
            stage
            for stage, enabled in (
                ("dti", True),
                ("freewater", config.microstructure_run_free_water),
                ("noddi", config.microstructure_run_noddi),
            )
            if enabled
        ],
        "postprocess_native_dir": config.postprocess_native_dir.expanduser().resolve().as_posix() if config.postprocess_native_dir else None,
        "postprocess_mri_dir": config.postprocess_mri_dir.expanduser().resolve().as_posix() if config.postprocess_mri_dir else None,
        "postprocess_backend_root": config.postprocess_backend_root.expanduser().resolve().as_posix() if config.postprocess_backend_root else None,
        "postprocess_mode": config.postprocess_mode,
        "postprocess_python_bin": config.postprocess_python_bin.expanduser().resolve().as_posix() if config.postprocess_python_bin else None,
        "postprocess_freesurfer_home": config.postprocess_freesurfer_home.expanduser().resolve().as_posix() if config.postprocess_freesurfer_home else None,
        "postprocess_atlases": list(config.postprocess_atlases) if config.postprocess_atlases else None,
        "postprocess_force": config.postprocess_force,
        "atlas_t2": atlas_t2.as_posix(),
        "ddseg_device": config.ddseg_device,
        "surface_device": config.surface_device,
        "resolved_ddseg_device": ddseg_device,
        "resolved_surface_device": surface_device,
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
        "resolved_tractcloud_device": tractcloud_device,
        "tractcloud_batch_size": config.tractcloud_batch_size,
        "elapsed_seconds": elapsed_seconds,
        "performance_profile_path": performance_profile.get("path"),
        "performance_profile": performance_profile,
        "tasks": task_payloads,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        from shared.output_tree_report import write_output_tree_report

        output_tree_report_paths = write_output_tree_report(
            output_root=layout.outputs,
            destination=layout.slicer_scene_report / f"{run_name}_output_tree.html",
            latest_destination=layout.slicer_scene_report / "output_tree.html",
            subject_id=config.subject_id,
            run_name=run_name,
        )
        manifest["output_tree_report_paths"] = output_tree_report_paths.to_dict()
    except Exception as exc:  # pragma: no cover - report generation must not break pipeline execution
        manifest["output_tree_report_error"] = str(exc)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        from shared.reporting import write_subject_reports

        report_paths = write_subject_reports(
            subject_root=subject_root,
            output_root=output_root,
            manifest_path=manifest_path,
            run_name=run_name,
        )
        manifest["report_paths"] = report_paths.to_dict()
        refreshed_output_tree_audit = _audit_output_tree(layout, subject_id=config.subject_id, selected_targets=targets)
        refreshed_output_tree_semantics = _write_output_tree_semantics(
            layout=layout,
            subject_id=config.subject_id,
            requested_targets=targets,
            run_targets=run_targets,
            tasks=tasks,
        )
        manifest["output_tree_audit_path"] = refreshed_output_tree_audit.get("path")
        manifest["output_tree_warnings"] = refreshed_output_tree_audit.get("warnings", [])
        manifest["output_tree_semantics_path"] = refreshed_output_tree_semantics.get("path")
        manifest["output_tree_semantics_summary"] = {
            "states": {
                state: sum(
                    1
                    for entry in refreshed_output_tree_semantics.get("entries", [])
                    if entry.get("state") == state
                )
                for state in sorted({entry.get("state") for entry in refreshed_output_tree_semantics.get("entries", [])})
            }
        }
    except Exception as exc:  # pragma: no cover - reporting must not break pipeline execution
        manifest["report_error"] = str(exc)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ProductOrchestratorResult(
        subject_id=config.subject_id,
        subject_root=subject_root,
        run_manifest_path=manifest_path,
        tasks=tuple(tasks),
        run_plan_path=plan.run_plan_path,
    )
