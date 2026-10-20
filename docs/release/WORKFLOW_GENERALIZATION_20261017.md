<div align="center">

# Workflow Generalization Checks

[Documentation](../README.md) | [Previous Audit](QC_FOLLOWUP_20261016.md) | [中文](WORKFLOW_GENERALIZATION_20261017.zh-CN.md)

</div>

This is an evidence record, not an all-QC-passed or clinical-readiness claim.
Historical failed runs remain immutable. Repository visibility is unchanged.

---

## Root Causes And Corrections

| Route | Finding | Correction | Remaining boundary |
| --- | --- | --- | --- |
| WMQL | The old CST example requires brainstem termination. A subsequent full-author preset also changed AF to regional crossing predicates, losing endpoint candidates. | Default to the named `ddparcel_act` combination: retain the original DDParcel AF endpoint expression and import the pinned author CST unchanged. Keep full `author` and `published_endpoints` presets. Record recursive hashes and immutable snapshots. | This is not an unchanged official AF/CST protocol or recovery of either historical failure. Counts do not prove anatomy; no subject-specific fallback or lowered sampling threshold. |
| WMA | Passing five major tracts did not establish suitability of all 74 atlas tracts. Five small tracts remained sparse after author outlier removal. | Add per-tract sampling eligibility, explicit exclusions and warnings. Global automatic QC now also requires every returned tract to pass sampling; cached acceptance rechecks decoded tract counts. | Do not disable author outlier rejection, duplicate fibers or infer statistical power from a minimum count. These five tracts are not rescued. |
| MK-Curve | One invalid RK/AK value excluded otherwise acceptable MK/FA at the same voxel. | Port version 2 exports individual parameter-validity masks; regional statistics use the matching metric mask. Keep the original joint validity mask and unconstrained author fit unchanged. | Genuine out-of-range results remain excluded, not filled or clipped into validity. |

Current verification: **1098 tests passed**, including a real DDSeg world-space
fixture; separate real-fixture tests also passed on 100206, 149741 and 877168.
This is implementation evidence, not certification of all scientific outputs.
The v11 Linux build passed 132 CTest suites and the 470-file CPack audit. Its
actual archive passed four isolated Slicer checks: Extension Manager install,
WMQL controls, compact EN/ZH UI and full WMA bundle loading. Evidence:
`ignore/validation/sdk_current_20261017_v11/sdk_build_report.json` and
`ignore/validation/sdk_package_gui_20261017_v8/acceptance.json`.

The default imports `freesurfer_queries.qry` at pinned upstream commit
`5c69c594d489859e08485110678dca7f6f4cba40`, then overrides only AF with the
existing DDParcel endpoint-candidate expression. An AST test verifies that AF
expression is unchanged from `AF_CST.qry` and CST is not overridden. This is
explicit compatibility adaptation, not certification of AF anatomy. Advanced
GUI, single-subject CLI and batch CLI forward the same three preset choices:
`ddparcel_act`, `author`, `published_endpoints`. No failed-run fallback occurs.

References: [author queries](https://github.com/demianw/tract_querier/blob/5c69c594d489859e08485110678dca7f6f4cba40/tract_querier/data/freesurfer_queries.qry),
[distinct endpoint example](https://tract-querier.readthedocs.io/en/latest/example_script.html),
[ACT tissue priors](https://mrtrix.readthedocs.io/en/latest/quantitative_structural_connectivity/act.html).

---

## Actual Read-Only And Rerun Evidence

The 100307 ACT-v3 source tractogram was not changed. The earlier full-author WMQL execution
took 55.02 s: AF left/right 70/28, CST left/right 154/311, minimum 20 unchanged.
This is a new named protocol, not an endpoint-equivalence experiment.

WMA intermediate-stage conservation checks passed for all five sparse tracts:
inverse transformation, hemisphere separation and author cluster-to-tract
assembly did not lose streamlines. EC bilateral candidates went from 75 before
outlier rejection to 15 afterwards, then left/right 8/7. Intra-CBLM-PaT
bilateral candidates went from 697 to 45, then left/right 40/5. These results
support an atlas/input sampling-or-matching limitation rather than a conversion
or append-file bug; they do not establish the reason for every rejected fiber.
Further tractography-domain/registration validation is still required.

MK-Curve raw maps were audited against the unchanged brain mask and coefficient
ordering. All coefficients, curves and residuals were finite. The union of
range failures exactly reproduced the recorded 4622 joint exclusions:

| Parameter | Own invalid voxels | Otherwise valid voxels lost through joint masking |
| --- | ---: | ---: |
| FA | 0 | 4622 |
| MD | 81 | 4541 |
| AD | 643 | 3979 |
| RD | 24 | 4598 |
| MK | 683 | 3939 |
| AK | 591 | 4031 |
| RK | 3508 | 1114 |

Failures overlap; the rows must not be summed. RK includes 219 negative and
3289 above-three values. Bounds are unchanged. Per-metric coverage does not
establish fit accuracy, repeatability or suitability in CSF/partial-volume
voxels. No raw map or old QC record was modified by these audits.

Local evidence:

- `ignore/validation/wmql_author_default_20261017/`
- `ignore/validation/scientific_roots_20261017/wma_sampling.json`
- `ignore/validation/scientific_roots_20261017/mkcurve_validity.json`
- `ignore/validation/gui_wmql_preset_20261017_v3/`: real Qt/MRML preset binding passed.

---

## Full-Brain MK-Curve Cohort

The same port-v2 protocol was fitted independently on three additional real
acquisitions: unchanged masks, b <= 2500 complete shells, correction threshold
0.5, batched WLLS, 16 workers. No parameter clipping or post-fit smoothing was
introduced. Fitting completed for every subject:

| Subject | Brain voxels | Joint-invalid voxels | MK-invalid voxels | Fit and audit time (s) |
| --- | ---: | ---: | ---: | ---: |
| 100206 | 936256 | 7353 | 505 | 1221.18 |
| 149741 | 825145 | 5828 | 891 | 1045.96 |
| 877168 | 699932 | 6367 | 565 | 886.92 |

Each original joint-mask/bounds audit passed. An additional read-only audit
checks all ten persisted per-parameter masks: native grid, binary values, zeros
outside the brain, exact agreement with recomputed validity, and agreement
with recorded coverage. Synthetic corruption tests reject a wrong, absent,
nonbinary, out-of-brain or incorrectly counted mask. A valid MK estimate is no
longer discarded solely because RK failed, but genuine MK failures remain
invalid. **None of these fits has all brain voxels valid.**

Evidence: `ignore/validation/mkcurve_cohort_20261017/acceptance.json` and each
subject's `independent_saved_masks_v2.json`. This is separate from the core
workflow cohort and is not an anatomical or clinical acceptance.

An additional stratified QR reference refit compared 128 positive-signal
outlier/control voxels per subject (384 total). All final corrected coefficients,
seven scalar maps and author abnormal/unusual/corrected-b0 decisions matched.
Raw synthetic curves did **not** all meet numerical parity: one point each in
149741 and 877168 differed at very large negative kurtosis, with near-zero
directional ADC and a negative diffusion eigenvalue. In the range where both
curves had absolute value <= 5, no comparison failed; maximum absolute error
was 1.56e-9. These sampled differences did not change the correction decisions.
The initial raw-curve parity failure remains retained, not rewritten to pass;
this sample check does not certify all synthetic curves or rescue invalid fits.
Evidence: `mkcurve_outlier_parity_20261017/acceptance.json` and
`mkcurve_curve_stability_20261017/acceptance.json` under `ignore/validation/`.

The WMA input-domain reference is also separate. The pinned author's two-tensor
UKF binary completed a b0 + b=3000 reference in 1830.84 s; subsequent author
ORG registration/classification finished in 16033.89 s. It failed strict all-tract
sampling: right Intra-CBLM-PaT has only two streamlines. A read-only stage audit
found 1524 bilateral initial assignments, 939 after author outlier removal,
then left/right 937/2 with exact transform/split/append conservation. No export
loss was found. Neither UKF execution nor another tracking protocol guarantees
all small tracts. This failed reference is retained, not substituted for a
passed result; its longer runtime is not a controlled cache comparison.
Evidence: `ignore/validation/ukf_domain_20261017/reference_100307_v2/acceptance.json`.

---

## WMA Input-Domain Revalidation

The earlier, separate two-tensor UKF run on 100307 was independently re-decoded
under the current strict contract. Its 277875 source tracks yielded 95755
assigned tracks; **all 74 tracts passed sampling**, minimum 60, with finite
positive geometry and source membership passing. AF was 287/602 and CST
446/520. The five CSD-derived sparse outputs compare as follows:

| Tract | CSD route | Separate UKF route |
| --- | ---: | ---: |
| CR-P left | 5 | 110 |
| EC left | 8 | 169 |
| EC right | 7 | 239 |
| EmC right | 7 | 218 |
| Intra-CBLM-PaT right | 5 | 1249 |

The UKF output used the older Slicer 5.2 author binary with two tensors and one
seed per voxel. It is not the new 5.10/b=3000/five-seed reference above.
Both the source and tracking protocol differ from CSD, so this is evidence of
route dependence, not isolated causal proof or repaired CSD results. After
the independent audit, only this successful UKF result's QC metadata was
revalidated to version 2, archiving previous records; no tract was modified.
`quantification_eligible=false` and `human_review=pending` remain explicit.

Evidence: `ignore/validation/scientific_roots_20261017/wma_ukf_alltract_current.json`
and `wma_ukf_alltract_revalidated.json`. The CSD failures remain unchanged.

---

## Audit And Resource Safeguards

### WMA Registration Performance

The registration atlas contains 1989106 streamlines. The author implementation
repeats the same length filtering and point copying before every iteration.
The native POSIX adapter now offers a bounded, process-local cache for that
deterministic step. It retains at most the filtered atlas and subject, checks
VTK modification times and length arguments, and never caches random sampling,
objectives, transforms or classification. Requested attributes/indices or
different filters bypass the cache. Only the verified upstream filter and
registration-source hashes enable it; other versions run unchanged. Windows
WSL currently keeps the original route without this POSIX shim optimization.
Retained VTK data is additionally limited to one quarter of available RAM,
capped at 4 GiB; without optional memory inspection the conservative budget is
256 MiB. Oversized results are returned normally without being retained.

Each invocation writes a separate `registration_cache_*.json` containing source
hashes, compatibility, hits/misses and measured filter time. Rerun manifests
cannot silently adopt earlier cache reports. `registration_preprocess_cache=False`
in `WMAOrgAtlasConfig` disables the optimization for a diagnostic comparison.
No upstream source, raw tractogram or atlas is edited.

A real full-input benchmark passed:
`ignore/validation/wma_cache_benchmark_20261017/acceptance.json` and
`ignore/validation/wma_cache_memory_20261017/acceptance.json`. With the same
1989106-atlas/277875-subject tracks and three seeds, original preprocessing and
sampling took 533.77 s versus 180.55 s cached (2.96x). Sampled indices, geometry,
registration arrays and random state were bitwise identical; original input
hashes were unchanged. The subsequent memory-budgeted version also matched the
preserved author signatures at all seeds, retaining 3374317568 bytes within
4 GiB (two misses/four hits). It is not a complete classification or anatomy
acceptance. The initial cache snapshot's fresh full WMA registration completed
in 560.87 s with two filter calls/eighteen hits. Its complete registration and
classification took 4664.83 s; all 74 tracts passed strict sampling and the
independent source-geometry audit passed. This snapshot predates the memory
budget, whose numerical parity was tested separately above. Human anatomical
review remains pending. Evidence:
`ignore/validation/wma_cache_full_20261017/acceptance.json`.
An old 6506.94-second WMA timing is a historical reference, not a controlled
paired estimate of the cache's whole-pipeline speedup.

The WMA execution path also now honors `--no-resume` at its inner cache check;
an existing successful output cannot turn an explicitly fresh run into a skip.
Future cohort drivers own their subprocess groups, reap descendants on timeout,
persist the failed attempt, and use unbuffered logs. The already running cohort
is not hot-patched or restarted.

### Existing Verification

- The independent endpoint audit explicitly recognizes `published_endpoints`
  after the default query change. A violated historical endpoint predicate
  cannot silently become not-applicable; author crossing rules are not
  incorrectly certified as endpoint rules.
- Duplicate task records fail future one-pass acceptance, so an embedded
  retry cannot conceal a first failure. The active cohort uses its original
  frozen runtime; no in-flight outputs or protocol settings were changed.
- CLI environments propagate an explicit OMP CPU budget to ITK consumers,
  preserving explicit ITK overrides and CUDA selection. No default cap is
  invented. This does **not** bound the VTK tensor estimator in SlicerDMRI;
  the timing record states this limitation. Eight executions on the same real `48 x 48 x 32 x 288` crop
  produced bitwise-identical tensors with 1/4/8/automatic ITK threads. This
  small-crop check establishes numerical parity, not a whole-brain speedup.
- Timing inventory rows retain the actual subject identifier and no longer
  assume every new subject is 100307 or every WMA input is 100k UKF tracks.

Thread evidence: `ignore/validation/native_dti_thread_20261017_v2/acceptance.json`.
The whole-brain 100307 comparison also produced bitwise-identical tensors:
155.32 s with ITK's environment set to four versus 129.49 s with it unset.
These are not four-core versus unrestricted VTK measurements, and do **not**
demonstrate a speedup or a cap on the tensor estimator. They exclude scalar exports and later workflow tasks. Evidence:
`ignore/validation/native_dti_fullbrain_thread_20261017/acceptance.json`.

Source boundary: [SlicerDMRI tensor CLI](https://github.com/SlicerDMRI/SlicerDMRI/blob/master/Modules/CLI/DWIToDTIEstimation/DWIToDTIEstimation.cxx)
uses the VTK/Teem estimator, not an ITK tensor-fitting filter.

The earlier Linux SDK build passed 131 CTest suites (129 backend suites and two
native Slicer tests). CPack resource auditing passed for 466 files. Its actual
archive was then installed through Extension Manager into a new private
directory; separate Slicer processes passed WMQL-preset binding and compact
EN/ZH UI tests. The first harness omitted a required fixture environment
variable; that failed record is retained and the corrected harness passed.
These checks share installed Slicer binaries/Python dependencies and are not
blank-machine, cross-platform or complete scientific-workflow acceptance.
Evidence: `ignore/validation/sdk_current_20261017_v7/sdk_build_report.json`
and `ignore/validation/sdk_package_gui_20261017_v2/acceptance.json`.

After the ITK/VTK scope correction, the v8 SDK build again passed all 131 CTest
suites and the 466-file CPack audit. Its own archive passed all four isolated
Slicer checks in `ignore/validation/sdk_package_gui_20261017_v5/acceptance.json`:
installation, WMQL controls, compact UI, and bundle loading/QC ownership.
All 74 UKF-derived WMA files (95755 streamlines) loaded with zero coordinate
delta; native loading took 36.34 s, excluding extraction/startup. The failed
CSD result remained excluded, and 40 manually owned nodes survived later QC
failure. The authoritative build record is
`ignore/validation/sdk_current_20261017_v8/sdk_build_report.json`.

---

## Preregistered One-Pass Cohort

`scripts/validate_pipeline_cohort.py` implements a stricter acceptance path:

1. Require distinct real DWI hashes and native-grid masks/gradients before execution.
2. Copy runtime code/resources and the author backend into a frozen run snapshot.
3. Create new subject roots with read-only-source input symlinks and empty outputs.
4. Apply identical CLI arguments to every subject, forcing `--no-resume` and `--no-user-config`.
5. Permit one attempt per subject; blocked, failed, missing or skipped selected tasks fail acceptance.
6. Independently audit decoded scientific outputs, then recheck input and snapshot hashes.

The initial cohort contains **100206, 149741, 877168**, all real HCP acquisitions,
each with shape `145 x 174 x 145 x 288`. It tests fresh DDSeg, DDParcel, DDSurfer,
DTI, one million CSD/ACT streamlines, fixed author WMQL and count/SIFT2
connectomes. HCP inputs are already preprocessed and include provided masks;
this is not a fresh preprocessing/PNL-mask test.

**Status: finished, failed; a WMQL sampling failure prevents this protocol
from passing.** Authoritative record:
`ignore/validation/cohort_onepass_20261017/acceptance.json`.
100206 completed its first and only attempt in 3473.56 s, including all selected
core products; the independent audit passed and input hashes were unchanged.
Its fixed-protocol WMQL yielded AF 63/27 and CST 159/136. On 149741 the exact
same one-million-track protocol produced AF 52/16 and CST 373/239. Right AF
fails the unchanged minimum 20 and is retained under `.failed_products` rather
than published as a passed result. Subject 149741 finished in 3404.39 s with
only WMQL failing; input hashes were unchanged. Subject 877168 passed its first
and only attempt in 3576.14 s, with an independent audit passing. All input,
runtime and backend hashes remained unchanged. This cohort remains failed.
No per-subject definition, threshold or tracking-budget
change is being used to rescue this cohort. AF and CST predicate/geometry
tracing has been extended to distinguish actual author selection from export
loss before any global protocol redesign.

The 149741 read-only AF trace found left/right frontal-temporal intersections
of 53/16, reduced to 52/16 by the original exclusions. All saved AF and CST
tracks matched the author-selected source multiset; no export loss was found.
DDParcel has no DK regional WM territories in this run: its source maps labels
through `map_label2aparc_aseg`. QC now explicitly describes cortical, generic WM
and regional WM label content instead of inferring full FreeSurfer `wmparc`
semantics from the historical filename. This is informative, not a new pass rule.

A controlled reference substituted only HCP T1-derived `wmparc`, nearest-neighbor
resampled using the native-world affines, while retaining the exact tracks and
queries. Right AF remained sparse (100206: 1, 149741: 4). Thus missing WM
territories alone are not established as the cause, and unvalidated projection
or dilation is not installed as a default fix. The T1-derived reference is
diagnostic only, not substituted into T1w-free outputs or accepted as a repaired
cohort. The declared brain-mask overlap check passed (Dice >= 0.85), but this
does not establish regional registration or anatomical ground truth.

Evidence: `subjects/149741/af_cst_predicate_parity/predicate_trace.json` inside the
cohort and `ignore/validation/wmql_atlas_reference_20261017/acceptance.json`.
References: [WMQL input guidance](https://tract-querier.readthedocs.io/en/latest/example_script.html),
[FreeSurfer WM parcellation](https://surfer.nmr.mgh.harvard.edu/fswiki/wmparc).

An additional read-only predicate trace reproduced the 159/136 author CST
sets and one-to-one saved geometry, with inputs unchanged. Evidence:
`subjects/100206/cst_predicate_parity/predicate_trace.json` inside that cohort.
This checks the implemented rule, not anatomical ground truth.

### Explicit DDParcel / ACT Compatibility Protocol

An independent endpoint-versus-crossing trace found 143/128 original AF
endpoint candidates on 100206 and 83/48 on 149741, whereas the full-author AF
rule selected 63/27 and 52/16 respectively. For 149741 right AF, only 16 tracks
met the initial frontal/temporal crossing intersection; no later AF exclusion
removed any. This identified the unintended AF-definition change, not an export
bug. It does not establish equivalence between the two anatomical definitions.
Evidence: `ignore/validation/wmql_af_endpoint_20261017/acceptance.json`.

The explicitly named `ddparcel_act` combines the original AF candidates with
unchanged author CST. Bundle-only replay independently compares the AF output
multiset against a fresh original-AF extraction and CST against the original
author output. The replay is not a complete workflow test. Record:
`ignore/validation/wmql_ddparcel_act_20261017/acceptance.json`.

Both replays passed: 100206 AF 143/128, CST 159/136; 149741 AF 83/48,
CST 373/239. All four output multisets per subject exactly matched their
respective original AF/CST definitions (zero coordinate delta), with source
hashes unchanged. Each subject's `current_independent_endpoint_audit.json`
also passed: zero AF endpoint violations; CST explicitly not certified as an
endpoint rule. These are integrity and sampling checks, not AF anatomy review.

A separate preregistered cold cohort is running in new directories on 100206,
149741 and additional subject **100408**. Every subject uses the same frozen
runtime, million-streamline budget and `ddparcel_act`; there are no retries,
subject-specific switches or resumed products. The new record is
`ignore/validation/cohort_ddparcel_act_20261017/acceptance.json` and must not be
confused with the failed author cohort. Neither the replay nor launch of the
new cohort permits an all-QC-passed claim. AF endpoints are audited separately;
CST crossing rules are not certified as endpoint predicates. The author trace
script rejects adapted/modified query snapshots instead of applying the wrong
AF diagnostic.

No success is inferred from launch, partial products or a previous subject.
Optional WMA, FW, NODDI, MK-Curve, SAF and expert anatomical review are not
covered by this particular core-cohort run. Other acquisitions and pathology
need their own preregistered validation; three HCP subjects cannot prove
universal one-pass success.

Example invocation with a locally supplied cohort protocol:

```bash
python3 scripts/validate_pipeline_cohort.py \
  --protocol /path/to/cohort.json \
  --report /path/to/new-empty-report-directory \
  --slicer /path/to/Slicer
```

The report directory must not exist. A failed attempt is retained, never
resumed or overwritten into a success record.

---

## Timing Ledger And Pending Controls

The updated [32-operation timing inventory](MODULE_RUNTIMES_20261017.md) saves
129 scoped entries, including failures. New `--one-pass-cohort` and
`--wma-acceptance` inputs require independent acceptance and unchanged sources
before a time can enter the successful representative table. Source/manifest
mismatches, missing QC, retries and incomplete runs are rejected. JSON retains
generation arguments and source hashes. READY means a measurement exists,
not scientific approval.

New CSD runs persist actual command, TRK conversion and output-validation
timings in `phase_timings`, including failures. Algorithms, RNG environment,
thread counts and output contracts are unchanged. Historical combined times
are not retroactively split; the cold cohort retains its earlier frozen code.

The complete fresh cached WMA took **4664.83 s**. Read-only comparison against
the earlier successful UKF result found exactly **95755 shared assignments**,
zero changed labels and no tracks unique to either result. Evidence:
`ignore/validation/wma_cache_full_20261017/repeat_geometry_audit.json`.

The failed newer high-shell UKF reference passed current source/geometry
checks but not all-tract sampling. Its `current_independent_audit.json` and
`sparse_stage_diagnosis.json` retain those separate conclusions. A new control
fixes the earlier successful b0+b1000 files and explicit UKF CLI settings,
changing the upstream/build version; implicit defaults are recorded separately.
Record: `ignore/validation/ukf_matched_protocol_20261017_v3/acceptance.json`.
Two harness failures before tracking are retained: unavailable old runtime
libraries, then unsupported `--xml` introspection. The current harness reads
both shipped parameter XMLs; no scientific fit was retried or threshold changed.

A frozen follow-up auditor waits for the new cold cohort, then checks all
three WMQL outputs with current endpoint/source rules and creates a local
timing ledger. It never retries the workflow or edits its outputs. Record:
`ignore/validation/cohort_ddparcel_act_20261017_followup/acceptance.json`.
Final packaging after the ledger/instrumentation updates is recorded in
`ignore/validation/sdk_current_20261017_v12/sdk_build_report.json` and
`ignore/validation/sdk_package_gui_20261017_v9/acceptance.json`; read their
actual persisted status, not an implied pass. Pending/failed records, invalid
fits, anatomical review and untested platforms must not be called all passed.
