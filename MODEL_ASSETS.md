# Model Assets and Weight Downloads

SlicerDDSurfer keeps distributable model weights, templates, and release test fixtures in Git LFS. Install Git LFS before using these commands. A normal `git clone` may leave these files as small LFS pointer files until they are explicitly downloaded.

Use the unified downloader instead of asking users to remember individual LFS paths:

```bash
scripts/download_model_assets.sh --profile core
```

The script runs `git lfs install --local` for the checkout, downloads the selected profile, and verifies that the selected files are real downloaded objects rather than Git LFS pointer files.

For a fast clone followed by a targeted model download:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/ChengjinLii/SlicerDDSurfer.git
cd SlicerDDSurfer
scripts/download_model_assets.sh --profile core
```

## Profiles

| Profile | Includes | Use when |
| --- | --- | --- |
| `surface` | DDSurfer checkpoints, surface templates, registration atlas | Running DDSurfer surface reconstruction. |
| `segmentation` | DDSeg CNN weights | Running WM/GM/CSF segmentation. |
| `parcellation` | DDParcel weights | Running DDParcel parcellation. |
| `core` | `surface` + `segmentation` + `parcellation` | Recommended default for local users and release quick-gate runs. |
| `quick-gate` | Alias for `core` | Matching the release smoke terminology. |
| `test-fixtures` | Parcellation conversion test data | Running conversion tests only. |
| `all` | Every LFS object tracked in the repository | Full offline mirror or release validation. |

Examples:

```bash
# Recommended after clone
scripts/download_model_assets.sh --profile core

# Only run DDSeg
scripts/download_model_assets.sh --profile segmentation

# Full offline checkout, including test fixtures
scripts/download_model_assets.sh --profile all
```

Use `--no-verify` only for debugging slow or interrupted downloads.

## Asset Layout

The core model assets are expected at:

```text
Resources/Data/100HCP-population-mean-T2.nii.gz
Resources/Data/ckpts/hcp/*.pt
Resources/Data/template/*
surface/template/*
segmentation/weights/*.pt
parcellation/weights/*.pkl
```

DDSurfer also supports external asset locations through environment variables:

| Variable | Purpose |
| --- | --- |
| `DDSURFER_CHECKPOINT_DIR` | Directory containing `hcp/*.pt` DDSurfer checkpoints. |
| `DDSURFER_TEMPLATE_DIR` | Directory containing DDSurfer surface templates. |
| `DDSURFER_REGISTRATION_ATLAS` | Path to `100HCP-population-mean-T2.nii.gz` or equivalent atlas. |

DDSeg and DDParcel currently use repository-local weights by default:

```text
segmentation/weights/
parcellation/weights/
```

## Recommended User Flow

1. Clone the repository.
2. Run `scripts/download_model_assets.sh --profile core`.
3. Run dependency doctor:

```bash
python3 run_subject_pipeline.py \
  --subject-root /path/to/subject \
  --targets validation,preprocessing,segmentation,parcellation,surface,microstructure \
  --doctor
```

4. If the doctor reports missing model assets, rerun the downloader for the relevant profile or configure the DDSurfer environment variables above.

## Notes for Maintainers

- Do not commit large `.pt`, `.pkl`, `.nii.gz`, `.mgz`, `.obj`, `.stl`, `.trk`, `.tck`, `.vtk`, or `.vtp` assets as normal Git blobs.
- Run `python3 scripts/release_audit.py` before pushing release changes; it checks the expected Git LFS patterns and pointer state.
- `scripts/docker/run_rc_smoke.sh` uses `SMOKE_LFS_MODE=full` for `SMOKE_STAGE=quick-gate`, which is equivalent to needing the `core` model assets plus any tracked runtime fixtures required by that smoke.
