"""Headless DDSurfer surface pipeline facade."""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from shared import ensure_registered_dti_bundle, find_subject_root, inspect_subject_directory
from shared.model_assets import model_asset_candidates

from .preprocessing import SubjectPreprocessingConfig, preprocess_subject


@dataclass(frozen=True)
class SurfaceConfig:
    subject_id: str
    subject_root: Path
    output_dir: Path
    predict_mode: str = "all"
    device: str = "cpu"
    template_dir: Optional[Path] = None
    checkpoint_root: Optional[Path] = None
    registration_atlas: Optional[Path] = None
    model_assets_dir: Optional[Path] = None
    cleanup_intermediates: bool = False
    execute: bool = False
    # DWI bundle to derive the registered DTI inputs from. None = the raw
    # subject input. The orchestrator passes the preprocessed bundle when
    # preprocessing ran, so surfaces share the tractography space.
    input_bundle: Optional[object] = None


@dataclass(frozen=True)
class SurfaceResult:
    subject_id: str
    output_dir: Path
    manifest_path: Path
    qc_path: Path
    generated_models: tuple[Path, ...]
    executed: bool


METRIC_PATTERNS = {
    "FractionalAnisotropy": "{subject_id}-dti-FractionalAnisotropy-Reg.nii.gz",
    "MinEigenvalue": "{subject_id}-dti-MinEigenvalue-Reg.nii.gz",
    "MidEigenvalue": "{subject_id}-dti-MidEigenvalue-Reg.nii.gz",
    "MaxEigenvalue": "{subject_id}-dti-MaxEigenvalue-Reg.nii.gz",
    "Trace": "{subject_id}-dti-Trace-Reg.nii.gz",
    "MeanDiffusivity": "{subject_id}-dti-MeanDiffusivity-Reg.nii.gz",
}


def _emit(message: str, log: Optional[Callable[[str], None]] = None) -> None:
    if log:
        log(message)


def _module_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _first_existing(candidates: list[Path], *, required_child: Optional[Path] = None) -> Optional[Path]:
    for candidate in candidates:
        candidate = candidate.expanduser()
        required = candidate / required_child if required_child is not None else candidate
        if required.exists():
            return candidate.resolve()
    return None


def resolve_surface_template_dir(
    template_dir: Optional[Path] = None,
    *,
    model_assets_dir: Optional[Path] = None,
) -> Optional[Path]:
    candidates: list[Path] = []
    if template_dir is not None:
        candidates.append(template_dir)
    env_template = os.environ.get("DDSURFER_TEMPLATE_DIR")
    if env_template:
        candidates.append(Path(env_template))
    root = _module_root()
    candidates.extend(model_asset_candidates("Resources/Data/template", repo_root=root, explicit_root=model_assets_dir))
    candidates.extend(
        [
            root / "Resources" / "Data" / "template",
            root / "Resources" / "template",
            root / "surface" / "template",
            root / "template",
            root.parent / "template",
        ]
    )
    return _first_existing(candidates, required_child=Path("100307-FA.nii.gz"))


def resolve_surface_checkpoint_root(
    checkpoint_root: Optional[Path] = None,
    *,
    model_assets_dir: Optional[Path] = None,
) -> Optional[Path]:
    candidates: list[Path] = []
    if checkpoint_root is not None:
        candidates.append(checkpoint_root)
    env_ckpt = os.environ.get("DDSURFER_CHECKPOINT_DIR")
    if env_ckpt:
        candidates.append(Path(env_ckpt))
    root = _module_root()
    candidates.extend(model_asset_candidates("Resources/Data/ckpts", repo_root=root, explicit_root=model_assets_dir))
    candidates.extend(
        [
            root / "Resources" / "Data" / "ckpts",
            root / "Resources" / "ckpts",
            root / "surface" / "ckpts",
            root / "ckpts",
            root.parent / "ckpts",
        ]
    )
    return _first_existing(candidates, required_child=Path("hcp"))


def resolve_surface_registration_atlas(
    registration_atlas: Optional[Path] = None,
    *,
    model_assets_dir: Optional[Path] = None,
) -> Optional[Path]:
    candidates: list[Path] = []
    if registration_atlas is not None:
        candidates.append(registration_atlas)
    env_atlas = os.environ.get("DDSURFER_REGISTRATION_ATLAS")
    if env_atlas:
        candidates.append(Path(env_atlas))
    root = _module_root()
    candidates.extend(
        model_asset_candidates(
            "Resources/Data/100HCP-population-mean-T2.nii.gz",
            repo_root=root,
            explicit_root=model_assets_dir,
        )
    )
    candidates.extend(
        [
            root / "Resources" / "Data" / "100HCP-population-mean-T2.nii.gz",
            root / "Resources" / "100HCP-population-mean-T2.nii.gz",
        ]
    )
    return _first_existing(candidates)


def inspect_surface_resources(config: SurfaceConfig) -> dict[str, object]:
    template_dir = resolve_surface_template_dir(config.template_dir, model_assets_dir=config.model_assets_dir)
    checkpoint_root = resolve_surface_checkpoint_root(config.checkpoint_root, model_assets_dir=config.model_assets_dir)
    registration_atlas = resolve_surface_registration_atlas(
        config.registration_atlas,
        model_assets_dir=config.model_assets_dir,
    )
    checkpoint_paths: list[Path] = []
    if checkpoint_root is not None:
        hcp_dir = checkpoint_root / "hcp"
        checkpoint_paths = [
            hcp_dir / "DDCSR_white_lh_Full_DualStream_no_b0_Cascaded.pt",
            hcp_dir / "DDCSR_white_rh_Full_DualStream_no_b0_Cascaded.pt",
            hcp_dir / "DDCSR_pial_lh_Full_DualStream_no_b0_Cascaded.pt",
            hcp_dir / "DDCSR_pial_rh_Full_DualStream_no_b0_Cascaded.pt",
        ]
    template_paths: list[Path] = []
    if template_dir is not None:
        template_paths = [
            template_dir / "100307-FA.nii.gz",
            template_dir / "hcp_hemi-left_init_160k.obj",
            template_dir / "hcp_hemi-right_init_160k.obj",
        ]
    missing = [path.as_posix() for path in checkpoint_paths + template_paths if not path.exists()]
    if registration_atlas is None:
        missing.append("registration_atlas")
    return {
        "available": not missing and template_dir is not None and checkpoint_root is not None and registration_atlas is not None,
        "template_dir": template_dir.as_posix() if template_dir else None,
        "checkpoint_root": checkpoint_root.as_posix() if checkpoint_root else None,
        "registration_atlas": registration_atlas.as_posix() if registration_atlas else None,
        "missing": missing,
    }


def _resolve_surface_inputs(config: SurfaceConfig, registration_atlas: Path, log: Optional[Callable[[str], None]]) -> tuple[dict[str, Path], Path, Path]:
    inspected = inspect_subject_directory(config.subject_root.expanduser().resolve(), config.subject_id)
    if inspected["mode"] == "missing":
        raise FileNotFoundError(f"Unable to resolve subject root for {config.subject_id}: {config.subject_root}")
    subject_dir = Path(inspected["subject_dir"]).resolve()
    if inspected["mode"] == "subject_root":
        raw_bundle = config.input_bundle or find_subject_root(config.subject_root, config.subject_id)
        registered = ensure_registered_dti_bundle(raw_bundle, atlas_t2=registration_atlas, fit_method="wls", reuse=True, log=log)
        return (
            {
                "FractionalAnisotropy": registered.fa_reg_path,
                "MinEigenvalue": registered.min_eig_reg_path,
                "MidEigenvalue": registered.mid_eig_reg_path,
                "MaxEigenvalue": registered.max_eig_reg_path,
                "Trace": registered.trace_reg_path,
                "MeanDiffusivity": registered.mean_diffusivity_reg_path,
            },
            registered.mask_reg_path,
            registered.transform_path,
        )

    def resolve_default(filename: str) -> Path:
        return subject_dir / filename.replace("{subject_id}", config.subject_id)

    metric_paths = {metric: resolve_default(pattern) for metric, pattern in METRIC_PATTERNS.items()}
    mask_path = resolve_default("{subject_id}-mask-Reg.nii.gz")
    transform_path = resolve_default("{subject_id}-b0ToAtlasT2.tfm")
    missing = [path for path in list(metric_paths.values()) + [mask_path, transform_path] if not path.exists()]
    if missing:
        raise FileNotFoundError("Required DDSurfer input files missing:\n" + "\n".join(path.as_posix() for path in missing))
    return metric_paths, mask_path, transform_path


def _cleanup_intermediates(work_root: Path, *, keep_native: bool) -> None:
    for name in ("raw", "preprocessed"):
        path = work_root / name
        if path.exists():
            shutil.rmtree(path)
    if not keep_native:
        predictions = work_root / "pred_results_SlicerDDSurfer"
        if predictions.exists():
            shutil.rmtree(predictions)


def run_surface(config: SurfaceConfig, *, log: Optional[Callable[[str], None]] = None) -> SurfaceResult:
    if not config.subject_id.strip():
        raise ValueError("subject_id is required.")
    if config.predict_mode not in {"all", "wm"}:
        raise ValueError("predict_mode must be one of: all, wm.")

    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "surface_manifest.json"
    qc_path = output_dir / "surface_qc.json"
    resources = inspect_surface_resources(config)
    manifest = {
        "kind": "ddsurfer_surface",
        "version": 1,
        "subject_id": config.subject_id,
        "subject_root": config.subject_root.expanduser().resolve().as_posix(),
        "input_dwi": (
            Path(str(config.input_bundle.dwi_path)).resolve().as_posix()  # type: ignore[union-attr]
            if config.input_bundle is not None
            else None
        ),
        "output_dir": output_dir.as_posix(),
        "predict_mode": config.predict_mode,
        "device": config.device,
        "executed": False,
        "status": "planned",
        "resources": resources,
        "outputs": {},
    }
    qc = {
        "subject_id": config.subject_id,
        "status": "planned",
        "executed": False,
        "model_count": 0,
        "elapsed_seconds": 0.0,
        "error": None,
    }
    generated_models: list[Path] = []
    start = time.monotonic()
    execution_error: Optional[str] = None
    if config.execute:
        if not resources["available"]:
            raise FileNotFoundError("DDSurfer surface resources are incomplete: " + ", ".join(resources["missing"]))  # type: ignore[index]
        manifest["executed"] = True
        manifest["status"] = "running"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            from .postprocessing import PostprocessingConfig, convert_meshes_to_native_space
            from .prediction import PredictionStageConfig, predict_subject

            template_dir = Path(str(resources["template_dir"]))
            checkpoint_root = Path(str(resources["checkpoint_root"]))
            registration_atlas = Path(str(resources["registration_atlas"]))
            metric_paths, mask_path, transform_path = _resolve_surface_inputs(config, registration_atlas, log)
            preprocess = preprocess_subject(
                SubjectPreprocessingConfig(
                    subject_id=config.subject_id,
                    metric_paths=metric_paths,
                    mask_path=mask_path,
                    transform_path=transform_path,
                    work_dir=output_dir,
                    template_volume_path=template_dir / "100307-FA.nii.gz",
                )
            )
            predictions = []
            predictions_root = output_dir / "pred_results_SlicerDDSurfer"
            for hemisphere in ("left", "right"):
                _emit(f"[Surface] Running DDSurfer prediction for {hemisphere}", log)
                predictions.append(
                    predict_subject(
                        PredictionStageConfig(
                            subject_id=config.subject_id,
                            hemisphere=hemisphere,
                            predict_mode=config.predict_mode,
                            device=config.device,
                            step_size=0.02,
                            n_svf=2,
                            n_res=3,
                            template_dir=template_dir,
                            checkpoint_root=checkpoint_root,
                            input_root=preprocess.preprocessed_dir.parent,
                            output_root=predictions_root,
                        )
                    )
                )
            native_outputs = convert_meshes_to_native_space(
                PostprocessingConfig(
                    subject_id=config.subject_id,
                    transform_path=preprocess.transform_copy_path,
                    predictions_root=predictions_root,
                ),
                predictions,
            )
            for paths in native_outputs.values():
                generated_models.extend(path for path in paths if not path.name.endswith("_orig.stl"))
            if config.cleanup_intermediates:
                _cleanup_intermediates(output_dir, keep_native=True)
        except Exception as exc:
            execution_error = str(exc)
        finally:
            qc.update(
                {
                    "status": "failed" if execution_error else "completed",
                    "executed": True,
                    "model_count": len(generated_models),
                    "elapsed_seconds": time.monotonic() - start,
                    "error": execution_error,
                }
            )
            manifest["status"] = qc["status"]
            manifest["outputs"] = {"models": [path.as_posix() for path in generated_models]}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    qc_path.write_text(json.dumps(qc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if execution_error is not None:
        raise RuntimeError(f"DDSurfer surface execution failed: {execution_error}")
    _emit(f"[Surface] Manifest: {manifest_path}", log)
    return SurfaceResult(
        subject_id=config.subject_id,
        output_dir=output_dir,
        manifest_path=manifest_path,
        qc_path=qc_path,
        generated_models=tuple(generated_models),
        executed=config.execute,
    )
