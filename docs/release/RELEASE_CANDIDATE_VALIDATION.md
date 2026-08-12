# SlicerDDSurfer Release-Candidate Validation

This document records the current release-candidate validation path: extension-like Slicer installation, one-command subject execution, resume, report/QC, and Slicer UI loading.

The current release gate targets Linux x86-64. Windows and macOS scientific
execution are outside this release scope.

The latest release-focused audit is documented in
[`VALIDATION_20260812.md`](VALIDATION_20260812.md). It supersedes older test
counts and the earlier statement that no real Extension Manager installation
had been performed.

## Verified Baseline

- Repository: `/data/chengjin/SlicerDDSurfer`
- Slicer: `/data/chengjin/software/Slicer-5.10.0-linux-amd64`
- Test subject: `/data/chengjin/SlicerDDSurfer-test/100307-release-candidate`
- Staged extension: `/data/chengjin/SlicerDDSurfer-test/extension-install-rc/SlicerDDSurfer`
- Copy-mode staged package: `/data/chengjin/SlicerDDSurfer-test/extension-package-rc/SlicerDDSurfer`
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

## 2026-07-25 Route Revalidation

The previously open DDSurfer post-processing, representative DICOM import,
MRtrix/FSL preprocessing and WMA checks were closed on a Linux x86-64 host.
Detailed local evidence is recorded in:

```text
/data/chengjin/SlicerDDSurfer-validation/VALIDATION_20260725.md
```

Key results:

- DDSurfer post-processing completed all 9 stages with `rtree 1.4.1` in
  Slicer's Python: 12 annotations, 14 statistics files, 8 fsaverage overlays
  and all four white/pial surfaces.
- A deidentified representative AP/PA DICOM fixture imported with 0 validation
  errors and 0 warnings. The AP DWI contains 31 volumes
  (`104 x 104 x 60 x 31`), including 30 diffusion directions and one b0.
- MRtrix/FSL preprocessing completed `topup + eddy` using the AP/PA pair,
  retained 11 QC diagnostics and produced finite corrected DWI values, rotated
  gradients and a final `dwi2mask` mask generated from the corrected image.
- WMA completed on a 100,000-streamline whole-brain CSD/ACT tractogram:
  10 registration iterations, 800 clusters and 74 anatomical tracts.
- ANTs was used only by the old SAF T1w/FreeSurfer-to-dMRI registration branch.
  That branch and its dependency were removed. SAF now requires surfaces
  already expressed in native dMRI space.
- Final regression: 289 fast tests, copy-mode Slicer smoke and extension
  metadata audit passed; release audit reported 0 blockers.

These are route-closure checks, not anatomical-accuracy or cohort-level
benchmarks. Long scientific routes were executed on Linux only.

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

Package-level validation was also repeated with a standalone copy-mode staging tree:

```bash
python3 scripts/stage_slicer_extension.py \
  --install-root /data/chengjin/SlicerDDSurfer-test/extension-package-rc \
  --clean \
  --link-mode copy
```

The same Slicer smoke passed against the copy-mode tree. On 2026-08-12, a clean
rooted archive was also installed through Slicer's real Extension Manager model;
the installed SlicerDDSurfer module was registered, loaded and available. The
top-level CMake contract and packaging helper passed. The binary Slicer tree
still does not provide `SlicerConfig.cmake`, so a full CMake/CPack build against
a complete Slicer SDK remains unverified.

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
  --microstructure-free-water-chunk-size 4 \
  --microstructure-free-water-engine joblib \
  --microstructure-free-water-n-jobs 8 \
  --execute \
  --print-manifest-only
```

For long-run monitoring, inspect:

```text
outputs/02_microstructure/freewater/freewater_progress.json
outputs/02_microstructure/noddi/noddi_progress.json
```

Validated result on `2026-06-08`:

```text
Free Water: completed, joblib engine, n_jobs=8, 37 chunks, 740916 voxels, 1308.749 seconds
NODDI: completed, 1557.665 seconds
Resume: Run plan: 0 will run, 3 skipped/reused, 0 blocked
```

The long-regression report was written to:

```text
outputs/06_slicer_scene_report/rc_microstructure_long_report.html
```

All DTI, Free Water, and NODDI maps were readable with shape `(145, 174, 145)` and finite voxel values.

## SAF One-Command Closure

SAF requires a FreeSurfer-style surface directory whose surfaces are already
expressed in native dMRI space. The historic closure below used a compatible
surface fixture and the RC ACT tractogram. SlicerDDSurfer no longer registers a
T1w/FreeSurfer surface directory to dMRI with ANTs:

```bash
/data/chengjin/software/run-slicer.sh --launch PythonSlicer \
  /data/chengjin/SlicerDDSurfer/run_subject_pipeline.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307-release-candidate \
  --subject-id 100307-release-candidate \
  --targets saf \
  --run-name rc_csd_act \
  --mrtrix-bin-dir /data/chengjin/software/mrtrix3_env/bin \
  --saf-fs-dir /data/chengjin/SlicerDDSurfer-test/100307-FastSurfer \
  --saf-pregenerated-tractogram /data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/04_tractography/cache/alternate_runs/tractograms/rc_csd_act/100307-release-candidate_csd_act_ifod2.tck \
  --execute \
  --print-manifest-only
```

Validated result:

```text
Run plan: 1 will run, 0 skipped/reused, 0 blocked
SAF status: completed
SAF streamline count: 1316
Resume: Run plan: 0 will run, 1 skipped/reused, 0 blocked
```

Key SAF outputs:

```text
outputs/04_tractography/saf/rc_csd_act/SAF.tck
outputs/04_tractography/saf/rc_csd_act/SAF.vtk
outputs/04_tractography/saf/rc_csd_act/saf_manifest.json
outputs/04_tractography/saf/rc_csd_act/saf_qc.json
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

Blocked optional targets are expected on a user machine unless their external
paths and data requirements are supplied:

- `surface_postprocess`: requires FreeSurfer command-line tools and
  `FREESURFER_HOME`; the configured-host closure is recorded in the 2026-07-25
  revalidation.
- `saf`: requires completed DDSurfer post-processing outputs or an explicit
  dMRI-space `--saf-fs-dir`.
- `wma`: requires WhiteMatterAnalysis, an ORG atlas and a Slicer/SlicerDMRI
  runtime; the representative-subject closure is recorded above.
- `tractcloud`: requires an explicit VTK/VTP tractogram plus a TractCloud
  Python/model runtime.

These blockers do not stop runnable targets unless `--strict-environment` is used.

WMA and TractCloud remain explicit optional external backends rather than
zero-configuration default features. WMA now has a dedicated
representative-subject validation, while the combined historical backend
closure remains summarized in:

```text
/data/chengjin/SlicerDDSurfer-test/100307/outputs/00_run_metadata/bundle_backend_closure.json
```

That closure records WMA 800 clusters / 74 anatomical tracts and TractCloud 17 bundles / 5 categories.

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
- `outputs/04_tractography/saf/rc_csd_act/SAF.tck`
- `outputs/04_tractography/saf/rc_csd_act/SAF.vtk`
- `outputs/02_microstructure/freewater/*_fw_fraction.nii.gz`
- `outputs/02_microstructure/freewater/*_fw_FA.nii.gz`
- `outputs/02_microstructure/freewater/*_fw_MD.nii.gz`
- `outputs/02_microstructure/noddi/*_noddi_NDI.nii.gz`
- `outputs/02_microstructure/noddi/*_noddi_ODI.nii.gz`
- `outputs/02_microstructure/noddi/*_noddi_IsoVF.nii.gz`
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
- `scripts/release_audit.py --json --warn-only` passed with `release_ready=true`, `blocker_count=0`.
- Slicer setting write warnings may appear under `xvfb-run` in this local environment. They are not treated as failures if the smoke assertions pass.
- STL surface files currently trigger Slicer warnings that coordinate-system metadata is absent and Slicer assumes LPS. This does not block loading, but should remain a future metadata/QC cleanup item.
