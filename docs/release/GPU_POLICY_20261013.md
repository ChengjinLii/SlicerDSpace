<div align="center">

# GPU Policy Verification

[Project](../../README.md) | [Documentation](../README.md) | [GPU Policy](../setup/GPU_EXECUTION.md) | [GPU 策略](../setup/GPU_EXECUTION.zh-CN.md)

</div>

---

## Scope

This working-tree campaign audits active inference defaults, runtime selection,
explicit CPU settings and hidden CUDA-error retries. It is not a new accuracy
certification or a rerun of every scientific model on every platform.
Scientific weights and the pinned DDSurfer snapshot are unchanged.

Source evidence is retained under `ignore/validation/pnl_gpu_20261013/`.
No raw/derived subject image is added to the public runtime package.

---

## Findings And Changes

| Finding | Change |
| --- | --- |
| PNL unconditionally set CUDA visibility to -1 | Default GPU-preferred Auto; explicit CPU/CUDA; selected device and runtime recorded |
| Official PNL startup references undefined DEVICE_ID_LIST | Launcher repairs only this startup block in memory, preserving caller GPU visibility |
| SynthStrip GPU flag omitted | Resolve in its own Python and supply -g on GPU; suppress old fixed physical-GPU-0 assignment in memory |
| FreeSurfer's bundled PyTorch 2.0/CUDA 11.7 stalls on H100 | Preserve failed/stopped test; block this unvalidated combination early; provide optional Advanced SynthStrip Python path |
| DDSeg direct API and CLI default CPU | Defaults Auto; resolve inside inference; record executing device |
| Surface facade defaults CPU / probes caller environment | Defaults Auto; resolve in selected surface Python; supply an explicitly generated native mask to avoid the standalone vendor CPU-only helper |
| Standalone DDParcel ignores GUI CPU selection | Device now forwarded; explicit CUDA without CUDA is an error |
| TractCloud Auto may resolve in Slicer's Python instead of its own | Resolve in the actual TractCloud interpreter; forward GUI selection; refuse CUDA-error CPU inference retry |
| PyTorch probe errors look like a CPU fallback | Failed probes produce unavailable/error states, not a silently resolved CPU |
| GUI device choices not all persisted | Shared JSON and Slicer settings preserve explicit choices and propagate single/batch flags |
| MRtrix upstream retries CPU after failed CUDA eddy | Wrapper disables that retry without changing eddy scientific parameters; records device, launcher/source hashes and arguments |
| CPU --nthr=4 rejected by real CUDA eddy | Launcher uses --nthr=1 only on CUDA; requested/effective arguments retained; CPU thread choice unchanged |

Tensor-to-NumPy conversion, CPU checkpoint validation, and current CPU-only
numerical/registration backends remain intact. The complete route inventory is
in [GPU policy](../setup/GPU_EXECUTION.md).

---

## Real Measurements

These are fresh mask-generation acceptances including hashing, b0 preparation,
external Python startup, scientific processing and automatic integrity QC.
Docker launch, installation and GUI startup are excluded. Each result also has
a native binary mask, provenance and an untouched supplied-mask check.

| Route / input | Runtime | Result |
| --- | ---: | --- |
| PNL CPU, HCP 100307, 145x174x145x288 | 78.96 s | Passed finite/binary/native-grid QC |
| PNL Auto -> H100, same input | 84.44 s | Real GPU CNN; passed integrity |
| PNL explicit CUDA repeat, same input | 79.77 s | Real GPU CNN; passed integrity |
| SynthStrip CPU, sub-dicom, 104x104x60x31, PyTorch 2.4.1/CUDA 12.1 | 14.27 s | Passed integrity |
| SynthStrip Auto -> H100, same input/runtime/script/weights | 9.49 s | Passed integrity, retained caller CUDA_VISIBLE_DEVICES=1 |
| TractCloud, HCP 100307, 50k existing CSD/ACT tracks, seed 0 | 18.50 s | CUDA; 39 readable/nonempty bundles; 21,432 assigned tracks |
| MRtrix/FSL full preprocessing, sub-dicom 104x104x60x31, reverse PE b0 | 719.48 s | Real CUDA eddy; 12 automatic integrity checks passed; includes CPU denoise/Gibbs/topup and final mask |

PNL CPU/GPU mask agreement: Dice 0.992779 and 0.993438, with 10,073 and
9,154 differing voxels. This is agreement between independently processed
repeats, including registration, not an isolated CNN equivalence test.
SynthStrip CPU/GPU agreement: Dice 0.999993918; two differing voxels.
All anatomical review remains **pending**; agreement is not ground-truth accuracy.

The historical PNL CPU record is 346.70 s. It is preserved but cannot be used
to claim a fourfold device speedup: this new paired CPU run was already 78.96 s.
The PNL GPU log includes H100 PTX/JIT warnings and startup costs. GPU preference
is a device policy, not a universal end-to-end speed guarantee.

The original FreeSurfer GPU attempt was stopped after 949.43 s without a mask
and is recorded as **failed**, not successful performance evidence. Its log
warned that the build lacked native sm_90 support. The modern isolated venv
reuses existing PyTorch 2.4.1/CUDA 12.1 and installs only surfa/xxhash there;
neither system FreeSurfer nor the base model environment was upgraded.

Official `fsl-eddy-cuda=2602.0=h1a432fe_1`, CPU eddy and topup were installed
in `/data/chengjin/software/slicerdsurfer-fsl-gpu`, separate from the existing
CPU FSL prefix. No driver/CUDA Toolkit upgrade or MRI Agent configuration change
was made. The initial real run stopped because CUDA eddy refuses `--nthr=4`;
its 365.18 s failed acceptance remains under `eddy_cuda_real/`. The corrected
fresh run under `eddy_cuda_fixed/` uses `--nthr=1` automatically and passes.
The same data, AP direction, 0.039655 s readout, reverse b0 and linear SLM were
used; scientific parameters were not retuned to obtain a successful test.
`nvidia-smi` captured the actual eddy process using GPU memory. The 719.48 s value
is the **whole preprocessing route**, not eddy-only time or a CPU/GPU speedup.

---

## Reproduce And Inspect

Runtime inventory follow-up separates two confirmed execution defects from a
non-reproduced historical slowdown. The stopped old SynthStrip GPU environment
is rejected early (1.58 s acceptance), rather than spending another 949 s without
a mask. A compatible GPU environment produces the same-input mask in 9.49 s.
The CUDA eddy thread-option defect is corrected only on CUDA; the full route
then completes in 719.48 s. Neither failed duration is a successful benchmark.

PNL's old 346.70 s record contains rounded upstream phases: about 31.8 s
preprocessing, 283.8 s model processing and 322.8 s upstream total. The new
CPU reference is about 37.8 / 15.0 / 60.0 s for those same phase labels.
Thus the historical excess lies mainly in model execution, not ANTs alignment
or processing all 288 DWI volumes individually. Its complete thread/runtime/load
metadata was not retained, so a unique cause is **not established**. Current GPU
runs also include TensorFlow's H100 PTX/JIT startup; they are not universally
faster than CPU. No model, weights, threshold or output resolution is changed
merely to reduce the displayed time.

Fresh mask manifests now retain non-overlapping `phase_seconds` (preflight/hash,
b0 preparation, external process and native QC) plus the actual thread-related
environment variables. These phases exclude some setup/publication overhead,
so they are not presented as a complete wall-time sum. New instrumented reruns
are separate ledger entries, not replacements chosen for being the fastest.

| Instrumented real repeat | Total | Preflight/hash | b0 preparation | External process | Native QC |
| --- | ---: | ---: | ---: | ---: | ---: |
| PNL Auto CUDA, HCP 100307 | 104.326 s | 13.927 s | 14.669 s | 75.656 s | 0.029 s |
| SynthStrip Auto CUDA, sub-dicom | 7.007 s | 0.247 s | 0.107 s | 6.637 s | 0.011 s |

Both fresh results pass finite/binary/nonempty/native-grid checks and leave
supplied inputs unchanged. Independent same-input comparisons also pass:
PNL CPU/repeat Dice 0.995407 (6,406 differing voxels, including independently
repeated ANTs registration); SynthStrip CPU/repeat Dice 0.999996959 (one voxel).
These are agreement checks, not ground-truth anatomical certification.
The 104 s PNL repeat includes about 29 s outside the external model process
for hashing and b0 preparation; neither phase is GPU CNN work. Concurrent
host tests/load are not controlled for a statistical speed comparison.

Evidence: `pnl_phase_gpu/`, `synthstrip_phase_gpu/`,
`runtime_update/pnl_phase_comparison.json` and
`runtime_update/synthstrip_phase_comparison.json` under the campaign directory.
The timing collector now inventories 32 operations and 88 records, preserving
all these repeats and the previous failures. Runtime/resource regression adds
8 timing tests and one required-resource test; the final full suite is
**940 tests: 937 passed, 3 skipped** (`runtime_update/tests.log`). CMake/Python
resource selection and staged-archive checks pass; this still does not establish
an official Slicer SDK/CPack build.

---

`scripts/compare_brain_mask_devices.py` rebuilds the comparison from actual
acceptance JSON and adjacent native masks. Numerical records:

- `comparison.json`: PNL repeated CPU/GPU timings, input hashes, geometry and Dice.
- `synthstrip-comparison.json`: same-input/runtime SynthStrip CPU/GPU comparison.
- `tractcloud/tractcloud_manifest.json`, `tractcloud_qc.json`, `tractcloud_device.json`: actual CUDA receipt/products.
- `synthstrip_gpu/synthstrip_acceptance.json`: failed old-runtime attempt; preserved separately.
- `eddy_device_discovery.json`: real installed MRtrix/FSL CPU backend discovery, **help-only**, not DWI correction.
- `eddy_cuda_fixed/acceptance.json`, adjacent QC/manifest and `eddy_cuda_active_gpu.csv`: actual GPU correction and unchanged-input/integrity checks.
- `gui-final/brain_mask_select.json`, `brain_mask_restore.json`: isolated Slicer Advanced controls, JSON/CLI mapping and restart persistence.

The GPU policy tests cover visible-device preservation, missing GPUs, explicit
CPU, old-runtime rejection, probe failures, TractCloud CPU-retry refusal and
eddy selection and CUDA-binary/cache changes. Before the runtime-inventory
follow-up, the full suite contained 931 tests: **926 passed, 5 skipped**
(`test-all-final.log`). Scoped preprocessing
tests pass 48 checks; distribution tests pass 9 with one SDK-dependent skip.
Metadata and active-document audits also pass. Skips are not successful SDK
build or cross-platform scientific evidence.

---

## Managed Installation Follow-up

`shared/managed_runtimes.py` and the Slicer setup action now provision only selected
MRtrix/FSL profiles, outside Slicer Python, and save paths after verification.
Model setup uses the default user directory and product-specific profiles.
FSL approval is explicit; installing/downloaded software is not a scientific QC.
The [setup guide](../setup/MANAGED_SETUP.md) records current coverage and limits.

Actual isolated evidence retained in the same campaign directory:

| Check | Outcome / evidence |
| --- | --- |
| No-Conda bootstrap | Official pinned Miniforge downloaded, SHA256 verified and installed under `bootstrap_only/`; reuse also succeeds |
| Fresh MRtrix + CUDA FSL setup | `managed_runtime_result.json`: completed, verified commands/libraries/versions; explicit lockfiles and executable hashes retained |
| Runtime reuse | `managed_runtime_reuse.json`: verified reuse without package installation |
| Real Slicer controls | `gui-managed-final/`: 127 selection checks and 58 restart/persistence checks pass, including license gate and automatic MRtrix paths |
| Setup process-tree cancellation | `setup-cancellation/setup_tree/setup_tree.json`: cancelled, TERM-resistant child stopped |
| Staged package | Cancellation acceptance also builds/audits an isolated source-staged package; this is not official SDK/CPack provenance |

The managed CUDA eddy and MRtrix tckgen executables are SHA256-identical to the
corresponding local verified executables. The managed environment's help/discovery
path is additionally checked; the complete real DWI run above used the separate
local FSL prefix, not a new claim of full computation in every managed environment.
The original install-channel failure, a cancelled slow dependency download and
the initial Qt confirmation-constructor failure are preserved separately from
the corrected final evidence. Clang packages are kept on the tested 22.1 generation
to avoid downloading mixed LLVM generations; MRtrix source/binaries are unchanged.

Existing live Slicer and MRI Agent sessions were not restarted. Settings checks
use isolated Slicer homes/configuration. Neither arbitrary existing Conda prefixes
nor system GPU drivers/shell files are modified by managed setup.

---

## Remaining Boundaries

CUDA eddy is now installed and one real Linux route is verified. This does not
establish acquisition-independent accuracy, numerical CPU/GPU equivalence or
whole-platform coverage. The original CPU-only help/discovery evidence remains
separate. Full Linux/Windows/macOS
scientific acceptance and manual mask/bundle boundary review are not inferred
from these tests. CPU-only DIPY/AMICO/SlicerDMRI/ANTs/MRtrix geometry and numerical
implementations are documented, not mislabeled as disabled GPU routes.

PNL and SynthStrip still require compatible external environments. An explicit
GPU or incompatible-GPU error must be fixed by configuring that environment
or choosing CPU, not hidden by changing models or falsifying QC.
