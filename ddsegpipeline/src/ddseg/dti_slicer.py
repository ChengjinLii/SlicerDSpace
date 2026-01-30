from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional


def _quote(p: Path) -> str:
    return f"\"{p}\""


def _launcher(cli: Path, slicer_exe: Optional[Path]) -> str:
    if slicer_exe and slicer_exe.exists():
        return f"{_quote(slicer_exe)} --launch {_quote(cli)}"
    return _quote(cli)


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

    launcher = _launcher(dwi_convert, slicer_exe)
    dwi_convert_cmd = (
        f"{launcher} --conversionMode FSLToNrrd "
        f"--inputBVectors {_quote(bvec_file)} "
        f"--inputBValues {_quote(bval_file)} "
        f"--fslNIFTIFile {_quote(nii_file)} "
        f"--outputVolume {_quote(dwi_nrrd)} "
        f"--allowLossyConversion"
    )

    launcher = _launcher(dti_est, slicer_exe)
    dti_est_cmd = (
        f"{launcher} --enumeration LS {_quote(dwi_nrrd)} {_quote(dti_nrrd)} {_quote(b0_nrrd)}"
    )

    launcher = _launcher(dti_scalar, slicer_exe)
    fa_cmd = f"{launcher} --enumeration FractionalAnisotropy {_quote(dti_nrrd)} {_quote(fa_nrrd)}"
    md_cmd = f"{launcher} --enumeration Trace {_quote(dti_nrrd)} {_quote(md_nrrd)}"
    e1_cmd = f"{launcher} --enumeration MinEigenvalue {_quote(dti_nrrd)} {_quote(e3_nrrd)}"
    e2_cmd = f"{launcher} --enumeration MidEigenvalue {_quote(dti_nrrd)} {_quote(e2_nrrd)}"
    e3_cmd = f"{launcher} --enumeration MaxEigenvalue {_quote(dti_nrrd)} {_quote(e1_nrrd)}"

    for cmd in [dwi_convert_cmd, dti_est_cmd, fa_cmd, md_cmd, e1_cmd, e2_cmd, e3_cmd]:
        subprocess.run(cmd, shell=True, check=True)

    if not dti_e3.exists():
        raise RuntimeError("DTI parameter extraction failed. Check Slicer CLI paths.")
