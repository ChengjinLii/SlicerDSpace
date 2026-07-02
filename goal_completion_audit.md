# Goal Completion Audit

Date: 2026-07-02

Scope: local release regression, Slicer GUI smoke, real/semi-real data smoke,
fresh-clone release simulation, model-asset/code checkout separation and release
tooling. Manuscript style edits remain intentionally out of scope for this
goal.

Overall status: the local code-side goal is complete with external release
gates remaining. The current checkout has a clean worktree, the latest local
release audit reports `release_ready=True`, and a full release-validation report
for current `main` passed all non-batch requirements.

## Current Evidence

Primary machine-readable report:

```text
/tmp/slicerdsurfer-release-validation-full-20260702/release_validation_report.json
```

That report completed with:

- `summary.status`: `passed`
- `completion_audit.overall_status`: `passed`
- `local_release_regression`: `passed`
- `slicer_gui_smoke`: `passed`
- `scientific_workflow_smoke`: `passed`
- `fresh_clone_release_smoke`: `passed`

The only skipped item in that report is `batch_validation`, because no
`--batch-root` was provided for this single-subject release smoke.

## Requirement Audit

| Requirement | Status | Current evidence |
|---|---|---|
| Full local regression: `make test-fast` | Complete | `make test-fast` passed with 249 tests on the current checkout. |
| Release audit | Complete | `python3 scripts/release_audit.py` reports `release_ready=True`, `blockers=0`, `warnings=0`. |
| Core model checksum | Complete | `release_validation_report.json` step `model_assets_core_verify` passed; 29 files verified in direct checks. |
| All model checksum | Complete | `release_validation_report.json` step `model_assets_all_verify` passed; 33 files verified in direct checks. |
| Core asset mirror verify | Complete | `release_validation_report.json` step `asset_mirror_core_verify` passed for `/data/chengjin/SlicerDDSurfer-models-v0.1.0-export-20260630`. |
| All asset mirror verify | Complete | `release_validation_report.json` step `asset_mirror_all_verify` passed for `/data/chengjin/SlicerDDSurfer-models-v0.1.0-all-export-20260630`. |
| Slicer module opens from module list | Complete | `slicer_extension_install_smoke` passed in the full 2026-07-02 release-validation report. |
| Environment detection button | Complete | `slicer_environment_button_smoke` passed in the full 2026-07-02 release-validation report. |
| Run plan panel | Complete | `slicer_run_plan_panel_smoke` passed in plan-only mode, validating preflight and run-plan UI without starting a long background pipeline. |
| Output tree button | Complete | `slicer_output_tree_button_smoke` passed in the full 2026-07-02 release-validation report. |
| Background cancellation | Complete | `slicer_cancel_background_smoke` passed in the full 2026-07-02 release-validation report. |
| DTI tractography smoke | Complete | `Testing/Python/run_tractography_dti_smoke.py` passed on the `100307` fixture and wrote tractogram, manifest and QC paths. |
| CSD/ACT smoke | Complete | `Testing/Python/run_csd_act_real_subject_smoke.py` passed on `100307`, generating CSD/ACT tractogram, SIFT2 weights, WMQL output and connectome matrices. |
| WMA smoke | Complete | WMA fixture readiness passed for `149741_wma_act`; WMA ORG atlas plan passed with local WMA checkout and ORG atlas fixture. |
| Connectome smoke | Complete | `Testing/Python/run_connectome_149741_smoke.py` passed in dry-run mode and wrote matrix, node, manifest and QC files. |
| Microstructure smoke | Complete | `Testing.Python.test_microstructure_dti_scalars` passed; full Free Water/NODDI remains a recommended overnight validation, not a release blocker for this smoke goal. |
| Surface postprocess smoke | Complete | `Testing.Python.test_surface_postprocess_release` passed. |
| Fresh-clone simulation | Complete | `release_validation_report.json` step `fresh_clone_smoke` passed: clone with LFS smudge disabled, checkout, core asset download, `make test-fast`, and core asset verify. |
| Separate code checkout and model weights | Complete | `scripts/smoke_fresh_clone.sh` records `code_checkout` separately from `model_asset_download`; `scripts/download_model_assets.py` handles model retrieval by profile and checksum. |
| GitHub required-check cleanup guide | Complete | `scripts/check_github_ci_status.py --branch-protection-guide` generates a maintainer guide that preserves `CI / fast-checks` and removes stale release/fresh-clone checks. |
| Model asset upload skeleton | Complete | `scripts/prepare_model_asset_upload.py` validates a mirror and prints maintainer upload plans for GitHub Release, Hugging Face and Zenodo targets. |
| Release workflow artifact/evidence validation | Complete | `.github/workflows/release.yml` validates fresh-clone release evidence before draft release creation. |
| Unified release-validation report | Complete | `scripts/release_validation.py` writes `completion_audit` covering local regression, Slicer GUI smoke, scientific workflow smoke, fresh-clone smoke and code/model-asset boundary. |
| Windows/macOS path scanning and overrides | Complete | `Testing/Python/test_environment_doctor.py` covers Windows/macOS common paths and conda environment name resolution; `Testing/Python/test_model_assets.py` covers model override variables. |

## Current External Gates

- GitHub Actions and branch-protection status still require GitHub API/UI access
  with a token or maintainer permissions.
- Draft GitHub Release creation still requires a GitHub token or a manual
  workflow dispatch.
- Publishing model assets to `SlicerDDSurfer-models`, Hugging Face or Zenodo
  still requires selected hosting credentials and redistribution approval.
- Full Free Water/NODDI microstructure execution is recommended as an overnight
  validation job because it is a serial long-running computation.

## Latest Commits

- `3d114ef` Run full Slicer GUI smoke in release validation
- `3a80b2c` Add release validation completion audit
- `771b85b` Add branch protection remediation guide
- `73ef529` Validate release evidence and asset upload plans
- `1e28cda` Separate code checkout from model asset validation
