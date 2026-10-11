# DDSurfer Pipeline Synchronization: 2026-10-05

## Source And Resources

SlicerDDSurfer now vendors DDSurfer commit
`a4ec44cf56651b411ab30b9c91cfac63cc3b2300`, following the previous
`c3fa631b340c3e06eb75ab4f0f9ac9a288a25488` snapshot.
`anatomy/surface/ddsurfer_backend/UPSTREAM.json` records hashes for 66 exact upstream
source, configuration and documentation assets, including the README image.

The four checkpoints, two initialization meshes and 1-mm registration atlas
are unchanged. The weight manifest changes the default precision from BF16
to FP32. Plugin download metadata and the independent model-repository mirror
index/manifest have been updated together. All 31 core assets passed checksum
verification; no DDSeg/DDParcel model change is included.

## Integration Changes

- GUI/batch configurations and both surface adapters default to FP32. Explicit
  `auto` and `bf16` remain available; BF16 requires a compatible CUDA device.
- Batch flags `--surface-cpu-threads` (default 4) and
  `--surface-max-gpu-gib` (default 24) reach upstream inference. These are resource
  budgets, not a guarantee that the model fits on every GPU.
- Raw-input resume reaches upstream preflight instead of accepting readable
  STL files alone. Upstream checks input geometry/gradients, model hashes,
  relevant runtime/settings and the content-checked final-result receipt.
  It can reuse verified results before checking CUDA availability.
- Registered-input reuse checks the subject, precision/budgets and hashes of
  input volumes, transform, atlas, checkpoint metadata, checkpoints, templates,
  canonical OBJ and compatibility STL products. Old receipts fail closed.
- The upstream subject lock covers the complete raw-input pipeline. Output
  and cache symlink guards and early FreeSurfer/runtime checks are preserved.
- Backend processes have owned process groups. Cancellation signals the backend,
  allowing upstream to terminate and reap its separately grouped stages.
  GUI force-kill grace is 15 seconds to accommodate upstream's 10-second stage
  cleanup. Surface manifests/QC record `cancelled` rather than `running`.
- `SurfaceConfig(auto_mask=True)` with an explicit raw-input bundle whose mask
  is `None` enables upstream CPU SynthStrip. It requires FreeSurfer's SynthStrip
  executable/model. Supplied masks are retained. This is an opt-in adapter API;
  the existing GUI/batch input preparation still uses its MRtrix mask route.

## Real Validation

All new scientific runs used subject **100307**. Local evidence is in
`ignore/validation/ddsurfer_sync_20261005/`; adjacent log files start with
`ignore/validation/ddsurfer_sync_20261005_`.

| Check | Outcome | Evidence |
| --- | --- | --- |
| Prepared raw dMRI to native surfaces, FP32 | Four finite, watertight surfaces; Euler characteristic 2; matching white/pial topology | `raw/surface_qc.json`, `output_audit.json` |
| Actual result reuse | Upstream logged verified completed-output reuse | Adjacent `resume.log`; `raw/upstream/100307/logs/pipeline.json` |
| Slicer default Python inference, FP32 | Four native surfaces completed from the same registered DTI channels | `slicer_registered/surface_qc.json` |
| No supplied mask, CPU SynthStrip to native surfaces | Native mask generation and the complete downstream pipeline passed | `auto_mask/surface_qc.json`, `auto_mask/upstream/100307/logs/mask.json` |
| Native scalar maps | Finite data and geometry in both raw-input runs | `output_audit.json` |
| Real Slicer loading | Eight RAS/LPS STL variants loaded; native RAS bounds error below 0.001 mm | `slicer_scene_smoke.json` |
| Cancellation | Real backend/stage process-group test confirms stage termination | `Testing/Python/test_ddsurfer_sync.py` |
| Plugin regression suite | 668 tests: 664 passed, 4 existing skips | Adjacent `plugin.log` |
| Exact upstream test suite | 120 passed in an isolated snapshot with matching resources | Adjacent `upstream.log` |
| Model resources | 31 core files verified | Adjacent `assets.log` |

The DDCSR reference environment uses PyTorch 2.4.1; PythonSlicer uses PyTorch
2.11.0. For FP32 runs on identical registered input channels, left-hemisphere
OBJ vertices matched exactly. Right-hemisphere mean corresponding-vertex
differences were below 0.000007 mm; the maximum across surfaces was below
0.00035 mm. This is numerical agreement, not a promise of bitwise equality
across package/device versions. Runtime versions are recorded per run.

The upstream tests require their expected `weights/` and `template/` layout.
They were run with the nine matching surface resources, excluding retained
legacy templates, in an ignored isolated snapshot. This does not put weights
inside the shipped plugin or alter vendored source files.

The new FreeSurfer environment checker passed against the local toolchain and
is covered by upstream regression tests.
Full surface postprocessing was exercised in the
[previous synchronization](DDSURFER_SYNC_20261004.md); it was not rerun for this
snapshot. Human anatomical review remains `pending`, and multi-subject accuracy
is not certified by these execution/geometry tests.

The subsequent [Linux Slicer acceptance campaign](SLICER_ACCEPTANCE_20261007.md)
reran complete surface postprocessing through the installed extension's GUI
with this synchronized backend. Its evidence and validation boundaries are
recorded separately from this synchronization snapshot.

## Reproduce And Deploy

```bash
python3 scripts/sync_ddsurfer_upstream.py \
  --upstream /data/chengjin/DDSurfer \
  --asset-root /data/chengjin/SlicerDDSurfer-models
python3 scripts/download_model_assets.py --profile core --verify-only \
  --asset-root /data/chengjin/SlicerDDSurfer-models
```

`Testing/Python/ddsurfer_sync_validation.py` runs raw-input, registered-input,
resume and optional SynthStrip checks. `ddsurfer_sync_output_audit.py` records
native geometry, scalar-map integrity and cross-runtime vertex differences.
These scripts generate scientific results; they do not modify a running Slicer
scene. Slicer loading was checked in a separate temporary X display with settings
disabled, without changing the active Slicer/MRI Agent sessions.

Restage an installed source copy and restart Slicer to activate it. Publish the
code and asset metadata together: the new weight-manifest hash differs even
though the binary checkpoints are unchanged. Existing redistribution notices
and licensing requirements still apply.
