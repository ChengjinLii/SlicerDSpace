#!/usr/bin/env python3
"""Unified CLI entrypoint for subject-root SlicerDDSurfer execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared import ProductOrchestratorConfig, run_subject_products


DEFAULT_PRODUCT_TARGETS = (
    "preprocessing",
    "segmentation",
    "parcellation",
    "surface",
    "microstructure",
    "tractography",
    "bundles",
    "connectome",
)
OPTIONAL_ALGORITHM_TARGETS = (
    "saf",
    "wma",
    "tractcloud",
)
ALL_CLI_TARGETS = ("validation",) + DEFAULT_PRODUCT_TARGETS + OPTIONAL_ALGORITHM_TARGETS


def _split_csv_or_repeat(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    items: list[str] = []
    for value in values:
        for token in value.split(","):
            token = token.strip().lower()
            if token:
                items.append(token)
    return tuple(items)


def _infer_subject_id(subject_root: Path) -> str:
    return subject_root.resolve().name


def _resolve_targets(args: argparse.Namespace) -> tuple[str, ...]:
    include = list(_split_csv_or_repeat(args.targets))
    exclude = set(_split_csv_or_repeat(args.skip_targets))

    if args.all:
        include = list(DEFAULT_PRODUCT_TARGETS)
    elif not include:
        include = ["microstructure", "tractography", "bundles", "connectome"]

    if args.with_validation:
        include = ["validation", *include]

    resolved: list[str] = []
    seen: set[str] = set()
    for target in include:
        if target == "all":
            for expanded in DEFAULT_PRODUCT_TARGETS:
                if expanded not in seen and expanded not in exclude:
                    resolved.append(expanded)
                    seen.add(expanded)
            continue
        if target not in seen and target not in exclude:
            resolved.append(target)
            seen.add(target)
    return tuple(resolved)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run SlicerDDSurfer from one subject-root entrypoint. "
            "Use --all for the full product tree, or --targets/--skip-targets to customize."
        )
    )
    parser.add_argument("--subject-root", required=True, type=Path, help="Subject root directory.")
    parser.add_argument("--subject-id", help="Optional subject id. Defaults to the subject-root directory name.")
    parser.add_argument("--output-root", type=Path, help="Optional output root. Defaults to <subject-root>/outputs.")
    parser.add_argument("--run-name", default="csd_act", help="Run name used for tractography/connectome subtrees.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run the full product tree: segmentation, parcellation, surface, microstructure, tractography, bundles, connectome.",
    )
    parser.add_argument(
        "--targets",
        action="append",
        help=(
            "Targets to include. May be repeated or comma-separated. "
            f"Choices: {', '.join(ALL_CLI_TARGETS)}."
        ),
    )
    parser.add_argument(
        "--skip-targets",
        action="append",
        help="Targets to skip. May be repeated or comma-separated.",
    )
    parser.add_argument("--with-validation", action="store_true", help="Also run shared input validation.")
    parser.add_argument("--execute", action="store_true", help="Actually execute workflows. Default is dry-run planning only.")
    parser.add_argument("--no-resume", action="store_true", help="Disable resume/skip of completed outputs.")
    parser.add_argument(
        "--preprocessing-backend",
        default="dipy",
        choices=("dipy", "mrtrix_fsl"),
        help="Optional DWI preprocessing backend.",
    )
    parser.add_argument("--preprocessing-force", action="store_true", help="Force rerun preprocessing even if outputs exist.")
    parser.add_argument("--preprocessing-mrtrix-bin-dir", type=Path, help="Optional MRtrix3 bin dir for preprocessing.")
    parser.add_argument("--preprocessing-fsl-bin-dir", type=Path, help="Optional FSL bin dir for preprocessing.")
    parser.add_argument("--preprocessing-reverse-phase-b0", type=Path, help="Optional reverse phase-encoding b0 for MRtrix/FSL preprocessing.")
    parser.add_argument("--preprocessing-phase-encoding-direction", help="Optional phase encoding direction for MRtrix/FSL preprocessing.")
    parser.add_argument("--preprocessing-readout-time", type=float, help="Optional readout time for MRtrix/FSL preprocessing.")
    parser.add_argument(
        "--tractography-backend",
        default="csd_act",
        choices=("csd_act", "dti_det"),
        help="Tractography backend.",
    )
    parser.add_argument(
        "--connectome-backend",
        default="python",
        choices=("python", "mrtrix"),
        help="Connectome backend.",
    )
    parser.add_argument("--select-streamlines", type=int, default=1000, help="Requested streamline count for tractography.")
    parser.add_argument(
        "--micro-fit-method",
        default="wls",
        choices=("wls", "ls"),
        help="DTI fit method used by microstructure and DTI tracking.",
    )
    parser.add_argument("--run-free-water", action="store_true", help="Enable Free Water stage under microstructure.")
    parser.add_argument("--run-noddi", action="store_true", help="Enable NODDI stage under microstructure.")
    parser.add_argument("--mrtrix-bin-dir", type=Path, help="Optional MRtrix3 bin directory.")
    parser.add_argument("--tract-querier-root", type=Path, help="Optional TractQuerier checkout root.")
    parser.add_argument("--atlas-t2", type=Path, help="Optional DDParcel/DDSurfer atlas T2 path override.")
    parser.add_argument("--ddseg-device", default="cpu", help="DDSeg/DDSurfer device, e.g. cpu or cuda.")
    parser.add_argument(
        "--compress-mrtrix-dense",
        action="store_true",
        help="Compress MRtrix dense connectome CSV into ROI-label edge list.",
    )
    parser.add_argument(
        "--print-manifest-only",
        action="store_true",
        help="Print only the orchestration manifest path instead of the full JSON result.",
    )
    parser.add_argument("--saf-fs-dir", type=Path, help="FreeSurfer/FastSurfer directory for SAF.")
    parser.add_argument("--saf-pregenerated-tractogram", type=Path, help="Optional pregenerated tractogram for SAF.")
    parser.add_argument("--saf-noregister", action="store_true", help="Run SAF without registration.")
    parser.add_argument("--saf-mrtrix-prefix", default="", help="Optional command prefix for SAF MRtrix calls.")
    parser.add_argument("--wma-input-tractography", type=Path, help="Optional VTK/VTP tractography input for WMA.")
    parser.add_argument("--wma-atlas-dir", type=Path, help="ORG atlas directory for WMA.")
    parser.add_argument("--wma-root", type=Path, help="Optional WhiteMatterAnalysis checkout root.")
    parser.add_argument("--slicer-executable", type=Path, help="Slicer executable used by WMA.")
    parser.add_argument("--wma-use-virtual-x", action="store_true", help="Enable xvfb-run mode for WMA.")
    parser.add_argument("--wma-export-diffusion-measures", action="store_true", help="Enable WMA diffusion measurements export.")
    parser.add_argument("--fiber-tract-measurements-cli", type=Path, help="Optional SlicerDMRI FiberTractMeasurements CLI for WMA.")
    parser.add_argument("--tractcloud-input-tractography", type=Path, help="Optional VTK/VTP tractography input for TractCloud.")
    parser.add_argument("--tractcloud-root", type=Path, help="Optional TractCloud source checkout root.")
    parser.add_argument("--tractcloud-python-executable", type=Path, help="Optional Python executable for TractCloud.")
    parser.add_argument("--tractcloud-data-dir", type=Path, help="Optional model/data directory for TractCloud.")
    parser.add_argument("--tractcloud-device", default="auto", choices=("auto", "cpu", "cuda"), help="TractCloud device.")
    parser.add_argument("--tractcloud-batch-size", type=int, default=2048, help="TractCloud batch size.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    targets = _resolve_targets(args)
    if not targets:
        parser.error("No targets selected. Use --all or --targets.")
    unsupported = sorted(set(targets) - set(ALL_CLI_TARGETS))
    if unsupported:
        parser.error(f"Unsupported targets: {', '.join(unsupported)}")

    subject_root = args.subject_root.expanduser().resolve()
    subject_id = (args.subject_id or _infer_subject_id(subject_root)).strip()
    output_root = args.output_root.expanduser().resolve() if args.output_root else None

    config = ProductOrchestratorConfig(
        subject_id=subject_id,
        subject_root=subject_root,
        output_root=output_root,
        targets=targets,
        run_name=args.run_name,
        tractography_backend=args.tractography_backend,
        execute=bool(args.execute),
        resume=not args.no_resume,
        preprocessing_backend=args.preprocessing_backend,
        preprocessing_force=bool(args.preprocessing_force),
        preprocessing_mrtrix_bin_dir=args.preprocessing_mrtrix_bin_dir,
        preprocessing_fsl_bin_dir=args.preprocessing_fsl_bin_dir,
        preprocessing_reverse_phase_b0=args.preprocessing_reverse_phase_b0,
        preprocessing_phase_encoding_direction=args.preprocessing_phase_encoding_direction,
        preprocessing_readout_time=args.preprocessing_readout_time,
        microstructure_fit_method=args.micro_fit_method,
        microstructure_run_free_water=bool(args.run_free_water),
        microstructure_run_noddi=bool(args.run_noddi),
        atlas_t2=args.atlas_t2,
        ddseg_device=args.ddseg_device,
        select_streamlines=args.select_streamlines,
        mrtrix_bin_dir=args.mrtrix_bin_dir,
        tract_querier_root=args.tract_querier_root,
        connectome_backend=args.connectome_backend,
        connectome_compress_mrtrix_dense=bool(args.compress_mrtrix_dense),
        saf_fs_dir=args.saf_fs_dir,
        saf_pregenerated_tractogram=args.saf_pregenerated_tractogram,
        saf_noregister=bool(args.saf_noregister),
        saf_mrtrix_prefix=args.saf_mrtrix_prefix,
        wma_input_tractography=args.wma_input_tractography,
        wma_atlas_dir=args.wma_atlas_dir,
        wma_root=args.wma_root,
        slicer_executable=args.slicer_executable,
        wma_use_virtual_x=bool(args.wma_use_virtual_x),
        wma_export_diffusion_measures=bool(args.wma_export_diffusion_measures),
        fiber_tract_measurements_cli=args.fiber_tract_measurements_cli,
        tractcloud_input_tractography=args.tractcloud_input_tractography,
        tractcloud_root=args.tractcloud_root,
        tractcloud_python_executable=args.tractcloud_python_executable,
        tractcloud_data_dir=args.tractcloud_data_dir,
        tractcloud_device=args.tractcloud_device,
        tractcloud_batch_size=args.tractcloud_batch_size,
    )

    result = run_subject_products(config, log=print)
    payload = {
        "subject_id": result.subject_id,
        "subject_root": result.subject_root.as_posix(),
        "run_manifest_path": result.run_manifest_path.as_posix(),
        "tasks": [
            {
                "name": task.name,
                "status": task.status,
                "reason": task.reason,
                "manifest_path": task.manifest_path.as_posix() if task.manifest_path else None,
                "qc_path": task.qc_path.as_posix() if task.qc_path else None,
                "outputs": task.outputs,
            }
            for task in result.tasks
        ],
    }

    if args.print_manifest_only:
        print(result.run_manifest_path.as_posix())
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    failure_like_statuses = {"blocked", "failed"}
    if args.execute and any(task.status in failure_like_statuses for task in result.tasks):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
