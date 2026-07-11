# Beginner Workflow and Configuration Summary

Date: 2026-07-11

This release work focused on making SlicerDDSurfer usable without prior
experience with Python environments, system `PATH` configuration or model
asset management.

## User-facing improvements

- A first-run setup wizard checks Slicer Python, model assets and external
  software, then presents a capability report.
- A one-click synthetic, non-human demo runs a lightweight DTI and
  deterministic-tractography trial without requiring private data, model
  weights or MRtrix3. Key scalar maps and the generated fibre bundle are loaded
  back into the Slicer scene.
- The main panel now provides English and Chinese labels, path examples, a
  runnable/blocked capability dashboard, actionable error dialogs and a
  copyable diagnostic report.
- Platform-specific setup pages separate Windows, macOS and Linux/HPC
  instructions.
- Model downloads expose progress, checksum verification and resumable partial
  files. A public 150-byte sentinel verifies network, mirror and checksum
  handling without downloading large weights.

## Shared settings

- The GUI and CLI share a versioned, user-local `user_config.json`.
- Language, recent subject/output paths, selected targets, backends,
  microstructure stages, streamline count, Python environment, model root and
  external software paths are restored after the first setup.
- Direct CLI options override an explicit dependency profile, which overrides
  the personal user config. CLI target and stage expansions are saved in their
  resolved form.
- The GUI retains compatible Slicer QSettings while treating the JSON file as
  the portable profile. Common field edits are saved after a short debounce;
  clearing a configured path removes it from both stores.
- Slicer-dependent DTI/anatomical targets require the real `slicer.util`
  runtime. System Python is stopped during preflight with a PythonSlicer setup
  instruction instead of failing after processing starts.

See [USER_CONFIG.md](../setup/USER_CONFIG.md) for paths and CLI examples.

## Benchmark export

`scripts/generate_protocol_benchmarks.py` converts orchestration manifests and
stage QC/progress records into run-, task-, storage- and stage-level CSV files,
a JSON summary, and PNG/SVG figures. It separates algorithm computation from
resume-check overhead, treats absent storage snapshots as missing rather than
zero, and reports per-stage medians and interquartile ranges for multi-subject
inputs.

The current local report is in
`ignore/protocol_benchmarks_20260710/`. It contains one complete subject and is
therefore descriptive only. Its recorded stage times include NODDI (25.96 min),
Free Water (21.81 min), CSD/ACT tractography (6.12 min), SAF (2.97 min) and
DDSurfer surface reconstruction (1.19 min). Cohort-scale repeated runs are
still required before making comparative performance claims.

The separate beginner-demo report is in
`ignore/protocol_benchmarks_demo_20260711/`. The current synthetic run completed
input validation, DTI scalar mapping and deterministic tractography in 2.51 s
of orchestration wall time. This measures a tiny functional smoke case, not
scientific-data performance.

See [PROTOCOL_BENCHMARKS.md](PROTOCOL_BENCHMARKS.md) for interpretation rules.

## Verification

- 275 repository Python tests passed.
- Real Slicer 5.10 extension smoke testing passed for module registration,
  parameter-node setup, onboarding controls, language switching and JSON target
  persistence.
- Real Slicer dependency-workflow smoke testing passed for model download UI,
  external path selection, persistence, clearing and restoration.
- A real one-click Slicer demo completed all three tasks and auto-loaded both
  the FA map and TRK tractogram into the MRML scene. TRK/TCK files are converted
  in memory to SlicerDMRI fibre nodes when the native loader cannot read them.
- Extension metadata audit and release audit passed with no blockers.
- The public model sentinel downloaded and verified successfully.

The optional `ruff` lint target was not run because `ruff` is not installed in
the current host Python. Syntax compilation, `git diff --check`, unit tests and
real-Slicer tests passed.
