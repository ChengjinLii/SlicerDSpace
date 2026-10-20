<div align="center">

# Regional Analysis

**Optional postprocessing of completed, QC-eligible results**

[Project](../../README.md) | [Documentation](../README.md) | [Results](AUTOMATIC_RESULTS.md) | [中文](REGIONAL_ANALYSIS.zh-CN.md)

</div>

---

## Select Regions

Open **Advanced settings > Regional analysis (optional)**. This section is
collapsed by default and does not change the products or methods in the main run.

1. Choose **Use latest run**, or browse to a single-subject `*_orchestration_manifest.json`.
2. Select **Load regions and available results**. Only explicitly recorded completed/reused products with acceptable recorded QC and current signatures are eligible. Failed products in a partial run remain excluded.
3. Search by atlas name, hemisphere or numeric label. Check individual regions, or select the currently visible search results.
4. Choose the available analyses and click **Analyze selected regions**.

DDParcel supplies the default atlas and FreeSurfer label names. A custom integer
NIfTI atlas and optional FreeSurfer-format LUT can be selected. Statistical maps
and the brain mask must share its shape and affine: the tool does not silently
resample or register images. A connectome needs the exact atlas recorded by its
parent run, not merely overlapping label numbers.

---

## Available Analyses

| Analysis | Inputs | Result |
| --- | --- | --- |
| Microstructure | Existing DTI, FW, NODDI or DKI/MK-Curve scalar maps | Per-region mean, standard deviation, minimum, maximum, valid/excluded counts and coverage |
| ROI streamline selection | A completed full tractogram; matching SIFT2 weights when explicitly recorded | Complete selected lines, source indices, associated weights and a separate display preview |
| Regional connectivity | Existing symmetric connectivity matrix and node table | Induced selected-region matrix plus all nonzero connections from selected nodes to other parent nodes |

Available measures follow the source run; enabling this panel does **not** fit
additional models. DTI includes FA/MD/AD/RD and recorded eigenvalue/trace maps.
FW tissue maps and NDI/ODI require explicit tissue-validity masks. DKI statistics
use raw scalar maps with their validity mask, not display-clipped images;
MK-Curve corrected maps use recorded per-metric masks when available.
Finite zero values remain legitimate observations. Excluded fits do not enter
the denominator; a region with no valid estimates is blank/null, never zero-filled.

Four streamline rules are available:

- **Pass through any** selected region: union of region intersections.
- **Pass through all** selected regions: intersection of region matches, limited to 16 regions per request.
- **At least one endpoint** in the selection: endpoint membership in the selected-region union.
- **Both endpoints** in the selection: both endpoints in the union, not necessarily in different regions.

Through-region rules use DIPY's [line-based ROI targeting](https://docs.dipy.org/stable/reference/dipy.tracking.html#dipy.tracking.utils.target_line_based),
including segment crossings between stored vertices. The output is a geometric
subset, **not new WMQL/WMA/TractCloud anatomical bundle identification**, and
streamline count is not an axon count. Endpoint filtering is an explicit voxel
lookup, not the parent connectome's radial-assignment algorithm.

Connectome weights are not normalized, thresholded, smoothed or recalculated.
Node-table atlas labels, not sequential node indices, identify regions. Missing
edges retain the parent matrix's zero-edge convention. Directed or inconsistent
matrices are rejected instead of being silently symmetrized.

---

## Outputs And Review

Jobs run in a cancellable background process. Key outputs automatically load into
the current scene, grouped by subject, regional run and product. Repeated loads
reuse existing result nodes. The main run's latest-result reference is retained.

By default, new uniquely named output folders are created under
`05_statistics/selected_regions/<parent-run>/<timestamp-id>/`:

```text
request.json
region_analysis_manifest.json
region_analysis_qc.json
selected_regions.nii.gz
selected_regions.csv
selected_microstructure.csv / .json       # if requested
selected_streamlines.vtk                  # complete matching geometry, if nonempty
selected_streamlines_preview.vtk          # display only
selected_streamline_ids.csv               # optional matching SIFT2 weight column
selected_tractography.json
selected_connectome_matrix.csv
selected_region_connections.csv
selected_connectome.json
```

VTK exports contain RAS-mm geometry, not copied tensor/point arrays. Source
indices retain the link to the original file. Full output coordinates are
written as doubles without clipping or resampling. The reproducible preview is
bounded to 30,000 lines and 1,000,000 points and is **not** a measurement input.
The scene records its full quantitative source separately.

FreeSurfer LUT foreground colors are made opaque in the scene's display table;
the original LUT and labels are not edited. Without a LUT, selected labels use
a deterministic display palette. Dense Slicer color tables support label IDs
up to 1,000,000 here; larger quantitative IDs remain valid exports but are not
silently relabelled for display.

Zero matching lines produce an explicit zero count and no fabricated tractogram.
Source/QC files are fingerprinted before and after processing; changes invalidate
the result. Existing output folders are not overwritten. A cancelled/incomplete
job is not accepted as completed. **Postprocessing consistency is not new upstream
fit validation or human anatomical approval.** Coverage and anatomy still require review.

---

## CLI And Verification

The same backend is available outside the GUI:

```bash
python scripts/analyze_regions.py --inspect /absolute/run_orchestration_manifest.json \
  --catalog /absolute/catalog.json
python scripts/analyze_regions.py --request /absolute/request.json
python scripts/validate_region_analysis.py /absolute/region_analysis_manifest.json \
  --report /absolute/independent_check.json
```

A request specifies `source_manifest`, positive integer `selected_labels`,
available `metrics` keys, optional task keys `tractogram` and `connectome`,
`tract_rule`, and a fresh `output_dir`. Optional atlas/LUT overrides and catalog
hashes are supported. The GUI writes this request automatically.

Native Slicer tests cover background execution, EN/ZH labels, 440-pixel layout,
label IDs above 1000, automatic result loading and duplicate reuse. Independent
checks compare regional statistics with direct Boolean-mask calculations,
every exported streamline with its recorded original, and exported connectivity
weights with the parent matrix. These checks do not establish clinical validity.

The [20 October validation record](../release/benchmarks/regional_analysis_20261020.json)
includes a real million-streamline HCP-YA case and separates postprocessing time
from upstream model fitting; it is not an algorithm-speedup benchmark.
