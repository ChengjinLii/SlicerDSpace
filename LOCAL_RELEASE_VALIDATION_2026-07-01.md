# Local Release Validation Summary

Date: 2026-07-01

## Scope

This run focused on separating source-code checkout from model-asset retrieval
and extending the local release-validation evidence chain.

## Code and Model Asset Boundary

- Code checkout is tested separately from model-asset retrieval.
- Fresh-clone smoke uses `GIT_LFS_SKIP_SMUDGE=1` for `git clone`.
- Model weights and templates are downloaded after checkout through
  `scripts/download_model_assets.py` with an explicit profile and checksum
  verification.
- `scripts/smoke_fresh_clone.sh` now records `code_checkout` and
  `model_asset_download` sections in `fresh_clone_smoke_report.json`.

## Local Checks Completed

- `make test-fast`: 245 tests passed.
- `python3 scripts/release_audit.py`: release ready, no blockers after commit.
- `python3 scripts/download_model_assets.py --profile core --verify-only`: 29 files verified.
- `python3 scripts/download_model_assets.py --profile all --verify-only`: 33 files verified.
- Core asset mirror verification:
  `/data/chengjin/SlicerDDSurfer-models-v0.1.0-export-20260630`, 29 files verified.
- All asset mirror verification:
  `/data/chengjin/SlicerDDSurfer-models-v0.1.0-all-export-20260630`, 33 files verified.
- Fresh-clone smoke:
  `/tmp/slicerdsurfer-fresh-clone-smoke-20260701/fresh_clone_smoke_report.json`, passed.
- Release-validation plan report:
  `/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/00_run_metadata/release_validation_latest/release_validation_report.json`, passed.

## Slicer GUI Smoke

- Extension install smoke passed after adding the local runtime library path for
  `libpcre2-16.so.0`.
- Run plan panel smoke passed.
- Output tree button smoke passed.
- Cancel-background smoke passed after switching the smoke test to an isolated
  `/tmp` output root and directly exercising the background QProcess
  cancellation path.
- Environment button smoke opened the dependency dialog and reported one
  missing Python backend, `tract_querier`; this blocks the optional `bundles`
  route but not core routes.

## Real and Semi-Real Data Smoke

- DTI tractography smoke passed on the `100307` fixture.
- CSD/ACT real-subject smoke passed on the `100307` fixture, including
  tractogram export, SIFT2 weights and connectome scaffold generation.
- Connectome dry-run smoke passed on the `149741_wma_act` fixture.
- WMA fixture readiness smoke passed.
- WMA ORG atlas plan passed using the local WMA checkout and ORG atlas fixture.
- Surface post-process release tests passed.
- Microstructure DTI scalar tests passed.
- Full Free Water/NODDI microstructure regression started a serial long-running
  fit and was stopped after confirming progress. Treat full Free Water/NODDI as
  an overnight or dedicated-host validation job.

## Additional Release Tooling

- `scripts/validate_release_evidence.py` validates fresh-clone smoke reports and
  asset mirror manifests before release publication.
- The manual GitHub `Release` workflow now validates fresh-clone release
  evidence before draft release creation.
- `scripts/prepare_model_asset_upload.py` validates an exported model-asset
  mirror and prints maintainer upload commands for a GitHub model release,
  Hugging Face dataset repository, or Zenodo record.
- `scripts/check_github_ci_status.py --branch-protection-guide` prints a
  maintainer-facing guide for removing stale release/fresh-clone required
  checks while preserving `CI / fast-checks`.
- Environment discovery tests now lock in representative macOS and Windows
  common paths for Slicer, MRtrix3, FSL and FreeSurfer.

## Remaining External Gates

- GitHub Actions status and branch-protection checks still require GitHub API or
  UI access.
- Draft GitHub Release creation still requires a GitHub token or manual
  workflow run.
- Publishing model assets to `SlicerDDSurfer-models`, Hugging Face or Zenodo
  still requires the selected hosting credentials and redistribution approval.
