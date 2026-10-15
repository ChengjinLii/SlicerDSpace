<div align="center">

# Pipeline QC And Performance

**15 October 2026 | Private working-tree validation**

[Project](../../README.md) | [Documentation](../README.md) | [Bundles](BUNDLE_QC_20261015.md) | [Timings](MODULE_RUNTIMES_20261015.md) | [中文](PIPELINE_QC_20261015.zh-CN.md)

</div>

---

## Scope

The later [scientific follow-up](SCIENTIFIC_CLOSURE_20261015.md) adds full-brain
MK-Curve and an unchanged-author-query UKF comparison. Historical tables below
are retained; see the later report for the current running/accepted scopes.

Later [CST diagnosis](WMQL_CST_20261015.md) resolved the definition ambiguity:
the current published-endpoint default passes paired automatic QC at 170/363;
the legacy crossing/exclusion query remains failed. The tables below retain the
earlier scoped records rather than claiming those historical failures passed.

Execution, automatic integrity checks, fit-quality review and anatomical acceptance
are separate states. **Not every result is scientifically accepted.** This report
does not certify all datasets or Windows/macOS. Original DWI, masks and tractograms
were not modified; failed products are retained. Active Slicer/MRI Agent sessions
were not restarted. Changes remain local, without a push or public release.

Evidence is under `ignore/validation/pipeline_qc_20261015/` and
`ignore/validation/bundle_fix_20261015/`, with new full-route evidence under
`ignore/validation/pipeline_completion_20261015/`. JSON/CSV preserve paths, hashes, scope,
failures and timings. Saved-task audits are independent task scopes, not a newly
assembled joint pipeline execution. The old run overview alone omitted tasks
after a later partial execution overwrote the same overview filename.

---

## Correctness Fixes

| Area | Defect | Current behavior |
| --- | --- | --- |
| DTI RD | Existing RD could survive a changed eigenvalue export | Recompute RD with every changed export; verify AD/RD/MD identities |
| DTI reuse | Optional FW/NODDI runs recopied scalar files | Separate source/output-stamped DTI export QC; unchanged exports reused |
| FW/NODDI reuse | Readable files or old green status could satisfy completion | Require explicit successful checks and unchanged source/output stamps; reject failed/corrupt/legacy QC |
| AMICO input cache | Existing links/copies could still target another input | Verify/refresh links; verified copy fallback for Windows |
| AMICO kernels | Upstream skips generation when an old dictionary exists | Isolate by input protocol, model options and AMICO version; NODDI stage version 3 rejects old cache |
| NODDI QC | Unconditional completed status after writing maps | Check native grid, finite/ranged parameters, binary/nonempty tissue validity and finite/nonnegative residuals |
| DKI | A fit with zero valid quantitative voxels could finish green | Fail before publishing maps; reject legacy zero-valid caches |
| Python MK-Curve | Zero corrected-valid voxels could still finish successfully | Fail the stage and independently reject empty corrected validity |
| Surface postprocessing | Completion/cache gate depended mostly on file presence | Decode mesh correspondence, thickness/area, morphometry, annotation and statistics; reject changed output stamps or changed brain reference |
| DDParcel | Native export could be skipped yet completion logged | Require native/registered labels and all four normalized inputs; decoded grid/label QC |
| Bundle audits | Legacy audit checked nonempty/aggregate coverage only | Decode files and apply the current requested-query and major-tract contracts |
| Timing selection | A short failed bundle run could look like a successful benchmark | Preserve failures in ledger, exclude them from representative successful timings |

Slicer computes Trace from the original tensor but fixes negative eigenvalues
for eigensystem scalars. DTI QC therefore checks MD against the exported
eigenvalue mean and allows Trace differences **only** at the clamped L3 boundary,
with Trace no larger than the clamped sum. For saved 100307, 9,894 brain voxels
have this behavior; MD matches the eigenvalue mean to 4.66e-10 mm²/s.
Values are not repaired to force equality. [Slicer implementation](https://github.com/Slicer/Slicer/blob/main/Libs/vtkTeem/vtkDiffusionTensorMathematics.cxx).

---

## Real Results

| Scope | Outcome | Boundary |
| --- | --- | --- |
| 26 independent saved task scopes | 24 passed; old sparse WMQL and old-version surface-postprocess cache rejected | Not a joint full rerun; source/version rejection is not an anatomical diagnosis |
| Saved 100307 DTI/FW/NODDI/DDParcel | Current scalar/geometry checks passed | Not a new FW fit or ground-truth validation |
| DDSeg world alignment | Recomputed WM Dice 0.860935 | Existing hard threshold 0.70; this does not validate every voxel |
| Fresh full-brain NODDI | 740,916 mask voxels; 343.098 s; 8 CPU threads; automatic QC passed | IsoVF tissue-valid fraction 92.109%; NRMSE p95 0.292770; anatomical review pending |
| NODDI numerical repeatability | NDI, ODI, IsoVF, RMSE, NRMSE and validity mask exactly equal to saved outputs | Same subject/protocol/library, not independent model validation |
| WMQL 1M input | AF 80/53, CST 133/304; 570 source-matched tracks; 176.894 s | Endpoint candidates, not reviewed canonical AF/CST |
| Author-original WMQL query, same 1M input | AF 64/21, CST 0/11; **failed**; 84.138 s | Source geometry/membership passed; insufficient CST remains. Candidate rules are not substituted for author-rule acceptance |
| WMA100307 fresh 50k input | 64/74 nonempty but CST 1/0: **failed**; 2071.373 s | Do not quantify or substitute a different classifier to hide failure |
| WMA149741 UKF input | Current decoding, source membership and major-tract sampling passed | Saved extraction, not a new model fit or clinical validation |
| Full-brain DKI WLS | **Passed automatic integrity/parity QC**; 740,916 mask, 735,319 fitted, 681,770 valid; 5496.222 s | Valid fraction 92.017%; no smoothing/hole filling; anatomical review pending |
| Direct DIPY DKI reference | 128 deterministic real voxels matched raw parameters, S0, all six metrics and residuals; valid NRMSE p95 0.093351 | Full-grid audit plus sample refit, not a second independent full fit |
| Current complete bilateral postprocessing | Snapshot c3b2d40; 726.217 s; meshes, morphometry, both atlases and statistics passed strengthened QC | Original surfaces unchanged; numerical review is not anatomical certification |
| WMA100307 fresh 1M input | **Running**, isolated output and original source preserved | No final QC/runtime claim before completion |
| Python MK-Curve | Existing author-parity/ROI checks; full-brain runtime still unmeasured | Not included as a full-brain acceptance claim |

The old surface-postprocessing cache belongs to a previous DDSurfer snapshot.
Current changed operations have real-output parity checks documented in
[DDSurfer synchronization](DDSURFER_SYNC_20261013.md). A fresh full bilateral run
now supplements those checks. Final strengthened QC/resume verification took 2.445 s;
that is not confused with the 726.217 s compute time. Left/right vertex counts
are 164,239/164,694, with median thickness 2.632/2.581 mm. This is not validation
against ground-truth cortical boundaries or thickness.
DKI is sensitive to implausible kurtosis estimates even with a correct implementation;
raw maps, display maps and validity masks remain separate. [DIPY DKI reference](https://docs.dipy.org/stable/examples_built/reconstruction/reconst_dki.html).

---

## Measured Performance

- DTI eight-map export plus QC: **1.103 s** fresh versus **0.00125 s** reuse; cached file stamps unchanged. This is not tensor-fitting speedup.
- NODDI: **343.098 s** for a fresh isolated full-brain run, compared with an older one-thread record of **1784.280 s**. Not a controlled paired hardware benchmark. Numerical outputs matched exactly.
- FW DWI access now uses one sequential gzip decode and disk-backed slabs. A real three-slab parity benchmark passed exact values/affines and unchanged input SHA256. It is not a full FW fitting-time claim.
- On this host without `indexed_gzip`, the three-slab benchmark took **37.252 s** with the original proxy versus **17.079 s** for one-pass decode/read. The real 64-voxel FW fit matched direct DIPY exactly; full-brain FW fitting time has not been remeasured.
- Automatic NODDI CPU parallelism is bounded by available CPUs and eight threads. Explicit positive thread counts remain supported; BLAS nesting stays bounded. No global CUDA disabling was introduced.
- Only backends that implement GPU support use CUDA. CPU-only DIPY/AMICO stages are not relabeled GPU computations.

The full [32-operation timing ledger](MODULE_RUNTIMES_20261015.md) preserves
different subjects, devices, versions and cached prerequisites. Its rows must
not be summed into an end-to-end runtime or interpreted as universal speed targets.

---

## Verification And Remaining Gates

Regression tests cover changed RD, source switching, Windows copy fallback,
empty validity, corrupt residuals, invalid geometry, zero-valid DKI, failed QC
reuse and legacy bundle timing selection. Isolated Linux Slicer install, compact
UI, failed-bundle rejection and package resource auditing passed. These tests do
not alter the active user's settings or prove native Windows/macOS execution.

The regression campaign ran **994 tests: 993 passed and one explicit existing skip**;
50 active Markdown documents passed link/style checks. Linux install/UI/bundle-QC
smokes passed in independent settings and displays. See retained logs and
`pipeline_completion_20261015/gui_final/gui_acceptance.json` for the exact staged patch scope.
The two earlier GUI bundle invocations omitted the required tasks configuration;
those failed harness records are retained, not counted as passes. The harness now
rejects missing assets/configuration before staging or launching Slicer.

Remaining: finish the new WMA100307 1M run and review coverage; obtain compatible
reviewed WMQL atlas/input; measure full-brain MK-Curve when feasible; perform
human anatomical review; finish native Windows/macOS
and official SDK/CPack acceptance. Thresholds were not relaxed to turn these green.

~~~bash
python3 scripts/audit_saved_task_records.py \
  --task-root ignore/validation/slicer_acceptance_20261006/science/subjects \
  --report ignore/validation/pipeline_qc_20261015/saved_tasks_current.json
python3 scripts/validate_pipeline_scalars.py --subject-root /path/to/subject \
  --report-dir /separate/evidence --refit-noddi
~~~

Revalidation writes its QC to a separate evidence directory. Optional full fits
create new outputs there. Existing failure metadata is only revalidated explicitly
with archival preservation; original scientific maps/tracks are not edited.
