# Model Assets and Weight Downloads

SlicerDDSurfer keeps distributable model weights, templates, and release test fixtures in Git LFS. Install Git LFS before using these commands. A normal `git clone` may leave these files as small LFS pointer files until they are explicitly downloaded.

Use the unified downloader instead of asking users to remember individual LFS paths:

```bash
scripts/download_model_assets.sh --profile core
```

The downloader reads `models/assets_manifest.json`, runs `git lfs install --local` for the checkout, downloads the selected profile, and verifies that the selected files are real downloaded objects rather than Git LFS pointer files.
It also prints profile-level asset groups and conservative terms notices so
users know when model weights, templates, or subject-derived fixtures require
separate license or redistribution confirmation.

To inspect the resolved profile without downloading anything:

```bash
python3 scripts/download_model_assets.py --profile core --print-plan
```

To verify an existing checkout without downloading:

```bash
python3 scripts/download_model_assets.py --profile core --verify-only
```

For a fast clone followed by a targeted model download:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/ChengjinLii/SlicerDDSurfer.git
cd SlicerDDSurfer
scripts/download_model_assets.sh --profile core
```

## Profiles

Profiles are configured in `models/assets_manifest.json`. Update that manifest when adding, removing, or moving model assets; `scripts/download_model_assets.sh` is a compatibility wrapper around the Python manifest reader.

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

# Equivalent explicit Python entrypoint
python3 scripts/download_model_assets.py --profile core

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

## Manifest Format

The manifest has one top-level `profiles` object. Each profile may define:

| Field | Meaning |
| --- | --- |
| `include_patterns` | Git LFS include patterns passed to `git lfs pull --include=...`. |
| `required_paths` | Concrete files that verification checks for existence and non-pointer contents. |
| `include_profiles` | Other profiles to merge into this profile. |
| `alias_for` | Profile alias, used by `quick-gate`. |
| `all_lfs` | Pull every Git LFS object tracked by the checkout. |
| `external_overrides` | Environment variables users may set instead of repository-local DDSurfer assets. |
| `asset_groups` | Human-readable asset groups included by the profile, used for manuscript and release audits. |
| `terms_notice` | Conservative license/redistribution notice printed by the downloader. This is not a license grant. |

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

## Asset Terms Boundary

The downloader proves that selected files are present and materialized from Git
LFS. It does not prove that model weights, templates, or subject-derived test
fixtures can be redistributed through GitHub, a DOI archive, or supplementary
materials. Before submission or public archival release, confirm asset source,
ownership, license, GitHub LFS redistribution permission, and DOI-archive
permission for each asset group.

## Notes for Maintainers

- Do not commit large `.pt`, `.pkl`, `.nii.gz`, `.mgz`, `.obj`, `.stl`, `.trk`, `.tck`, `.vtk`, or `.vtp` assets as normal Git blobs.
- Run `python3 scripts/release_audit.py` before pushing release changes; it checks the expected Git LFS patterns and pointer state.
- `scripts/docker/run_rc_smoke.sh` defaults `SMOKE_STAGE=quick-gate` to `SMOKE_LFS_MODE=profile` with `SMOKE_ASSET_PROFILE=quick-gate`, so fresh-clone quick-gate runs download only the manifest-selected `core` assets by default. Use `SMOKE_LFS_MODE=full` if you explicitly want every tracked LFS object.
