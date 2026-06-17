# SlicerDDSurfer

SlicerDDSurfer is a 3D Slicer scripted module that bundles multiple diffusion-MRI workflows in one extension:

- **DDSurfer**: cortical surface reconstruction (white/pial meshes) from DTI-derived scalar volumes.
- **DDParcel**: 101-region parcellation pipeline built on diffusion features.
- **DDSeg**: WM/GM/CSF segmentation from DWI using multi-view CNNs.
- **Microstructure**: FA/MD, ROI-wise statistics, Free Water, and AMICO NODDI.
- **Tractography**: DTI tracking, MRtrix CSD/FOD/ACT, WMQL bundles, WMA, TractCloud wrapper, and SAF short association fibres.
- **Connectome**: tractography + DDParcel streamline-count, SIFT2, length, and scalar-weighted matrix execution.
- **Surface post-process**: bundled DDSurfer postprocess backend for FreeSurfer-style surf/label/stats refinement.

**Chinese version:** [README.zh-CN.md](README.zh-CN.md)

**External dependencies and local configuration:** [EXTERNAL_DEPENDENCIES.md](EXTERNAL_DEPENDENCIES.md)

**Model weights and template downloads:** [MODEL_ASSETS.md](MODEL_ASSETS.md)

**Release-candidate install/run validation:** [RELEASE_CANDIDATE_VALIDATION.md](RELEASE_CANDIDATE_VALIDATION.md)

The Slicer UI and CLI both support external dependency path overrides. In Slicer, use `Environment & Dependencies` to import/export a CLI-compatible dependency config; on the CLI, use explicit path flags or `--dependency-config` / `--save-dependency-config`.
Imported dependency profiles are re-scanned on the current machine; saved paths are treated as hints, not proof that another computer has the same environment.

After each orchestrated run, SlicerDDSurfer writes:
- `outputs/00_run_metadata/<run_name>_orchestration_manifest.json`
- `outputs/00_run_metadata/output_tree_audit.json`
- `outputs/00_run_metadata/output_tree_semantics.json`
- `outputs/06_slicer_scene_report/report.html`
- `outputs/06_slicer_scene_report/output_tree.html`
- `outputs/06_slicer_scene_report/summary.md`
- `outputs/06_slicer_scene_report/provenance.json`
- `outputs/06_slicer_scene_report/qc_summary.json`

Before pushing a release branch, run:

```bash
python3 scripts/release_audit.py
```

For a fuller reproducibility check that plans the subject pipeline, batch path,
WMQL/WMA/TractCloud bundle routes, output-tree HTML, release audit and optional
Slicer smoke, run:

```bash
python3 scripts/release_validation.py \
  --subject-root /path/to/subject \
  --batch-root /path/to/study_subjects \
  --run-name Test1 \
  --warn-only
```

The default mode plans scientific workflows. Add `--execute` only for a
prepared long-running validation host. The script writes
`outputs/00_run_metadata/release_validation/release_validation_report.json`.

---

## Model Weights And Templates

Model weights and template assets are stored with Git LFS. Install Git LFS first, then download the recommended core asset profile before running DDSurfer, DDSeg, or DDParcel:

```bash
scripts/download_model_assets.sh --profile core
```

Profiles and required paths are defined in `models/assets_manifest.json`. To inspect what a profile will download without touching the network:

```bash
python3 scripts/download_model_assets.py --profile core --print-plan
```

For targeted downloads:

```bash
scripts/download_model_assets.sh --profile surface
scripts/download_model_assets.sh --profile segmentation
scripts/download_model_assets.sh --profile parcellation
```

See [MODEL_ASSETS.md](MODEL_ASSETS.md) for the manifest format, profiles, expected paths, verification behavior, and external DDSurfer asset environment variables.

---

## Repository layout

```
SlicerDDSurfer.py              # Slicer ScriptedLoadableModule entry
CMakeLists.txt
Resources/
  Icons/                        # Module icon
  UI/                           # .ui for SlicerDDSurfer
  Data/
    ckpts/                      # DDSurfer model weights (LFS)
    template/                   # DDSurfer templates

# Final product-area packages

shared/                       # Shared subject-root / DTI / registration caches
surface/                      # DDSurfer preprocessing / prediction / postprocessing
parcellation/                 # DDParcel pipeline, conversion, data loader, weights
segmentation/                 # DDSeg package, runner, weights
microstructure/               # FA/MD, ROI-wise stats, Free Water, NODDI
tractography/                 # DTI, ACT, WMA scaffolds and planned CSD workflows
connectome/                   # Tractography + DDParcel connectome planning/execution
workflow_catalog.py           # Product taxonomy and navigation metadata
PRODUCT_ARCHITECTURE.md       # Product-level mapping and design notes

surface/ddsurfer_postprocess_release/  # bundled DDSurfer postprocess backend
```

---

## Slicer integration (SlicerDDSurfer.py)

### UI and navigation
- The current Slicer UI is organized around one shared `Subject root` and `Output directory`.
- Users select target products and a small set of run parameters: `run_name`, tractography backend, bundle backend, microstructure stages, and streamlines.
- Advanced external paths live under `Environment & Dependencies` and can be imported/exported as JSON.

### Parameter node
`SlicerDDSurferParameterNode` stores all UI state for:
- DDSurfer inputs/outputs
- DDParcel inputs/outputs/atlas
- DDSeg inputs/weights/device
- DDSurfer post-process configuration

### Runtime behaviors
- Runs dependency preflight before execution and continues runnable targets when optional targets are blocked.
- Installs only missing Python packages into the active Slicer Python environment when requested.
- Writes per-task manifest/QC/log records, a subject-level HTML/provenance/QC report, and an annotated output-tree HTML report.
- Auto-loads key output volumes, surfaces, tables, and tractography bundles into the Slicer scene when loaders are available.

---

## Surface (`surface/`)

### 1) Preprocessing (`preprocessing.py`)
- Copies/normalizes subject DTI metrics to a working directory.
- Skull-strips with mask, resamples into template space.
- Z-score normalizes volumes inside the mask.
- Outputs:
  - `preprocessed/<subject>/` volumes
  - `raw/<subject>/` cached raw/masked volumes

### 2) Prediction (`prediction.py`)
- Loads TANet models for white/pial surfaces.
- Uses template mesh (`hcp_hemi-*_init_160k.obj`) as seed.
- Predicts displacement fields, applies Taubin smoothing.
- Produces STL meshes per hemisphere.

### 3) Postprocessing (`postprocessing.py`)
- Converts meshes from template space back to subject-native space.
- Uses transform file and SimpleITK.
- Outputs STL meshes (native space).

---

## Parcellation (`parcellation/`)

Entry: `parcellation.pipeline.run_ddparcel`.

Key steps:
- Converts DWI + mask to NHDR.
- Runs Slicer CLI DTI extraction (dwitodtiestimation).
- Registers to atlas T2, normalizes, predicts parcellation.
- Uses pretrained weights in `parcellation/weights/`.

Inputs (expected under subject directory):
```
<T1w>/Diffusion/
  data.nii.gz
  bvals
  bvecs
  nodif_brain_mask.nii.gz
```

Outputs (under output root):
- Reg / normalized DTI features
- DDSurfer-wmparc
- Parcellation map in NIfTI/MGZ

---

## Input validation (`shared.validation`)

Entry: `shared.validate_subject_inputs`.

Implemented checks:
- Required subject-root files: `input/data.nii.gz`, `input/bvals`, `input/bvecs`, `input/nodif_brain_mask.nii.gz`.
- Phase-encoding / readout-time metadata from BIDS sidecars such as `input/data.json`.
- bval/bvec parsing, shape checks, b0 count, shell summary, and b-vector norm sanity checks.
- Dependency status checks for Python modules and external commands by workflow group.
- Lightweight QC JSON report under `outputs/validation/`.
- The main GUI `Validate` button calls this shared validation for subject-root inputs and logs the QC report path without installing dependencies.

100307 smoke command:
```bash
python3 Testing/Python/run_input_validation_smoke.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307 \
  --subject-id 100307
```

---

## Segmentation (`segmentation/`)

Entry: `segmentation.pipeline::run_ddseg`.

Key steps:
- Runs DTI feature extraction via Slicer CLI.
- Normalizes and stacks diffusion features.
- Multi-view inference (axial/sagittal/coronal).
- Combines views and outputs segmentation + probability maps.

Outputs:
- `SegmentationMap_GMWMCSF.nii.gz`
- `ProbabilisticMap_GM.nii.gz`
- `ProbabilisticMap_WM.nii.gz`
- `ProbabilisticMap_CSF.nii.gz`

---

## Microstructure (`microstructure/`)

Entry: `microstructure.pipeline::run_microstructure`.

Key steps:
- Reuses shared native DTI cache for FA/MD.
- Fits Free Water with DIPY.
- Fits NODDI with AMICO.
- Computes ROI-wise CSV/JSON summaries.

Outputs:
- Native-space FA / MD
- Free Water fraction / tissue FA / tissue MD
- NODDI NDI / ODI / FWF
- ROI-wise microstructure tables

---

## Tractography (`tractography/`)

Current entries: `tractography.run_dti_tracking`, `tractography.csd.run_csd_act`, `tractography.wmql.run_wmql_bundles`, `tractography.pipeline.run_wma_org_atlas_pipeline`, and `tractography.wma.run_wma_org_atlas`.

Implemented scaffold:
- Prepares DTI tractography manifests and QC placeholders from `subject_root/input`.
- Scans `cache/native_dti/<fit_method>` and records whether FA/MD/DTI cache can be reused.
- Reserves stable output paths under `outputs/tractography/` without launching long tracking jobs by default.
- Prepares ACT manifests/QC around an optional MRtrix3 backend.
- Builds and executes the MRtrix3 CSD/FOD/ACT command chain (`mrconvert`, `dwi2response`, `dwi2fod`, `mtnormalise`, `tckgen`, `tcksift2`) when MRtrix3 and ACT prep inputs are available.
- Launches MRtrix Python scripts with a Slicer-isolated environment so `PythonSlicer` does not leak `PYTHONHOME`/`PYTHONPATH` into external backends.
- Exports ACT tractograms as TCK and TRK so WMQL / TractQuerier can consume the same run output.
- Records DDParcel/parcellation as the required node dependency and checks 5TT/GMWMI readiness for standard ACT.
- Does not treat DDParcel alone as a complete ACT tissue model.
- Wraps WMA ORG atlas clustering as an optional external backend.
- Discovers WMA via explicit `wma_root`, `SLICERDDSURFER_WMA_ROOT`, `WMA_ROOT`, or `wm_apply_ORG_atlas_to_subject.sh` on `PATH`.
- Writes `wma_org_atlas_manifest.json` before execution.
- Writes `wma_org_atlas_qc.json` with backend status, atlas layout status, return code, runtime, and output summary.
- Checks the expected ORG atlas folders: `ORG-RegAtlas-100HCP` and `ORG-800FC-100HCP`.
- Defaults to dry-run mode; real WMA execution requires `execute=True` and valid VTK/VTP tractography plus ORG atlas paths.

Validated:
- `100307-release-candidate` quick gate runs DTI microstructure, MRtrix CSD/FOD/ACT, WMQL AF/CST bundles, and connectome matrices from one command. See [RELEASE_CANDIDATE_VALIDATION.md](RELEASE_CANDIDATE_VALIDATION.md).

100307 smoke command:
```bash
python3 Testing/Python/run_tractography_dti_smoke.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307 \
  --subject-id 100307 \
  --require-native-cache
```

WMA backend / atlas smoke command:
```bash
python3 Testing/Python/run_wma_org_atlas_smoke.py \
  --subject-id 100307 \
  --input-tractography /path/to/subject.vtk \
  --atlas-dir /path/to/ORG-Atlases \
  --output-dir /path/to/wma-output \
  --slicer-executable /path/to/Slicer \
  --wma-root /path/to/whitematteranalysis
```

Copied fixture check:
```bash
python3 Testing/Python/run_wma_149741_fixture_smoke.py
```

The copied WMA-ready tractography fixture is:
`/data/chengjin/SlicerDDSurfer-test/149741_wma_act/tractography/149741_ukf_pp_downsampled.vtk`.
Full WMA clustering still requires an explicit external WMA backend and ORG atlas directory.

## Connectome (`connectome/`)

Current entry: `connectome.run_connectome`.

Implemented:
- Requires a tractography file (`.trk`, `.tck`, `.vtk`, or `.vtp`) and a DDParcel/parcellation label map.
- Writes matrix CSV and nodes TSV headers, plus manifest and QC JSON.
- Supports `execute=True` through MRtrix3 `tck2connectome` for `.tck` inputs when available.
- Supports Python endpoint-label assignment for `.trk`/`.tck` and legacy `.vtk`; `.vtp` additionally requires the optional `vtk` Python module.
- Defaults to dry-run planning when execution is not requested.

149741 copied-fixture connectome verification:
```bash
python3 Testing/Python/run_connectome_149741_smoke.py --execute
```

ACT MRtrix planning smoke:
```bash
python3 Testing/Python/run_act_mrtrix_smoke.py \
  --subject-id 149741 \
  --parcellation-path /data/chengjin/SlicerDDSurfer-test/149741_wma_act/parcellation/wmparc.nii.gz \
  --output-dir /data/chengjin/SlicerDDSurfer-test/149741_wma_act/outputs/act_smoke
```

---

## Docker post-process (run_postprocess_docker.py)

This helper stages DDSurfer native STL outputs and MRI files into a
`postprocess-release` repository and runs the docker pipeline.

Required inputs:
- `brain.mgz`
- `DDSurfer-wmparc.nii.gz`
- native STL meshes: `*_predicted_*_orig.stl`

Configurable fields:
- `postprocess-release` repo path
- FreeSurfer license path
- mode: left / right / whole
- docker image tag override

---

## Model weights (Git LFS)

Large weights are tracked via Git LFS and downloaded through `models/assets_manifest.json`:
- `Resources/Data/ckpts/hcp/*.pt` (DDSurfer)
- `parcellation/weights/*.pkl` (DDParcel)
- `segmentation/weights/*.pt` (DDSeg)

Recommended fetch:
```bash
scripts/download_model_assets.sh --profile core
```

See [MODEL_ASSETS.md](MODEL_ASSETS.md) for profile definitions, verification
commands, external override environment variables, and the license or
redistribution boundary for model weights and templates.

---

## Requirements

- 3D Slicer (with Python environment)
- PyTorch extension (installed via Slicer Extension Manager)
- Python packages: `nibabel`, `SimpleITK`, `trimesh`, `tqdm`, `networkx`
- For Docker post-process: Docker, FreeSurfer license, postprocess-release repo

This is only a minimal summary. Full optional backend requirements, environment
variables, and per-target dependency notes are documented in
[EXTERNAL_DEPENDENCIES.md](EXTERNAL_DEPENDENCIES.md).

Before running on a new machine, use the environment doctor:

```bash
python3 run_subject_pipeline.py \
  --subject-root /path/to/subject \
  --targets microstructure,tractography,bundles,connectome \
  --microstructure-stages dti \
  --tractography-backend csd_act \
  --bundle-backend wmql \
  --doctor
```

It reports runnable/blocked targets and writes install helpers under
`outputs/00_run_metadata/environment/`.

When executing, environment preflight is target-aware. Missing optional backend
dependencies block only the affected target by default; runnable targets still
run and blocked targets are recorded in the orchestration manifest. Use
`--strict-environment` only when you want any selected missing dependency to
abort the whole run.

Useful high-level selectors:

- `--microstructure-stages dti|dti,freewater|dti,freewater,noddi|all`
- `--tractography-backend csd_act|dti_det|saf`
- `--bundle-backend wmql|wma|tractcloud|all`
- `--select-streamlines <N>` and `--run-name <name>`; the default run name is `Test1`

To preview execution without running algorithms:

```bash
python3 run_subject_pipeline.py \
  --subject-root /path/to/subject \
  --targets validation,preprocessing,microstructure,tractography,bundles,connectome \
  --microstructure-stages all \
  --bundle-backend all \
  --plan
```

The run plan records `will_run`, `skipped`, and `blocked` targets with blocker
categories such as `environment`, `data`, `upstream`, and `configuration`.
Executed runs also write normalized per-task records under
`outputs/00_run_metadata/tasks/<run_name>/<task>/manifest.json`, `qc.json`, and
`logs/`.
Each orchestrator run also writes
`outputs/00_run_metadata/output_tree_audit.json` to report missing canonical
directories, legacy top-level outputs, or unexpected nested subject outputs.
It also writes `outputs/00_run_metadata/output_tree_semantics.json`, which
marks canonical directories as selected, blocked, not selected, empty, or
containing outputs. Directories for products that were not selected are not
treated as required in the audit.
The Slicer UI mirrors the same information in the `Run Plan & Progress` table
and lets users open manifest/QC/log paths from the result rows.
Long UI runs are submitted through a background `QProcess` that calls the
unified CLI, so the Slicer main thread stays responsive. The `Cancel running
job` button terminates the background process and writes a
`*_cancelled_orchestration_manifest.json` record.

Batch runs use the same subject CLI for each subject:

```bash
python3 scripts/run_batch_pipeline.py \
  --batch-root /path/to/study_subjects \
  --output-root /path/to/batch_outputs \
  --batch-size 2 \
  --run-name Test1 \
  --all \
  --execute
```

Expected input layout is one subject directory per child folder, each with
`input/data.nii.gz`, `input/bvals`, `input/bvecs`, and
`input/nodif_brain_mask.nii.gz`. If raw files are directly inside each subject
folder, add `--arrange-inputs symlink` or `--arrange-inputs copy` to create the
required `input/` folder without manually restructuring the study. Batch outputs
are written under `<output-root>/<subject-id>/` when `--output-root` is set.
All unknown options are forwarded to `run_subject_pipeline.py`, so selectors
such as `--targets`, `--bundle-backend`, dependency path overrides, and
`--skip-environment-check` behave identically in single-subject and batch mode.

100307 regression command:

```bash
PYTHON_BIN="/data/chengjin/software/run-slicer.sh --launch PythonSlicer" \
  scripts/run_100307_regression.sh
```

Set `DRY_RUN=1` to only generate the plan.

---

## Notes

- DDSurfer expects DTI-derived scalar volumes and a transform from subject to atlas space.
- DDSeg and DDParcel rely on DTI feature extraction via Slicer CLI modules.
- Product architecture notes are summarized in [PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md).
