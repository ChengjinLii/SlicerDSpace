<div align="center">

# Bundle Backend Verification

**13 October 2026 · Source review, real products and repeatability**

[Project](../../README.md) | [Documentation](../README.md) | [Runtimes](MODULE_RUNTIMES_20261013.md) | [中文](BUNDLE_BACKENDS_20261013.zh-CN.md)

</div>

Confirmed adapter defects have been corrected. **Not every historical result
passes QC.** Geometry, source membership, correct query execution and anatomical
accuracy are different claims; expert anatomical review remains pending.

---

## Real Results

| Route / input | Actual output | Automatic checks | Interpretation |
| --- | --- | --- | --- |
| WMQL, 100307, 50,000 CSD/ACT tracks, fresh rerun | AF.left 1; AF.right 1; CST.left 11; CST.right 14 | 27/27 match source within 0.001 mm; 27/27 independently satisfy endpoint-label rules; identical previous assignments | **PARTIAL scientifically**: one AF track per side is inadequate for reliable bundle-level interpretation. Shipped queries are DDParcel-adapted endpoint candidates, not canonical anatomical ground truth. |
| TractCloud, same input, two seed-0 runs | **39 nonempty bundles, 21,432 assigned tracks**, both runs | Finite/positive geometry, source membership, disjoint classes; **100% identical emitted track/label sets** on the same hardware/configuration | Anatomical review pending; absent classes and excluded Other tracks need separate interpretation. |
| WMA, 149741, 100,000 UKF tracks, existing rigid run | **74 readable/nonempty bundles, 40,338 assigned tracks** | Current contract, full geometry, source membership and native Slicer loading pass | Existing official run audited, **not a fresh full WMA computation**. |
| WMA, 100307, 1,000,000 tracks, `qc_verified_20260916` | 74 readable files, only **45 nonempty**, 51,674 assigned tracks | Geometry/source membership pass; **population contract fails** | Retain failure. Inspect coverage, track lengths and atlas registration; do not use as a reliable whole-atlas result. |
| WMA, 100307, legacy `linux_acceptance_20260813_full` | 74 readable files, only **34 nonempty** | Old completed status fails the present population contract | Legacy green status is not accepted as current evidence. |

WMA's minimum 73 readable / 55 nonempty outputs is a conservative **local output
contract**, not an author-prescribed anatomical-accuracy threshold. WMA/WMQL
queries may overlap; emitted TractCloud labels must be disjoint.

---

## Source-Based Corrections

| Adapter | Original reference | Correction |
| --- | --- | --- |
| WMA | [SlicerDMRI WMA](https://github.com/SlicerDMRI/whitematteranalysis), `4532b911386d2d1bc7ebba63fdd13e65b1660623` | Author shell skips existing stage directories. Fresh staging prevents old registration/clusters becoming new results. Publish only contract-valid products; archive prior outputs/records and retain failed evidence. Record explicit transform metadata. |
| WMQL | [Tract Querier](https://github.com/demianw/tract_querier), `5c69c594d489859e08485110678dca7f6f4cba40` | Full finite VTK/VTP decoding replaces header-only checks; verify subject/requested query names; isolate reruns; preserve old products; validate finite thresholds; flag single-track candidates. |
| TractCloud | [Author implementation](https://github.com/SlicerDMRI/TractCloud), local snapshot `94de6275d07d7b5eeb50e4cd4d6e85fde29d5fb0` | Fresh directories prevent stale classes. Preserve virtualenv executable identity; isolate external Python from Slicer overrides. Fix/record seeds and model-file SHA256; resume rejects old adapters and changed seeds/resources/settings. |
| TractCloud bootstrap | [Author pipeline](https://github.com/SlicerDMRI/TractCloud/blob/main/src/tractcloud/pipeline.py) | Supply the missing logging global in CUDA-error/CPU fallback, then run the official CLI. No external source, architecture, inference, labels or weights are rewritten. Preserve the actual bootstrap command. |
| SlicerDMRI discovery | [Slicer factory API](https://apidocs.slicer.org/main/classqSlicerAbstractModuleFactoryManager.html) | Search active additional module paths, not only the installation tree. Verified with fresh full-volume WLS fitting and six scalar conversions. |

These are **external author-code adapters**, not local algorithm rewrites. No
thresholds were loosened to make QC green, no endpoint dilation was introduced,
and no scientific output was fabricated.

Result objects also propagate their actual QC status to orchestration: a zero
exit with missing/invalid TractCloud products no longer becomes a completed task.

---

## Repeatability and Slicer

Unseeded TractCloud executions agreed on only **63.19% of the emitted-track
union**. This denominator is not the entire input and not anatomical accuracy.
Fixing Python/NumPy/PyTorch seeds gives identical 21,432 assignments in two real
seed-0 runs. Cross-device/library bitwise equivalence and every optional branch
remain unverified; the CUDA-failure logger bootstrap has a unit regression, not
a claim that incompatible-GPU recovery was exercised on real hardware.

Isolated Slicer 5.10 / SlicerDMRI loads **117 real files** (4 WMQL, 39 seeded
TractCloud, 74 WMA) as FiberBundle nodes. TRK world-coordinate/float32 conversion
is checked to 0.001 mm (maximum delta below 0.00001 mm), not claimed bit-exact;
VTP point arrays compare exactly. Private settings/runtime/X displays leave the
user's Slicer and MRI Agent untouched. Fresh full-volume native DTI fitting and
scalar conversion took **135.999 s**, separately from startup and ROI statistics.

The full Python campaign records **902 tests: 899 passed, 3 skipped**. Synthetic
fixtures validate engineering branches only, never scientific performance.

---

## Evidence

Root: `ignore/validation/bundles_runtime_20261013/`.

| File | Scope |
| --- | --- |
| `wmql_endpoint_verified_audit.json` | All emitted tracks, independent endpoint rules and repeat identity |
| `tractcloud_seed0_repeat_audit.json` | Source membership, disjoint classes and same-seed repeatability |
| `wma_149741_previous.json` | All 74 existing WMA bundles |
| `wma_100307_failed_audit.json` | Geometrically valid but under-populated failure |
| `native_cli_fixed/gui_acceptance.json` | Native loading and fresh full-volume DTI |
| `native_seeded/gui_acceptance.json` | Latest staged package and seeded products |
| `unittest_completion.log` | Final full regression campaign |
| `timings/module_runtimes.json` | Successful/failed/reused timing ledger, record hashes |

```bash
python scripts/audit_bundle_products.py --manifest /path/to/real/manifest.json --report /path/to/audit.json
python scripts/revalidate_bundle_backend.py --manifest /path/to/previous/manifest.json --output-dir /new/output
python scripts/collect_module_runtimes.py --output-dir /path/to/timing-report
```

Old scientific outputs remain unchanged; new products live in the evidence
root. Existing unseeded TractCloud results are not relabelled verified. Expert
review, failed WMA coverage/registration investigation and full-brain DKI/MK-Curve
timing remain explicit follow-up work.
