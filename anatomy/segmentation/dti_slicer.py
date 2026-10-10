from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional


def _launcher(cli: Path, slicer_exe: Optional[Path]) -> list[str]:
    if slicer_exe and slicer_exe.exists():
        return [str(slicer_exe), "--launch", str(cli)]
    return [str(cli)]


def _find_slicer_lib_dir(slicer_base: Path) -> Path:
    slicer_lib = slicer_base / "lib"
    if not slicer_lib.exists():
        raise FileNotFoundError(f"Missing Slicer lib directory: {slicer_lib}")
    candidates = sorted(p for p in slicer_lib.iterdir() if p.is_dir() and p.name.startswith("Slicer-"))
    if not candidates:
        raise FileNotFoundError(f"No Slicer-* directory under {slicer_lib}")
    return candidates[0]


def run_dti_feature_extraction(
    nii_file: Path,
    bval_file: Path,
    bvec_file: Path,
    output_folder: Path,
    slicer_base: Optional[Path] = None,
    slicer_ext: Optional[Path] = None,
) -> None:
    output_folder.mkdir(parents=True, exist_ok=True)
    dti_e3 = output_folder / "DTI_E3.nrrd"
    if dti_e3.exists():
        return

    if slicer_base is None:
        raise ValueError("slicer_base is required for DTI feature extraction.")
    if slicer_ext is None:
        raise ValueError("slicer_ext is required for DTI feature extraction.")

    slicer_lib_dir = _find_slicer_lib_dir(slicer_base)
    dwi_convert = slicer_lib_dir / "cli-modules" / "DWIConvert"
    dti_est = slicer_ext / "lib" / slicer_lib_dir.name / "cli-modules" / "DWIToDTIEstimation"
    dti_scalar = slicer_ext / "lib" / slicer_lib_dir.name / "cli-modules" / "DiffusionTensorScalarMeasurements"

    slicer_exe = slicer_base / "Slicer"

    dwi_nrrd = output_folder / "DWI.nrrd"
    dti_nrrd = output_folder / "DTI.nrrd"
    b0_nrrd = output_folder / "b0.nrrd"
    fa_nrrd = output_folder / "DTI_FA.nrrd"
    md_nrrd = output_folder / "DTI_MD.nrrd"
    e1_nrrd = output_folder / "DTI_E1.nrrd"
    e2_nrrd = output_folder / "DTI_E2.nrrd"
    e3_nrrd = output_folder / "DTI_E3.nrrd"

    # Argument lists passed to subprocess.run() without shell=True: no shell
    # is involved, so paths containing spaces, semicolons, or other shell
    # metacharacters are passed through literally with no quoting needed.
    dwi_convert_cmd = _launcher(dwi_convert, slicer_exe) + [
        "--conversionMode",
        "FSLToNrrd",
        "--inputBVectors",
        str(bvec_file),
        "--inputBValues",
        str(bval_file),
        "--fslNIFTIFile",
        str(nii_file),
        "--outputVolume",
        str(dwi_nrrd),
        "--allowLossyConversion",
    ]

    dti_est_cmd = _launcher(dti_est, slicer_exe) + [
        "--enumeration",
        "LS",
        str(dwi_nrrd),
        str(dti_nrrd),
        str(b0_nrrd),
    ]

    scalar_launcher = _launcher(dti_scalar, slicer_exe)
    fa_cmd = scalar_launcher + ["--enumeration", "FractionalAnisotropy", str(dti_nrrd), str(fa_nrrd)]
    md_cmd = scalar_launcher + ["--enumeration", "Trace", str(dti_nrrd), str(md_nrrd)]
    e1_cmd = scalar_launcher + ["--enumeration", "MinEigenvalue", str(dti_nrrd), str(e3_nrrd)]
    e2_cmd = scalar_launcher + ["--enumeration", "MidEigenvalue", str(dti_nrrd), str(e2_nrrd)]
    e3_cmd = scalar_launcher + ["--enumeration", "MaxEigenvalue", str(dti_nrrd), str(e1_nrrd)]

    for cmd in [dwi_convert_cmd, dti_est_cmd, fa_cmd, md_cmd, e1_cmd, e2_cmd, e3_cmd]:
        subprocess.run(cmd, check=True)

    if not dti_e3.exists():
        raise RuntimeError("DTI parameter extraction failed. Check Slicer CLI paths.")
