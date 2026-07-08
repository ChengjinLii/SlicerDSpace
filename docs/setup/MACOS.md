# macOS Setup

This page is for users who want to run SlicerDDSurfer from 3D Slicer on macOS.
Use the Slicer UI first; use Terminal only when troubleshooting.

## 1. Install 3D Slicer

Download and install 3D Slicer from <https://www.slicer.org/>.

Open Slicer, then open the SlicerDDSurfer module. If this is your first time,
click `First-run setup wizard`.

## 2. Choose A Model Asset Folder

Recommended example:

```text
/Users/yourname/SlicerDDSurfer-model-assets
```

Command-line equivalent:

```bash
python3 scripts/download_model_assets.py \
  --profile core \
  --asset-root /Users/yourname/SlicerDDSurfer-model-assets \
  --source url \
  --source-id slicerdsurfer_models_git
```

## 3. Prepare Subject Data

Recommended layout:

```text
/Users/yourname/data/sub-01/
  input/
    data.nii.gz
    bvals
    bvecs
    nodif_brain_mask.nii.gz
```

In SlicerDDSurfer:

1. Set `Subject ID` to `sub-01`.
2. Set `Subject root` to `/Users/yourname/data/sub-01`.
3. Leave `Output directory` empty unless you need a custom output folder.

## 4. External Tools

MRtrix3, FSL, FreeSurfer, WMA and TractCloud are optional depending on selected
targets. Install them using your lab's preferred method, Homebrew, conda or the
official project instructions. Then select the installed path in
SlicerDDSurfer.

Common examples:

```text
MRtrix bin: /opt/mrtrix3/bin
FSL bin: /usr/local/fsl/bin
FreeSurfer home: /Applications/freesurfer
```

## 5. If Something Fails

Click `Copy diagnostic report` in SlicerDDSurfer and paste it into your support
message. Include the exact target you tried to run.

