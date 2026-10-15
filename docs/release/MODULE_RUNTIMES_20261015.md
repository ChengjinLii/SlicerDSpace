<div align="center">

# Module Runtime Inventory

**2026-10-15 · Measured, scoped, traceable**

[Project](../../README.md) | [QC](BUNDLE_BACKENDS_20261013.md) | [GPU verification](GPU_POLICY_20261013.md) | [CSV](benchmarks/module_runtimes_20261015.csv) | [JSON](benchmarks/module_runtimes_20261015.json) | [Other language](MODULE_RUNTIMES_20261015.zh-CN.md)

</div>

Real historical records and new measurements cover 32 operations. READY means a scoped time exists, not anatomical certification. Missing values are not zero; failed/skipped/cache checks are not successful computation. CSV/JSON preserve the ledger and source hashes.

New measurements include three imports, MRtrix/SynthStrip masks, fresh full-volume DTI, six-map ROI statistics and native bundle loading. WMQL/TractCloud use real reruns; WMA replaces the scoped 149741 record only after a new independent acceptance. PNL/SynthStrip and MRtrix/FSL now include real GPU acceptances; CPU references, repeats and failures are shown separately below.

---

| Module | Subject | Device | Seconds | Minutes | Status | Input / Scope |
| --- | --- | --- | ---: | ---: | --- | --- |
| NIfTI import | sub-dicom | not recorded | 2.880 | 0.048 | READY | [104, 104, 60, 31] |
| DICOM import | sub-dicom | not recorded | 0.271 | 0.005 | READY | [104, 104, 60, 31] |
| NRRD import | sub-dicom | not recorded | 2.296 | 0.038 | READY | [104, 104, 60, 31] |
| Input validation | sub-dicom | not recorded | 0.013 | 0.000 | READY | 31-volume real DWI |
| PNL diffusion CNN mask | 100307 | cuda | 84.437 | 1.407 | READY | 288-volume real HCP DWI |
| MRtrix dwi2mask | sub-dicom | not recorded | 2.455 | 0.041 | READY | [104, 104, 60, 31] |
| SynthStrip mask | sub-dicom | cuda | 9.494 | 0.158 | READY | 31-volume real DWI |
| DIPY preprocessing | sub-dicom | not recorded | 657.224 | 10.954 | READY | 31-volume real DWI |
| MRtrix/FSL preprocessing | sub-dicom | cuda | 719.476 | 11.991 | READY | 31-volume real DWI / reverse-PE b0 |
| Fresh native DTI fitting | 100307 | not recorded | 135.999 | 2.267 | READY | [145, 174, 145, 288] |
| DDSeg | 100307 | not recorded | 57.417 | 0.957 | READY | HCP 100307 / task-specific real inputs |
| DDSeg world-coordinate QC | 100307 | not recorded | 0.514 | 0.009 | READY | HCP 100307 / task-specific real inputs |
| DDParcel | 100307 | not recorded | 290.240 | 4.837 | READY | HCP 100307 / task-specific real inputs |
| DDSurfer native surfaces | 100307 | not recorded | 222.562 | 3.709 | READY | HCP 100307 / task-specific real inputs |
| Surface postprocessing | 100307 | cpu | 726.217 | 12.104 | READY | Fresh full bilateral current-snapshot surface postprocessing; independent geometry/morphometry/annotation checks |
| DTI scalar export / ROI | 100307 | not recorded | 6.953 | 0.116 | READY | HCP 100307 / task-specific real inputs |
| Free-water | 100307 | not recorded | 1288.584 | 21.476 | READY | HCP 100307 / task-specific real inputs |
| AMICO NODDI | 100307 | not recorded | 1784.280 | 29.738 | READY | HCP 100307 / task-specific real inputs |
| DIPY DKI WLS | 100307 | cpu | 5496.222 | 91.604 | READY | Full supplied brain mask: 740916 voxels; 681770 valid; read-only full-grid and direct-DIPY sample parity passed |
| Python MK-Curve | 100307 | cpu | 989.384 | 16.490 | READY | 740916 mask voxels / 736294 corrected-valid; not all voxels valid |
| DTI deterministic tractography | 100307 | not recorded | 67.922 | 1.132 | READY | HCP 100307 / task-specific real inputs |
| CSD / ACT / SIFT2 route | 100307 | not recorded | 1011.515 | 16.859 | READY | HCP 100307 / task-specific real inputs |
| SAF re-filtering | 100307 | not recorded | 209.474 | 3.491 | READY | 100k tracks -> 13043 SAF candidates |
| WMQL | 100307 | cpu | 23.358 | 0.389 | READY | 277875 UKF tracks; independent audit passed |
| WMA ORG atlas | 100307 | cpu | 6506.938 | 108.449 | READY | 277875 UKF tracks; independent audit passed |
| TractCloud | 100307 | cuda | 18.500 | 0.308 | READY | 50k CSD/ACT tracks / batch 2048 / seed 0 |
| Count connectome | 100307 | not recorded | 2.978 | 0.050 | READY | HCP 100307 / task-specific real inputs |
| SIFT2 connectome | 100307 | not recorded | 2.678 | 0.045 | READY | HCP 100307 / task-specific real inputs |
| Six-map regional statistics | 100307 | not recorded | 6.198 | 0.103 | READY | 101 regions |
| Slicer WMQL result loading | 100307 | not recorded | 0.189 | 0.003 | READY | 4 files / 27 streamlines |
| Slicer TractCloud result loading | 100307 | not recorded | 6.320 | 0.105 | READY | 39 files / 21432 streamlines |
| Slicer WMA result loading | 149741 | not recorded | 8.269 | 0.138 | READY | 74 files / 40338 streamlines |

---

## Measurement Boundaries

- DKI/MK-Curve use full-brain times only after independent acceptance; historical 64/8-voxel records remain, never extrapolated. MK-Curve timing does not imply every voxel is valid.
- DTI scalar export reuses a fitted tensor; fresh DTI includes fitting and six scalar conversions.
- A new surface-postprocessing time replaces the historical record only after independent full-route acceptance; JSON records identify the actual scope/version.
- CSD/ACT/SIFT2 is a combined stage; no individual FOD/ACT/SIFT2 timings are invented.
- Slicer loading includes independent coordinate comparison but excludes startup/extraction. The 165.7 s DTI acceptance process is not confused with the 136 s fitting measurement.
- Different subjects, sizes, caches, threads, versions and concurrent load cannot be compared or summed directly. Missing historical hardware/thread metadata is not inferred.
- The PNL representative is the default Auto GPU run, not the fastest repeat. CPU reference, explicit CUDA repeat and historical 346.7 s CPU time remain in JSON. The new CPU time is already about 79 s: no fourfold GPU speedup is claimed.
- The approximately 719 s MRtrix/FSL GPU acceptance is the whole route, including CPU denoise/Gibbs/topup/final mask, not isolated eddy time.
- The stopped 949 s old-runtime SynthStrip attempt and failed 365 s CUDA eddy thread-option attempt are not successful computation; corrected acceptances are about 9 s and 719 s, with anatomical review still pending.
- The historical slow PNL record is dominated by its CNN phase (about 284 s in rounded logs versus about 15 s in the current CPU log). Historical load/full threading metadata is missing, so its cause is not uniquely established. Fresh masks now retain phase timings and thread environment; instrumented GPU repeats are recorded separately.
- New-measurement host: Xeon Platinum 8360Y, 144 logical CPUs, about 503.5 GiB RAM and two H100 GPUs; not every operation used GPUs.
- Downloads, optional UKF tracking/WMA diffusion-measurement export, batch scheduling and final scene saving are outside this catalog.

---

## CPU / GPU References And Failed Attempts

| Module | Run / Scope | Requested / Actual Device | Seconds | Execution / Integrity Status |
| --- | --- | --- | ---: | --- |
| PNL diffusion CNN mask | CPU reference | cpu / cpu | 78.961 | pass |
| PNL diffusion CNN mask | Default Auto GPU run | auto / cuda | 84.437 | pass / representative |
| PNL diffusion CNN mask | Explicit CUDA repeat | cuda / cuda | 79.775 | pass |
| SynthStrip mask | Compatible-runtime CPU reference | cpu / cpu | 14.268 | pass |
| SynthStrip mask | Compatible-runtime Auto GPU run | auto / cuda | 9.494 | pass / representative |
| SynthStrip mask | Stopped incompatible-runtime attempt; no mask | not recorded / not recorded | 949.431 | fail |
| SynthStrip mask | Incompatible-runtime rejection; no inference | not recorded / not recorded | 1.579 | fail |
| MRtrix/FSL preprocessing | Failed CUDA eddy thread-option attempt | not recorded / not recorded | 365.179 | FAIL |
| MRtrix/FSL preprocessing | Corrected CUDA eddy full preprocessing | not recorded / cuda | 719.476 | PASS / representative |
| TractCloud | Seeded CUDA inference and decoded QC | cuda / cuda | 18.500 | completed / representative |
| PNL diffusion CNN mask | Phase-instrumented Auto GPU repeat | auto / cuda | 104.326 | pass |
| SynthStrip mask | Phase-instrumented Auto GPU repeat | auto / cuda | 7.007 | pass |

Unrecorded device choices are not inferred from logs. Software versions, input hashes, source files and full timing scopes remain in JSON. Failed durations are for troubleshooting, never representative compute timings.

```bash
python scripts/collect_module_runtimes.py --output-dir /path/to/report --documentation-dir docs/release
```

This updated inventory includes scoped historical timings; not every module was rerun on this date.
