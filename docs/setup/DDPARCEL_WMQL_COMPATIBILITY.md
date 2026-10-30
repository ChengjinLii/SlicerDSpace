<div align="center">

# DDParcel And WMQL Label Compatibility

[Setup](../README.md) | [Regional queries](WMQL_CEREBELLAR.md) | [中文](DDPARCEL_WMQL_COMPATIBILITY.zh-CN.md)

</div>

---

## Label Conventions

DDParcel predicts 101 anatomical regions: 82 merged network classes followed by
lateralization of selected cortical regions. Training explicitly combines regional
WM into left/right `2/41` and callosal subdivisions into `192`. The absence of
regional WM labels is therefore expected for the model. The legacy `wmparc`
filename does not imply a complete FreeSurfer white-matter parcellation.

| Structure | DDParcel | Pinned official WMQL rules |
| --- | --- | --- |
| Cerebral WM | Left/right `2/41` | Some rules require cortical-region-specific `3000/4000` labels |
| Corpus callosum | `192` | `corpuscallosum.left/right` use `1004/3004` and `2004/4004` |
| Centrum semiovale / unsegmented WM | Merged into `2/41` | Author aliases reference `5001/5002` |

Missing alias territories can make official queries empty or excessively strict.
Required callosal factors in `CC`, `CC_5` and `CC_6` cannot be satisfied when their
labels are absent. The `only()` operator can also reject candidates traversing
generic WM. `CC_4` instead uses bilateral precentral endpoints and needs a separate
coverage assessment.

## Recorded Checks

- Local inference label mapping, training-label conversion and sagittal mapping
  match the author functions' ASTs at commit `257ec7c2a02209f86365dc5c0b39755458a3f776`.
- Registered and native outputs both contain the full 101 nonbackground labels,
  with no unexpected labels.
- Callosal label `192` occupies 3,814 registered and 1,754 native voxels. The grids
  have different voxel sizes; these counts should not be compared directly.
- Repeating native export with the recorded inverse transform and Slicer CLI
  reproduces every voxel and the affine exactly.
- UKF and the native labels share the spatial grid and brain mask. UKF uses the
  recorded b0 plus b~1000 subset, with b0 values and vectors explicitly zeroed in
  the working copy, rather than all 288 original volumes.

No label-mapping, native-export or common-grid error was found in these checks.
Anatomical accuracy is assessed with image review or reference-label experiments.
The [recorded audit](../release/benchmarks/ddparcel_wmql_compatibility_20261030.json)
also retains the single half-voxel-boundary rounding difference in the separate
SimpleITK implementation; the actual Slicer CLI repeat is exact.

## Selecting Inputs

WMQL QC records execution, output integrity, per-query sampling and label
compatibility separately. Valid DDParcel output does not guarantee sufficient
coverage for every official query. The current combined example retains seven
empty and ten undersampled queries at the unchanged QC threshold.

Use a reviewed, aligned atlas compatible with the selected rules, or separately
validated, explicitly named custom queries. Do not duplicate generic WM into
regional labels or remove `only()` conditions merely to increase track counts.
WMA and TractCloud do not use these DDParcel region predicates; assess their
coverage independently.

## Experimental Adjacent-WM Preparation

The CLI supports `--wmql-atlas-mode ddparcel_wm` for a separately named pilot.
The default remains `native`. The option keeps the author's rules and the native
DDParcel image unchanged, and writes a derived atlas under the WMQL output:

- Within each original cerebral WM mask, assign the nearest same-hemisphere
  cortical region's WM label up to 5 mm from its voxel centres, measured in
  scanner coordinates. More distant WM receives `5001/5002`.
- Split the existing callosal `192` territory by proximity to original left/right
  cerebral WM into `3004/4004`; equidistant voxels retain `192`.
- Preserve cortical, subcortical, cerebellar and background voxels exactly.
- Record source/output/implementation hashes, affine, units and preparation
  parameters. Changed inputs or damaged derived files invalidate reuse.

The 5-mm neighbourhood follows the scale used by FreeSurfer's WM parcellation;
this experimental volume-centre construction is **not FreeSurfer wmparc**.
`5001/5002` denote residual unsegmented WM, not a validated centrum-semiovale ROI.
Anatomical review remains pending even when sampling checks pass, and the pilot
does not receive an automatic scientific pass. No tissue mask is dilated and no
streamline is generated, duplicated or reassigned to force query coverage.

```sh
"$SLICER_LAUNCHER" --launch PythonSlicer run_subject_pipeline.py \
  --subject-root /path/to/subject --subject-id sub-01 \
  --targets parcellation,tractography,bundles \
  --tractography-backend ukf --bundle-backend wmql \
  --wmql-query-preset official_cerebellar \
  --wmql-atlas-mode ddparcel_wm --run-name wmql-territories-pilot --plan
```

Inspect the plan, then replace `--plan` with `--execute`. UKF uses the installed
UKFTractography extension. Use a separate run name when comparing with native
labels. GUI defaults and the reviewed publication illustration are unchanged.

### Paired Pilot

The same tractogram, author queries, thresholds and output inventory are used
within each pair. The original sampling minimum remains 20 streamlines.

| Subject / tracking input | Native nonempty / 51 | Derived nonempty / 51 | Native sampling passes / 51 | Derived sampling passes / 51 |
| --- | --- | --- | --- | --- |
| 100307 / UKF | 44 | 50 | 34 | 43 |
| 100206 / CSD/ACT | 39 | 51 | 32 | 48 |
| 149741 / CSD/ACT | 32 | 50 | 27 | 49 |

This is a coverage improvement, not complete acceptance. Some counts decrease:
100307 SOFF-right changes from 63 to 10; 100206 AF-left/right change from
63/27 to 15/4. Regional WM also activates the author's exclusion predicates.
These trade-offs are why the derived route remains opt-in and the publication
figure keeps the reviewed native-label result. In the UKF case, a second direct
author-engine run reproduces all 51 query results exactly; every extracted
streamline is present in the source input. Independently sampled atlas assignments
and whole-volume non-WM preservation pass across all three subjects.

See the [paired evidence and per-query counts](../release/benchmarks/wmql_territories_20261030.json).

---

Sources: [DDParcel paper](https://doi.org/10.1109/TMI.2023.3331691),
[author label conversion](https://github.com/zhangfanmark/DDParcel/blob/257ec7c2a02209f86365dc5c0b39755458a3f776/data_loader/load_neuroimaging_data.py),
[WMQL input requirements](https://tract-querier.readthedocs.io/en/latest/example_script.html),
[FreeSurfer WM parcellation source](https://github.com/freesurfer/freesurfer/blob/dev/mri_aparc2aseg/mri_aparc2aseg.cpp),
[FreeSurfer label definitions](https://surfer.nmr.mgh.harvard.edu/fswiki/FsTutorial/AnatomicalROI/FreeSurferColorLUT).
