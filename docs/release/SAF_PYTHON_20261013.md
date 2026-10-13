<div align="center">

# SAF Python Verification

**13 October 2026 · Source comparison, geometric corrections and real products**

[Project](../../README.md) | [Implementation](../architecture/IMPLEMENTATION_PROVENANCE.md) | [中文说明](#中文结论) | [Documentation](../README.md)

</div>

**Conclusion:** the port implements the core SAF filtering sequence, but it is
not a literal, bitwise-equivalent MATLAB backend. Confirmed endpoint projection
and index/weight bookkeeping defects have been corrected. The three audited
real tractograms pass the stated geometry checks; biological/anatomical review
remains pending. This report does not certify every streamline as an adjacent-
gyri U-fibre or every optional route as validated.

---

## Reference and Scope

Reference: [Dmitri Shastin's MATLAB SAF](https://github.com/dmitrishastin/SAF/tree/7e2a9d152caf1cf3e6bface64e7e176faac0c14f),
commit `7e2a9d152caf1cf3e6bface64e7e176faac0c14f`. Local author sources under
ignored `third_party/SAF/` are unchanged. Local and remote upstream HEAD agree.
Original-source hashes are saved with each independent comparison.

Python facade: `tractography/saf.py`. New implementation identity:
`python-native-20261013`, saved in both manifest and QC. Resume rejects older or
missing identities. This is a native-diffusion-only port; it does not implement
the original optional structural-to-diffusion ANTs registration.

| Stage | Comparison / finding | Verification level |
| --- | --- | --- |
| GG: cortical endpoint proximity | Nearest mid-cortical vertex, local half-thickness and optional inward margin checks reviewed against `.m` | Source review and Python indexing tests, not full original-runtime numerical parity |
| HH: hemisphere eligibility | Both ends must belong to the same hemisphere; side allocation reviewed | Source review, saved-state checks on all audited tracks |
| PG: optional pial escape filter | Zero-based escape bookkeeping reviewed; empty hemispheres/no surviving chains now handled | Source review and branch fixtures; representative real runs had PG off |
| Initial-track length limit | `tckstats` length filtering precedes GWG, as upstream | Real re-filtering at 40 mm; all output lengths checked |
| Fast triangle intersection | Original signed-volume equations versus Python | 1,200 general-position synthetic pairs, exact flags |
| Complete triangle intersection | General-position flags match; boundary handling intentionally corrected | 1,200 general-position pairs plus independent edge/vertex/shared-point gold cases |
| Fast/complete cropping | Original `.m` versus Python coordinates and original-track/point indices | Exact synthetic comparisons and 128 real right-hemisphere source tracks |
| Endpoint surface vertex assignment | Coordinate/face layouts were inconsistent; original `.m` also has this ambiguity | Corrected Python verified against analytic asymmetric multi-track geometry; strict `.m` vertex parity explicitly excluded |
| Hard-split weights | Filtered weight positions were mistaken for original source positions | Corrected original-index mapping in a unit fixture; real weighted/hard-split route not run in this campaign |
| K-means search | Same nearest-cluster strategy, different MATLAB/sklearn clustering implementations | Source review; whole-pipeline cluster/output parity not claimed |

---

## Confirmed Corrections

**Endpoint projection.** Both crop modes previously combined `[all starts;
all ends]` coordinates with interleaved crossed faces. Coordinates and cropped
chains were unaffected, but the chosen vertex within the crossed face could
be wrong. The original MATLAB final lookup also mixes layouts. Python now
consistently pairs each endpoint with its own face. Existing endpoint-density,
mean-length and scalar surface maps must be recomputed, not declared valid
because their associated TCK passes geometry QC.

**Extremely short inputs.** GG previously dropped one-/two-point tracks from its
index matrices without dropping them from the original track list. Zero-filled
columns now preserve the source positions for all subsequent masks and weights.

**Split weights.** Hard-split `pre_c` addresses original whole-tractogram indices,
not the filtered weight vector. The corrected mapping retains that provenance.
Copied split weights are not freshly optimized SIFT2 coefficients.

**Optional pial filtering.** Empty hemisphere subsets no longer fail in the crop
kernel; a source with no retained pial chain is rejected. These branch fixtures
do not constitute a full real-data PG/hard/weighted route validation.

Existing complete-mode geometric corrections are intentionally retained. The
author `.m` kernel clears its computed edge/vertex flags before combining them;
reproducing that defect would contradict the documented complete-mode intent.

---

## Independent Author-Code Checks

GNU Octave **7.3.0**, in isolated image `slicer-mkcurve-reference:20261012`, executes
the **unmodified author `.m` kernels**. It is not MATLAB itself. No native Slicer
session, MRI Agent container or original scientific output was changed.

The initial strict comparison reproduced endpoint-vertex disagreement in both
crop modes. Source inspection and analytic geometry identified the upstream
layout defect. The final record separates exact author-code parity from
documented corrections; it does not turn that discrepancy into a false
whole-pipeline equivalence claim.

The synthetic campaign passes 8 exact intersection/cropping checks plus 2
independent analytic endpoint-vertex checks. The real campaign passes both
crop modes' coordinates, original-source indices and point indices for **128
uniformly selected, retained right-hemisphere source tracks**. This is a scoped
sample, not a random whole-tractogram or full-subject MATLAB reproduction.

```bash
python Testing/Python/saf_reference_acceptance.py \
  --upstream third_party/SAF \
  --output ignore/validation/saf_python_20261013/final \
  --docker-image slicer-mkcurve-reference:20261012
```

Add `--real-state`, `--real-initial` and `--sample-count` for recorded real crops.
Fixtures, original selected indices, `.mat` outputs, logs, hashes and JSON checks
are preserved beside the comparison results.

---

## Real Tractogram Audit

All three use the real HCP **100307** subject; `100307-release-candidate` is a
workspace/run name, not a different participant. All coordinates and lengths
are decoded, not inferred from screenshots. Hemisphere/surface-index checks
cover every selected track. Triangle distances cover start/middle/end points
in the stated sample; VTK coordinate comparisons use 201 uniformly selected
lines, while VTK counts cover the whole file.

| Product | Tracks | Median / P95 / max length (mm) | Triangle-proximity sample | Maximum sampled white endpoint distance (mm) |
| --- | ---: | --- | ---: | ---: |
| 6 October GUI/science acceptance | 6,436 | 19.23 / 34.61 / 39.36 | All 6,436 | 0.595 |
| Existing manuscript rendering source | 127,055 | 19.78 / 34.65 / 39.39 | 20,000, both hemispheres | 0.614 |
| New corrected re-filtering of archived 100,000 initial tracks | 13,043 | 19.78 / 34.63 / 39.39 | All 13,043 | 0.611 |

Each passed finite/positive-length checks, its 40 mm maximum, saved selected
track count, same-hemisphere flags, cortex vertex membership, source-manifest
identity, VTK count and sampled coordinate agreement. No evidence of a
whole-brain tractogram being substituted into these three SAF files was found.
The canonical files are named **`SAF.tck`**, not `saf_native.tck`; manifests record
`native_dMRI`. The filename difference alone is not a source mismatch.

The new run reuses an archived **real initial tractogram**, not a display subset,
synthetic input or an old SAF output. It inherits the reference run's filter
settings, including PG off, soft GWG and a 40 mm maximum. It does not regenerate
FODs, surfaces or MRtrix tracking. Comparing its count with a differently seeded
old run is not a measure of the correction's efficacy.

Approximately 66.7%, 67.2% and 66.9% respectively have chord/arc ratio at most
0.7. This is **descriptive curvature**, not a validated U-fibre threshold.
Minimum post-truncation lengths are approximately 0.61 mm; GWG can retain
two-point fragments, so these very short candidates need particular scrutiny at
the acquisition resolution. No values were edited, smoothed or hidden to
improve appearance. Source TCK/SD hashes are saved in the read-only audit.

```bash
python scripts/audit_saf_geometry.py \
  --saf-dir /path/to/actual/saf/run \
  --output /path/to/new/audit.json
```

The new products reside at
`ignore/validation/saf_python_20261013/refilter_100k/`, without overwriting any old
tractogram or manuscript asset.

---

## Evidence and Remaining Gates

Local ignored evidence root: `ignore/validation/saf_python_20261013/`.

| Evidence | Scope |
| --- | --- |
| `before/parity.json`, `after/parity.json` | Preserved strict endpoint-vertex mismatches before the upstream defect was accounted for |
| `final/parity.json` | Synthetic author-code comparison and independently corrected endpoint gold cases |
| `real_128_reference/parity.json` | Original `.m` cropping on real selected source tracks |
| `current_6436_geometry.json` | Recent GUI output audit |
| `manuscript_127055_geometry.json` | Existing manuscript source audit |
| `refilter_13043_geometry.json` | New corrected real re-filtering audit |
| `refilter_100k/saf_manifest.json`, `saf_qc.json`, `log.txt` | Actual inputs, port identity, options and run status |
| `unit_tests.log`, `focused_tests.log` | Python regression evidence, not biological validation |
| `unit_tests_final.log` | Final full suite: 888 tests, 885 passed and 3 explicitly skipped |
| `native_slicer/saf_product/saf_product.json` | Actual Slicer 5.10/SlicerDMRI native fiber reader and indexing helper |
| `native_slicer/saf_product/settings_isolation.json` | User and revision settings both isolated and writable |
| `native_slicer/package_resource_audit.json` | Staged package: 396 expected runtime files, no missing/changed/unsafe resources |

The focused SAF suite passes **36 tests**. The three full-suite skips are the
unconfigured heavy DDSeg subject check and two unavailable PowerShell checks;
they are not SAF successes. Package, documentation and metadata checks also
pass, within their stated scopes.

A native Slicer 5.10 test loads the new **13,043-track** VTK as
`vtkMRMLFiberBundleNode`; all loaded point coordinates are exactly equal to
the exported VTK, with no RAS/LPS mirroring. The corrected index helper also
passes in Slicer's Python. The initial ad-hoc native probe failed because the
separate SlicerDMRI shared-library path was absent; it was not a fitting error.
The final test uses the isolated acceptance launcher and explicit SlicerDMRI
library/module paths. The failure log is retained as `slicer_product.log`, not
silently relabeled as a pass. Final writable user/revision settings isolation
is independently recorded. This validates loading, not expert anatomy.

Not completed: MATLAB-runtime full-pipeline parity; cross-runtime k-means
agreement; a new independent-subject cohort; actual PG/hard-split/weighted
scientific runs; whole-path cortical depth/pial-containment analysis; expert
adjacent-gyri/U-shape validation. Old manuscript images were not automatically
replaced. Code/weights were not pushed and active Slicer installations were not
restaged or restarted in this task.

---

## 中文结论

SAF 的核心筛选顺序与原版一致，但不是 MATLAB 原码的逐位全功能复刻。
本轮修复了端点/三角面配对、极短纤维索引、拆段权重映射及 PG 空半球处理。
原版公开 `.m` 本身的端点配对和 complete 标志清零问题已明确记录，
不为了追求“完全一样”保留几何错误。

近期 6,436 条、论文来源 127,055 条，以及重算的 13,043 条真实 SAF
候选均通过本报告限定的几何检查。**没有发现明显坐标错位或混入整个全脑
tractogram 的证据，但不能保证每条均为真实相邻脑回 U-fibre。**
旧的表面密度/长度/标量投影需重算；自动 QC 不替代专家解剖核验。

DDSeg、SAF、MK-Curve 已在中英文 Markdown 明确标为 Python/PyTorch
改写或移植；PNL 掩膜明确为调用已有官方 Python，而不是重写整套 PNLpipeline。
