#!/usr/bin/env python3
"""Prepare DICOM, NIfTI or NRRD diffusion inputs for SlicerDDSurfer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.input_import import InputImportConfig, detect_import_source_kind, prepare_inputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize external diffusion inputs into the SlicerDDSurfer subject-root layout: "
            "input/data.nii.gz, input/bvals, input/bvecs, optional input/dwi.json and optional mask."
        )
    )
    parser.add_argument("--source", required=True, type=Path, help="DICOM folder, DWI NIfTI, NRRD/NHDR, or canonical subject root.")
    parser.add_argument("--subject-root", required=True, type=Path, help="Destination SlicerDDSurfer subject root.")
    parser.add_argument("--subject-id", required=True, help="Subject identifier recorded in the import manifest.")
    parser.add_argument("--source-kind", choices=("auto", "canonical", "dicom", "nifti", "nrrd"), default="auto")
    parser.add_argument("--backend", choices=("auto", "copy", "dcm2niix", "mrconvert", "dwiconvert"), default="auto")
    parser.add_argument("--output-kind", choices=("canonical-nifti", "compat-nrrd"), default="canonical-nifti")
    parser.add_argument("--bval", dest="bval_path", type=Path, help="bval sidecar for NIfTI input.")
    parser.add_argument("--bvec", dest="bvec_path", type=Path, help="bvec sidecar for NIfTI input.")
    parser.add_argument("--metadata", dest="metadata_path", type=Path, help="JSON sidecar to copy to input/dwi.json.")
    parser.add_argument("--mask", dest="mask_path", type=Path, help="Optional mask copied to input/nodif_brain_mask.nii.gz.")
    parser.add_argument("--dcm2niix", dest="dcm2niix_executable", type=Path, help="Explicit dcm2niix executable.")
    parser.add_argument("--mrconvert", dest="mrconvert_executable", type=Path, help="Explicit MRtrix3 mrconvert executable.")
    parser.add_argument("--dwiconvert", dest="dwiconvert_executable", type=Path, help="Explicit SlicerDMRI DWIConvert executable.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned import without running conversion commands.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing canonical input files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    source_kind = detect_import_source_kind(args.source) if args.source_kind == "auto" else args.source_kind
    manifest = prepare_inputs(
        InputImportConfig(
            source=args.source,
            subject_root=args.subject_root,
            subject_id=args.subject_id,
            source_kind=source_kind,
            backend=args.backend,
            output_kind=args.output_kind,
            bval_path=args.bval_path,
            bvec_path=args.bvec_path,
            metadata_path=args.metadata_path,
            mask_path=args.mask_path,
            dcm2niix_executable=args.dcm2niix_executable,
            mrconvert_executable=args.mrconvert_executable,
            dwiconvert_executable=args.dwiconvert_executable,
            dry_run=args.dry_run,
            force=args.force,
        )
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
