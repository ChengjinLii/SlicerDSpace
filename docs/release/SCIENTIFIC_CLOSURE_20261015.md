<div align="center">

# Scientific Validation Follow-Up

**15 October 2026 | Subject 100307 | Private working tree**

[Project](../../README.md) | [Documentation](../README.md) | [Earlier QC](PIPELINE_QC_20261015.md) | [Timings](MODULE_RUNTIMES_20261015.md) | [中文](SCIENTIFIC_CLOSURE_20261015.zh-CN.md)

</div>

---

## Current Scope

**Later correction:** the [CSD/ACT investigation](CSD_ACT_DIAGNOSIS_20261015.md)
identified an incorrect VentralDC-to-sGM mapping in legacy ACT preparation.
The 161 passing checks below predate the new tissue-mapping gate and are historical,
not current acceptance of that CSD route. Read-only re-audit now reports 164 passed
checks and one failure. Rebuild ACT, dependent tracking, bundles and connectomes;
the separate UKF comparison does not use this ACT image.

This campaign adds a full-brain MK-Curve fit, same-subject UKF tracking and
author-original WMQL extraction, plus a new Slicer-triggered processing graph.
**It does not certify every output as anatomically correct.** WMA and the joint
graph have now completed and passed independent automatic integrity checks.
The joint graph passed 161 checks with zero failures. Expert review remains pending.

All evidence is retained under `ignore/validation/scientific_closure_20261015/`.
Original DWI, masks, parcellations and historical tractograms remain unchanged.
Failed attempts are retained, not overwritten. The user's Slicer and MRI Agent
sessions are not restarted; GUI validation uses separate settings and displays.

---

## Author-Original WMQL

The prior [CST report](WMQL_CST_20261015.md) distinguishes the author's legacy
crossing/exclusion query from the [published tutorial endpoint definition](https://tract-querier.readthedocs.io/en/latest/example_script.html).
Changing that definition did not fix the legacy query on its original CSD input.
This campaign therefore tests **the unchanged legacy query on new UKF tracks**.

| Item | New measured result |
| --- | --- |
| Input | 277,875 real two-tensor UKF tracks, same subject 100307 |
| Query | Original `freesurfer_queries.qry`; crossing threshold 2.0 unchanged |
| AF left / right | 1,184 / 1,216 |
| CST left / right | 168 / 252 |
| Extraction wall time | 23.358 s; excludes UKF tracking |
| Independent source membership | 2,820 / 2,820; maximum coordinate difference 0 mm |
| Recomputed author CST predicates | Exact sets match saved left/right outputs |
| Scientific acceptance | Automatic sampling/integrity passed; expert anatomy pending |

This is not a relabeled endpoint-preset result. Native SlicerDMRI loading also
preserves all 420 CST tracks and their coordinates, while the historical failed
QC is still rejected. Some circuitous tracks remain visible in the review
plates; sufficient counts are not proof of anatomical specificity.

UKF uses the complete b~1000 shell (90 directions) and 18 baselines, selected
before fitting. Its matching official Slicer extension CLI runs in a separate,
network-disabled compatible runtime; an incompatible newer binary is not loaded
into Slicer 5.10. The original 288-volume acquisition is not changed. This is a
method/protocol comparison, **not** an isolated causal test of one parameter or
proof that every CSD tractogram is unsuitable for WMQL.

---

## WMA Diagnosis

The failed million-track CSD output was traced through the exact CST cluster
list in the author's atlas. Its 11 CST atlas clusters initially receive only
11 subject tracks; outlier removal leaves seven, and hemisphere separation
produces 3/4. This loss occurs **before** final tract merging or Slicer display.

The new 277,875-track UKF input completed original WMA/ORG using unchanged
registration and coverage gates. All 74 tracts are readable/nonempty: AF left/right
287/602, CST 446/520 and CC4 1,278 tracks. All 95,755 output tracks matched their
source geometry in independent audit. No other classifier was substituted and
no minimum-count threshold was lowered. Automatic integrity/sampling passed;
expert anatomical acceptance is pending. Extraction/acceptance took 6,510.590 s
(108.5 min), excluding UKF tracking; audit wait time is not extraction time.
The [atlas documentation](https://dmri.slicer.org/atlases/) describes UKF as its
construction method but also permits RAS streamline inputs; this is not a claim
that WMA formally supports only UKF.

A real wrapper defect was fixed: a selected shell launcher could prevent
discovery of its PythonSlicer, allowing an external interpreter to inherit a
different Python standard library (`SRE module mismatch`). Runtime discovery
now uses the launcher's own advertised `SLICER_HOME`, verifies its interpreter,
cleans inherited Python overrides and records the resolved runtime. Direct
native launchers avoid an extra probe. Author clustering code is unchanged.

---

## Full-Brain MK-Curve

| Item | Measured result |
| --- | --- |
| Supplied mask | 740,916 voxels, all fitted |
| Protocol | Complete b~1000/b~2000 shells, 18 b0 averaged; 90 high-b volumes excluded by the predeclared 2500 s/mm² policy |
| Synthetic-b0 grid | 202 samples, unchanged author-style correction |
| Execution | 989.384 s; 16 CPU workers; bounded chunks |
| Corrected voxels | 320,556 |
| Corrected-valid voxels | 736,294 (99.376%) |
| General reference audit | 128 deterministic real voxels; pivoted-QR coefficients, raw maps, curves and correction decisions compared |
| Targeted invalid audit | 128 invalid voxels; reference QR reproduces parameters and validity decisions |

The optional batched WLLS path solves the same weighted objective. Ill-conditioned
systems fall back to pivoted QR; the original reference solver remains available.
There is no smoothing, parameter filling or raw metric clipping. Independent
full-grid/source-hash/reference checks passed. The fit's strict all-voxels-valid
flag remains **false**, distinct from successful execution and integrity checks.

All 4,622 invalid voxels have finite maps. Major overlapping failures are RK
outside [0,3] (3,508 voxels), MK above 3 (683), and AD above 0.005 mm²/s (643).
DDSeg labels place 2,510 in predicted WM, 61 in GM and 2,051 in CSF. Only 1,360
are within 2 mm of the brain-mask boundary: these cannot simply be called
normal CSF holes. They remain quantitatively invalid, with explicit masks.
The original unconstrained fit's limitations are not repaired cosmetically.

Curve comparisons use stated relative/absolute tolerances. Very large values
in pathological uncorrected curves can have large absolute differences despite
passing relative tolerances; this is not a claim of uniformly tiny absolute
error or an independent full-brain MATLAB execution.

---

## Joint Graph And Review

The new GUI-triggered graph starts from already-preprocessed HCP DWI, and runs
DDSeg, DDParcel, native surfaces, complete bilateral postprocessing, DTI/NODDI,
million-track CSD/ACT, WMQL and a count connectome into a separate output root.
Existing unchanged native DTI prerequisites may be reused. Optional FW, DKI,
MK-Curve, WMA and SAF have separate scoped evidence, not a claim that all optional
backends ran in one graph. The joint graph and count/SIFT2 connectomes completed,
and real GUI loading passed. Independent checks passed again after the subsequent
display/audit fixes. The GUI case took 9,243.587 s (154.1 min). Its fixed seed forces
single-thread MRtrix generation for bit reproducibility; this is not a default
interactive performance benchmark or a global disabling of GPU-capable backends.

The run exposed and fixed a real GUI/API mismatch: the widget passed
`tractcloud_device`, but plan/run logic signatures did not accept it. Regression
tests now bind actual widget options to both entry points. Another acceptance
harness defect was fixed by snapshotting its stdlib archive inspector alongside
the test script instead of assuming the original checkout-relative location.
The corrected real Extension Manager installation passed in 14.0 s; compact UI
and native bundle loading/QC rejection also passed in separate test scopes.

### Failure-Path Follow-Up

The final review found and corrected three additional reporting/display defects:

- A task-level bundle rejection had no file path, but the automatic loader indexed
  it as a per-file rejection, raising `KeyError`. It now retracts only this run's
  automatically loaded nodes for the failed product, preserving manual/user data.
  Automatic reuse no longer relabels manual nodes as automatic, and source refresh
  preserves older manual review nodes while replacing only automatic previews.
- A stale `automatic_qc_passed=true` could override explicit failed status/checks
  or an error. Explicit failure now wins; failed tasks cannot borrow old passed
  QC. Failed/cancelled tasks also retract their old automatic previews.
- WMA audits previously included nonapplicable TractCloud partition and WMQL
  endpoint checks as true. Only applicable checks are now counted; `checks_not_run`
  records the exclusions. Fresh WMA and author-query WMQL audits still pass their
  actual source-membership/geometry/sampling checks; author CST predicate evidence
  remains a separate explicit comparison.

Regression tests reproduce the pre-fix failures. Real Slicer follow-up verifies
positive WMA/WMQL loading, rejected historical QC and failed-product preview
retraction without removing manually loaded nodes, including reuse followed by
failed QC. The prior scientific graph is
read-only re-audited, not described as a new 2.5-hour fit after these display fixes.

| Joint-graph stage | Recorded seconds | Timing scope |
| --- | ---: | --- |
| DDSeg | 21.589 | GPU inference and QC; existing native DTI prerequisite |
| DDParcel | 205.811 | Regional inference/export/QC |
| Native surfaces | 242.775 | Native reconstruction and QC |
| Surface postprocessing | 740.658 | Current full bilateral route |
| DTI | 8.091 | Scalar export/ROI, not fresh tensor estimation |
| NODDI | 280.157 | Full mask, 8 CPU threads |
| CSD/ACT/SIFT2 | 7,276.363 | Fixed-seed single-thread generation; combined stage |
| WMQL | 76.474 | Joint graph's CSD input and published-endpoint preset, not the separate UKF/legacy query |
| Count connectome | 138.851 | Python count matrix and validation |
| SIFT2 connectome | 137.682 | Python weighted matrix and validation |

Stage times are distinct from GUI startup/loading. They are not universal speed
targets or controlled hardware comparisons against earlier runs.

`review_packet/` contains 12 data-derived PNG plates; `review_packet_surfaces/`
adds native white/pial intersections for 13 plates, a PDF, source hashes and an
unsigned `manual_review.json`. Labels/scalars use native grids and nearest
display; bundle views are explicitly marked **projections, not slices**.
Preview-only deterministic sampling never alters saved tractograms. Expert
reviewer identity, decisions and date remain blank. The packet is preparation
for review, not a fabricated human approval.

`qc_followup/review_packet/` is the updated 22-plate PDF/PNG packet, adding actual
WMA AF/CST/CC4, DTI and NODDI maps. All captured source hashes remained unchanged.

Remaining gates are expert anatomical acceptance, handling the explicitly invalid
MK-Curve quantitative voxels, and native platform/SDK release validation. The old
CSD-to-WMA failure remains failed, not replaced by a green label on the old data.
No push or public release is performed by this campaign.

The latest regression suite ran **1,020 tests: 1,019 passed and one explicit skip**.
All 54 active Markdown files passed link/style checks. These are software
verification counts, not a clinical or all-backend scientific certification.
Logs, fresh read-only audits and isolated GUI acceptance are under `qc_followup/`;
`gui_release/` identifies the final manual-ownership follow-up. Earlier failed
reproduction logs remain evidence of the defects, not successful validation.
