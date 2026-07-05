# Repository Layout

This repository is organized as a 3D Slicer scripted extension with a stable
top-level module entry point and Python package directories for the processing
domains.

## Root Directory

The root directory should stay small because it is the first view users see on
GitHub and because 3D Slicer scans top-level scripted-module files.

Keep only:

- `SlicerDDSurfer.py`: the Slicer scripted-module entry point.
- `SlicerDDSurfer.s4ext`: Slicer extension metadata.
- `CMakeLists.txt`: extension packaging.
- `README.md` and `README.zh-CN.md`: short user entry points.
- `LICENSE`, `CITATION.cff`, `codemeta.json`, `.zenodo.json`: project metadata.
- `Makefile`, `pyproject.toml`, `requirements-ci.txt`: development and CI entry points.
- `run_subject_pipeline.py`: stable CLI entry point documented for users.
- `run_postprocess_docker.py`: legacy container helper retained for compatibility.
- `workflow_catalog.py`: stable workflow catalog module used by tests and CLI.

Do not add generated reports, manuscripts, release drafts, validation outputs,
or long design notes to the root directory. Put durable documentation under
`docs/`; put local reports under ignored `ignore/` or `local_reports/`.

## Documentation

- `docs/assets/`: model-asset manifest, download policy, redistribution notes.
- `docs/setup/`: dependency and installation guidance.
- `docs/release/`: release workflow, release notes and DOI/archive guidance.
- `docs/architecture/`: design and repository-structure notes.

This mirrors the SlicerDMRI pattern of keeping project documentation in a
dedicated documentation tree instead of crowding the repository root.

## Source Packages

- `shared/`: common Slicer UI, dependency, IO, reporting and orchestration code.
- `preprocessing/`, `segmentation/`, `parcellation/`, `surface/`,
  `microstructure/`, `tractography/`, `connectome/`: domain-specific pipeline
  packages.
- `models/assets_manifest.json`: canonical model/template asset manifest.

The current layout keeps each processing domain importable as a plain Python
package. A future Slicer-style `Modules/Scripted/SlicerDDSurfer/` migration is
possible, but it should be done as a dedicated compatibility release because it
would affect module loading, packaging paths and documented CLI examples.

## Resources And Assets

- `Resources/Icons/` and `Resources/UI/` are normal Slicer extension resources.
- Large model weights and templates are not tracked in this code repository.
  They are restored from the independent `SlicerDDSurfer-models` repository or
  another manifest-compatible mirror.
- Keep only `models/assets_manifest.json`, checksums and download tooling in
  this code repository.

## Testing

- `Testing/Python/test_*.py` contains unittest-discovered tests.
- `Testing/Python/run_*_smoke.py`, `slicer_*_smoke.py`, `summarize_*.py` and
  related helpers are manual or release-candidate smoke tools.

The flat `Testing/Python` layout is retained for simple unittest discovery and
Slicer extension compatibility. If the helper set grows further, split it into
`Testing/Python/smoke/` and `Testing/Python/tools/` in a dedicated refactor.

## Third-Party Or Reference Code

- `tractography/saf_backend/` is bundled runtime code used by SAF tracking.
- `tractography/slicer_dmri_reference/` is reference material and should not be
  packaged as runtime extension code.
- `third_party/` is ignored and must not be used for packaged runtime content.

Any bundled third-party code must include provenance and license information.
