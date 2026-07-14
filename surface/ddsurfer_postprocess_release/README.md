# DDSurfer Postprocess Optimize

`postprocess-release-optimize` is an optimized, standalone version of the
original DDSurfer postprocessing pipeline. It converts DDSurfer raw outputs
into a FreeSurfer-compatible subject workspace and then syncs the user-facing
results into a canonical product layout.

## What It Does

The pipeline takes:

- `DDSurfer-wmparc.nii.gz`
- `brain.mgz`
- left/right white-matter STL surfaces
- left/right pial STL surfaces

and produces:

- FreeSurfer-style `surf/`, `label/`, `stats/`
- projected atlas annotations
- per-region statistics
- fsaverage-resampled surface overlays
- `manifest.json`, `qc.json`, `provenance.json`, `validation.json`

This is a DDSurfer-to-FreeSurfer-compatible postprocess, not a FreeSurfer
`recon-all` reconstruction. It does not create the complete T1-derived
`mri/`, `scripts/`, and `transforms/` subject tree produced by `recon-all`.

## Folder Layout

```text
postprocess-release-optimize/
  config/
    pipeline.conf
  inputs/
    <subject_id>/
      mri/
        DDSurfer-wmparc.nii.gz
        brain.mgz
      surf/
        <subject_id>_predicted_wm_lh_orig.stl
        <subject_id>_predicted_wm_rh_orig.stl
        <subject_id>_predicted_pial_lh_orig.stl
        <subject_id>_predicted_pial_rh_orig.stl
  outputs/
    <subject_id>/
      03_structural/
        ddsurfer/
          postprocess/
          _subjects/<subject_id>/   # internal FreeSurfer workdir
          mri/                       # materialized Windows-readable output
          surf/                      # materialized Windows-readable output
          label/                     # materialized Windows-readable output
          fsaverage/
          logs/
          manifest.json
          qc.json
          provenance.json
          validation.json
      05_statistics/
        ddsurfer/
          postprocess/
            stats/                   # materialized Windows-readable output
  run.sh
  scripts/
  src/
```

## Requirements

- FreeSurfer installed
- Python 3
- Python packages:
  - `nibabel`
  - `numpy`
  - `trimesh`
  - `rtree`

On this machine, a working FreeSurfer install is:

```bash
/data/chengjin/software/freesurfer
```

If `recon-all` is already on `PATH`, the pipeline will try to infer
`FREESURFER_HOME` automatically.

## Main Entry Point

```bash
bash run.sh --subject-id <id> --mode <left|right|whole> [options]
```

Backward-compatible form is still supported:

```bash
bash run.sh <subject_id> <left|right|whole>
```

## CLI Options

- `--subject-id ID`
- `--mode left|right|whole`
- `--inputs-dir PATH`
- `--outputs-dir PATH`
- `--nest-subject-outputs 0|1`
- `--stage-mode copy|symlink|inplace`
- `--stages CSV`
- `--atlases CSV`
- `--freesurfer-home PATH`
- `--python-bin BIN`

## Stages

Available stages:

- `validate_inputs`
- `stage_inputs`
- `convert_surfaces`
- `build_fs_surfaces`
- `project_annotations`
- `extract_labels`
- `compute_stats`
- `resample_fsaverage`
- `sync_outputs`

Default stage chain:

```text
validate_inputs,stage_inputs,convert_surfaces,build_fs_surfaces,project_annotations,extract_labels,compute_stats,resample_fsaverage,sync_outputs
```

## Atlas Configuration

Atlases are configurable with `--atlases` instead of being hardcoded.

Default atlases:

```text
aparc,aparc.a2009s,Yeo2011_7Networks_N1000,Yeo2011_17Networks_N1000,PALS_B12_Brodmann,PALS_B12_Lobes
```

Example:

```bash
bash run.sh --subject-id 877168 --mode whole \
  --atlases aparc,aparc.a2009s,Yeo2011_7Networks_N1000
```

## Quick Start

### 1. Lightweight validation / conversion test

This path validates inputs, stages them, converts STL to FreeSurfer surfaces,
and writes canonical reports without requiring the full downstream atlas/stat
workflow.

```bash
cd /data/chengjin/DDSurfer-mine-v0/postprocess-release-optimize
bash run.sh \
  --subject-id 877168 \
  --mode whole \
  --stage-mode symlink \
  --stages validate_inputs,stage_inputs,convert_surfaces,sync_outputs
```

### 2. Full postprocess run

```bash
cd /data/chengjin/DDSurfer-mine-v0/postprocess-release-optimize
bash run.sh \
  --subject-id 877168 \
  --mode whole \
  --freesurfer-home /data/chengjin/software/freesurfer
```

## Output Notes

- Internal FreeSurfer execution happens under:
  - `outputs/<subject_id>/03_structural/ddsurfer/postprocess/_subjects/<subject_id>/`
- User-facing canonical outputs live under:
  - `outputs/<subject_id>/03_structural/ddsurfer/postprocess/`
  - `outputs/<subject_id>/05_statistics/ddsurfer/postprocess/`

This split keeps FreeSurfer happy without exposing only the raw subject tree.

## Validation and Resume Semantics

The optimized pipeline adds structured files for downstream orchestration:

- `validation.json`: required-input checks
- `manifest.json`: requested stages, atlas list, inferred stage status
- `qc.json`: core-output counts and presence checks
- `provenance.json`: runtime paths and environment summary

These files make it easier to reuse this backend from `SlicerDDSurfer`.

## Testing Subject

The bundled example subject is:

```text
inputs/877168
```

It contains the six required raw DDSurfer inputs and is the first subject that
should be used for regression testing.
