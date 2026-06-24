# Slicer Module Comparison Notes

This note records engineering gaps found by comparing SlicerDDSurfer with the local SlicerDMRI, WMA, TractCloud and tract-parcellation reference modules, plus common deep-learning Slicer extension patterns.

## Already Covered

- Slicer extension packaging declares Slicer-level dependencies through `CMakeLists.txt` and `SlicerDDSurfer.s4ext`.
- The runtime dependency doctor lets the UI load before reporting missing optional tools or model resources.
- Core execution is scriptable from the CLI and testable outside Slicer.
- Long-running jobs run in a background process, with logs and cancellation state.
- Model assets have a manifest-driven download and verification path in `MODEL_ASSETS.md` and `scripts/download_model_assets.py`.
- The repository now has fast unit tests, Slicer smoke entrypoints, release metadata checks, and representative output inventory generation.

## Gaps To Keep Tracking

- Sample data: SlicerDMRI-style modules commonly expose small SampleData entries for immediate GUI smoke tests. SlicerDDSurfer still needs a redistributable minimal diffusion fixture before this can be added safely.
- Scene-native inputs: several Slicer modules accept MRML nodes directly. SlicerDDSurfer currently prioritizes subject-root folders, which is better for full protocol runs but less convenient for quick interactive experiments.
- Model provenance in the UI: the downloader verifies assets, but the GUI should eventually show profile, resolved path, LFS pointer status and checksum state in one compact panel.
- Deep-learning runtime install flow: PyTorch-centered extensions usually delegate torch installation to the Slicer PyTorch extension. SlicerDDSurfer depends on PyTorch but should continue avoiding silent external installs.
- Module metadata drift: SlicerDDSurfer now has an automated metadata audit; keep it in CI so `.s4ext`, CMake and help text stay synchronized.
- `shared/module_widget.py` remains too large. More pure helpers should be split out so UI formatting, dependency summary, output loading and process handling can be tested without Slicer.

## Current Policy

- Do not auto-install external runtimes such as MRtrix3, FSL, FreeSurfer, WMA command-line tools or TractCloud system dependencies.
- Python packages may be installed only into the active Slicer Python environment when the user explicitly clicks the install action.
- Model weights and templates are treated as release assets with explicit download, verification and redistribution notes.
