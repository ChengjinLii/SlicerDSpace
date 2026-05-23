#!/usr/bin/env python3
"""Regression runner for the phase-3 microstructure workflow."""

from __future__ import annotations

import argparse
import json
import subprocess
import shutil
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and validate Microstructure phase-3 on a test subject.")
    parser.add_argument(
        "--subject-root",
        default="/data/chengjin/SlicerDDSurfer-test/100307",
        help="Subject root containing input/ and cache/ directories.",
    )
    parser.add_argument(
        "--subject-id",
        default="100307",
        help="Subject identifier.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override output directory. Defaults to <subject_root>/outputs/microstructure_regression.",
    )
    parser.add_argument(
        "--fit-method",
        choices=["wls", "ls"],
        default="wls",
        help="Native DTI cache fit to reuse.",
    )
    parser.add_argument(
        "--expected-roi-count",
        type=int,
        default=101,
        help="Expected number of ROI rows in the output JSON.",
    )
    parser.add_argument(
        "--clean-output",
        action="store_true",
        help="Delete the output directory before running.",
    )
    parser.add_argument(
        "--bootstrap-dipy",
        action="store_true",
        help="Install DIPY into the active Python environment if it is missing.",
    )
    parser.add_argument(
        "--bootstrap-amico",
        action="store_true",
        help="Install AMICO into the active Python environment if it is missing.",
    )
    parser.add_argument(
        "--run-free-water",
        dest="run_free_water",
        action="store_true",
        default=True,
        help="Run (or reuse) Free Water stage.",
    )
    parser.add_argument(
        "--skip-free-water",
        dest="run_free_water",
        action="store_false",
        help="Disable Free Water stage; requires existing cached Free Water outputs.",
    )
    parser.add_argument(
        "--run-noddi",
        dest="run_noddi",
        action="store_true",
        default=True,
        help="Run (or reuse) NODDI stage.",
    )
    parser.add_argument(
        "--skip-noddi",
        dest="run_noddi",
        action="store_false",
        help="Disable NODDI stage; requires existing cached NODDI outputs.",
    )
    parser.add_argument(
        "--force-recompute",
        action="store_true",
        help="Recompute selected stages even when stage cache manifests match.",
    )
    parser.add_argument(
        "--validate-stage-reuse",
        action="store_true",
        help="Run a 3-pass cache regression: full recompute, NODDI-only recompute, then full reuse.",
    )
    return parser.parse_args()


def ensure_dipy(bootstrap: bool) -> None:
    try:
        import dipy  # noqa: F401
        return
    except ModuleNotFoundError:
        if not bootstrap:
            raise

    cmd = [sys.executable, "-m", "pip", "install", "dipy>=1.11,<1.13"]
    print("Bootstrapping DIPY:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def ensure_amico(bootstrap: bool) -> None:
    try:
        import amico  # noqa: F401
        return
    except ModuleNotFoundError:
        if not bootstrap:
            raise

    cmd = [sys.executable, "-m", "pip", "install", "dmri-amico"]
    print("Bootstrapping AMICO:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _stage_timestamps(output_dir: Path, subject_id: str) -> dict[str, int]:
    files = {
        "fwf": output_dir / f"{subject_id}-freewater-Fraction.nii.gz",
        "fw_tissue_fa": output_dir / f"{subject_id}-freewater-TissueFA.nii.gz",
        "fw_tissue_md": output_dir / f"{subject_id}-freewater-TissueMD.nii.gz",
        "noddi_ndi": output_dir / f"{subject_id}-noddi-NDI.nii.gz",
        "noddi_odi": output_dir / f"{subject_id}-noddi-ODI.nii.gz",
        "noddi_fwf": output_dir / f"{subject_id}-noddi-FWF.nii.gz",
        "freewater_manifest": output_dir / "freewater_manifest.json",
        "noddi_manifest": output_dir / "noddi_manifest.json",
    }
    timestamps: dict[str, int] = {}
    for key, path in files.items():
        if not path.is_file():
            raise FileNotFoundError(f"Expected stage output missing: {path}")
        timestamps[key] = path.stat().st_mtime_ns
    return timestamps


def _assert_columns(result, expected_roi_count: int) -> None:
    if result.roi_stats_csv_path is None or result.roi_stats_json_path is None:
        raise RuntimeError("ROI-wise statistics were not produced.")
    payload = json.loads(result.roi_stats_json_path.read_text(encoding="utf-8"))
    roi_count = int(payload.get("roi_count", -1))
    if roi_count != expected_roi_count:
        raise RuntimeError(
            f"Unexpected ROI count: expected {expected_roi_count}, got {roi_count}"
        )
    expected_columns = {
        "fa_mean",
        "md_mean",
        "fwf_mean",
        "fw_tissue_fa_mean",
        "fw_tissue_md_mean",
        "noddi_ndi_mean",
        "noddi_odi_mean",
        "noddi_fwf_mean",
    }
    row_keys = set(payload["rows"][0].keys()) if payload.get("rows") else set()
    missing_columns = sorted(expected_columns - row_keys)
    if missing_columns:
        raise RuntimeError(f"Missing expected ROI columns: {missing_columns}")


def _run_once(
    *,
    args: argparse.Namespace,
    raw,
    native_bundle,
    output_dir: Path,
    run_free_water: bool,
    run_noddi: bool,
    force_recompute: bool,
):
    from microstructure import MicrostructureConfig, run_microstructure

    result = run_microstructure(
        MicrostructureConfig(
            subject_id=args.subject_id,
            raw_input_bundle=raw,
            native_bundle=native_bundle,
            output_dir=output_dir,
            run_free_water=run_free_water,
            run_noddi=run_noddi,
            force_recompute=force_recompute,
        ),
        log=print,
    )
    required = [
        result.fa_path,
        result.md_path,
        result.fwf_path,
        result.fw_tissue_fa_path,
        result.fw_tissue_md_path,
        result.noddi_ndi_path,
        result.noddi_odi_path,
        result.noddi_fwf_path,
        output_dir / "freewater_manifest.json",
        output_dir / "noddi_manifest.json",
    ]
    if result.roi_stats_csv_path is None or result.roi_stats_json_path is None:
        raise RuntimeError("ROI-wise statistics were not produced.")
    required.extend([result.roi_stats_csv_path, result.roi_stats_json_path])
    missing = [path for path in required if not path.is_file()]
    if missing:
        missing_str = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"Regression output missing:\n{missing_str}")
    _assert_columns(result, args.expected_roi_count)
    return result


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    need_dipy = bool(args.validate_stage_reuse or args.run_free_water)
    need_amico = bool(args.validate_stage_reuse or args.run_noddi)
    if need_dipy:
        ensure_dipy(args.bootstrap_dipy)
    if need_amico:
        ensure_amico(args.bootstrap_amico)

    from shared import ensure_native_dti_bundle, find_subject_root

    subject_root = Path(args.subject_root).expanduser().resolve()
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else subject_root / "outputs" / "microstructure_regression"
    )

    if args.clean_output and output_dir.exists():
        shutil.rmtree(output_dir)

    raw = find_subject_root(subject_root, args.subject_id)
    native_bundle = ensure_native_dti_bundle(raw, fit_method=args.fit_method, reuse=True, log=print)
    if args.validate_stage_reuse:
        print("Stage reuse regression: pass-1 full recompute")
        result = _run_once(
            args=args,
            raw=raw,
            native_bundle=native_bundle,
            output_dir=output_dir,
            run_free_water=True,
            run_noddi=True,
            force_recompute=True,
        )
        ts1 = _stage_timestamps(output_dir, args.subject_id)
        time.sleep(1.2)

        print("Stage reuse regression: pass-2 NODDI-only recompute (Free Water disabled)")
        _run_once(
            args=args,
            raw=raw,
            native_bundle=native_bundle,
            output_dir=output_dir,
            run_free_water=False,
            run_noddi=True,
            force_recompute=True,
        )
        ts2 = _stage_timestamps(output_dir, args.subject_id)
        time.sleep(1.2)

        for key in ("fwf", "fw_tissue_fa", "fw_tissue_md", "freewater_manifest"):
            if ts2[key] != ts1[key]:
                raise RuntimeError(f"Expected Free Water output to be reused, but mtime changed: {key}")
        for key in ("noddi_ndi", "noddi_odi", "noddi_fwf", "noddi_manifest"):
            if ts2[key] <= ts1[key]:
                raise RuntimeError(f"Expected NODDI output to be recomputed, but mtime did not advance: {key}")

        print("Stage reuse regression: pass-3 full reuse")
        _run_once(
            args=args,
            raw=raw,
            native_bundle=native_bundle,
            output_dir=output_dir,
            run_free_water=True,
            run_noddi=True,
            force_recompute=False,
        )
        ts3 = _stage_timestamps(output_dir, args.subject_id)
        for key in ts2:
            if ts3[key] != ts2[key]:
                raise RuntimeError(f"Expected cached output reuse on pass-3, but mtime changed: {key}")
        roi_count = args.expected_roi_count
    else:
        result = _run_once(
            args=args,
            raw=raw,
            native_bundle=native_bundle,
            output_dir=output_dir,
            run_free_water=bool(args.run_free_water),
            run_noddi=bool(args.run_noddi),
            force_recompute=bool(args.force_recompute),
        )
        payload = json.loads(result.roi_stats_json_path.read_text(encoding="utf-8"))
        roi_count = int(payload.get("roi_count", -1))

    if args.validate_stage_reuse:
        stage_mode = "stage_reuse_validation(full_recompute->noddi_only_recompute->full_reuse)"
    else:
        enabled_stages = []
        if args.run_free_water:
            enabled_stages.append("FreeWater")
        if args.run_noddi:
            enabled_stages.append("NODDI")
        stage_mode = "+".join(enabled_stages)

    print(f"REGRESSION PASS: {args.subject_id}")
    print(f"  output_dir={output_dir}")
    print(f"  stages={stage_mode}")
    print(f"  freewater_manifest={(output_dir / 'freewater_manifest.json').name}")
    print(f"  noddi_manifest={(output_dir / 'noddi_manifest.json').name}")
    print(f"  roi_count={roi_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
