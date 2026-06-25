# Goal Progress: Release Smoke, Input Preparation UI, and Asset Verification

Date: 2026-06-25

## Completed Engineering Changes

- Added `scripts/smoke_fresh_clone.sh`, a fresh-clone release smoke gate that
  clones into `/tmp`, downloads the `core` model-asset profile, runs
  `make test-fast`, verifies core assets with `--verify-only`, and writes
  `fresh_clone_smoke_report.json` plus per-step logs.
- Added a manual GitHub Actions `workflow_dispatch` job for fresh-clone smoke.
  Normal push and pull-request CI still avoids downloading large Git LFS model
  assets.
- Added a Slicer `Prepare Inputs` panel that wraps the existing DICOM,
  NIfTI+bval/bvec, NRRD/NHDR and canonical subject-root import logic and writes
  `input/input_import_manifest.json`.
- Added model-asset UI controls for checking core/all status, verifying the
  core profile, and writing a core model-asset lockfile.
- Updated `make test-slicer` so it can run either through `xvfb-run` or through
  an existing X/VNC display using `SLICERDDSURFER_USE_EXISTING_DISPLAY=1`.
- Added `GITHUB_RELEASE_DRAFT_v0.1.0.md` with a ready-to-review GitHub Release
  body, attachment list and DOI/code-only archive boundary.
- Added `scripts/create_github_release.py`, a GitHub REST API helper that can
  validate the release plan in dry-run mode or create the draft release and
  upload artifacts when `GITHUB_TOKEN` or `GH_TOKEN` is available.
- Extended the manual GitHub Actions workflow with `create_github_release=true`
  so maintainers can create or update the draft GitHub Release from the GitHub
  UI using the workflow `GITHUB_TOKEN`. If `run_fresh_clone_smoke=true` is used
  in the same dispatch, the smoke report is attached to the release.
- Updated `README.md`, `RELEASE.md` and `DOI_ARCHIVE_PREP.md` with the new
  smoke gate, Slicer smoke modes, release draft and DOI boundary.

## Verification Performed

- `make test-fast`: 223 tests passed.
- `python3 scripts/release_audit.py`: `release_ready=True`, `blockers=0`,
  `warnings=0`.
- `python3 scripts/download_model_assets.py --profile core --verify-only`:
  29 core files verified.
- `python3 scripts/download_model_assets.py --profile all --verify-only`:
  33 LFS-managed files verified.
- Fresh clone from the local committed checkout passed all smoke steps.
- Fresh clone from `git@github.com:ChengjinLii/SlicerDDSurfer.git` on `main`
  passed all smoke steps:
  `git_clone`, `git_checkout`, `download_model_assets_core`,
  `make_test_fast`, and `verify_model_assets_core`.
- `make test-slicer` passed with the existing `:99` X/VNC display and Slicer
  5.10 after providing the missing `libpcre2-16.so.0` locally through
  `LD_LIBRARY_PATH`.

## Remaining Manual Boundary

- The GitHub Release page itself was not created from this local shell because
  no `GITHUB_TOKEN`/`GH_TOKEN` is available. It can now be created from GitHub
  Actions with `create_github_release=true`, or from a maintainer machine with
  `scripts/create_github_release.py`.
- DOI remains code-only unless every model/template/validation asset group has
  confirmed redistribution and DOI-archive permission.
