# SlicerDDSurfer

SlicerDDSurfer is a 3D Slicer module for diffusion-MRI anatomical
reconstruction and connectivity analysis. It helps users prepare one subject,
check dependencies, run selected diffusion products, and review outputs with
logs, quality-control files and provenance.

**中文说明:** [README.zh-CN.md](README.zh-CN.md)

## 5-Minute Start

1. Install [3D Slicer](https://www.slicer.org/) and open SlicerDDSurfer.
2. Click `First-run setup wizard`.
3. Choose a `Model assets root`, for example `~/SlicerDDSurfer-model-assets`.
4. Click `Check environment dependencies`.
5. Choose a `Subject root`, for example:

```text
sub-01/
  input/
    data.nii.gz
    bvals
    bvecs
    nodif_brain_mask.nii.gz   # optional but recommended
```

6. Review the capability dashboard. It tells you what can run now and what
   still needs setup.
7. Click `Preflight and run`.
8. Open the output tree/report from the run status panel.

If you only want to test the interface, click `Demo / Try with sample data`.
This creates a tiny synthetic DWI subject with no human data and selects a
lightweight DTI-oriented run plan.

## Install The Code

```bash
git clone https://github.com/ChengjinLii/SlicerDDSurfer.git
cd SlicerDDSurfer
```

`git clone` downloads the source code, documentation, scripts and
`models/assets_manifest.json`. It does not download the large model weights.

## Download Model Assets

Recommended command:

```bash
scripts/download_model_assets.sh --profile core
```

Explicit equivalent:

```bash
python3 scripts/download_model_assets.py \
  --profile core \
  --asset-root ~/SlicerDDSurfer-model-assets \
  --source url \
  --source-id slicerdsurfer_models_git
```

Quick network/checksum test without large files:

```bash
python3 scripts/download_model_assets.py \
  --profile sentinel \
  --asset-root /tmp/slicerdsurfer-model-sentinel \
  --source url \
  --source-id slicerdsurfer_models_git
```

Details: [docs/assets/MODEL_ASSETS.md](docs/assets/MODEL_ASSETS.md).

## Platform Setup

- Windows: [docs/setup/WINDOWS.md](docs/setup/WINDOWS.md)
- macOS: [docs/setup/MACOS.md](docs/setup/MACOS.md)
- Linux/HPC: [docs/setup/LINUX_HPC.md](docs/setup/LINUX_HPC.md)
- Dependency workflow: [docs/assets/DEPENDENCY_SETUP_WORKFLOW.md](docs/assets/DEPENDENCY_SETUP_WORKFLOW.md)

Python packages, external software and model weights are handled differently:

- Python packages install into the selected Slicer Python or conda/Python
  environment. SlicerDMRI and PyTorch are expected Slicer extension/runtime
  dependencies for the corresponding workflows.
- External tools such as MRtrix3, FSL, FreeSurfer, WMA and TractCloud are
  detected from saved paths, environment variables, `PATH` and common install
  locations. They are not installed silently.
- Model weights download into the user-selected `Model assets root`.

## Command-Line Preflight

```bash
python3 run_subject_pipeline.py \
  --subject-root /path/to/sub-01 \
  --targets validation,microstructure,tractography,connectome \
  --tractography-backend dti_det \
  --doctor
```

Generate a plan without running algorithms:

```bash
python3 run_subject_pipeline.py \
  --subject-root /path/to/sub-01 \
  --targets validation,microstructure,tractography,connectome \
  --tractography-backend dti_det \
  --plan
```

## Need Help?

In the Slicer module, click `Copy diagnostic report` and paste the report into
an issue or support message. It includes Slicer/Python paths, model asset root,
missing dependencies, checked paths and recent logs.

## Developer Checks

```bash
make test-fast
make fresh-clone-smoke
python3 scripts/release_audit.py
```

Release details are in [docs/release/RELEASE.md](docs/release/RELEASE.md).

## Citation

Use [CITATION.cff](CITATION.cff) for citation metadata.
