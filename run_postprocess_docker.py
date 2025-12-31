#!/usr/bin/env python3
"""
Utility script to invoke postprocess-release inside Docker after SlicerDDSurfer.

This script stages the required inputs (MRI + predicted STL surfaces) into the
postprocess-release repository and calls its docker/run_container.sh helper to
run FreeSurfer-based refinement without requiring a local FreeSurfer install.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_MRI_FILES = ("brain.mgz", "DDSurfer-wmparc.nii.gz")


def log(msg: str) -> None:
    print(msg, flush=True)


def copy_file(src: Path, dest: Path) -> None:
    if not src.is_file():
        raise FileNotFoundError(f"Required file not found: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def stage_subject_inputs(subject_id: str, native_dir: Path, mri_dir: Path, inputs_dir: Path, clobber: bool) -> Path:
    subject_input_dir = inputs_dir / subject_id
    surf_dir = subject_input_dir / "surf"
    mri_out_dir = subject_input_dir / "mri"

    if clobber and subject_input_dir.exists():
        shutil.rmtree(subject_input_dir)
    surf_dir.mkdir(parents=True, exist_ok=True)
    mri_out_dir.mkdir(parents=True, exist_ok=True)

    for filename in REQUIRED_MRI_FILES:
        copy_file(mri_dir / filename, mri_out_dir / filename)
        log(f"Copied {filename} to {mri_out_dir}")

    pattern = f"{subject_id}_predicted_*_orig.stl"
    stl_paths = sorted(native_dir.glob(pattern))
    if not stl_paths:
        raise FileNotFoundError(
            f"No STL files matching '{pattern}' under {native_dir}. "
            "Ensure SlicerDDSurfer prediction completed successfully."
        )
    for stl in stl_paths:
        copy_file(stl, surf_dir / stl.name)
        log(f"Copied {stl.name} to {surf_dir}")

    return subject_input_dir


def run_docker(subject_id: str, mode: str, postprocess_repo: Path, license_path: Path, inputs_dir: Path, outputs_dir: Path, image_tag: str | None) -> None:
    docker_script = postprocess_repo / "docker" / "run_container.sh"
    if not docker_script.is_file():
        raise FileNotFoundError(f"Docker helper not found: {docker_script}")
    if not os.access(docker_script, os.X_OK):
        docker_script.chmod(0o755)
    env = os.environ.copy()
    env["FREESURFER_LICENSE"] = str(license_path)
    env["INPUTS_DIR"] = str(inputs_dir)
    env["OUTPUTS_DIR"] = str(outputs_dir)
    if image_tag:
        env["DDSURFER_POST_IMAGE"] = image_tag

    cmd = ["bash", str(docker_script), subject_id, mode]
    log(f"Running docker command: {' '.join(cmd)}")
    proc = subprocess.run(cmd, env=env, cwd=str(postprocess_repo))
    if proc.returncode != 0:
        raise RuntimeError(f"Docker postprocess failed with exit code {proc.returncode}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage SlicerDDSurfer outputs and run postprocess-release inside Docker.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("subject_id", help="Subject identifier (e.g., 877168)")
    parser.add_argument("native_dir", help="Path to SlicerDDSurfer native output directory (contains *_orig.stl)")
    parser.add_argument("mri_dir", help="Path to MRI directory holding brain.mgz and DDSurfer-wmparc.nii.gz")
    parser.add_argument("--postprocess-repo", default="/data/chengjin/postprocess-release", help="postprocess-release repository root")
    parser.add_argument("--mode", choices=["left", "right", "whole"], default="whole", help="Hemisphere mode for postprocess run.sh")
    parser.add_argument("--license", default=os.environ.get("FREESURFER_LICENSE", str(Path.home() / ".freesurfer-license")), help="Path to FreeSurfer license file")
    parser.add_argument("--image-tag", default=None, help="Custom Docker image tag (defaults to docker/run_container.sh default)")
    parser.add_argument("--inputs-dir", default=None, help="Override inputs directory passed to docker (defaults to <repo>/inputs)")
    parser.add_argument("--outputs-dir", default=None, help="Override outputs directory passed to docker (defaults to <repo>/outputs)")
    parser.add_argument("--force", action="store_true", help="Remove any existing staged subject folder before copying inputs")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    subject_id = args.subject_id
    native_dir = Path(args.native_dir).expanduser().resolve()
    mri_dir = Path(args.mri_dir).expanduser().resolve()
    postprocess_repo = Path(args.postprocess_repo).expanduser().resolve()
    inputs_dir = Path(args.inputs_dir).expanduser().resolve() if args.inputs_dir else postprocess_repo / "inputs"
    outputs_dir = Path(args.outputs_dir).expanduser().resolve() if args.outputs_dir else postprocess_repo / "outputs"
    license_path = Path(args.license).expanduser().resolve()

    for path, desc in [(native_dir, "native output directory"), (mri_dir, "MRI directory"), (postprocess_repo, "postprocess repo")]:
        if not path.exists():
            raise FileNotFoundError(f"{desc} not found: {path}")
    if not license_path.is_file():
        raise FileNotFoundError(f"FreeSurfer license not found: {license_path}")

    log(f"Staging inputs for subject {subject_id}...")
    staged_dir = stage_subject_inputs(subject_id, native_dir, mri_dir, inputs_dir, args.force)
    log(f"Inputs staged under {staged_dir}")

    outputs_dir.mkdir(parents=True, exist_ok=True)

    log("Launching Docker postprocess pipeline...")
    run_docker(
        subject_id=subject_id,
        mode=args.mode,
        postprocess_repo=postprocess_repo,
        license_path=license_path,
        inputs_dir=inputs_dir,
        outputs_dir=outputs_dir,
        image_tag=args.image_tag,
    )
    log("Docker postprocess completed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
