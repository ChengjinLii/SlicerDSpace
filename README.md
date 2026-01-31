# SlicerDDSurfer

SlicerDDSurfer is a 3D Slicer scripted module that bundles multiple diffusion-MRI workflows in one extension:

- **DDSurfer**: cortical surface reconstruction (white/pial meshes) from DTI-derived scalar volumes.
- **DDParcel**: 101-region parcellation pipeline built on diffusion features.
- **DDSeg**: WM/GM/CSF segmentation from DWI using multi-view CNNs.
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

# Pipelines

ddsurferpipeline/              # DDSurfer main pipeline
  preprocessing.py
  prediction.py
  postprocessing.py
  networks/
  models/
  template/
  sculpting/                    # topology-preserving surface editor

# 101-region parcellation

ddparcpipeline/
  pipeline.py
  conversion/
  models/
  weights/                      # LFS

# WM/GM/CSF segmentation

ddsegpipeline/
  src/ddseg/                    # DDSeg implementation
  weights/                      # LFS

run_postprocess_docker.py       # Docker post-process helper
```

---

## Slicer integration (SlicerDDSurfer.py)

### UI and navigation
- A **top navigation bar** provides quick jumps to:
  - 101-region parcellation (DDParcel)
  - WM/GM/CSF segmentation (DDSeg)
  - WM & Pial surface (DDSurfer)
  - Surface post-process (Docker + sculptor)
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

## DDSurfer pipeline (ddsurferpipeline/)

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

## DDParcel pipeline (ddparcpipeline/)

Entry: `ddparcpipeline.pipeline.run_ddparcel`.

Key steps:
- Converts DWI + mask to NHDR.
- Runs Slicer CLI DTI extraction (dwitodtiestimation).
- Registers to atlas T2, normalizes, predicts parcellation.
- Uses pretrained weights in `ddparcpipeline/weights/`.

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

## DDSeg pipeline (ddsegpipeline/)

Entry: `ddsegpipeline/src/ddseg/pipeline.py::run_ddseg`.

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
- `ddparcpipeline/weights/*.pkl` (DDParcel)
- `ddsegpipeline/weights/*.pt` (DDSeg)

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

