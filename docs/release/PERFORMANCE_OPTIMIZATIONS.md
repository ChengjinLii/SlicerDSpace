<div align="center">

# Performance Optimizations

**Reviewed 20 October 2026 · New direct original-author comparison**

[Project](../../README.md) | [Documentation](../README.md) | [Runtimes](MODULE_RUNTIMES_20261017.md) | [Author-reference CSV](benchmarks/author_wma_optimizations_20261020.csv) | [JSON](benchmarks/author_wma_optimizations_20261020.json) | [中文](PERFORMANCE_OPTIMIZATIONS.zh-CN.md)

</div>

**Primary claims now require actually executing original-author code.** The new
WMA implementation accelerates fresh length filtering/copying without using
completed-stage cache hits. It preserves the scientific definition, not proposing
a different estimator or claiming better anatomical accuracy.

The earlier 10-11x regional-statistics and 1.42x MK-Curve observations compare
against older plugin code, **not original author implementations**. They remain
in an engineering appendix, not evidence of outperforming the original algorithm.
Device changes and inherited upstream improvements are also separate categories.

This review recomputes historical JSON and adds new paired implementation
experiments without rerunning or modifying the previous full-brain fits.
The reviewed working tree is dirty, based on commit
`a48fc95e0a52a88a1ae99dd683a547520acc0c5d`; that commit alone does not identify
the measured implementations. The JSON records evidence and reviewed-code hashes.

---

## Direct Original-Author WMA Optimization

The reference is unmodified SlicerDMRI/whitematteranalysis
[`filter.py`](https://github.com/SlicerDMRI/whitematteranalysis/blob/4532b911386d2d1bc7ebba63fdd13e65b1660623/whitematteranalysis/filter.py),
pinned at `4532b911386d2d1bc7ebba63fdd13e65b1660623`. Independent downloads of
the pinned filtering, registration-dispatch and license files match local SHA256
values exactly. An older plugin is not substituted for the author reference.
Both implementations run under the same Slicer Python 3.12.10, NumPy 2.2.6,
VTK 9.5.2 and Linux host.

| Real input | Measured streamlines | Author | Optimized | Ratio | Protocol |
| --- | ---: | ---: | ---: | ---: | --- |
| HCP 100206 CSD subset | 50,000 | 6.323 s | 0.110 s | **57.27x** | One warmup, three alternating repeats, medians |
| HCP 149741 CSD subset | 50,000 | 5.899 s | 0.085 s | **69.26x** | Same |
| HCP 877168 CSD subset | 50,000 | 5.841 s | 0.108 s | **53.92x** | Same |
| Complete ORG registration atlas | 1,989,106 | 134.289 s | 2.484 s | **54.06x** | One fresh full-input pair, no warmup |
| Complete 100307 UKF | 277,875 | 37.415 s | 0.690 s | **54.19x** | One fresh full-input pair, no warmup |

**These ratios apply only to attribute-free `preprocess()` filtering and geometry
copying, never complete WMA, bundle quantification or the plugin.** Timings exclude
file loading, comparison hashes, later sampling/registration/classification and
startup. Full-input observations are single pairs, not confidence intervals;
hardware is shared. The three subsets are selected from million-line real inputs
using the author's `downsample`, with predefined seed 2026. Both methods receive
identical inputs; the optimized method does not process fewer streamlines.
Every timed call recomputes the filter, without a result cache.

The [bulk implementation](../../tractography/wma_preprocessing.py) replaces
per-point Python/VTK calls with offsets/connectivity and bounded NumPy block
copies into fresh VTK buffers. A block contains at most **262,144 points**.
Full output and line-count-proportional indices still require memory; this is
not a whole-process constant-memory claim.

The author's first-eligible-line step-size estimator, accumulation order,
point-count thresholds, Python rounding, 40/260 mm limits, point/line order,
shared-point duplication and float32 `vtkPoints` output are preserved. It does
not substitute true per-line arc lengths or introduce a new precision reduction.
Only originally attribute-free calls are accelerated; requested attributes,
indices, other filters or unsupported layouts run the author implementation.
Sampling, optimization, transforms, outlier rejection and classification are unchanged.

All output coordinate and topology bytes match across the five cases. Original
seeded sampling at 124/125/126 also matches indices, geometry, R/A/S registration
arrays and MT19937 state words. A regression test separately verifies that the
complete random state is not consumed. Source hashes remain unchanged. Edge
tests include float64-to-author-float32 copying, shared/reversed points, empty
selection, 32-bit connectivity, block boundaries and original-code fallback.

An additional real-AF-derived numeric fixture explicitly introduces a synthetic
**+20 mm R displacement**, with 128/64 fixed/moving fibers and a 300-evaluation
budget. The unchanged author affine optimizer produces identical complete
objective histories and nonidentity transforms; both objective changes are
**-58.57054461025365**. This is controlled numeric regression, not acquired data,
whole-brain registration or anatomical accuracy. The unshifted control did not
improve the objective in either route; its unchanged trajectory and unsuccessful
improvement record remain, not relabeled successful registration.

The production [registration entry](../../scripts/run_wma_registration.py)
enables bulk filtering only when author-source hashes match, with the existing
bounded cache available afterward. No user setting, new dependency or GPU-policy
change is required. Logs record real bulk calls, bypasses and implementation
hashes. The verified POSIX hook is integrated; Windows/WSL keeps its original
route and native macOS performance is unmeasured. The exact upstream license
and provenance ship with the extension. Old failed bundles and QC gates are unchanged.

Use the [author-reference benchmark](../../scripts/benchmark_wma_author_preprocessing.py)
to repeat the comparison. The [JSON](benchmarks/author_wma_optimizations_20261020.json)
retains raw times, downloaded-source hashes, full geometry/sampling signatures
and optimizer evidence; the [CSV](benchmarks/author_wma_optimizations_20261020.csv)
summarizes five cases. Original local evidence is under
`ignore/validation/wma_author_bulk_20261020/`. Complete 74-tract classification
has not been rerun, so no proportional full-WMA acceleration is claimed.

This round's full backend regression ran **1110 tests: 1105 passed, five explicitly
skipped, no failures**. Its final local log is `full_tests_final.log` in that
directory. Packaged documentation links and resource integrity also pass.
This is not full-brain scientific, anatomical or cross-platform
performance acceptance. Current Slicer sessions were not restarted; older
installed copies require redeployment to use the new implementation.

---

## Engineering Appendix: Older Plugin Reference Only

These changes were implemented on **20 October 2026**, rather than merely
documented. They apply automatically, add no dependency/user setting and do not
change device selection or reduce scientific computation.

| Operation | Subject | Before, median | After, median | Ratio | Consistency |
| --- | --- | ---: | ---: | ---: | --- |
| Full-volume six-map ROI export | 100206 | 5.550 s | 0.552 s | **10.05x** | Byte-identical CSV |
| Full-volume six-map ROI export | 149741 | 5.562 s | 0.521 s | **10.68x** | Byte-identical CSV |
| Full-volume six-map ROI export | 877168 | 5.523 s | 0.483 s | **11.44x** | Byte-identical CSV |
| MK-Curve parameter extraction, 1024 voxels | 100206 | 0.528 s | 0.370 s | **1.42x** | Ten exactly equal raw parameter arrays |
| MK-Curve parameter extraction, 1024 voxels | 149741 | 0.524 s | 0.369 s | **1.42x** | Same |
| MK-Curve parameter extraction, 1024 voxels | 877168 | 0.527 s | 0.371 s | **1.42x** | Same |
| Complete MK-Curve 64-voxel numeric chunk | 100206 | 0.940 s | 0.849 s | **1.11x** | Exact coefficients, curves, parameters, masks and residuals |
| Complete MK-Curve 64-voxel numeric chunk | 149741 | 0.951 s | 0.861 s | **1.10x** | Same |
| Complete MK-Curve 64-voxel numeric chunk | 877168 | 0.974 s | 0.877 s | **1.11x** | Same |

The [ROI implementation](../../microstructure/pipeline.py) replaces repeated
whole-volume region/finite masks with one stable grouping of positive labels.
It preserves the original C-order sample sequence and reduction operations,
including per-metric validity, brain masks, nonfinite values, empty estimates and
coverage counts. Grouping indices require memory proportional to labeled voxels;
no peak-RSS reduction is claimed.

The [MK-Curve tensor routines](../../microstructure/mkcurve_tensor.py) cache
constant monomial metadata and two read-only quadrature bases for the author's
256 directions, totaling **42 KiB per process**. They do not cache voxel signals
or predictions. WLLS, QR fallback, directions, curve samples, thresholds and
validity conditions remain unchanged. Parameter extraction saves about 29.7%;
the complete numeric chunk saves **9.46%-9.97%**, not the same larger percentage.

Protocol: three independent real HCP subjects, an immutable pre-edit snapshot
versus current code, one warmup per method, three alternating-order repetitions
and median wall times in the same process. OMP/OpenBLAS/MKL were each set to one
only for these CPU benchmarks, not plugin defaults. ROI timings include reading,
validation, signatures, statistics and CSV/JSON writing for the full
`145 x 174 x 145` grid, FA/MD/AD/RD/L1/Trace and the brain mask. JSON also matches
except its runtime field.

Parameter tests uniformly select 1024 existing real coefficient rows per subject.
Full numeric chunks use 64 finite positive-signal voxels from predetermined
uniform raw-DWI candidates, retaining **200/201/200 synthetic-b0 samples** and
181 measurements. Chunk work includes WLLS, curves, detection/correction,
parameters, validity and residuals, but excludes input decompression/preparation
and full-brain file export. **The reference is the preceding Python implementation,
not author MATLAB; these ratios are not full-brain or workflow speedups.**

Input hashes remain unchanged; no old fit/failure is overwritten. The host is
shared, not exclusive, and native Windows/macOS performance and improved accuracy
are unmeasured. See [new CSV](benchmarks/compute_optimizations_20261020.csv) and
[complete JSON](benchmarks/compute_optimizations_20261020.json). The immutable
snapshot, real signal subsets, script and logs remain in local
`ignore/validation/compute_optimization_20261020/`. New
development-checkout tests in `Testing/Python/test_compute_optimizations.py` cover
read-only caches, exact sample order, sparse/empty labels and nonfinite inputs.
Acceleration does not turn previous invalid estimates into valid ones.

That earlier round's full backend regression: **1103 tests, 1098 passed, five explicitly skipped,
no failures**; the local log is `full_tests.log` in that directory. This does not
replace GUI, anatomical or cross-platform scientific acceptance. Running Slicer
sessions were not restarted; an older installed copy must be redeployed to use
these changes.

---

## Historical Stage And Device Comparisons

Speed ratio = `reference_seconds / optimized_seconds`.
Time reduction = `100 * (1 - optimized_seconds / reference_seconds)`.

| Operation | Reference | Optimized | Ratio | Reduction | Output check / scope |
| --- | ---: | ---: | ---: | ---: | --- |
| WMA registration-input preparation | 533.775 s | 180.550 s | **2.96x** | 66.17% | Three fixed-seed calls, including initial cache fill; bitwise-equal registration inputs |
| Shared mapping of four surface overlays | 13.379 s | 3.519 s | **3.80x** | 73.70% | One real left hemisphere; four commands versus one multi-frame command; four byte-identical MGH outputs |
| Three-slab DWI reads | 37.252 s | 17.079 s | **2.18x** | 54.15% | Includes sequential decompression; exact slab arrays and affine; unchanged source |
| SynthStrip CPU to GPU | 14.268 s | 9.494 s | **1.50x** | 33.46% | Same input/script/weights/runtime; Dice 0.999993918, two differing voxels |

These are **not whole-pipeline speedups**. Surface mapping measures command
execution, excluding extra Python packing, validation and publication overhead.
DWI timings do not measure FW fitting. SynthStrip is a single device pair using
the upstream GPU implementation, not a new estimator. The first three rows each
use one subject; three WMA seeds are sampling iterations, not independent
end-to-end trials. No confidence intervals are available, and local savings
cannot be added together to predict workflow acceleration.

### WMA Cache

The [bounded cache](../../tractography/wma_registration.py) and
[author-entry adapter](../../scripts/run_wma_registration.py) retain deterministic
length-filtered atlas/subject polydata. The full inputs contain 1,989,106 and
277,875 streamlines. Original random sampling, random state, objectives,
transforms and classification remain unchanged. Only verified author-source
hashes enable interception; unknown versions run unmodified. VTK modification
times and filter settings invalidate entries, and attribute/index requests bypass
the cache. `WMAOrgAtlasConfig.registration_preprocess_cache` defaults to true.

The current memory-bounded revision separately took **181.542 s**, or **2.94x**
against the preserved author reference. This is not another independent paired
control. Peak retained cache memory was **3,374,317,568 bytes / 3.14 GiB**, not
whole-process peak RSS. Its budget is one quarter of available RAM, capped at
4 GiB, or a conservative 256 MiB without memory discovery. Lower memory can
reduce hits, not scientific requirements. The POSIX adapter optimization is not
enabled on the current Windows/WSL route; native macOS performance is unmeasured.

A fresh full WMA run took **4664.826 s**, with a separate unchanged 95,755-track
assignment audit. It lacks a matched complete no-cache run, so **2.96x must not
be attributed to complete WMA**. Anatomical review remains separate. See
[workflow evidence](WORKFLOW_GENERALIZATION_20261017.md).

### Surface Postprocessing

This optimization is **inherited from pinned DDSurfer upstream `c3b2d40`**, not
a novel plugin reconstruction algorithm. The [overlay writer](../../anatomy/surface/ddsurfer_backend/postprocessing/overlays.py)
maps thickness, curvature, sulcal depth and pial area together with
`mri_surf2surf --split`. Each result has 163,842 target vertices; values,
geometry, headers and additional MGH bytes match separate commands exactly.
The displayed ratio is recomputed from the plugin's own preserved command record.

Python regional labels, in-process statistics, shared inputs and bilateral
thread budgeting are also inherited. Plugin verification found 109 byte-identical
regional labels and matching statistics, but has no complete paired replacement
timings for those operations. Additional upstream warm-file observations are
documented in its [optimization notes](../../anatomy/surface/ddsurfer_backend/postprocessing/OPTIMIZATIONS.md),
not presented as plugin end-to-end benchmarks. Scientific registration/thickness
commands are retained.

### DWI Access

The [reader](../../shared/diffusion_io.py) decompresses `.nii.gz` once to
temporary disk, reads it through memory mapping and cleans up on exit. The
unchanged real input is `145 x 174 x 145 x 288`; z=0/72/144 were compared without
`indexed_gzip`. This is one timing pair with uncontrolled OS page cache, not a
storage-independent guarantee or a measured percentage reduction in peak RSS.
Sufficient temporary disk is required. A separate exact 64-voxel FW fit does
not establish full-brain fitting speed. See the [I/O benchmark](../../scripts/benchmark_diffusion_chunk_io.py).

---

## Observations And Unmeasured Benefits

| Route | Evidence | Permitted interpretation / limit |
| --- | --- | --- |
| NODDI CPU parallelism | Historical one-thread 1784.280 s; later eight-thread 343.098 s; observed ratio 5.20 | Six saved arrays match exactly. Different-time observations are not a controlled 5.20x speedup or an improvement over AMICO itself |
| DTI export reuse | Fresh eight-map export/QC 1.102781 s; reuse 0.001251 s; output timestamps unchanged | Avoids a completed stage; not approximately 881x faster tensor estimation |
| MK-Curve Python port | Chunking, disk backing, optional processes and condition-checked batched WLLS with pivoted-QR fallback | Numeric reference/full-brain records exist, but no matched full author MATLAB/Octave-versus-Python timing |
| DDSeg Python/PyTorch port | Converted network weights, three-view inference and automatic device selection | Reduces MATLAB deployment requirements; no complete original-runtime per-view accuracy/speed comparison |
| Native DDSurfer, DDParcel, TractCloud | Upstream networks and backend-aware GPU selection; scoped TractCloud CUDA run 18.50 s | Device use and a runtime record do not demonstrate acceleration over the author algorithm |
| SAF Python port | Partial author-kernel comparisons, explicit geometry fixes and real candidate-track checks | No full original-runtime timing or clustering-output equivalence claim |

NODDI uses upstream `nthreads`, automatically bounded by available CPUs and eight;
explicit positive counts remain supported. AMICO BLAS threads are set to one to
avoid nested oversubscription; kernel reuse is protocol/version keyed. Compared
arrays are NDI, ODI, IsoVF, RMSE, NRMSE and the validity mask. Compressed files
can differ while decoded voxels agree. Historical load/cache/environment were
not controlled for causal speed attribution.

MK-Curve also retains extreme synthetic-curve comparison failures. Parameter
agreement must not become an unconditional all-curve equivalence or valid-fit
claim. See [implementation provenance](../architecture/IMPLEMENTATION_PROVENANCE.md)
and [numerical limits](WORKFLOW_GENERALIZATION_20261017.md).

---

## GPU Is Not A Speed Guarantee

PNL calls the official Python/TensorFlow CNN and ANTs; it is not a rewrite of the
whole PNLpipeline. Same-input CPU took **78.961 s**, default Auto GPU **84.437 s**
and explicit CUDA repeat **79.775 s**. Auto was about **6.94% slower** in this
wall-time pair. Startup/JIT, registration, hashing and b0 preparation can dominate.
The historical **346.70 s** CPU record has incomplete environment metadata and
cannot support a fourfold GPU acceleration claim.

SynthStrip's 1.50x ratio is a single same-input device measurement; Dice is
CPU/GPU agreement, not accuracy against expert masks. Real CUDA eddy execution
is recorded, but no matched CPU timing exists; roughly 719 s measures complete
preprocessing, not eddy alone. Failed/stopped runs are not successful baselines.
See [GPU evidence](GPU_POLICY_20261013.md).

---

## Metrics And Reproduction Limits

Recorded metrics include scoped wall time, ratios, time reduction, array/byte/
geometry agreement, device-mask Dice and differing voxels, and WMA retained-cache
bytes/hits/misses. Whole-process RSS, peak VRAM, energy and throughput do not have
a uniform paired original-versus-optimized measurement. Integrity agreement is
not anatomical or clinical accuracy.

The initial evidence review reran the WMA-cache, diffusion-I/O, scalar-cache and
MK-Curve Python suites: **36 tests passed**. The subsequent implementation changes
also passed the full regression reported above. Unit testing is implementation
regression, not a scientific timing/accuracy trial. The CSV/JSON retain unrounded times, comparison
categories, source report paths/hashes and limitations, without imaging data.
Original evidence lives under ignored local `ignore/validation/`; a GitHub reader
can inspect the saved numerical summary, not independently reproduce the local
benchmark from the summary alone.

Primary local records are `wma_cache_benchmark_20261017/acceptance.json`,
`wma_cache_memory_20261017/acceptance.json`,
`ddsurfer_sync_20261013/real-postprocess-100307/parity.json`, the I/O/refit/cache
records in `pipeline_qc_20261015/`, and the device comparison records in
`pnl_gpu_20261013/`. Exact paths and SHA256 values are in the JSON.
The new original-author comparisons are `three_subjects.json`, `full_inputs.json`,
`upstream_verification.json` and `optimizer_shifted_300.json` under
`wma_author_bulk_20261020/`; the nonimproving control remains
`optimizer_parity_300.json`.

Next benchmarks should fix inputs, parameters, source versions, thread budgets,
devices and cache state; repeat both implementations on multiple independent
subjects while recording wall time, RSS/VRAM, output error and failures. Highest
priorities are full WMA cache on/off, paired NODDI thread counts, complete FW
I/O comparison and the author MK-Curve runtime. Linux evidence does not certify
native Windows/macOS scientific performance.

**Original-author manuscript claim:** with identical inputs and parameters,
equivalent bulk geometry copying accelerated the unmodified author's
attribute-free WMA length-filter stage by 53.92-69.26x on three real-subject
50,000-streamline subsets. Single paired full-atlas and UKF measurements were
54.06x and 54.19x. All output coordinate/topology bytes, fixed-seed samples and
the controlled author-optimizer comparison matched. This optimizes computation,
not the scientific estimator; it is not a complete-WMA or accuracy improvement.

**Historical-stage manuscript claim:** selected real-input stage measurements showed about
2.96x for registration-input caching, 3.80x for shared surface mapping and 2.18x
for sequential DWI decompression, with corresponding output-consistency checks.
These are not universal end-to-end, accuracy or cross-platform improvements.
Shared surface mapping must be attributed to DDSurfer upstream.

The new work can separately be reported as a three-subject, paired **10.05-11.44x**
reduction in full six-map regional-export wall time with byte-identical CSV, and
**9.46%-9.97%** lower complete 64-voxel MK-Curve chunk time with exactly equal
compared coefficient/curve/parameter arrays and masks. The latter is not measured
whole-brain MK-Curve or complete-plugin acceleration.
