# DOI Archive Preparation

This repository is prepared for a code/documentation DOI archive. Asset-inclusive
archival release requires additional terms confirmation.

## Code-Only DOI Scope

Include:

- Source code and tests.
- Documentation, release notes and metadata.
- `LICENSE`, `CITATION.cff`, `codemeta.json`, `.zenodo.json`.
- `RELEASE.md`, `MODEL_ASSETS.md`, `MODEL_ASSET_TERMS.md`.
- `MODEL_ASSET_HOSTING_PLAN.md`.
- Release validation report and generated artifact manifests.

Exclude unless redistribution and DOI-archive permission are confirmed:

- `Resources/Data/ckpts/**`
- `Resources/Data/template/**`
- `Resources/Data/100HCP-population-mean-T2.nii.gz`
- `surface/template/**`
- `segmentation/weights/**`
- `parcellation/weights/**`
- `parcellation/conversion/tests/data/**`

## Generate Archive Support Files

```bash
make release-artifacts
```

This writes:

- `model_assets_core_lock.json`
- `code_only_archive_manifest.json`
- `asset_exclusion_checklist.md`
- optional `release_validation_report.json`

## Zenodo/Figshare Notes

Use `.zenodo.json` as the starting metadata file. Before publishing:

1. Confirm the archived Git tag.
2. Confirm whether the archive is code-only or asset-inclusive.
3. If code-only, verify that restricted weights, templates and subject-derived
   fixtures are excluded.
4. Upload release validation report and generated release artifact manifests.
5. Record the final DOI in `CITATION.cff`, `codemeta.json`, `RELEASE.md` and the
   manuscript availability statement.

For the current `v0.1.0` GitHub Release page, use
`GITHUB_RELEASE_DRAFT_v0.1.0.md` as the release body and attach the generated
code-only support files from `release_artifacts/v0.1.0/`. The helper
`scripts/create_github_release.py` can create the draft release and upload these
artifacts when `GITHUB_TOKEN` or `GH_TOKEN` is available; the manual GitHub
Actions workflow can run the same helper with `create_github_release=true`.

## Current Boundary

The current asset terms decision record is `MODEL_ASSET_TERMS.md`. Until every
asset group is cleared for public redistribution and DOI archiving, publish only
code/documentation DOI archives or document an approved external access route.
Use `MODEL_ASSET_HOSTING_PLAN.md` when preparing a separate asset repository or
DOI-backed model-asset record.
