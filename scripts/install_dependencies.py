#!/usr/bin/env python3
"""Generate or execute SlicerDDSurfer dependency install plans.

This script intentionally installs Python packages only when --execute is
provided. External tools such as MRtrix3, FSL, FreeSurfer, ANTs, WMA, and
TractCloud require platform-specific choices, licenses, or model data, so the
script writes install notes instead of silently modifying the system.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.environment import EnvironmentDoctorConfig, run_environment_doctor, write_environment_report


DEFAULT_TARGETS = (
    "validation",
    "preprocessing",
    "segmentation",
    "parcellation",
    "surface",
    "microstructure",
    "tractography",
    "bundles",
    "connectome",
)
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


def _split_csv(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    result: list[str] = []
    for value in values:
        for token in value.split(","):
            token = token.strip().lower()
            if token:
                result.append(token)
    return tuple(dict.fromkeys(result))


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
    for key, path in _load_dependency_config(config_path).items():
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check and optionally install Python dependencies for selected SlicerDDSurfer targets. "
            "External software is reported in install_external_tools.md."
        )
    )
    parser.add_argument("--all", action="store_true", help="Use the default product target set.")
    parser.add_argument(
        "--targets",
        action="append",
        help="Targets to check/install. May be repeated or comma-separated.",
    )
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "install_plan", help="Where to write doctor/install reports.")
    parser.add_argument("--dependency-config", type=Path, help="Optional JSON file containing saved external dependency paths.")
    parser.add_argument("--save-dependency-config", type=Path, help="Write resolved external dependency paths to this JSON file.")
    parser.add_argument("--python-executable", default=sys.executable, help="Python executable to use for pip installation.")
    parser.add_argument("--execute", action="store_true", help="Actually run pip install for missing Python packages.")
    parser.add_argument(
        "--strict-exit-code",
        action="store_true",
        help="Return exit code 2 when required dependencies are still missing after planning/installation.",
    )
    parser.add_argument("--preprocessing-backend", default="dipy", choices=("dipy", "mrtrix_fsl"))
    parser.add_argument("--tractography-backend", default="csd_act", choices=("csd_act", "dti_det"))
    parser.add_argument("--connectome-backend", default="python", choices=("python", "mrtrix"))
    parser.add_argument("--ddseg-device", default="auto", help="Requested DDSeg torch device. auto uses cuda:0 when available, otherwise cpu.")
    parser.add_argument("--surface-device", default="auto", help="Requested DDSurfer torch device. auto uses cuda:0 when available, otherwise cpu.")
    parser.add_argument("--tractcloud-device", default="auto", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--run-free-water", action="store_true")
    parser.add_argument("--run-noddi", action="store_true")
    parser.add_argument("--mrtrix-bin-dir", type=Path)
    parser.add_argument("--preprocessing-mrtrix-bin-dir", type=Path)
    parser.add_argument("--preprocessing-fsl-bin-dir", type=Path)
    parser.add_argument("--postprocess-freesurfer-home", type=Path)
    parser.add_argument("--wma-root", type=Path)
    parser.add_argument("--wma-atlas-dir", type=Path)
    parser.add_argument("--slicer-executable", type=Path)
    parser.add_argument("--fiber-tract-measurements-cli", type=Path)
    parser.add_argument("--tract-querier-root", type=Path)
    parser.add_argument("--tractcloud-root", type=Path)
    parser.add_argument("--tractcloud-python-executable", type=Path)
    parser.add_argument("--tractcloud-data-dir", type=Path)
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
    targets = DEFAULT_TARGETS if args.all else _split_csv(args.targets)
    if not targets:
        parser.error("No targets selected. Use --all or --targets.")

    config = EnvironmentDoctorConfig(
        targets=targets,
        repo_root=REPO_ROOT,
        output_dir=args.output_dir,
        python_executable=Path(args.python_executable).expanduser().resolve(),
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
    result = run_environment_doctor(config)
    written = write_environment_report(result, args.output_dir)

    if args.execute and result.missing_python_packages:
        cmd = [
            args.python_executable,
            "-m",
            "pip",
            "install",
            *result.missing_python_packages,
        ]
        subprocess.run(cmd, check=True)
        result = run_environment_doctor(config)
        written = write_environment_report(result, args.output_dir)

    payload = {
        "environment": result.to_dict(),
        "report_paths": {key: path.as_posix() for key, path in written.items()},
        "executed_python_install": bool(args.execute),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 2 if args.strict_exit_code and result.blocker_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
