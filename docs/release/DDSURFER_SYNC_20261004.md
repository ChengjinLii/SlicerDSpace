# DDSurfer synchronization: 2026-10-04

## Pinned Source And Assets

The active surface workflow now uses an unmodified snapshot of
`/data/chengjin/DDSurfer` at commit
`c3fa631b340c3e06eb75ab4f0f9ac9a288a25488`.
`anatomy/surface/ddsurfer_backend/UPSTREAM.json` records SHA256 checksums for 59 source
and configuration files. GUI and batch execution call this backend in a
separate Python process rather than reimplementing its neural network.

The independent asset repository at `/data/chengjin/SlicerDDSurfer-models`
contains the matching nine surface resources:

```text
surface/weights/
  manifest.json
  SHA256SUMS
  ddsurfer_lh_wm.pt
  ddsurfer_rh_wm.pt
  ddsurfer_lh_pial.pt
  ddsurfer_rh_pial.pt
surface/template/
  ddsurfer_lh_template.obj
  ddsurfer_rh_template.obj
  100HCP-population-mean-T2-1mm.nii.gz
```

The downloader manifest, mirror index and mirror manifest have matching hashes.
The `core` profile contains 31 required files. Old weights are retained in the
asset repository but are no longer selected by the surface profile. DDSeg and
DDParcel weights are unchanged. The older atlas used by DDParcel remains in
the parcellation profile; it is not interchangeable with the new surface atlas.
Clear or update old `DDSURFER_CHECKPOINT_DIR`, `DDSURFER_TEMPLATE_DIR` and
`DDSURFER_REGISTRATION_ATLAS` overrides when migrating. Overrides that select
old resources fail validation instead of silently mixing model releases.

## Runtime Changes

- Model construction, checkpoint loading, hemisphere crops, precision and
  smoothing follow the upstream release manifest. The TANet encoder uses
  channels 32/64/128/256/512 and the upstream refinement configuration.
- Raw-input execution uses upstream DTI estimation, atlas registration,
  masking, fixed-grid resampling and normalization. The training grid is
  176 x 224 x 176 at 1 mm, with channels FA, MidEigenvalue, MinEigenvalue,
  MaxEigenvalue and MD in that order. Native DTI outputs retain Trace as well.
- Native indexed OBJ surfaces are the canonical scanner-RAS-mm products.
  Compatibility STL files retain the historical naming: ordinary STL uses
  LPS, while `_orig.stl` uses RAS. White/pial vertex correspondence is preserved.
- Surface-only FreeSurfer postprocessing uses upstream code for curvature,
  thickness, spherical registration, annotations, regional statistics and
  fsaverage transfer. It accepts native white/pial OBJ pairs without DDParcel
  or T1w input. FreeSurfer and a valid license are still required. A generated
  geometry-only reference is not an anatomical T1 image or a `recon-all` result.
- Current surface resume requires the pinned revision and successful automatic
  QC. Current postprocessing also checks native surface hashes. Its cache is
  keyed by input geometry, atlas selection, hemisphere mode and upstream
  revision; force creates a fresh cache without deleting previous results.
- Backend launch isolates Slicer's Python, library and ITK factory overrides
  from an external Python environment. This fixes the real stdlib mismatch
  and SimpleITK bus error encountered during the integration test.

## Validation Evidence

Real validation used subject 100307 throughout. Evidence is stored locally in
`ignore/validation/ddsurfer_sync_20261004/`; images and subject data are excluded
from the code repository.

| Check | Result | Evidence |
| --- | --- | --- |
| Matching model assets | All 31 core files verified | Model-repository `release-manifests/ddsurfer-sync-20261004.json` |
| Raw dMRI to native surfaces | Four surfaces completed; finite coordinates, watertight, Euler characteristic 2 | `raw/surface_qc.json` |
| Unified batch entry point | Actual raw-input run completed from PythonSlicer using the external reference environment | `orchestrator.log`, `orchestrator_outputs/00_run_metadata/` |
| Resume behavior | Current surface and postprocessing runs reused successfully; tests reject changed geometry/atlas selection and obsolete receipts | `orchestrator_resume.log`, `postprocess_resume.log`, `cache_tests.log` |
| Registered-input cleanup | Actual Slicer inference preserved all four native surfaces and removed only generated intermediate subject folders | `cleanup_validation.log`, `slicer_registered_cleanup/surface_qc.json` |
| Preprocessing parity | All five normalized channels and affines exactly equal | `output_validation.json` |
| Reference inference parity | All four OBJ files have identical SHA256 and zero vertex error under PyTorch 2.4.1 | `output_validation.json` |
| Slicer inference parity | All four OBJ files have identical SHA256 and zero vertex error against upstream under PyTorch 2.11.0 | `output_validation.json` |
| Surface-only postprocessing | Both hemispheres and aparc/aparc.a2009s completed without DDParcel; coordinate round-trip error below 0.00001 mm | `postprocess/03_structural/ddsurfer/postprocess/qc.json` |
| Surface metric integrity | Thickness, curvature, sulc and pial-area arrays are finite and have the expected vertex counts; annotation indices are valid | `output_validation.json` |
| Actual Slicer scene loading | All eight RAS/LPS STL variants loaded with world bounds matching canonical OBJ within 0.001 mm | `slicer_scene_smoke.json` |
| Plugin regression suite | 660 tests: 656 passed, 4 skipped | `slicer_python_tests.log` |
| Upstream regression suite | 86 tests passed in an isolated snapshot | `upstream_tests.log` |

PythonSlicer uses PyTorch 2.11.0+cu129, whereas the reference DDCSR environment
uses PyTorch 2.4.1. Comparing BF16 inference between these two runtimes gives
mean corresponding-vertex differences of approximately 0.021-0.026 mm and
maximum differences of approximately 0.148-0.426 mm. This is not bitwise
cross-version reproducibility. Exact source parity was verified separately
within each runtime. Pin Python/PyTorch/CUDA and precision when reproducing
reference results; surface manifests record the actual interpreter and package
versions.

Automatic geometry and execution checks do not establish anatomical accuracy
across populations. Human anatomical review remains marked `pending`. This
sync is validated on Linux with one representative subject; it does not certify
other platforms or a packaged Extension Manager release.

## Local Use And Future Synchronization

For the existing local asset checkout:

```bash
export SLICERDDSURFER_MODEL_ASSETS_DIR=/data/chengjin/SlicerDDSurfer-models
```

The default interpreter is PythonSlicer inside the Slicer GUI. To reproduce the
reference environment, set `DDSURFER_PYTHON_BIN` before launching Slicer, or use
the batch flag `--surface-python-bin`. For this machine:

```bash
export DDSURFER_PYTHON_BIN=/home/chengjin/miniconda3/envs/DDCSR/bin/python
```

Batch execution also supports `--surface-precision auto|bf16|fp32` and
`--surface-atlas-t2`. The older `--atlas-t2` flag applies to DDParcel, not DDSurfer.
Do not install the old DDCSR Python version into Slicer's own Python environment.

To synchronize a future committed upstream revision and verify the asset root:

```bash
python3 scripts/sync_ddsurfer_upstream.py \
  --upstream /data/chengjin/DDSurfer \
  --asset-root /data/chengjin/SlicerDDSurfer-models
python3 scripts/download_model_assets.py --profile core --verify-only \
  --asset-root /data/chengjin/SlicerDDSurfer-models
```

Re-run staging after updating an installed source copy. The source and asset
repositories must be published together before remote users can download this
new release. Public redistribution terms remain subject to the existing
third-party and model-asset notices.
