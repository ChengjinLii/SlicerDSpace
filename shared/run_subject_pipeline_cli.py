#!/usr/bin/env python3
"""Unified CLI entrypoint for subject-root SlicerDDSurfer execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared import (
    EnvironmentDoctorConfig,
    EnvironmentDoctorResult,
    ProductOrchestratorConfig,
    blocked_target_reasons,
    plan_subject_products,
    run_environment_doctor,
    run_subject_products,
    normalize_orchestrator_targets,
    subject_layout,
    summarize_environment_doctor,
    write_environment_report,
)


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
    "microstructure_freewater",
    "microstructure_noddi",
    "surface_postprocess",
    "saf",
    "wma",
    "tractcloud",
)
ALL_CLI_TARGETS = ("validation",) + DEFAULT_PRODUCT_TARGETS + OPTIONAL_ALGORITHM_TARGETS
DEPENDENCY_CONFIG_KEYS = (
    "mrtrix_bin_dir",
    "preprocessing_mrtrix_bin_dir",
    "preprocessing_fsl_bin_dir",
    "postprocess_freesurfer_home",
    "wma_root",
    "wma_atlas_dir",
    "slicer_executable",
    "fiber_tract_measurements_cli",
    "tract_querier_root",
    "tractcloud_root",
    "tractcloud_python_executable",
    "tractcloud_data_dir",
)


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


def _split_csv_preserve_case(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    items: list[str] = []
    for value in values:
        for token in value.split(","):
            token = token.strip()
            if token:
                items.append(token)
    return tuple(items)


def _resolve_microstructure_stages(args: argparse.Namespace) -> tuple[str, ...]:
    raw_values = _split_csv_or_repeat(args.microstructure_stages)
    if not raw_values:
        raw_values = ("dti",)
    expanded: list[str] = []
    aliases = {
        "dt": "dti",
        "dti": "dti",
        "fa": "dti",
        "fa_md": "dti",
        "free_water": "freewater",
        "freewater": "freewater",
        "fw": "freewater",
        "noddi": "noddi",
    }
    for value in raw_values:
        if value in {"all", "full"}:
            expanded.extend(("dti", "freewater", "noddi"))
            continue
        try:
            expanded.append(aliases[value])
        except KeyError as exc:
            raise ValueError("microstructure stages must contain only: dti, freewater, noddi, all.") from exc
    if args.run_free_water:
        expanded.append("freewater")
    if args.run_noddi:
        expanded.append("noddi")
    if "freewater" in expanded or "noddi" in expanded:
        expanded.append("dti")
    return tuple(stage for stage in ("dti", "freewater", "noddi") if stage in set(expanded))


def _infer_subject_id(subject_root: Path) -> str:
    return subject_root.resolve().name


def _load_dependency_config(path: Path) -> dict[str, Path]:
    data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if "external_dependencies" in data and isinstance(data["external_dependencies"], dict):
        data = data["external_dependencies"]
    result: dict[str, Path] = {}
    for key in DEPENDENCY_CONFIG_KEYS:
        value = data.get(key)
        if value:
            result[key] = Path(str(value)).expanduser()
    return result


def _apply_dependency_config(args: argparse.Namespace) -> None:
    if not args.dependency_config:
        return
    config_path = args.dependency_config.expanduser()
    if not config_path.is_file():
        raise FileNotFoundError(f"Dependency config not found: {config_path}")
    config = _load_dependency_config(config_path)
    for key, path in config.items():
        if getattr(args, key, None) is None:
            setattr(args, key, path)


def _write_dependency_config(args: argparse.Namespace, path: Path) -> Path:
    payload = {
        "kind": "slicerdsurfer_dependency_config",
        "version": 1,
        "external_dependencies": {
            key: getattr(args, key).expanduser().as_posix()
            for key in DEPENDENCY_CONFIG_KEYS
            if getattr(args, key, None) is not None
        },
    }
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


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
    return tuple(
        target
        for target in normalize_orchestrator_targets(
            tuple(resolved),
            tractography_backend=args.tractography_backend,
            bundle_backend=args.bundle_backend,
            microstructure_run_free_water=bool(args.run_free_water),
            microstructure_run_noddi=bool(args.run_noddi),
        )
        if target not in exclude
    )


def _environment_config_from_args(
    args: argparse.Namespace,
    *,
    targets: tuple[str, ...],
    output_root: Path | None,
) -> EnvironmentDoctorConfig:
    subject_root = args.subject_root.expanduser().resolve()
    layout = subject_layout(subject_root, output_root=output_root)
    return EnvironmentDoctorConfig(
        targets=targets,
        repo_root=REPO_ROOT,
        output_dir=args.doctor_output_dir.expanduser().resolve()
        if args.doctor_output_dir
        else layout.run_metadata / "environment",
        python_executable=args.doctor_python_executable,
        preprocessing_backend=args.preprocessing_backend,
        tractography_backend=args.tractography_backend,
        connectome_backend=args.connectome_backend,
        ddseg_device=args.ddseg_device,
        surface_device=args.surface_device,
        tractcloud_device=args.tractcloud_device,
        run_free_water=bool(args.run_free_water),
        run_noddi=bool(args.run_noddi),
        mrtrix_bin_dir=args.mrtrix_bin_dir,
        preprocessing_mrtrix_bin_dir=args.preprocessing_mrtrix_bin_dir,
        preprocessing_fsl_bin_dir=args.preprocessing_fsl_bin_dir,
        postprocess_freesurfer_home=args.postprocess_freesurfer_home,
        wma_root=args.wma_root,
        wma_atlas_dir=args.wma_atlas_dir,
        slicer_executable=args.slicer_executable,
        fiber_tract_measurements_cli=args.fiber_tract_measurements_cli,
        tract_querier_root=args.tract_querier_root,
        tractcloud_root=args.tractcloud_root,
        tractcloud_python_executable=args.tractcloud_python_executable,
        tractcloud_data_dir=args.tractcloud_data_dir,
    )


def _run_environment_doctor_from_args(
    args: argparse.Namespace,
    *,
    targets: tuple[str, ...],
    output_root: Path | None,
) -> tuple[EnvironmentDoctorResult, dict[str, str]]:
    config = _environment_config_from_args(args, targets=targets, output_root=output_root)
    result = run_environment_doctor(config)
    output_dir = config.output_dir
    if output_dir is None:
        output_dir = subject_layout(args.subject_root.expanduser().resolve(), output_root=output_root).run_metadata / "environment"
    written = write_environment_report(result, output_dir)
    return result, {key: path.as_posix() for key, path in written.items()}


def _print_run_plan_summary(plan, *, stream) -> None:
    summary = plan.to_dict()["summary"]
    print(
        "Run plan: "
        f"{summary['will_run']} will run, {summary['skipped']} skipped/reused, {summary['blocked']} blocked.",
        file=stream,
    )
    for item in plan.items:
        detail = f" ({item.reason})" if item.reason else ""
        print(f"- {item.target}: {item.status}{detail}", file=stream)


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
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Check local environment for selected targets, write install plan, and exit before running products.",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Run environment preflight, write a target run plan, print it as JSON, and exit before execution.",
    )
    parser.add_argument(
        "--doctor-output-dir",
        type=Path,
        help="Optional environment doctor output directory. Defaults to <outputs>/00_run_metadata/environment.",
    )
    parser.add_argument(
        "--dependency-config",
        type=Path,
        help=(
            "Optional JSON file containing saved external dependency paths. "
            "Explicit CLI path arguments override this file."
        ),
    )
    parser.add_argument(
        "--save-dependency-config",
        type=Path,
        help="Write the resolved external dependency path configuration to this JSON file.",
    )
    parser.add_argument(
        "--doctor-python-executable",
        type=Path,
        help="Optional Python executable to use for dependency checks. Defaults to the current Python.",
    )
    parser.add_argument(
        "--skip-environment-check",
        action="store_true",
        help="Skip the pre-execution dependency doctor. Only use when running in a known-good managed environment.",
    )
    parser.add_argument(
        "--ignore-environment-blockers",
        action="store_true",
        help="Deprecated compatibility flag. Partial execution is now the default.",
    )
    parser.add_argument(
        "--strict-environment",
        action="store_true",
        help="Abort before execution when any selected target has missing required dependencies.",
    )
    parser.add_argument("--execute", action="store_true", help="Actually execute workflows. Default is dry-run planning only.")
    parser.add_argument("--no-resume", action="store_true", help="Disable resume/skip of completed outputs.")
    parser.add_argument(
        "--preprocessing-backend",
        default="dipy",
        choices=("dipy", "mrtrix_fsl"),
        help="Optional DWI preprocessing backend.",
    )
    parser.add_argument("--preprocessing-force", action="store_true", help="Force rerun preprocessing even if outputs exist.")
    parser.add_argument(
        "--preprocessing-dipy-denoise-method",
        default="mppca",
        choices=("mppca", "localpca", "patch2self", "none"),
        help="DIPY denoise method for preprocessing.",
    )
    parser.add_argument("--preprocessing-skip-gibbs", action="store_true", help="Skip Gibbs removal in DIPY preprocessing.")
    parser.add_argument("--preprocessing-skip-motion", action="store_true", help="Skip between-volume motion correction in DIPY preprocessing.")
    parser.add_argument("--preprocessing-mrtrix-bin-dir", type=Path, help="Optional MRtrix3 bin dir for preprocessing.")
    parser.add_argument("--preprocessing-fsl-bin-dir", type=Path, help="Optional FSL bin dir for preprocessing.")
    parser.add_argument("--preprocessing-reverse-phase-b0", type=Path, help="Optional reverse phase-encoding b0 for MRtrix/FSL preprocessing.")
    parser.add_argument("--preprocessing-phase-encoding-direction", help="Optional phase encoding direction for MRtrix/FSL preprocessing.")
    parser.add_argument("--preprocessing-readout-time", type=float, help="Optional readout time for MRtrix/FSL preprocessing.")
    parser.add_argument(
        "--tractography-backend",
        default="csd_act",
        choices=("csd_act", "dti_det", "saf"),
        help="Tractography backend. saf expands tractography to CSD/FOD plus SAF surface filtering.",
    )
    parser.add_argument(
        "--bundle-backend",
        default="wmql",
        help=(
            "Bundle backend selection. Use wmql, wma, tractcloud, all, or comma-separated values. "
            "When target bundles is selected this expands to the concrete backend targets."
        ),
    )
    parser.add_argument(
        "--connectome-backend",
        default="python",
        choices=("python", "mrtrix"),
        help="Connectome backend.",
    )
    parser.add_argument("--select-streamlines", type=int, default=100000, help="Requested streamline count for tractography.")
    parser.add_argument(
        "--micro-fit-method",
        default="wls",
        choices=("wls", "ls"),
        help="DTI fit method used by microstructure and DTI tracking.",
    )
    parser.add_argument(
        "--microstructure-stages",
        action="append",
        help=(
            "Microstructure stages to run. May be repeated or comma-separated. "
            "Choices: dti, freewater, noddi, all. Defaults to dti."
        ),
    )
    parser.add_argument("--run-free-water", action="store_true", help="Enable Free Water stage under microstructure.")
    parser.add_argument("--run-noddi", action="store_true", help="Enable NODDI stage under microstructure.")
    parser.add_argument("--postprocess-native-dir", type=Path, help="DDSurfer native STL directory for postprocess.")
    parser.add_argument("--postprocess-mri-dir", type=Path, help="MRI directory containing brain.mgz and DDSurfer-wmparc.nii.gz.")
    parser.add_argument("--postprocess-backend-root", type=Path, help="Optional override for bundled DDSurfer postprocess backend.")
    parser.add_argument("--postprocess-mode", default="whole", choices=("whole", "left", "right"), help="DDSurfer postprocess hemisphere mode.")
    parser.add_argument("--postprocess-python-bin", type=Path, help="Optional Python interpreter for DDSurfer postprocess backend.")
    parser.add_argument("--postprocess-freesurfer-home", type=Path, help="Optional FreeSurfer home for DDSurfer postprocess backend.")
    parser.add_argument("--postprocess-atlases", action="append", help="Optional comma-separated atlas list for DDSurfer postprocess.")
    parser.add_argument("--postprocess-force", action="store_true", help="Force restaging DDSurfer postprocess inputs.")
    parser.add_argument("--mrtrix-bin-dir", type=Path, help="Optional MRtrix3 bin directory.")
    parser.add_argument("--tract-querier-root", type=Path, help="Optional TractQuerier checkout root.")
    parser.add_argument("--atlas-t2", type=Path, help="Optional DDParcel/DDSurfer atlas T2 path override.")
    parser.add_argument("--ddseg-device", default="auto", help="DDSeg torch device. auto uses cuda:0 when available, otherwise cpu.")
    parser.add_argument("--surface-device", default="auto", help="DDSurfer torch device. auto uses cuda:0 when available, otherwise cpu.")
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
    parser.add_argument(
        "--saf-fs-dir",
        type=Path,
        help="Optional FreeSurfer/FastSurfer directory for SAF. Defaults to completed whole DDSurfer postprocess outputs when available.",
    )
    parser.add_argument("--saf-pregenerated-tractogram", type=Path, help="Optional pregenerated tractogram for SAF.")
    parser.add_argument("--saf-tckgen-options", default="", help="Optional MRtrix tckgen options string for SAF when it generates its own tractogram.")
    saf_registration = parser.add_mutually_exclusive_group()
    saf_registration.add_argument("--saf-noregister", dest="saf_noregister", action="store_true", help="Run SAF without registration.")
    saf_registration.add_argument("--saf-register", dest="saf_noregister", action="store_false", help="Run SAF registration using FA/ANTs inputs.")
    parser.set_defaults(saf_noregister=True)
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
    try:
        _apply_dependency_config(args)
    except Exception as exc:
        parser.error(str(exc))
    if args.save_dependency_config:
        written_config = _write_dependency_config(args, args.save_dependency_config)
        print(f"Dependency config written: {written_config}", file=sys.stderr)

    try:
        microstructure_stages = _resolve_microstructure_stages(args)
    except ValueError as exc:
        parser.error(str(exc))
    args.run_free_water = "freewater" in microstructure_stages
    args.run_noddi = "noddi" in microstructure_stages

    try:
        targets = _resolve_targets(args)
    except ValueError as exc:
        parser.error(str(exc))
    if not targets:
        parser.error("No targets selected. Use --all or --targets.")
    unsupported = sorted(set(targets) - set(ALL_CLI_TARGETS))
    if unsupported:
        parser.error(f"Unsupported targets: {', '.join(unsupported)}")

    subject_root = args.subject_root.expanduser().resolve()
    subject_id = (args.subject_id or _infer_subject_id(subject_root)).strip()
    output_root = args.output_root.expanduser().resolve() if args.output_root else None

    if args.doctor:
        doctor_result, doctor_paths = _run_environment_doctor_from_args(
            args,
            targets=targets,
            output_root=output_root,
        )
        print(
            json.dumps(
                {
                    "environment": doctor_result.to_dict(),
                    "report_paths": doctor_paths,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    preflight_blocked_targets: dict[str, str] = {}
    doctor_result: EnvironmentDoctorResult | None = None
    doctor_paths: dict[str, str] = {}
    if (args.execute or args.plan) and not args.skip_environment_check:
        doctor_result, doctor_paths = _run_environment_doctor_from_args(
            args,
            targets=targets,
            output_root=output_root,
        )
        print(summarize_environment_doctor(doctor_result), file=sys.stderr)
        print(f"Environment report: {doctor_paths['json']}", file=sys.stderr)
        print(f"Python install helper: {doctor_paths['python_sh']}", file=sys.stderr)
        print(f"External tool notes: {doctor_paths['external_notes']}", file=sys.stderr)
        preflight_blocked_targets = {
            target: reason
            for target, reason in blocked_target_reasons(doctor_result).items()
            if target in targets
        }
        if preflight_blocked_targets and args.strict_environment and args.execute:
            print(
                "Aborting before execution because required dependencies are missing. "
                "Install/configure them, rerun --doctor, or omit --strict-environment to run available targets only.",
                file=sys.stderr,
            )
            return 2
        if preflight_blocked_targets:
            mode = "execution" if args.execute else "planning"
            print(
                f"Continuing with partial {mode}. Blocked target(s): "
                + "; ".join(f"{target}: {reason}" for target, reason in preflight_blocked_targets.items()),
                file=sys.stderr,
            )

    config = ProductOrchestratorConfig(
        subject_id=subject_id,
        subject_root=subject_root,
        output_root=output_root,
        targets=targets,
        run_name=args.run_name,
        tractography_backend=args.tractography_backend,
        bundle_backend=args.bundle_backend,
        execute=bool(args.execute),
        resume=not args.no_resume,
        preprocessing_backend=args.preprocessing_backend,
        preprocessing_force=bool(args.preprocessing_force),
        preprocessing_dipy_denoise_method=args.preprocessing_dipy_denoise_method,
        preprocessing_dipy_run_gibbs=not args.preprocessing_skip_gibbs,
        preprocessing_dipy_run_motion_correction=not args.preprocessing_skip_motion,
        preprocessing_mrtrix_bin_dir=args.preprocessing_mrtrix_bin_dir,
        preprocessing_fsl_bin_dir=args.preprocessing_fsl_bin_dir,
        preprocessing_reverse_phase_b0=args.preprocessing_reverse_phase_b0,
        preprocessing_phase_encoding_direction=args.preprocessing_phase_encoding_direction,
        preprocessing_readout_time=args.preprocessing_readout_time,
        microstructure_fit_method=args.micro_fit_method,
        microstructure_run_free_water=bool(args.run_free_water),
        microstructure_run_noddi=bool(args.run_noddi),
        postprocess_native_dir=args.postprocess_native_dir,
        postprocess_mri_dir=args.postprocess_mri_dir,
        postprocess_backend_root=args.postprocess_backend_root,
        postprocess_mode=args.postprocess_mode,
        postprocess_python_bin=args.postprocess_python_bin,
        postprocess_freesurfer_home=args.postprocess_freesurfer_home,
        postprocess_atlases=_split_csv_preserve_case(args.postprocess_atlases) or None,
        postprocess_force=bool(args.postprocess_force),
        atlas_t2=args.atlas_t2,
        ddseg_device=args.ddseg_device,
        surface_device=args.surface_device,
        select_streamlines=args.select_streamlines,
        mrtrix_bin_dir=args.mrtrix_bin_dir,
        tract_querier_root=args.tract_querier_root,
        connectome_backend=args.connectome_backend,
        connectome_compress_mrtrix_dense=bool(args.compress_mrtrix_dense),
        saf_fs_dir=args.saf_fs_dir,
        saf_pregenerated_tractogram=args.saf_pregenerated_tractogram,
        saf_tckgen_options=args.saf_tckgen_options,
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
        preflight_blocked_targets=preflight_blocked_targets,
    )

    if args.plan:
        plan = plan_subject_products(config, write=True)
        print(
            json.dumps(
                {
                    "environment": doctor_result.to_dict() if doctor_result is not None else None,
                    "environment_report_paths": doctor_paths,
                    "run_plan_path": plan.run_plan_path.as_posix(),
                    "run_plan": plan.to_dict(),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.execute:
        plan = plan_subject_products(config, write=True)
        _print_run_plan_summary(plan, stream=sys.stderr)

    result = run_subject_products(config, log=print)
    try:
        manifest_payload = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
        task_payloads = manifest_payload.get("tasks", [])
    except Exception:
        task_payloads = [
            {
                "name": task.name,
                "status": task.status,
                "reason": task.reason,
                "manifest_path": task.manifest_path.as_posix() if task.manifest_path else None,
                "qc_path": task.qc_path.as_posix() if task.qc_path else None,
                "outputs": task.outputs,
            }
            for task in result.tasks
        ]
    payload = {
        "subject_id": result.subject_id,
        "subject_root": result.subject_root.as_posix(),
        "run_manifest_path": result.run_manifest_path.as_posix(),
        "run_plan_path": result.run_plan_path.as_posix() if result.run_plan_path else None,
        "tasks": task_payloads,
    }

    if args.print_manifest_only:
        print(result.run_manifest_path.as_posix())
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    failure_like_statuses = {"failed"}
    if args.execute and any(task.status in failure_like_statuses for task in result.tasks):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
