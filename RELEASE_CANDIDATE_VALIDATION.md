# SlicerDDSurfer Release-Candidate Validation

This document records the current release-candidate validation path: extension-like Slicer installation, one-command subject execution, resume, report/QC, and Slicer UI loading.

## Verified Baseline

- Repository: `/data/chengjin/SlicerDDSurfer`
- Slicer: `/data/chengjin/software/Slicer-5.10.0-linux-amd64`
- Test subject: `/data/chengjin/SlicerDDSurfer-test/100307-release-candidate`
- Staged extension: `/data/chengjin/SlicerDDSurfer-test/extension-install-rc/SlicerDDSurfer`
- Canonical outputs: `/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs`

The clean subject input tree used for release-candidate testing is:

```text
100307-release-candidate/
  input/
    data.nii.gz
    bvals
    bvecs
    nodif_brain_mask.nii.gz
```

## Stage the Extension

Do not point Slicer at the repository root. The repository contains many helper `.py` files that must not be registered as Slicer modules.

Use the staging helper to create an extension-like install tree:

```bash
cd /data/chengjin/SlicerDDSurfer
python3 scripts/stage_slicer_extension.py \
  --install-root /data/chengjin/SlicerDDSurfer-test/extension-install-rc \
  --clean \
  --link-mode hardlink
```

Expected check:

```text
top_level_python_files: ["SlicerDDSurfer.py"]
top_level_python_ok: true
```

Then run the real Slicer smoke test:

```bash
env PATH=/data/chengjin/software/xvfb/usr/bin:$PATH \
  SLICERDDSURFER_EXTENSION_MODULE_DIR=/data/chengjin/SlicerDDSurfer-test/extension-install-rc/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules \
  xvfb-run -a /data/chengjin/software/run-slicer.sh --no-splash \
  --additional-module-paths /data/chengjin/SlicerDDSurfer-test/extension-install-rc/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules \
  --python-script /data/chengjin/SlicerDDSurfer/Testing/Python/slicer_extension_install_smoke.py
```

Expected checks:

```text
SLICERDDSURFER_EXTENSION_TOP_LEVEL_PY=['SlicerDDSurfer.py']
SLICERDDSURFER_EXTENSION_TARGET_REGISTERED=True
SLICERDDSURFER_EXTENSION_FORBIDDEN_REGISTERED=[]
SLICERDDSURFER_EXTENSION_MODULE_FILE_SYMLINK=False
SLICERDDSURFER_EXTENSION_RUN_PANEL_READY=True
SLICERDDSURFER_EXTENSION_ENV_PATHS_READY=True
```

## Run a Clean Subject from One Command

For full pipeline execution, use Slicer's `PythonSlicer`. Plain `python3` is acceptable for light inspection, docs, and some unit tests, but the integrated subject run needs Slicer CLI modules such as `DWIConvert`, `DWIToDTIEstimation`, `BRAINSFit`, and `ResampleScalarVectorDWIVolume`.

Release-candidate quick gate:

```bash
/data/chengjin/software/run-slicer.sh --launch PythonSlicer \
  /data/chengjin/SlicerDDSurfer/run_subject_pipeline.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307-release-candidate \
  --subject-id 100307-release-candidate \
  --targets validation,preprocessing,segmentation,parcellation,surface,microstructure,tractography,bundles,connectome \
  --tractography-backend saf \
  --bundle-backend all \
  --microstructure-stages dti \
  --run-name rc_csd_act \
  --mrtrix-bin-dir /data/chengjin/software/mrtrix3_env/bin \
  --tract-querier-root /data/chengjin/SlicerDDSurfer/third_party/tract_querier \
  --preprocessing-dipy-denoise-method none \
  --preprocessing-skip-gibbs \
  --preprocessing-skip-motion \
  --execute \
  --print-manifest-only
```

This command verifies the fast release path:

- input validation
- optional preprocessing fast path
- DDSeg
- DDParcel
- DDSurfer surface
- DTI FA/MD/AD/RD/L1/L2/L3/Trace
- ROI-wise DTI statistics
- MRtrix CSD/FOD
- ACT tractography
- SIFT2 weights
- WMQL AF/CST bundles
- streamline-count connectome
- SIFT2-weighted connectome
- subject-level report/QC/provenance

Free Water and NODDI are not part of the quick release gate because they are long model fits. Run them as a separate long regression:

```bash
/data/chengjin/software/run-slicer.sh --launch PythonSlicer \
  /data/chengjin/SlicerDDSurfer/run_subject_pipeline.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307-release-candidate \
  --subject-id 100307-release-candidate \
  --targets microstructure \
  --microstructure-stages dti,freewater,noddi \
  --run-name rc_microstructure_long \
  --execute \
  --print-manifest-only
```

## Resume Check

Run the same quick-gate command again. Expected run plan:

```text
Run plan: 1 will run, 8 skipped/reused, 4 blocked.
validation: will_run
preprocessing: skipped
segmentation: skipped
parcellation: skipped
surface: skipped
microstructure: skipped
tractography: skipped
bundles: skipped
connectome: skipped
```

Blocked optional targets on the current machine are expected:

- `surface_postprocess`: FreeSurfer command-line tools and `FREESURFER_HOME` are not configured.
- `wma`: WMA ORG atlas and WMA shell entrypoint are not configured.
- `saf`: requires completed DDSurfer postprocess outputs or explicit `--saf-fs-dir`.
- `tractcloud`: requires an explicit VTK/VTP tractogram and TractCloud backend configuration.

These blockers do not stop runnable targets unless `--strict-environment` is used.

## Output Audit

The quick-gate command writes:

```text
outputs/
  00_run_metadata/
    rc_csd_act_run_plan.json
    rc_csd_act_orchestration_manifest.json
    output_tree_audit.json
    environment/
    tasks/
    validation/
  01_preproc/
  02_microstructure/
    dti/
  03_structural/
    ddseg/
    ddparcel/
    ddsurfer/
  04_tractography/
    act_prep/
    csd/rc_csd_act/
    tractograms/rc_csd_act/
    bundles/wmql/rc_csd_act/
    connectome/rc_csd_act/
  05_statistics/
    regional_microstructure/
  06_slicer_scene_report/
    report.html
    summary.md
    provenance.json
    qc_summary.json
```

Key release-candidate outputs verified on `100307-release-candidate`:

- `outputs/02_microstructure/dti/*_dti_FA.nii.gz`
- `outputs/02_microstructure/dti/*_dti_MD.nii.gz`
- `outputs/02_microstructure/dti/*_dti_AD.nii.gz`
- `outputs/02_microstructure/dti/*_dti_RD.nii.gz`
- `outputs/03_structural/ddseg/SegmentationMap_GMWMCSF.nii.gz`
- `outputs/03_structural/ddparcel/*-DDSurfer-wmparc.nii.gz`
- `outputs/03_structural/ddsurfer/surface_manifest.json`
- `outputs/04_tractography/csd/rc_csd_act/*_wmfod_norm.mif`
- `outputs/04_tractography/tractograms/rc_csd_act/*_csd_act_ifod2.tck`
- `outputs/04_tractography/tractograms/rc_csd_act/*_csd_act_ifod2.trk`
- `outputs/04_tractography/tractograms/rc_csd_act/*_sift2_weights.txt`
- `outputs/04_tractography/bundles/wmql/rc_csd_act/*_af.left.trk`
- `outputs/04_tractography/bundles/wmql/rc_csd_act/*_cst.left.trk`
- `outputs/04_tractography/connectome/rc_csd_act/*streamline_count.csv`
- `outputs/04_tractography/connectome/rc_csd_act/sift2_weighted_streamline_count/*sift2_weighted_streamline_count.csv`
- `outputs/06_slicer_scene_report/report.html`
- `outputs/06_slicer_scene_report/summary.md`
- `outputs/06_slicer_scene_report/provenance.json`
- `outputs/06_slicer_scene_report/qc_summary.json`

The MRtrix dense DWI/FOD intermediates under `outputs/04_tractography/csd/<run_name>/` are large runtime products and must not be committed to Git.

## Slicer UI Report and Auto-Load Smoke

After staging the extension and running the subject once, validate the Slicer UI layer:

```bash
env PATH=/data/chengjin/software/xvfb/usr/bin:$PATH \
  SLICERDDSURFER_SMOKE_SUBJECT_ROOT=/data/chengjin/SlicerDDSurfer-test/100307-release-candidate \
  SLICERDDSURFER_SMOKE_SUBJECT_ID=100307-release-candidate \
  SLICERDDSURFER_SMOKE_RUN_NAME=rc_csd_act \
  SLICERDDSURFER_SMOKE_MICROSTRUCTURE_STAGES=dti \
  SLICERDDSURFER_EXTENSION_MODULE_DIR=/data/chengjin/SlicerDDSurfer-test/extension-install-rc/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules \
  xvfb-run -a /data/chengjin/software/run-slicer.sh --no-splash \
  --additional-module-paths /data/chengjin/SlicerDDSurfer-test/extension-install-rc/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules \
  --python-script /data/chengjin/SlicerDDSurfer/Testing/Python/slicer_run_plan_panel_smoke.py
```

Expected checks:

```text
SLICERDDSURFER_RUN_PANEL_STATUS_LABEL=Completed with 4 blocked task(s)
SLICERDDSURFER_RUN_PANEL_MANIFEST_EXISTS=True
SLICERDDSURFER_RUN_PANEL_PLAN_EXISTS=True
SLICERDDSURFER_RUN_PANEL_REPORT_BUTTON_ENABLED=True
SLICERDDSURFER_RUN_PANEL_LATEST_REPORT=.../outputs/06_slicer_scene_report/report.html
```

The smoke test also verifies that key DTI maps, DDParcel/DDSSeg volumes, and DDSurfer surface models can be loaded into the Slicer scene.

## Important Integration Notes

- MRtrix Python scripts must be launched with a Slicer-isolated environment. The CSD/ACT backend strips Slicer `PYTHONHOME`, `PYTHONPATH`, and Slicer runtime paths before calling `dwi2response`, `dwi2fod`, `tckgen`, and `tcksift2`.
- If this isolation regresses, `dwi2response` can fail inside `PythonSlicer` with `AssertionError: SRE module mismatch`.
- Slicer setting write warnings may appear under `xvfb-run` in this local environment. They are not treated as failures if the smoke assertions pass.
- STL surface files currently trigger Slicer warnings that coordinate-system metadata is absent and Slicer assumes LPS. This does not block loading, but should remain a future metadata/QC cleanup item.
