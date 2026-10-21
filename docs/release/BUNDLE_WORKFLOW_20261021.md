<div align="center">

# Bundle Workflow Review

**Automatic handoff, decoded products and layered QC | 21 October 2026**

[Project](../../README.md) | [UKF](../setup/UKF.md) | [Evidence](benchmarks/bundle_workflow_20261021.json) | [中文](BUNDLE_WORKFLOW_20261021.zh-CN.md)

</div>

---

## Findings

Process completion, automatic integrity/sampling checks and expert anatomical
validation are different claims. No thresholds were relaxed, tracks duplicated,
network weights changed or historical failures overwritten.

| Route and source | Actual work this campaign | Result |
| --- | --- | --- |
| WMQL `ddparcel_act`, 100206 | Re-decoded saved 1M-track results; source membership and applicable endpoint rules | AF 132/107, CST 98/131; passed |
| WMQL `ddparcel_act`, 100408 | Same audit | AF 402/95, CST 86/165; passed |
| WMQL `ddparcel_act`, 149741 | Same audit | AF 80/48, CST 402/317; passed |
| WMA, 100307, saved UKF | Re-decoded 277,875 source tracks and 74 saved bundles; sampling and membership | 74/74 passed, minimum 60; AF 287/602, CST 446/520 |
| TractCloud, 100307, old 50k CSD | Actual fresh inference plus independent membership/disjoint-assignment audit | 39 nonempty groups, 21,432 assigned tracks; four groups only 1/1/2/14, not reliable quantitative bundles |
| TractCloud, 100307, saved UKF | Actual fresh inference plus independent membership/disjoint-assignment audit | 42 nonempty groups, 117,925 assigned tracks, minimum 82; current checks passed |

WMA registration was **not** rerun. TractCloud used the same network, weights,
seed and batch parameters on different sources. Its 42 groups are not the same
label grouping as WMA's 74 lateralized tracts. The old 50k CSD source is an
adapter/repeatability fixture, not current ACT acceptance. `ddparcel_act` is
an explicit adapted definition, not an unchanged author AF/CST protocol.

TractCloud now records per-bundle counts and a **local 20-track sampling screen**.
This is not an author accuracy criterion or anatomical ground truth. Sparse
bundles are listed in `sampling_screen.excluded_from_quantification`. Successful
file/geometry QC with sampling warnings is shown as a warning, not an all-clear.
`quantification_eligible=false` preserves the expert-review boundary. Source
membership and disjoint assignment have separate independent audits; the basic
`automatic_qc_passed` flag alone does not establish that these audits ran.

---

## Automation And Fixes

CSD/ACT and WMQL remain the defaults; selecting bundles does not run every method.
Choosing **UKF + WMA** under Advanced automatically converts inputs, invokes the
official UKF CLI, exports VTK/TRK and passes the result to WMA. Running UKF in
another module and manually importing its output is not required. First-time
UKFTractography/SlicerDMRI installation and WMA/ORG resources remain prerequisites.

- Forward both discovered UKF and DWIConvert executable paths from the GUI to workers, including out-of-tree extension installations; build each CLI's library environment separately.
- Apply shared loading-QC gates to TractCloud as well as WMQL/WMA; reject explicit failures, contradictory error/check fields and legacy records without current explicit QC.
- Require current WMA QC version, explicit acceptance and all-tract sampling before cache reuse.
- Preserve orchestrator QC failure when a backend returns `completed`; never promote backend failure through an outer success state.
- Automatically export the selected DTI run to full RAS VTK for TractCloud instead of finding an old CSD file.
- Verify every converted track/point within 0.0001 mm; reuse only matching source/output SHA256. No display subsampling or track repair.

These are orchestration, cache and QC improvements, not a reimplementation or
an algorithm-speed/accuracy claim. Existing-tractogram overrides remain optional.
Without suitable WMA input, the message points to the automatic UKF route rather
than requiring a standard manual-file workflow or silently changing methods.

---

## Verification

Unit regression: **1,189 run, 1,184 passed, five skipped, zero failed**. Coverage
includes GUI/worker parameters, stale-QC rejection, failure-state precedence,
same-run DTI binding and lossless conversion/cache invalidation.

Isolated Slicer 5.10 UKF controls and real author-CLI synthetic tracking passed:
1,728 tracks, full mask overlap, requested tensor/FA arrays and VTK/TRK coordinate
verification. The initial isolated launch omitted the SlicerDMRI library path;
fiber loading failed. Supplying that test-process path passed on rerun; the
failure remains in `native/`. This is not a fresh marketplace UKF installation
or human anatomical acceptance.

The isolated scene also loaded **128 actual bundle files**: 12 WMQL files from
three subjects, 74 WMA files and 42 fresh UKF-input TractCloud files. Maximum
coordinate delta was 0.00000763 mm for WMQL and zero for WMA/TractCloud, below
the 0.001 mm acceptance tolerance. Legacy TractCloud QC rejection, automatic
node retraction and preservation of manually owned nodes also passed.

The fresh UKF-input TractCloud call took **104.39 s**, with **16.97 s** for its
separate decoded geometry/source audit, excluding UKF tracking, downloads and
Slicer startup. Other GPU jobs were active. Different inputs and execution
conditions prohibit treating these numbers as before/after acceleration.

Local raw evidence lives in `ignore/validation/bundles_review_20261021/`.
The machine-readable inventory includes source/code hashes, counts, audit
checks and native Slicer reports. Old failures were not promoted.

---

## Remaining Gates

Expert anatomical review, cold-start multi-subject WMA using outputs generated
directly by the latest UKF defaults, and Windows/macOS full scientific acceptance
remain outstanding. Saved older UKF results cannot substitute for these gates.
Execution completion, automatic QC, sampling warnings and human review remain
separate states.
