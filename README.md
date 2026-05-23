# SlicerDDSurfer

SlicerDDSurfer is a 3D Slicer scripted module that bundles multiple diffusion-MRI workflows in one extension:

- **DDSurfer**: cortical surface reconstruction (white/pial meshes) from DTI-derived scalar volumes.
- **DDParcel**: 101-region parcellation pipeline built on diffusion features.
- **DDSeg**: WM/GM/CSF segmentation from DWI using multi-view CNNs.
- **Microstructure**: FA/MD, ROI-wise statistics, Free Water, and AMICO NODDI.
- **Tractography**: DTI tracking scaffold, ACT dependency scaffold, and WMA ORG atlas clustering scaffold, with CSD planned.
- **Connectome**: tractography + DDParcel dependency checks and optional streamline-count matrix execution.
- **Surface post-process**: Docker-based refinement using the `postprocess-release` repo.

**Chinese version:** [README.zh-CN.md](README.zh-CN.md)

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
surface/                      # DDSurfer preprocessing / prediction / postprocessing / sculpting
parcellation/                 # DDParcel pipeline, conversion, data loader, weights
segmentation/                 # DDSeg package, runner, weights
microstructure/               # FA/MD, ROI-wise stats, Free Water, NODDI
tractography/                 # DTI, ACT, WMA scaffolds and planned CSD workflows
connectome/                   # Tractography + DDParcel connectome planning/execution
workflow_catalog.py           # Product taxonomy and navigation metadata
PRODUCT_ARCHITECTURE.md       # Product-level mapping and design notes

run_postprocess_docker.py     # Docker post-process helper
```

---

## Slicer integration (SlicerDDSurfer.py)

### UI and navigation
- A **top navigation bar** provides quick jumps to:
  - Parcellation
  - Microstructure
  - Segmentation
  - Surface
  - Surface post-process
- The main DDSurfer panel is a collapsible section labeled **"DDSurfer"**.
- Additional panels exist for DDParcel, DDSeg, and Docker post-process.

### Parameter node
`SlicerDDSurferParameterNode` stores all UI state for:
- DDSurfer inputs/outputs
- DDParcel inputs/outputs/atlas
- DDSeg inputs/weights/device
- Docker post-process configuration

### Runtime behaviors
- Validates required inputs before running each pipeline.
- Uses Slicer’s Python package installer and/or the **PyTorch extension** when needed.
- Loads output meshes into the scene once DDSurfer completes.

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

### 4) Sculptor (`sculpting/surface_sculptor.py`)
- Brush-based, topology-preserving surface editing.
- Works in slice and 3D views.
- Tools: Smooth / Paint (Grow) / Erase (Shrink) / Flatten.
- Supports undo and STL export.

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

Current entries: `tractography.run_dti_tracking`, `tractography.run_act_tracking`, `tractography.pipeline.run_wma_org_atlas_pipeline`, and `tractography.wma.run_wma_org_atlas`.

Implemented scaffold:
- Prepares DTI tractography manifests and QC placeholders from `subject_root/input`.
- Scans `cache/native_dti/<fit_method>` and records whether FA/MD/DTI cache can be reused.
- Reserves stable output paths under `outputs/tractography/` without launching long tracking jobs by default.
- Prepares ACT manifests/QC around an optional MRtrix3 backend.
- Builds the MRtrix3 ACT command chain (`mrconvert`, `dwi2response`, `dwi2fod`, `tckgen`, `tcksift2`) and can execute it when all required external inputs are present.
- Records DDParcel/parcellation as the required node dependency and checks 5TT/GMWMI readiness for standard ACT.
- Does not treat DDParcel alone as a complete ACT tissue model.
- Wraps WMA ORG atlas clustering as an optional external backend.
- Discovers WMA via explicit `wma_root`, `SLICERDDSURFER_WMA_ROOT`, `WMA_ROOT`, or `wm_apply_ORG_atlas_to_subject.sh` on `PATH`.
- Writes `wma_org_atlas_manifest.json` before execution.
- Writes `wma_org_atlas_qc.json` with backend status, atlas layout status, return code, runtime, and output summary.
- Checks the expected ORG atlas folders: `ORG-RegAtlas-100HCP` and `ORG-800FC-100HCP`.
- Defaults to dry-run mode; real WMA execution requires `execute=True` and valid VTK/VTP tractography plus ORG atlas paths.

Planned:
- CSD tractography.
- Real ACT execution after MRtrix3 command invocation, 5TT/GMWMI generation, and small-data validation.

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

Large weights are tracked via Git LFS:
- `Resources/Data/ckpts/hcp/*.pt` (DDSurfer)
- `parcellation/weights/*.pkl` (DDParcel)
- `segmentation/weights/*.pt` (DDSeg)

To fetch them:
```bash
git lfs install
git lfs pull
```

---

## Requirements

- 3D Slicer (with Python environment)
- PyTorch extension (installed via Slicer Extension Manager)
- Python packages: `nibabel`, `SimpleITK`, `trimesh`, `tqdm`, `networkx`
- For Docker post-process: Docker, FreeSurfer license, postprocess-release repo

---

## Notes

- DDSurfer expects DTI-derived scalar volumes and a transform from subject to atlas space.
- DDSeg and DDParcel rely on DTI feature extraction via Slicer CLI modules.
- Surface sculpting is topology-preserving (only vertex positions change).
- Product architecture notes are summarized in [PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md).
