# Goal Completion Audit

Date: 2026-06-17

This audit maps the active thread goal to current repository evidence. It is
not a submission-readiness declaration. It records what is implemented,
validated and still incomplete.

## Summary

Overall status: not fully complete.

The release-validation, dependency-profile, output-semantics, model-governance
and manuscript-source-data work now has concrete repository evidence. The
Slicer GUI has also been restructured around the requested three-step
"choose input, choose products, run" flow, with advanced dependency and runtime
controls folded by default. Cross-platform dependency logic now includes a
Linux/macOS/Windows profile matrix dry-run, but Windows and macOS have not been
executed on native Windows/macOS hosts in this audit.

The manuscript package is now versioned, the normal manuscript validation gate
passes, and the validation source-data package is complete, including the
optional UI screenshot record. Full submission readiness remains intentionally
open for author metadata, release DOI/license, LFS asset terms and final Word
production items; those are tracked but were explicitly not resolved in this
goal pass.

## Evidence Commands

Last verified in this checkout:

```bash
make -C manuscript_nature_protocols validate
make -C manuscript_nature_protocols validation-package-check
make -C manuscript_nature_protocols readiness-check
make -C manuscript_nature_protocols release-metadata-check asset-availability-check
python3 -m unittest Testing/Python/test_release_validation.py Testing/Python/test_model_assets.py Testing/Python/test_environment_doctor.py Testing/Python/test_dependency_profile_matrix.py
python3 -m unittest Testing/Python/test_release_validation.py Testing/Python/test_model_assets.py Testing/Python/test_product_orchestrator.py Testing/Python/test_run_batch_pipeline.py Testing/Python/test_run_subject_pipeline_cli.py Testing/Python/test_environment_doctor.py
python3 -m unittest Testing/Python/test_slicer_ui_layout_contract.py
python3 -m py_compile scripts/release_validation.py shared/orchestrator.py shared/environment.py shared/module_widget.py scripts/download_model_assets.py scripts/install_dependencies.py scripts/dependency_profile_matrix.py
python3 scripts/install_dependencies.py --targets validation --platform Windows --output-dir /tmp/slicerdsurfer_install_dependencies_windows_smoke
python3 scripts/dependency_profile_matrix.py --output-dir /data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/00_run_metadata/dependency_profile_matrix
python3 scripts/release_validation.py --subject-root /data/chengjin/SlicerDDSurfer-test/100307-release-candidate --batch-root /data/chengjin/SlicerDDSurfer-test/release-validation-batch --report-dir /data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/00_run_metadata/release_validation_with_smoke --run-name Test1 --timeout-seconds 300 --warn-only --skip-environment-check
```

The latest GUI layout change was also checked with a staged headless Slicer
smoke test using `scripts/stage_slicer_extension.py --link-mode copy`,
`xvfb-run`, `--disable-cli-modules` and
`Testing/Python/slicer_extension_install_smoke.py`.

Prior key commits before this audit update:

- `d4e21c1 Add Nature Protocols manuscript package`
- `828eab6 Improve dependency profile portability`
- `974ced4 Add release validation evidence workflow`
- `0011bee Polish Slicer external path UI`
- `7ecf182 Document model asset term boundaries`

## Requirement Audit

### Manuscript content and Nature Protocols style

Status: implemented for the repository draft, not final submission-ready.

Evidence:

- `manuscript_nature_protocols/main.tex`
- `manuscript_nature_protocols/sections/`
- `manuscript_nature_protocols/figures/`
- `manuscript_nature_protocols/tables/`
- `manuscript_nature_protocols/guidance/nature_protocols_style_examples.md`
- `manuscript_nature_protocols/guidance/source_guidelines.md`
- `make -C manuscript_nature_protocols validate` passed.

Remaining boundary:

- `make -C manuscript_nature_protocols readiness-check` reports 11 active
  readiness blockers, mostly author metadata, supporting-paper status,
  license/release/DOI, LFS asset terms and final Word production. These are
  tracked in `manuscript_nature_protocols/guidance/completion_audit_manifest.csv`
  and `manuscript_nature_protocols/guidance/submission_blockers.csv`.

### Validation source data package

Status: complete for required metadata-only validation artifacts.

Evidence:

- `manuscript_nature_protocols/supplementary/scripts/collect_validation_source_data.py`
- `manuscript_nature_protocols/supplementary/source_data/validation/`
- `manuscript_nature_protocols/supplementary/source_data/validation_expected_manifest.csv`
- `manuscript_nature_protocols/supplementary/source_data/validation_gap_snapshot.json`
- `make -C manuscript_nature_protocols validation-package-check` reports:
  `validation_required_missing=0`,
  `validation_optional_missing=0`,
  `validation_package_complete=True`.

Remaining boundary:

- The package is complete according to the current expected manifest. Manual
  redaction and data-use review are still required before public submission.

### Final completion audit

Status: implemented as manuscript readiness audit plus this thread-level audit.

Evidence:

- `manuscript_nature_protocols/guidance/completion_audit_manifest.csv`
- `manuscript_nature_protocols/scripts/check_completion_audit.py`
- `make -C manuscript_nature_protocols validate` includes
  `completion_audit_status=passed`.
- This file records the thread-level software/manuscript objective audit.

### Release and reproducibility validation loop

Status: implemented.

Evidence:

- `scripts/release_validation.py`
- `Testing/Python/test_release_validation.py`
- `README.md` release validation section.
- Generated example report path from the validation run:
  `/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/00_run_metadata/release_validation_with_smoke/release_validation_report.json`.
- The report summary is `status=passed`, `step_count=9`, with
  `slicer_smoke=passed` and no skipped steps.
- Unit tests for release validation pass.

### Dependency installation and dependency profile

Status: implemented for scanning, export/import, Python auto-install planning
and platform-specific wrapper entry points.

Evidence:

- `shared/environment.py`
- `shared/module_widget.py`
- `scripts/install_dependencies.py`
- `scripts/dependency_profile_matrix.py`
- `scripts/install_deps_linux.sh`
- `scripts/install_deps_macos.sh`
- `scripts/install_deps_windows.ps1`
- `EXTERNAL_DEPENDENCIES.md`
- `Testing/Python/test_environment_doctor.py`
- `828eab6 Improve dependency profile portability`.

Implemented behavior:

- Python packages can be installed only when explicitly requested.
- External tools such as MRtrix3, FSL, FreeSurfer, WMA and TractCloud are
  detected and reported with setup notes instead of being silently installed.
- Imported dependency configs are treated as path hints and are re-scanned on
  the current machine.
- Windows command scanning checks extensionless command names plus `.exe`,
  `.cmd` and `.bat` variants.
- The dependency profile matrix writes per-platform `environment_doctor.json`,
  `dependency_profile.json`, Python install helpers and external setup notes
  for Linux, Darwin/macOS and Windows discovery rules.

Boundary:

- Native Windows and native macOS execution were not performed in this audit.
  The matrix rows for non-native platforms are platform-rule dry-runs on the
  current host, not proof that those operating systems have the tools installed.

### Output directory semantics

Status: implemented.

Evidence:

- `shared/orchestrator.py`
- `Testing/Python/test_product_orchestrator.py`
- `outputs/00_run_metadata/output_tree_semantics.json` generated by the
  orchestrator.

Implemented behavior:

- Expected top-level output directories are derived from selected targets.
- Unselected stages are not treated as required missing output directories.
- The semantics manifest distinguishes selected, unselected, blocked, reused,
  empty and populated output states.

### GUI usability

Status: implemented for the current Slicer panel.

Evidence:

- `shared/module_widget.py`
- `Resources/UI/SlicerDDSurfer.ui`
- `Testing/Python/test_slicer_ui_layout_contract.py`
- `0011bee Polish Slicer external path UI`
- Staged headless Slicer smoke on 2026-06-17:
  `/tmp/slicerdsurfer_ui_layout_smoke.log`.
- Earlier UI smoke evidence in the validation source-data package.

Implemented behavior:

- The primary panel now presents a three-step sequence: `1. Choose input`,
  `2. Choose products`, and `3. Run`.
- The run action is simplified to `Preflight and run`.
- Dependency profile controls are under `Advanced: Dependency profile` and are
  collapsed by default.
- Backend, batch, streamlines and optional microstructure controls are under
  `Advanced settings: backends, batch, streamlines` and are collapsed by
  default.
- External path groups were renamed and regrouped.
- Model assets are handled as a unified model-assets concept.
- Batch styling and dependency-dialog styling were improved.
- Advanced dependency summaries are hidden behind detail controls.
- Run name default was changed to `Test1`.

Boundary:

- This audit confirms module load and layout contract, not manual usability on
  every screen size.

### Error messages

Status: implemented for major user-facing paths.

Evidence:

- `shared/module_widget.py`
- Key dialogs now use an actionable structure: what happened, why, what to do
  next, automatic fix availability and details.

Boundary:

- This audit did not exhaustively click every possible error path in the GUI.
  Unit and smoke evidence cover the main dependency and planning paths.

### Model weight governance

Status: implemented as workflow and documentation; final asset terms remain
open for submission.

Evidence:

- `MODEL_ASSETS.md`
- `scripts/download_model_assets.py`
- `Testing/Python/test_model_assets.py`
- `manuscript_nature_protocols/guidance/lfs_asset_terms_manifest.csv`
- `manuscript_nature_protocols/guidance/lfs_asset_inventory.csv`
- `make -C manuscript_nature_protocols asset-availability-check` reports no
  manifest hard errors.

Boundary:

- Asset redistribution and DOI-archive terms remain unresolved and tracked as
  `lfs_asset_terms`, as requested.

### Terminology consistency

Status: implemented for the committed manuscript and docs.

Evidence:

- `manuscript_nature_protocols/guidance/software_terminology_alignment.md`
- `manuscript_nature_protocols/guidance/terminology_manifest.csv`
- `manuscript_nature_protocols/scripts/check_terminology.py`
- `make -C manuscript_nature_protocols validate` reports
  `terminology_status=passed`.

## Remaining Recommended Work

1. Run dependency doctor dry-runs on native Windows and native macOS machines.
2. Resolve external submission blockers only when author, license, release DOI
   and model-asset terms are ready.
