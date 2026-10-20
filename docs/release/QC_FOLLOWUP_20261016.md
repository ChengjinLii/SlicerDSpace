<div align="center">

# Scientific QC Follow-Up

**16 October 2026 | Subject 100307 | Scoped acceptance, unresolved checks retained**

[Project](../../README.md) | [Documentation](../README.md) | [ACT diagnosis](CSD_ACT_DIAGNOSIS_20261015.md) | [中文](QC_FOLLOWUP_20261016.zh-CN.md)

</div>

---

## Acceptance Boundary

This is not an all-green release certificate. The previous CSD-dependent graph
has 164 passing checks and one failed ACT-current check under the 15 October
audit. Legacy WMA CST counts of 3/4 and failed historical WMQL queries remain
failed. Independent UKF bundle acceptance is not evidence for the CSD route.
The new ACT v3 CSD/WMA comparison below does not retroactively validate those
old files. Human anatomical review and native Windows/macOS execution remain
incomplete. Linux real SDK/CPack and selected private-install checks have passed,
not a blank-machine full scientific workflow. The repository remains private.

---

## Quantitative Exclusion

The full-brain MK-Curve fit contains 740916 brain voxels: 736294 satisfy its
declared validity criteria; 4622 (0.624%) do not. Invalid estimates remain in the
raw maps and are excluded from quantitative summaries. They are not filled,
smoothed, clipped into validity or described as uniformly normal CSF.

`scripts/audit_regional_validity.py` exports tables through the production
statistics implementation and independently recomputes counts and estimates
from the original scalar maps in float64. Against the newly generated DDParcel
atlas, the audit passes for **101 regions, seven maps and 2828 estimate
comparisons**. SHA256 fingerprints of the audited inputs remain unchanged.
The second audit takes 17.539 s, excluding fitting. Its evidence is:

```text
ignore/validation/act_v3_completion_20261016/mkcurve_quantification_v2/
  acceptance.json
  regional_mkcurve.csv
  regional_mkcurve.json
```

`automatic_quantitative_exclusion_qc_passed=true` means exclusion/statistics are
correct; the original `automatic_qc_passed=false` still means not every brain
voxel meets fitting validity. Expert anatomical acceptance is pending.

The production table schema now records each metric's valid/excluded counts and
coverage, separately from the anatomical ROI voxel count. Empty estimates are
JSON null / blank CSV cells, not zero measurements; all atlas labels remain.
Free-water tissue validity is explicitly propagated instead of being replaced
by a nonzero-value heuristic. Mask files must be binary, finite and on the native
grid. NODDI tissue validity applies to NDI/ODI, not the isotropic fraction itself.

Resume rejects legacy tables, changed atlas/scalar/mask files, missing required
DTI metrics, and inconsistent CSV/JSON exports. This rebuilds summaries from
eligible scalar outputs without requiring a model refit. Quantitative masking
does not change the separate continuous-display policy.

A subsequent read-only audit independently checks existing tables without
calling the exporter. MK-Curve passes **4949 count/estimate comparisons** across
101 regions and seven metrics. Of the atlas's 553750 labelled voxels, 551094
satisfy the MK-Curve validity mask; this atlas-restricted count is distinct from
the full-brain counts above. Evidence: `mkcurve_statistics_readonly/acceptance.json`
under the same validation directory.

The native atlas contains 12 labelled voxels outside the actual fitting brain
mask. Production statistics now intersect the fitting mask while retaining the
anatomical ROI total. An independently exported current table from the real
DTI/NODDI outputs passes **7777 comparisons for 101 regions and 11 metrics**.
DTI and IsoVF use 553738 labelled, brain-mask voxels; conditional NDI/ODI use
544927 after their additional tissue-validity exclusion. No scalar map changes.
Evidence is `regional_current_independent/acceptance.json`. The joint scientific
auditor now verifies declared regional tables numerically, not just by file
existence. Tests include mutually consistent but numerically wrong CSV/JSON
tables to ensure a matching cache record cannot substitute for raw-map agreement.

---

## New CSD Route

An isolated real Slicer GUI run uses the packaged `a48fc95` source snapshot and
fresh outputs under `act_v3_completion_20261016/products`. The HCP input/mask and
matching native SlicerDMRI DTI cache are reused; this is not a fresh raw-data
preprocessing or DTI-estimation benchmark. New DDSeg, DDParcel and native surface
execution have completed; the first surface postprocess takes 746.742 s and DTI
scalar export/ROI reporting takes 8.178 s. New NODDI fitting completes in
424.115 s and its automatic QC passes. The fresh ACT v3 CSD route has completed
one million tracks, SIFT2 and format/geometry checks in 1892.7 s.

The run requests ACT v3, one million iFOD2 tracks, SIFT2, WMQL, count and weighted
connectomes, using eight tracking/SIFT2 threads and normal dynamic seeding. No fixed
single-thread diagnostic seed or lowered bundle-sampling gate is substituted.

WMA consumed this exact new TCK only after the current ACT, export and SIFT2
gates passed. Its official ORG execution took **4756.080 s (79.27 min)**,
separately from 2350.282 s waiting for CSD. All 74 tracts are nonempty, with
AF **1800/1301**, CST **337/937** and CC4 **4868** tracks. Independent finite
geometry/source-membership checks passed; the maximum coordinate difference
is 7.63e-6 mm. The TCK and CSD manifest/QC hashes did not change.

This is not permission to quantify every tract. Five small outputs remain
below the 20-track sampling reference: left CR-P (5), bilateral EC (8/7),
right EmC (7), and right Intra-CBLM-PaT (5). The fixed major-tract gate does
not certify these smaller bundles; expert review and quantitative eligibility
remain pending. The old WMA CST 3/4 result remains failed.

WMQL on the same new source reveals a **definition-dependent failure**:

| Explicit query | AF L/R | CST L/R | Extraction | Automatic result |
| --- | ---: | ---: | ---: | --- |
| Bundled published CST endpoints | 61/54 | 13/18 | 90.936 s | Failed, unchanged 20-track gate |
| Unmodified author-repository crossing/exclusion | 70/28 | 154/311 | 85.224 s | Sampling and independent source checks passed |

The original GUI full run therefore ended **FAIL**, not complete scientific
acceptance. The author-repository result is a separately identified comparison,
not a fallback or replacement for the failed endpoint preset. A direct trace
reproduces both predicate counts and matches the saved author-selected track
multisets one-to-one within 0.001 mm. Exact byte equality is false because of
ASCII export precision (maximum difference 1.53e-5 mm), not altered trajectories.
The audit checks interior points, counts and duplicate assignments, not endpoints
alone. The first byte-only diagnostic remains retained; the corrected geometry
diagnostic is `wmql_legacy_predicates_geometry/predicate_trace.json`.

Source: [author query snapshot](https://github.com/demianw/tract_querier/blob/5c69c594d489859e08485110678dca7f6f4cba40/tract_querier/data/freesurfer_queries.qry).
Query and regional-alias bytes match that pinned upstream snapshot. Installed
packages previously misidentified original aliases when the development checkout
was absent; provenance now uses the pinned upstream SHA256 instead. Each run
also has a separate query/import snapshot so later runs cannot overwrite its
historical executed definitions. Neither change lowers sampling gates or changes
the default anatomical rule.

### Scoped Stage Timings

These are measured task times from this run, not controlled cross-version
speedups. DTI uses a matching existing fit; WMA is a separate follow-up on the
same TCK. Do not add waiting or independent audit time to extraction time.

| Stage | Seconds | Scope/result |
| --- | ---: | --- |
| DDSeg | 16.623 | New inference |
| DDParcel | 225.406 | New inference |
| Native surfaces | 240.498 | New inference/export |
| Surface postprocess | 746.742 | First execution, not accidental repeat |
| DTI scalar/ROI export | 8.178 | Existing native DTI, old ROI schema later refreshed |
| NODDI | 424.115 | New fit |
| CSD/ACT/SIFT2 | 1892.681 | New million-track route |
| Default WMQL | 90.936 | Failed endpoint sampling, not a successful benchmark |
| Author-repository WMQL | 85.224 | Separate definition, anatomy pending |
| WMA follow-up wrapper | 4756.080 | Excludes 2350.282 s predecessor wait |
| Count connectome | 137.304 | New matrix |
| SIFT2 connectome | 136.602 | New weighted matrix |

The machine-readable task ledger is the retained
`products/00_run_metadata/act_v3_csd_orchestration_manifest.json`; separate WMA
timing is in `wma_csd_v3/acceptance.json` (`wma_execution_seconds`).

The snapshot only forwarded the thread setting to tracking/SIFT2. Current code
also applies it to MRtrix conversion, response estimation, FOD fitting and
normalization, retaining single-thread pinning only for explicitly seeded
tracking. The active snapshot is not hot-patched. An eight-thread real VTK export
retains 7637/7637 curves and 1467928/1467928 points with finite coordinates;
maximum coordinate error is 5.34e-5 mm (ASCII output precision). This is an export
check, not a new bundle/anatomical result or full thread-budget benchmark.

The original GUI package predates the regional-table changes above. Its old tables
were independently rejected, backed up and refreshed using current production
code, without refitting or changing scalar/atlas/fit-source hashes. The current
packaged-source GUI resumed DTI as cached and loaded the results in **32.015 s**.
`regional_refresh_scope/acceptance.json` records this scoped pass and explicitly
retains `core_automatic_qc_passed=false` and the original failed full-run record.
The joint audit now passes the regional numerical gate; the WMQL-related checks
still fail. Historical failed tractograms and bundle reports are not overwritten.

The first `surface_independent` helper invocation repeated postprocessing rather
than only auditing. That attempt is retained as repeat-execution evidence, not a
read-only audit or a normal workflow timing. The helper's `--existing-output-root`
mode has now been made strictly read-only and must not execute or repair failed
products. The repeat has finished in 791.224 s and is not a workflow benchmark.
The subsequent `surface_readonly/acceptance.json` passes all 16 current-output,
correspondence, finite-overlay and annotation checks in 0.562 s without stage
execution. This still does not establish expert anatomical validity.

`finish_core.py` correctly stopped when the original GUI failed and did not
modify its outputs. The separate `refresh_regional_scope.py` recipe above repairs
only the identified regional-table issue and cannot turn a failed WMQL graph green.

---

## SDK Work

Official Slicer v5.10.0 source (`a2b6d082be04274a849884fbb1e85634a9df90fb`)
has completed the real superbuild, including VTK, ITK, CTK, SimpleITK and Slicer.
Missing
OpenGL development files are extracted into a private SDK sysroot, not installed
into the user's running applications. A Qt/C++ ABI linker incompatibility was
reproduced and the isolated CTK launcher subsequently compiled successfully.
Extension configure/build succeeded, but initial CTest attempts exposed missing
headless-display/test-dependency setup and a zero-test main-module suite. Those
failed attempts are retained, not counted as release acceptance. A real native
parameter/logic smoke test and a zero-test rejection guard now prevent that false
success. Backend unit fixtures are tested in an explicitly selected independent
Python; generic/native module tests still execute in the real SDK Slicer.
The corrected run passed **128 CTests (126 independent backend suites and two
native Slicer suites)** in 108.65 s. CPack produced a real TGZ; its 460 runtime
resources matched source hashes without missing/unexpected/unsafe entries.

That actual archive, not a staging substitute, passed Extension Manager
installation with private user/revision settings and installed-directory imports.
Subsequent native tests passed bundle QC rejection/retraction/manual-ownership,
five WMA products (9243 tracks), two author WMQL CSTs (465 tracks), rendered CST
previews, and GUI DTI-cache/ROI-table resume/loading. WMQL's TRK display conversion
preserved points within 7.63e-6 mm. The test durations were 13.836 s for installation,
115.635 s for the bundle suite, and 24.200 s for the cached DTI GUI case.

Evidence: `sdk/extension-build-native/sdk_build_report.json` and
`cpack_clean_install_verified/acceptance.json`. The first clean-install attempt
requested obsolete `.vtk` names while the author backend actually produced `.trk`;
that failed test configuration is retained under `cpack_clean_install_native/`.
The corrected test uses the real TRK products, without relabeling the failure.

The official Slicer binary and SlicerDMRI/scientific prerequisites were already
available; settings and extension installation were clean. This does not prove
empty-machine dependency installation, fresh full-brain DTI refitting, every
algorithm, or expert anatomy. The failed endpoint-WMQL result remains excluded.

This custom developer build disables WebEngine/multimedia and reads the existing
Qt installation without modifying it. It does not establish compatibility with
all official Slicer binaries or native Windows/macOS. No fabricated
`SlicerConfig.cmake`, contract-only package or user settings change substitutes
for actual release evidence.

The latest review packet, `review_packet_labeled/`, contains 25 source-derived
PNG plates, a PDF, source hashes and an unsigned review form. Every bundle plate
identifies its recorded status, run and query definition so controls are not
confused. Source files are unchanged; `scientific_accepted=false` and reviewer
fields remain empty until a qualified reviewer signs off.

---

## Software Regression

The latest complete Python suite runs **1052 tests: 1051 pass, one is explicitly
skipped**, in 57.366 s. New tests cover stale regional tables, explicit validity,
unfinished/mismatched CSD predecessors, strictly read-only surface auditing and
thread-budget propagation throughout MRtrix commands, fitting-mask intersection,
independent numerical auditing of regional exports, immutable WMQL snapshots,
pinned query provenance and one-to-one precision-aware predicate parity.
The retained log is `ignore/validation/act_v3_completion_20261016/software_tests.log`.
These tests do not establish human anatomical or native-platform acceptance.
