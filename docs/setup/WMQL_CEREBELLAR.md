<div align="center">

# Regional Cerebellar Queries

[Setup](../README.md) | [CLI templates](CLI_TEMPLATES.md) | [Author WMQL](https://tract-querier.readthedocs.io/en/latest/example_script.html) | [中文](WMQL_CEREBELLAR.zh-CN.md)

</div>

---

## Select A Preset

| Preset | Outputs | Scope |
| --- | --- | --- |
| `official` (default) | 48 | Unchanged author bundle queries |
| `official_cerebellar` | 51 | The same 48 queries plus three SlicerDSpace regional selections |
| `cerebellar` | 3 | Regional selections only |

In Slicer, choose **Advanced settings > Model parameters > WMQL definition**.
No extra model or runtime is needed. The CLI accepts the same choice:

```bash
"$SLICER" --launch PythonSlicer run_subject_pipeline.py --no-user-config \
  --subject-root /path/to/subject --subject-id SUBJECT --output-root /path/to/results \
  --targets validation,parcellation,tractography,bundles --tractography-backend ukf \
  --bundle-tractography-backend ukf --bundle-backend wmql \
  --wmql-query-preset official_cerebellar --plan
```

Confirm the plan, then replace `--plan` with `--execute`. To select only the new
outputs, use `--wmql-query-selection cerebellar_brainstem,cerebellar_bilateral`.
Keep different presets in separate runs/output directories.

## Definitions

The inputs are the original whole-brain tractogram and aligned, native-space
FreeSurfer-compatible labels: cerebellar WM/cortex `7/8` and `46/47`, brainstem
`16`. The author Tract Querier executes the queries without modifying tracks,
resampling the label image or adding streams from another method.

| Output | Required anatomy |
| --- | --- |
| `cerebellar_brainstem.left` | Left cerebellar endpoint; both endpoints in left cerebellum or brainstem; left cerebellar WM and brainstem traversal; no right cerebellar or supratentorial endpoint/crossing |
| `cerebellar_brainstem.right` | Homologous right-side conditions |
| `cerebellar_bilateral` | One endpoint in each cerebellar hemisphere; bilateral cerebellar WM and brainstem traversal; no supratentorial endpoint/crossing |

These are broad regional streamline candidates. Their labels do not identify
individual ICP/MCP/SCP tracts or establish synaptic connections. Peduncle-specific
work requires additional anatomical waypoints and corresponding review.

Crossings retain the author's default `2.0` threshold: the proportion of sampled
points **per label**, not millimetres. Endpoint exclusions are evaluated separately.
Query sources and every imported file are snapshotted and hashed. The combined
wrapper imports the original rules first, then the extension definitions without
re-importing label aliases; this preserves the original CST and hemisphere sets.

## Recorded Run

The official rules and DDParcel use different WM/callosal label conventions;
see [label compatibility](DDPARCEL_WMQL_COMPATIBILITY.md) before interpreting missing bundles.

The retained UKF example contains 277,875 input streamlines. The combined run
takes 19.57 seconds and yields 44 nonempty outputs, including 315 left
cerebellar--brainstem, 436 right and 432 bilateral candidates. All three exceed
the unchanged local sampling minimum of 20 streamlines.

Checks compare all original 48 outputs with the earlier official run, all 51
queries with a direct author-engine invocation, and each new output with an
independent evaluation of the complete input tractogram. They also check exact
source membership, finite positive geometry, input hashes and frozen queries.
The original seven empty and ten sparsely sampled official outputs remain
recorded; the combined run does not become an all-bundle QC pass.

See the [independent regional audit](../release/benchmarks/wmql_cerebellar_20261030.json),
the [coverage audit](../release/benchmarks/wmql_coverage_20261030.json) for the
original preset and the reproducible checks in `scripts/audit_wmql_cerebellar.py`
and `scripts/validate_wmql_official.py`.

---

The Results illustration includes the actual three new selections with a
method-specific colour key. The figure caption distinguishes them from the
unmodified official bundles. Human anatomical review remains separate from
execution, rule agreement and sampling checks.
