# Windows Setup

This page is for users who want to run SlicerDDSurfer from 3D Slicer on
Windows. Use the Slicer UI first; use commands only when troubleshooting.

## 1. Install 3D Slicer

Download and install 3D Slicer from <https://www.slicer.org/>.

Open Slicer, then open the SlicerDDSurfer module. If this is your first time,
click `First-run setup wizard`.

## 2. Choose A Model Asset Folder

Recommended example:

```text
C:\Users\YourName\SlicerDDSurfer-model-assets
```

Use this path in the Slicer UI `Model assets root` field, or run:

```powershell
python scripts\download_model_assets.py `
  --profile core `
  --asset-root C:\Users\YourName\SlicerDDSurfer-model-assets `
  --source url `
  --source-id slicerdsurfer_models_git
```

## 3. Prepare Subject Data

Recommended layout:

```text
C:\Users\YourName\data\sub-01\
  input\
    data.nii.gz
    bvals
    bvecs
    nodif_brain_mask.nii.gz
```

In SlicerDDSurfer:

1. Set `Subject ID` to `sub-01`.
2. Set `Subject root` to `C:\Users\YourName\data\sub-01`.
3. Leave `Output directory` empty unless you need a custom output folder.

## 4. External Tools

Start with lightweight targets first. MRtrix3, FSL, FreeSurfer, WMA and
TractCloud are optional depending on the selected products.

Click `Check environment dependencies`. If a tool is missing, use the row-level
`Choose path / setup` button to select an existing install path or read setup
notes. SlicerDDSurfer does not silently install system tools.

## 5. If Something Fails

Click `Copy diagnostic report` in SlicerDDSurfer and paste it into your support
message. Include the exact target you tried to run.

