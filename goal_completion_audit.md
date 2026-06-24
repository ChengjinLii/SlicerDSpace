# Goal Completion Audit

Date: 2026-06-24

Scope: code, packaging, dependency handling, Slicer UI engineering and release
readiness. Manuscript wording and Nature Protocols style edits are intentionally
deferred per the current user instruction.

Overall status: release-candidate code work is mostly complete; final release is
not complete yet.

The code-side release infrastructure is now much stronger than the previous
state: fast tests, CMake test registration, dependency schema, conservative
installer behavior, Python/conda path configuration, Slicer extension metadata
checks, representative-output collection, release metadata files, model-asset
download governance and UI module extractions are in place. The goal should not
be marked complete yet because the worktree is not committed, `make test-slicer`
has not been run in this environment, and DOI/model-asset redistribution terms
require external decisions outside this checkout.

## Verification

Commands run in this checkout:

```bash
make test-fast
python3 scripts/download_model_assets.py --profile core --verify-only
python3 scripts/audit_slicer_extension_metadata.py --json
python3 scripts/release_validation.py --warn-only
SLICERDDSURFER_RELEASE_SUBJECT_ROOT=/data/chengjin/SlicerDDSurfer-test/100307-release-candidate make release-check
```

Results:

- `make test-fast`: passed, 207 Python tests.
- `download_model_assets.py --profile core --verify-only`: passed; 29 core
  files verified and terms notices were printed for DDCSR, DDSeg and DDParcel
  assets.
- `audit_slicer_extension_metadata.py`: passed, zero errors and zero warnings;
  CMake and `.s4ext` both depend on `SlicerDMRI` and `PyTorch`.
- `release_validation.py --warn-only`: exits with an explicit error because no
  `--subject-root` or `SLICERDDSURFER_RELEASE_SUBJECT_ROOT` was provided. This is
  expected and confirms it no longer silently defaults to a local dataset path.
- `make release-check`: passed with
  `SLICERDDSURFER_RELEASE_SUBJECT_ROOT=/data/chengjin/SlicerDDSurfer-test/100307-release-candidate`.
  The release audit reported `release_ready=True`, `blockers=0`, and one dirty
  worktree warning. Model asset verification checked 29 core files.
- `make test-slicer`: not run because this checkout has a Slicer launcher at
  `/data/chengjin/software/Slicer-5.10.0-linux-amd64/Slicer` but `xvfb-run` is
  not available in the current environment.

## Requirement Audit

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | Standard dev/CI entrypoints: `pyproject`, `make test-fast`, `test-slicer`, `release-check` | Complete | `pyproject.toml`; `Makefile`; `make test-fast` passed. |
| 2 | Fix CMake test registration | Complete | `Testing/CMakeLists.txt` adds `Testing/Python`; registered Python tests in `Testing/Python/CMakeLists.txt`. |
| 3 | Split `shared/module_widget.py` into focused UI modules | Mostly complete | Added `shared/ui_environment_panel.py`, `shared/ui_environment_paths.py`, `shared/ui_environment_dialog.py`, `shared/ui_run_controller.py`, `shared/ui_output_loading.py`, `shared/ui_error_dialogs.py`, `shared/ui_styles.py`, `shared/ui_parameter_sync.py`, `shared/ui_run_status_panel.py` and tests. Run-plan/result rows, manifest summaries, run kwargs builders, batch/single-subject input validation, plan-blocker extraction, partial-run text and background progress key mapping now live in `ui_run_controller.py`; environment path status mapping, detected-source text, backend highlight styles, model-assets summary text, Environment Paths schema iterator and environment-dialog render state now live in `ui_environment_panel.py`; Qt Environment Paths construction now lives in `ui_environment_paths.py`; environment-results dialog construction now lives in `ui_environment_dialog.py`; global UI styles, run-summary state styles and environment-dialog styles now live in `ui_styles.py`; parameter-node to widget synchronization now lives in `ui_parameter_sync.py`; run status panel construction/table updates now live in `ui_run_status_panel.py`. `shared/module_widget.py` is 1990 lines and its largest function is 112 lines. |
| 4 | Remove local hardcoded defaults from `scripts/release_validation.py` | Complete | `release_validation.py` now requires `--subject-root` or `SLICERDDSURFER_RELEASE_SUBJECT_ROOT`; missing input fails explicitly. |
| 5 | Unify dependency config schema | Complete | `shared/dependency_config.py` is the shared schema source; Python executable, Python/conda environment and external paths flow through this schema. |
| 6 | Make pip installer conservative with per-package logs and failure categories | Complete | `scripts/install_dependencies.py`; `python_install_results.json`; categories include package unavailable, non-writable Python environment, network and pip failure. |
| 7 | Schema-driven UI Environment Paths | Complete | UI grouping/highlighting uses dependency schema helpers in `shared/ui_environment_panel.py`; Qt rendering and config buttons now live in `shared/ui_environment_paths.py`; model assets are a single manifest-backed row rather than separate weight-path entries. |
| 8 | Clarify optional backend versus core validity | Complete | Dependency checks distinguish runnable core targets from optional backend setup; external tools are reported with setup notes and not silently installed. |
| 9 | Manuscript notes should not affect code release audit | Complete | Manuscript notes live under `manuscript_nature_protocols/notes/`; validation scripts ignore notes. |
| 10 | Script representative outputs/source data/timing JSON for Figure 3/4 evidence | Code side complete, manuscript side deferred | `scripts/collect_representative_outputs.py` exists and is integrated into `scripts/release_validation.py`; final manuscript figure replacement audit is paused. |
| 11 | Add LICENSE, CITATION and release tag/DOI flow | Partial | `LICENSE`, `CITATION.cff`, `codemeta.json`, `.zenodo.json`, `RELEASE.md` and `MODEL_ASSET_TERMS.md` are present. `CITATION.cff`, `codemeta.json` and `.zenodo.json` are set to version `0.1.0`. `make release-check` passes locally, but no DOI archive exists and final model-asset redistribution/DOI-archive terms remain external blockers. |
| 12 | Clean manuscript WIP out of the release worktree | Complete | `.gitignore` ignores `ignore/`; manuscript WIP is archived under `ignore/manuscript_wip_2026-06-24/` with `manuscript_tracked_changes.patch`, notes and reference PDF. |

## Current Remaining Work

- Commit or otherwise finalize the current release-candidate worktree, then
  create the local `v0.1.0` tag. The current `release-check` warning is the
  dirty worktree.
- Run `make test-slicer` after installing or providing `xvfb-run` for the local
  Slicer launcher.
- Resolve external release metadata: create the actual GitHub release tag and
  DOI. Do not create an asset-inclusive DOI archive until model-asset
  redistribution and DOI-archive terms are confirmed in `MODEL_ASSET_TERMS.md`.
- When manuscript work resumes, audit and replace Figure 3/4 evidence from the
  representative-output collector and manuscript source-data package.
- Generate the final “all improvements summary” Markdown only after the above
  completion boundary is reached, so it is not mistaken for a finished-goal
  report.

## Recommended Next Action

The remaining locally actionable release step is to stage/commit the
release-candidate changes and, if `xvfb-run` becomes available, run
`make test-slicer`. DOI publication remains gated by external archive metadata
and model-asset terms.
