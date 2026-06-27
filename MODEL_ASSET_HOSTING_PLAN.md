# Model Asset Hosting Plan

This plan separates SlicerDDSurfer source code from large model weights,
templates and validation fixtures. The current Git LFS objects remain a
compatibility source, but the release-facing route should move to an independent
asset host after redistribution terms are confirmed.

## Target Layout

- Code repository: `ChengjinLii/SlicerDDSurfer`
- Asset repository or record: `ChengjinLii/SlicerDDSurfer-models`, Hugging Face,
  Zenodo, OSF, Figshare or institutional object storage
- Source of truth for paths, sizes and checksums:
  `models/assets_manifest.json`
- Runtime downloader:
  `scripts/download_model_assets.py`

The asset host should preserve repository-relative paths such as:

```text
Resources/Data/ckpts/hcp/DDCSR_white_lh_Full_DualStream_no_b0_Cascaded.pt
segmentation/weights/dti_axial.pt
parcellation/weights/Fused-Unet-v3-noMax-axial.pkl
surface/template/hcp_hemi-left_init_160k.obj
```

Preserving relative paths lets the existing pipeline keep using repository-local
defaults while the downloader changes only the source backend.

## Migration Steps

1. Confirm redistribution, public hosting and DOI/archive permissions for each
   asset group in `MODEL_ASSET_TERMS.md`.
2. Create the external asset host.
3. Upload files listed under `asset_records` in `models/assets_manifest.json`.
4. Preserve paths exactly, or add per-record `urls` for hosts that flatten file
   names.
5. Keep SHA256 and `size_bytes` unchanged.
6. Change the relevant `asset_sources.<id>.status` from `planned` to `active`.
7. Validate from a clean checkout:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone git@github.com:ChengjinLii/SlicerDDSurfer.git /tmp/slicerdsurfer-url-smoke
cd /tmp/slicerdsurfer-url-smoke
python3 scripts/download_model_assets.py \
  --profile core \
  --source url \
  --source-id slicerdsurfer_models_release
python3 scripts/download_model_assets.py --profile core --verify-only
```

8. Run the normal release gates:

```bash
make test-fast
python3 scripts/release_audit.py
scripts/smoke_fresh_clone.sh
```

## Supported Source Types

- `git-lfs`: compatibility source inside the code repository.
- `url-template`: URL or mirror source using manifest templates.
- `--base-url`: ad-hoc mirror for local testing or institutional storage.

The URL downloader verifies every file after download. A mirror is accepted only
if the file size and SHA256 match the manifest.

## Recommended Release Policy

- Keep the code DOI archive code-only unless model redistribution is explicitly
  approved.
- Publish weights through a governed asset host with clear terms.
- Attach or publish `model_assets_core_lock.json` with release records.
- Do not remove Git LFS compatibility until an external source has passed
  fresh-clone URL-mode validation.
