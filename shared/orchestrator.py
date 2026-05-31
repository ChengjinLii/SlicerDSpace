"""Lightweight subject-root product orchestrator with resume support.

This is intentionally small: it gives the Slicer UI one backend entrypoint for
target-product execution while leaving each product pipeline responsible for its
own scientific details and manifest/QC files.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from shared.io_layout import materialize_canonical_output_tree, subject_layout
from shared.validation import InputValidationConfig, validate_subject_inputs


SUPPORTED_TARGETS = {
    "validation",
    "segmentation",
    "parcellation",
    "surface",
    "microstructure",
    "tractography",
    "bundles",
    "connectome",
}


@dataclass(frozen=True)
class ProductOrchestratorConfig:
    subject_id: str
    subject_root: Path
    targets: tuple[str, ...]
    output_root: Optional[Path] = None
    run_name: str = "csd_act"
    execute: bool = False
    resume: bool = True
    microstructure_fit_method: str = "wls"
    atlas_t2: Optional[Path] = None
    ddseg_device: str = "cpu"
    select_streamlines: int = 1000
    mrtrix_bin_dir: Optional[Path] = None
    tract_querier_root: Optional[Path] = None
    connectome_backend: str = "python"
    connectome_compress_mrtrix_dense: bool = False


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


def _microstructure_dti_outputs(subject_root: Path, subject_id: str) -> dict[str, Path]:
    layout = subject_layout(subject_root)
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


def _microstructure_dti_complete(subject_root: Path, subject_id: str) -> bool:
    return all(path.is_file() for path in _microstructure_dti_outputs(subject_root, subject_id).values())


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
    if config.connectome_backend not in {"python", "mrtrix"}:
        raise ValueError("connectome_backend must be one of: python, mrtrix.")

    targets = _normalize_targets(config.targets)
    subject_root = config.subject_root.expanduser().resolve()
    output_root = config.output_root.expanduser().resolve() if config.output_root is not None else None
    layout = subject_layout(subject_root, output_root=output_root)
    run_name = config.run_name.strip().replace("/", "_") or "csd_act"
    tasks: list[ProductTaskRecord] = []
    start = time.monotonic()

    materialize_canonical_output_tree(subject_root, output_root=output_root, mode="symlink", archive_legacy=False)

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

    raw = _resolve_raw_inputs(subject_root)
    segmentation = _resolve_segmentation(subject_root)
    parcellation = _resolve_parcellation(subject_root, config.subject_id)
    atlas_t2 = config.atlas_t2.expanduser().resolve() if config.atlas_t2 is not None else _default_atlas_t2()
    segmentation_outputs = _segmentation_outputs(subject_root)
    parcellation_outputs = _parcellation_outputs(subject_root, config.subject_id)
    surface_outputs = _surface_outputs(subject_root, config.subject_id)
    micro_outputs = _microstructure_dti_outputs(subject_root, config.subject_id)
    csd_dir = layout.csd if run_name == "csd_act" else layout.tractography / run_name
    tractogram_dir = layout.tractograms / run_name
    wmql_dir = layout.bundles_wmql / run_name
    connectome_dir = layout.connectome / run_name
    sift2_connectome_dir = layout.connectome / f"{run_name}_sift2"
    csd_qc = csd_dir / "csd_act_qc.json"
    tractogram = tractogram_dir / f"{config.subject_id}_csd_act_ifod2.tck"
    tractogram_trk = tractogram.with_suffix(".trk")
    sift2_weights = tractogram.with_name(f"{tractogram.stem}_sift2_weights.txt")

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
        if config.resume and _microstructure_dti_complete(subject_root, config.subject_id):
            tasks.append(
                ProductTaskRecord(
                    name="microstructure.dti",
                    status="skipped",
                    reason="completed DTI outputs found",
                    manifest_path=micro_outputs["manifest"],
                    outputs={key: path.as_posix() for key, path in micro_outputs.items() if key != "manifest"},
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
                    },
                )
            )

    if "tractography" in targets:
        if config.resume and _qc_completed(csd_qc) and tractogram.is_file() and tractogram_trk.is_file():
            tasks.append(
                ProductTaskRecord(
                    name="tractography.csd_act",
                    status="skipped",
                    reason="completed outputs found",
                    qc_path=csd_qc,
                    manifest_path=csd_dir / "csd_act_manifest.json",
                    outputs={"tractogram": tractogram.as_posix(), "tractogram_trk": tractogram_trk.as_posix()},
                )
            )
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="tractography.csd_act", status="planned", reason="execute=False"))
        elif segmentation is None:
            tasks.append(ProductTaskRecord(name="tractography.csd_act", status="blocked", reason="missing DDSeg segmentation"))
        elif any(not path.is_file() for path in raw.values()):
            missing = [label for label, path in raw.items() if not path.is_file()]
            tasks.append(ProductTaskRecord(name="tractography.csd_act", status="blocked", reason="missing raw input: " + ", ".join(missing)))
        else:
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
                    name="tractography.csd_act",
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

    if "connectome" in targets:
        weighted_connectome_handled = False
        conn_qc = connectome_dir / f"{config.subject_id}-connectome-streamline_count_qc.json"
        if config.resume and _qc_completed(conn_qc):
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="skipped", reason="completed outputs found", qc_path=conn_qc, manifest_path=connectome_dir / f"{config.subject_id}-connectome-streamline_count_manifest.json"))
        elif not config.execute:
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="planned", reason="execute=False"))
        elif parcellation is None:
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="blocked", reason="missing parcellation"))
        elif not tractogram.is_file():
            tasks.append(ProductTaskRecord(name="connectome.streamline_count", status="blocked", reason="missing TCK tractogram"))
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
        "execute": config.execute,
        "resume": config.resume,
        "microstructure_fit_method": config.microstructure_fit_method,
        "atlas_t2": atlas_t2.as_posix(),
        "ddseg_device": config.ddseg_device,
        "select_streamlines": config.select_streamlines,
        "connectome_backend": config.connectome_backend,
        "connectome_compress_mrtrix_dense": config.connectome_compress_mrtrix_dense,
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
