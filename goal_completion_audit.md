# Goal Completion Audit

Date: 2026-06-17

This audit maps the active thread goal to current repository evidence. It is
not a submission-readiness declaration. It records what is implemented,
validated and still incomplete.

## Summary

Overall status: not fully complete.

The release-validation, dependency-profile, output-semantics, model-governance
and manuscript-source-data work now has concrete repository evidence. The
remaining software-side gap is the larger Slicer GUI simplification requested in
the goal: the interface has been polished and grouped, but it has not yet been
fully redesigned into a strict three-step "choose input, choose products, run"
flow. Cross-platform dependency logic exists, but Windows and macOS have not
been executed on native Windows/macOS hosts in this audit.

The manuscript package is now versioned, the normal manuscript validation gate
passes, and the validation source-data package is complete except for the
optional UI screenshot. Full submission readiness remains intentionally open
for author metadata, release DOI/license, LFS asset terms and final Word
production items; those are tracked but were explicitly not resolved in this
goal pass.

## Evidence Commands

Last verified in this checkout:

```bash
make -C manuscript_nature_protocols validate
make -C manuscript_nature_protocols validation-package-check
make -C manuscript_nature_protocols readiness-check
make -C manuscript_nature_protocols release-metadata-check asset-availability-check
python3 -m unittest Testing/Python/test_release_validation.py Testing/Python/test_model_assets.py Testing/Python/test_environment_doctor.py
python3 -m unittest Testing/Python/test_release_validation.py Testing/Python/test_model_assets.py Testing/Python/test_product_orchestrator.py Testing/Python/test_run_batch_pipeline.py Testing/Python/test_run_subject_pipeline_cli.py Testing/Python/test_environment_doctor.py
python3 -m py_compile scripts/release_validation.py shared/orchestrator.py shared/environment.py shared/module_widget.py scripts/download_model_assets.py scripts/install_dependencies.py
```

Key current commits:

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
  `validation_optional_missing=1`,
  `validation_missing_optional=ui_smoke_screenshot`,
  `validation_package_complete=True`.

Remaining boundary:

- The optional UI screenshot is not present. The UI smoke command/log evidence
  is present.

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
  `/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/00_run_metadata/release_validation/release_validation_report.json`.
- Unit tests for release validation pass.

Boundary:

- The committed release-validation script supports Slicer smoke, but the most
  recent machine-readable dry-run report skipped Slicer smoke while a separate
  staged Slicer smoke log passed and is included in the validation source-data
  package.

### Dependency installation and dependency profile

Status: implemented for scanning, export/import, Python auto-install planning
and platform-specific wrapper entry points.

Evidence:

- `shared/environment.py`
- `shared/module_widget.py`
- `scripts/install_dependencies.py`
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

Boundary:

- Native Windows and native macOS execution were not performed in this audit.
  The code paths and wrappers are present and unit-tested where practical on
  Linux.

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

Status: partially implemented.

Evidence:

- `shared/module_widget.py`
- `0011bee Polish Slicer external path UI`
- Earlier UI smoke evidence in the validation source-data package.

Implemented behavior:

- External path groups were renamed and regrouped.
- Model assets are handled as a unified model-assets concept.
- Batch styling and dependency-dialog styling were improved.
- Advanced dependency summaries are hidden behind detail controls.
- Run name default was changed to `Test1`.

Remaining gap:

- The whole Slicer panel has not been fully restructured into a strict
  three-step workflow. Advanced dependencies, backends, batch options and
  streamlines are improved, but the main UI is still partly an engineering
  configuration panel.

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

1. Finish the GUI three-step restructuring if strict user-facing simplicity is
   required before release.
2. Run dependency doctor dry-runs on native Windows and native macOS machines.
3. Decide whether the optional UI screenshot should be added to the validation
   source-data package.
4. Resolve external submission blockers only when author, license, release DOI
   and model-asset terms are ready.
5. Generate a release-validation report with Slicer smoke included in the same
   report, or keep the current split evidence and document that split in the
   release notes.
