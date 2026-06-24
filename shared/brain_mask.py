"""Brain-mask generation helpers backed by established neuroimaging tools."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from shared.external_process import merged_startup_environment


def _manifest_path_for_mask(mask_path: Path) -> Path:
    name = mask_path.name.replace(".nii.gz", ".manifest.json")
    return mask_path.with_name(name)


def _candidate_tool_paths(tool_name: str, explicit_bin_dir: Optional[Path] = None) -> list[Path]:
    candidates: list[Path] = []
    if explicit_bin_dir is not None:
        candidates.append(explicit_bin_dir.expanduser().resolve() / tool_name)
    for env_key in ("SLICERDDSURFER_MRTRIX_BIN_DIR", "MRTRIX_BIN_DIR"):
        env_value = os.environ.get(env_key)
        if env_value:
            candidates.append(Path(env_value).expanduser().resolve() / tool_name)
    resolved = shutil.which(tool_name)
    if resolved:
        candidates.append(Path(resolved).resolve())
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def resolve_dwi2mask(explicit_bin_dir: Optional[Path] = None) -> Optional[Path]:
    """Resolve MRtrix3 dwi2mask from explicit, environment, or PATH locations."""

    for candidate in _candidate_tool_paths("dwi2mask", explicit_bin_dir):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def generate_brain_mask_with_dwi2mask(
    dwi_path: Path,
    bval_path: Path,
    bvec_path: Path,
    output_mask_path: Path,
    *,
    mrtrix_bin_dir: Optional[Path] = None,
    force: bool = False,
) -> dict[str, Any]:
    """Generate a DWI brain mask with MRtrix3 dwi2mask."""

    dwi_path = dwi_path.expanduser().resolve()
    bval_path = bval_path.expanduser().resolve()
    bvec_path = bvec_path.expanduser().resolve()
    output_mask_path = output_mask_path.expanduser().resolve()
    manifest_path = _manifest_path_for_mask(output_mask_path)

    if output_mask_path.exists() and not force:
        return {
            "status": "reused",
            "backend": "mrtrix_dwi2mask",
            "mask_path": output_mask_path.as_posix(),
            "manifest_path": manifest_path.as_posix() if manifest_path.exists() else None,
        }

    dwi2mask = resolve_dwi2mask(mrtrix_bin_dir)
    if dwi2mask is None:
        raise FileNotFoundError(
            "Cannot generate input/nodif_brain_mask.nii.gz automatically because MRtrix3 dwi2mask was not found. "
            "Install MRtrix3, add its bin directory to PATH, set SLICERDDSURFER_MRTRIX_BIN_DIR, or provide the mask."
        )

    output_mask_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        dwi2mask.as_posix(),
        dwi_path.as_posix(),
        output_mask_path.as_posix(),
        "-fslgrad",
        bvec_path.as_posix(),
        bval_path.as_posix(),
        "-force",
    ]
    completed = subprocess.run(
        cmd,
        env=merged_startup_environment(os.environ.copy()),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "MRtrix3 dwi2mask failed with exit code "
            f"{completed.returncode}: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    if not output_mask_path.is_file():
        raise RuntimeError(f"MRtrix3 dwi2mask completed but did not create {output_mask_path}.")

    manifest = {
        "kind": "generated_brain_mask",
        "version": 1,
        "status": "completed",
        "backend": "mrtrix_dwi2mask",
        "command": cmd,
        "mask_path": output_mask_path.as_posix(),
        "source_dwi": dwi_path.as_posix(),
        "source_bvals": bval_path.as_posix(),
        "source_bvecs": bvec_path.as_posix(),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "note": "Generated with MRtrix3 dwi2mask. Review the mask before quantitative use.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
