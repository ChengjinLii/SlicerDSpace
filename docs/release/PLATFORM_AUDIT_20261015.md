<div align="center">

# Platform And Runtime Audit

**2026-10-15 · Evidence before certification**

[Project](../../README.md) | [中文平台表](../setup/SUPPORT_MATRIX.zh-CN.md) | [Platforms](../setup/SUPPORT_MATRIX.md) | [Timings](MODULE_RUNTIMES_20261015.md)

</div>

---

## Status

**Not every component/result is certified correct, and Windows/macOS scientific
execution remains unverified.** This audit starts from `1f457c4` and tests the
subsequent working-tree fixes. It does not open the private repository or restart
the user's live Slicer/MRI Agent. Host evidence is retained under
`ignore/validation/platform_audit_20261015/`.

The configured baseline suite passes 940 tests (939 passed, one skipped).
An initial attempt used the CMake tool environment's Python, which lacked imaging
dependencies; that failed invocation is retained, not counted as a pass.

---

## Fixes

| Finding | Correction | Evidence boundary |
| --- | --- | --- |
| WSL installed CPU-only torch regardless of GPU | Device Auto/CPU/CUDA plan, pinned official CUDA/CPU wheel, actual allocation probe, isolated device-specific FSL prefixes | Plan/mock contracts; no real Windows installation here |
| WSL preprocessing bypassed strict eddy policy or interpreted a PE bridge as Python | Owned bridge config identifies actual Linux MRtrix script/Python; same policy runs through a dedicated Python bridge; missing/mixed bridges fail early | Source/argument tests; Linux real route retested separately |
| Reverse-PE bridge list missed commands | Add dwiextract/mrcat/Python and conditional CUDA eddy bridges | Installer contract and PowerShell plan |
| WSL discarded caller GPU visibility | Forward only CUDA_VISIBLE_DEVICES as an env argument, not Windows PATH/PYTHONHOME | C# compilation/source contract, not real cancellation acceptance |
| Legacy DDSeg hardcoded Linux executable names | Resolve .exe and macOS app Contents/MacOS layouts | Filesystem/argv tests, not host-specific science |
| External Python/CLI library setup was Linux-specific | Strip Slicer dylib paths for external Python; choose native PATH/DYLD/LD variable for CLI libraries | Environment tests |
| SAF POSIX quoting was passed to Windows cmd.exe | Decode quoted command to argv and move PATH prefix to env; reject shell operators; no cmd shell | Windows-mode argument tests; scientific kernels unchanged |
| macOS TensorFlow Metal could be labeled CUDA | PNL macOS uses explicitly recorded CPU; CUDA requests fail; unvalidated Metal is not auto-enabled | Device tests, not a Metal port |

Fresh Windows configs from the explicit full WSL installer use MRtrix masking;
existing user defaults and supplied masks are preserved. PNL remains the Linux
default and is not silently replaced after errors. FSL license acceptance is
now explicit before actual Windows/WSL installation; plan mode changes no backend.

---

## Scientific Limits

- WMQL on 100307 has AF counts 1/1 and CST counts 11/14. Rule execution/source checks pass, but AF is **PARTIAL**, not reliable quantitative bundle extraction.
- Historical WMA 100307 coverage fails the current contract. The separate 149741 output passes scoped decoded-product checks; this does not repair/certify the old subject output.
- Masks, cortical surfaces and bundle classification still require expert anatomical review. Numerical agreement/finite coordinates do not establish anatomical accuracy.
- DKI/MK-Curve have real small-ROI fitting evidence, not full-brain performance or every acquisition validation.
- Windows/WSL process-tree cancellation, macOS MPS/Metal acceleration and full native Windows/macOS scene/scientific acceptance remain open.
- Full SDK/CTest/CPack and clean-install acceptance on all three systems are not inferred from resource selection or Python tests.

See [bundle QC](BUNDLE_BACKENDS_20261013.md), [GPU evidence](GPU_POLICY_20261013.md),
and the [platform matrix](../setup/SUPPORT_MATRIX.md).

---

## Timing Interpretation

The traceable [32-operation inventory](MODULE_RUNTIMES_20261013.md) retains
88 historical/new records and excludes failed/cache-only operations from
representative timings. PNL is about 79 s CPU and 80-104 s GPU on recorded HCP
input; SynthStrip is about 14 s CPU and 7-9 s GPU on the smaller clinical input.
The prior CUDA eddy **whole preprocessing** route is 719.48 s, not eddy-only time.
FW (21.5 min), NODDI (29.7 min) and single-thread WMA (49.7 min) are different
voxelwise/registration workloads; high duration alone is not proof of a defect.
Historical PNL 346.7 s has an unresolved old CNN-stage slowdown, not a validated
fourfold GPU speedup. DKI/MK-Curve ROI times must not be extrapolated.

This audit does not rerun every long scientific model. Its fresh CUDA eddy
acceptance uses unchanged clinical input/parameters in a separate output
directory; concurrent GPU load is recorded and is not controlled benchmarking.
The fresh route completes in **684.599 s**, versus the historical 719.476 s.
All 12 automatic integrity checks pass: pipeline/device/no-retry, native
shape/world grid, finite/nonempty DWI, gradient count/finite/unit norms, mask grid
and unchanged input hashes. This is not a GPU accuracy-equivalence experiment.
The [updated inventory](MODULE_RUNTIMES_20261015.md) has 32 operations and 89
records, selecting this current-policy rerun by protocol recency rather than
choosing the minimum duration. The October 13 inventory remains untouched.
CSV/JSON numerical files are beside the new report and retain source record hashes.

---

## Current Verification

| Check | Result | Not established |
| --- | --- | --- |
| Full updated Python suite | **961 tests: 960 passed, one skipped**, 46.8 s | Whole-platform scientific accuracy |
| Scoped bridge/device/SAF tests | 87 initial scoped checks, then 48 SAF/bridge/installer checks pass | Actual Windows/WSL execution |
| PowerShell plan-only execution | Pass on Linux PowerShell, no WSL contacted | Windows install completion or driver compatibility |
| C# bridge compilation | Pass with installed .NET/PowerShell | Real Windows process-tree cancellation |
| Linux fresh CUDA preprocessing | **684.599 s; 12/12 integrity checks pass** | Isolated eddy speed or accuracy equivalence |
| Real isolated Slicer extension/compact UI | Both PASS (21.1 s / 16.5 s); user/revision stores private and writable | All algorithms rerun through GUI |
| Packaging/metadata/docs | Resource selector/archives and local metadata/link tests pass | Official SDK/CPack publication |

The first portable-install UI invocation emitted revision-settings write
warnings. It is retained separately. Final `gui_isolated/` acceptance uses the
existing private-runtime/settings harness and verifies both writable stores;
it is the selected UI evidence, not the warning-bearing preliminary invocation.
Existing live application sessions were not restarted or replaced.

Reproduction and receipts are in the ignored campaign directory:

- `baseline_configured_tests.log`, `final_all_tests.log`.
- `scoped_tests.log`, `saf_bridge_tests.log`, `windows_plan/install-plan.json`, `bridge_compile.log`.
- `eddy_cuda_fresh/acceptance.json`, adjacent manifest/QC and `concurrent_gpu_load.csv`.
- `gui_isolated/gui_acceptance.json`, isolated Slicer logs and settings-isolation receipts.
- `timings/module_runtimes.{csv,json}`; matching dated numerical files are retained in `docs/release/benchmarks/`.

This audit supports continuing Linux research use with explicit QC boundaries,
not an assertion that every historical output or Windows/macOS component is ready.
