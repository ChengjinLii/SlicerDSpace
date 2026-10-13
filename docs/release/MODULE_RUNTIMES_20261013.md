<div align="center">

# Module Runtime Inventory

**2026-10-13 · Measured, scoped, traceable**

[Project](../../README.md) | [QC](BUNDLE_BACKENDS_20261013.md) | [CSV](benchmarks/module_runtimes_20261013.csv) | [JSON](benchmarks/module_runtimes_20261013.json) | [Other language](MODULE_RUNTIMES_20261013.zh-CN.md)

</div>

Real historical records and new measurements cover 32 operations. READY means a scoped time exists, not anatomical certification. Missing values are not zero; failed/skipped/cache checks are not successful computation. CSV/JSON preserve the ledger and source hashes.

New measurements include three imports, MRtrix/SynthStrip masks, fresh full-volume DTI, six-map ROI statistics and native bundle loading. WMQL/TractCloud use corrected reruns; WMA uses the existing scoped-pass 149741 run.

---

| Module | Subject | Seconds | Minutes | Status | Input / Scope |
| --- | --- | ---: | ---: | --- | --- |
| NIfTI import | sub-dicom | 2.880 | 0.048 | READY | [104, 104, 60, 31] |
| DICOM import | sub-dicom | 0.271 | 0.005 | READY | [104, 104, 60, 31] |
| NRRD import | sub-dicom | 2.296 | 0.038 | READY | [104, 104, 60, 31] |
| Input validation | sub-dicom | 0.013 | 0.000 | READY | 31-volume real DWI |
| PNL diffusion CNN mask | 100307 | 346.698 | 5.778 | READY | 288-volume real HCP DWI |
| MRtrix dwi2mask | sub-dicom | 2.455 | 0.041 | READY | [104, 104, 60, 31] |
| SynthStrip mask | sub-dicom | 31.317 | 0.522 | READY | 31-volume real DWI |
| DIPY preprocessing | sub-dicom | 657.224 | 10.954 | READY | 31-volume real DWI |
| MRtrix/FSL preprocessing | sub-dicom | 2375.537 | 39.592 | READY | 31-volume real DWI |
| Fresh native DTI fitting | 100307 | 135.999 | 2.267 | READY | [145, 174, 145, 288] |
| DDSeg | 100307 | 57.417 | 0.957 | READY | HCP 100307 / task-specific real inputs |
| DDSeg world-coordinate QC | 100307 | 0.514 | 0.009 | READY | HCP 100307 / task-specific real inputs |
| DDParcel | 100307 | 290.240 | 4.837 | READY | HCP 100307 / task-specific real inputs |
| DDSurfer native surfaces | 100307 | 222.562 | 3.709 | READY | HCP 100307 / task-specific real inputs |
| Surface postprocessing (historical) | 100307 | 882.262 | 14.704 | READY | HCP 100307 / task-specific real inputs |
| DTI scalar export / ROI | 100307 | 6.953 | 0.116 | READY | HCP 100307 / task-specific real inputs |
| Free-water | 100307 | 1288.584 | 21.476 | READY | HCP 100307 / task-specific real inputs |
| AMICO NODDI | 100307 | 1784.280 | 29.738 | READY | HCP 100307 / task-specific real inputs |
| DIPY DKI WLS (64 voxels) | 100307 | 0.188 | 0.003 | PARTIAL | 64 fit voxels / 288 volumes |
| Python MK-Curve (8 voxels) | 100307 | 0.431 | 0.007 | PARTIAL | 8 fit voxels / 288 volumes |
| DTI deterministic tractography | 100307 | 67.922 | 1.132 | READY | HCP 100307 / task-specific real inputs |
| CSD / ACT / SIFT2 route | 100307 | 1011.515 | 16.859 | READY | HCP 100307 / task-specific real inputs |
| SAF re-filtering | 100307 | 209.474 | 3.491 | READY | 100k tracks -> 13043 SAF candidates |
| WMQL | 100307 | 5.948 | 0.099 | READY | 50k CSD/ACT tracks |
| WMA ORG atlas | 149741 | 2982.609 | 49.710 | READY | 100k UKF tracks / 74 nonempty bundles |
| TractCloud | 100307 | 18.556 | 0.309 | READY | 50k CSD/ACT tracks / CUDA batch 2048 / seed 0 |
| Count connectome | 100307 | 2.978 | 0.050 | READY | HCP 100307 / task-specific real inputs |
| SIFT2 connectome | 100307 | 2.678 | 0.045 | READY | HCP 100307 / task-specific real inputs |
| Six-map regional statistics | 100307 | 6.198 | 0.103 | READY | 101 regions |
| Slicer WMQL result loading | 100307 | 0.189 | 0.003 | READY | 4 files / 27 streamlines |
| Slicer TractCloud result loading | 100307 | 6.320 | 0.105 | READY | 39 files / 21432 streamlines |
| Slicer WMA result loading | 149741 | 8.269 | 0.138 | READY | 74 files / 40338 streamlines |

---

## Measurement Boundaries

- **DKI / MK-Curve are PARTIAL real-ROI measurements**, 64 / 8 voxels respectively. Full-brain times are unmeasured and not extrapolated.
- DTI scalar export reuses a fitted tensor; fresh DTI includes fitting and six scalar conversions.
- Surface postprocessing is the October 6 historical full route, not an October 13 optimized-version speed claim.
- CSD/ACT/SIFT2 is a combined stage; no individual FOD/ACT/SIFT2 timings are invented.
- Slicer loading includes independent coordinate comparison but excludes startup/extraction. The 165.7 s DTI acceptance process is not confused with the 136 s fitting measurement.
- Different subjects, sizes, caches, threads, versions and concurrent load cannot be compared or summed directly. Missing historical hardware/thread metadata is not inferred.
- New-measurement host: Xeon Platinum 8360Y, 144 logical CPUs, about 503.5 GiB RAM and two H100 GPUs; not every operation used GPUs.
- Downloads, optional UKF tracking/WMA diffusion-measurement export, batch scheduling and final scene saving are outside this catalog.

```bash
python scripts/collect_module_runtimes.py --output-dir /path/to/report
```
