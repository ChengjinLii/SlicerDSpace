# Release-Candidate Improvement Summary

Date: 2026-06-24

Version target: `v0.1.0`

This summary covers the non-manuscript work completed for the current
SlicerDDSurfer release-candidate goal.

## Engineering And Packaging

- Added standard developer entrypoints through `Makefile` and `pyproject.toml`.
- Added release metadata scaffolding: `LICENSE`, `CITATION.cff`,
  `codemeta.json`, `.zenodo.json` and `RELEASE.md`.
- Set release metadata to version `0.1.0` for the first code/documentation
  release tag.
- Fixed Python test registration under CMake so repository tests are discoverable
  from the extension build tree.
- Added Slicer extension metadata auditing for `.s4ext`, CMake dependencies and
  module help text.

## Dependency And Runtime Handling

- Centralized dependency-path schema in `shared/dependency_config.py`.
- Added conservative Python environment handling with Slicer Python and optional
  conda/runtime path configuration.
- Updated dependency installation so Python packages require explicit user
  action and external runtimes are never installed silently.
- Expanded dependency checks for common Windows, macOS and Linux paths.
- Added per-package install result logging and clearer failure categories for
  pip failures, non-writable environments, unavailable packages and network
  problems.

## Model Assets

- Added a unified model-asset download and verification route through
  `MODEL_ASSETS.md`, `models/assets_manifest.json` and
  `scripts/download_model_assets.py`.
- Added `MODEL_ASSET_TERMS.md` to separate local asset verification from public
  redistribution and DOI-archive permission.
- Verified the current `core` model-asset profile locally: 29 files checked.
- Current release decision: code/documentation release can proceed after normal
  release gates; asset-inclusive DOI archive must wait for confirmed asset
  redistribution and archive terms.

## UI And Slicer Module Structure

- Split `shared/module_widget.py` into focused helpers:
  `ui_environment_panel.py`, `ui_environment_paths.py`,
  `ui_environment_dialog.py`, `ui_run_controller.py`,
  `ui_run_status_panel.py`, `ui_parameter_sync.py`, `ui_output_loading.py`,
  `ui_error_dialogs.py` and `ui_styles.py`.
- Reduced `shared/module_widget.py` to about 1990 lines; its largest remaining
  function is the high-level run orchestration handler at about 112 lines.
- Improved Environment Paths grouping so model assets are handled as one
  manifest-backed bundle and optional WMA/TractCloud paths are visually grouped.
- Kept preflight text and detailed target/backend summaries behind explicit
  controls to reduce UI clutter.

## Pipeline, Validation And Outputs

- Removed local hardcoded defaults from release validation; subject root must be
  supplied explicitly or through `SLICERDDSURFER_RELEASE_SUBJECT_ROOT`.
- Added representative-output collection support for release validation and
  source-data inventory.
- Added MRtrix-backed brain-mask generation support without silently inventing a
  custom masking method.
- Preserved structured provenance, logs and release-validation report generation.

## Verification

Commands passed in the current checkout:

```bash
python3 scripts/download_model_assets.py --profile core --verify-only
make test-fast
python3 scripts/audit_slicer_extension_metadata.py --json
SLICERDDSURFER_RELEASE_SUBJECT_ROOT=/data/chengjin/SlicerDDSurfer-test/100307-release-candidate make release-check
```

Results:

- `make test-fast`: 207 tests passed.
- Model assets: 29 core files verified.
- Metadata audit: zero errors and zero warnings.
- `release-check`: passed with `release_ready=True`, `blockers=0` and one dirty
  worktree warning.

## Remaining Release Gates

- Commit or otherwise finalize the release-candidate worktree.
- Run `make test-slicer` after `xvfb-run` is available for the local Slicer
  launcher.
- Choose the release version and update `CITATION.cff` and `codemeta.json`.
- Confirm model-asset redistribution and DOI-archive terms, or explicitly make
  the DOI archive code/documentation-only.
- Create and push the release tag only after the worktree is clean and the
  selected release scope is final.
