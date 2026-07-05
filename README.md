# SlicerDDSurfer

SlicerDDSurfer is a 3D Slicer scripted module for diffusion-MRI anatomical
reconstruction and connectivity analysis. It combines subject-root input
preparation, environment checks, segmentation, parcellation, surface
reconstruction, microstructure maps, tractography, bundle analysis, connectome
generation and Slicer-based review.

The project is intended for research workflows that need traceable outputs,
quality-control files and provenance before downstream analysis.

**Chinese README:** [README.zh-CN.md](README.zh-CN.md)

## What It Provides

- Slicer GUI module for interactive setup, preflight, run planning and review.
- Command-line pipeline for scripted single-subject or batch execution.
- Manifest-driven model asset downloader with checksum verification.
- Canonical subject-root outputs with run manifests, QC files and logs.
- Optional integrations for PyTorch, MRtrix3, FSL, FreeSurfer, WMA,
  TractQuerier, TractCloud and SlicerDMRI-dependent utilities.

## Quick Start

Clone the code first, then download model assets separately:

```bash
git clone https://github.com/ChengjinLii/SlicerDDSurfer.git
cd SlicerDDSurfer

scripts/download_model_assets.sh --profile core
python3 scripts/download_model_assets.py --profile core --verify-only
```

`git clone` downloads source code, scripts, documentation, configuration files,
`models/assets_manifest.json` and Git LFS pointer files. It is not a complete
model-weight download. The downloader materializes the selected model/template
profile and verifies file size and SHA256 checksums.

## Minimal CLI Use

Prepare a subject root with diffusion data:

```text
sub-01/
  input/
    data.nii.gz
    bvals
    bvecs
    dwi.json                  # optional
    nodif_brain_mask.nii.gz   # optional
```

Run a preflight check:

```bash
python3 run_subject_pipeline.py \
  --subject-root /path/to/sub-01 \
  --targets validation,preprocessing,microstructure,tractography,connectome \
  --doctor
```

Generate a run plan without executing algorithms:

```bash
python3 run_subject_pipeline.py \
  --subject-root /path/to/sub-01 \
  --targets validation,preprocessing,microstructure,tractography,bundles,connectome \
  --microstructure-stages dti \
  --tractography-backend csd_act \
  --bundle-backend wmql \
  --plan
```

Execute selected products:

```bash
python3 run_subject_pipeline.py \
  --subject-root /path/to/sub-01 \
  --subject-id sub-01 \
  --targets microstructure,tractography,connectome \
  --microstructure-stages dti \
  --tractography-backend dti_det \
  --execute
```

Outputs are written under `<subject-root>/outputs/` by default.

## Slicer Use

Install or stage the module in 3D Slicer, then open `SlicerDDSurfer` from the
module list. The UI supports:

- subject-root selection;
- dependency preflight and external path overrides;
- run-plan review before execution;
- background execution with cancellation;
- output-tree, report, manifest and QC inspection.

Detailed dependency setup is in
[docs/setup/EXTERNAL_DEPENDENCIES.md](docs/setup/EXTERNAL_DEPENDENCIES.md).

## Model Assets

Recommended profile:

```bash
scripts/download_model_assets.sh --profile core
```

Useful profiles:

- `core`: surface + segmentation + parcellation assets.
- `surface`: DDSurfer surface reconstruction assets.
- `segmentation`: DDSeg weights.
- `parcellation`: DDParcel weights.
- `all`: all LFS-managed assets and test fixtures.

See [docs/assets/MODEL_ASSETS.md](docs/assets/MODEL_ASSETS.md) for manifest
format, external mirrors, lockfiles and redistribution notes.

## Input Preparation

Use `scripts/prepare_inputs.py` to normalize external data into the expected
subject-root layout:

```bash
python3 scripts/prepare_inputs.py \
  --source /path/to/dicom_or_dwi_file \
  --subject-root /path/to/sub-01 \
  --subject-id sub-01
```

Supported routes include DICOM through `dcm2niix`, NIfTI with bval/bvec
sidecars, and NRRD/NHDR through MRtrix3 `mrconvert`.

## Validation

Common local checks:

```bash
make test-fast
python3 scripts/release_audit.py
python3 scripts/download_model_assets.py --profile core --verify-only
```

Fuller release-candidate validation:

```bash
python3 scripts/release_validation.py \
  --subject-root /path/to/sub-01 \
  --asset-mirror-dir /path/to/SlicerDDSurfer-models-core \
  --all-asset-mirror-dir /path/to/SlicerDDSurfer-models-all \
  --run-fresh-clone-smoke \
  --warn-only
```

See
[docs/release/RELEASE_CANDIDATE_VALIDATION.md](docs/release/RELEASE_CANDIDATE_VALIDATION.md)
for release-candidate validation details.

## Documentation

- [docs/assets/MODEL_ASSETS.md](docs/assets/MODEL_ASSETS.md): model weights,
  templates and mirrors.
- [docs/setup/EXTERNAL_DEPENDENCIES.md](docs/setup/EXTERNAL_DEPENDENCIES.md):
  Python packages and external runtime setup.
- [docs/architecture/PRODUCT_ARCHITECTURE.md](docs/architecture/PRODUCT_ARCHITECTURE.md):
  workflow and output organization.
- [docs/release/RELEASE.md](docs/release/RELEASE.md): release workflow.
- [docs/release/DOI_ARCHIVE_PREP.md](docs/release/DOI_ARCHIVE_PREP.md):
  code/archive boundary.

## License And Citation

See [LICENSE](LICENSE), [CITATION.cff](CITATION.cff) and
[docs/assets/MODEL_ASSET_TERMS.md](docs/assets/MODEL_ASSET_TERMS.md).
