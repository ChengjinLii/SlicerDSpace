# Validation Report: 2026-08-16

This report records the final Linux full-route validation performed for the
current SlicerDDSurfer release candidate. The implementation changes are in
commit `336ff7f`. Testing used Linux x86-64 and 3D Slicer 5.10.0. Windows and
macOS scientific execution are intentionally outside this release gate.

No existing experiment container was reused. The new DDSeg executions ran on
CPU so that they did not interfere with GPUs occupied by other workloads.

## Resolved Defects

- TractCloud now consumes the SAF tractogram produced by the same run when SAF
  and TractCloud are selected together. It no longer falls back to a stale
  tractogram from another run, and it blocks if the current SAF output is not
  produced.
- Explicitly configured or automatically discovered WMA, TractCloud,
  FreeSurfer and Slicer paths now satisfy the environment doctor. A complete
  full-route preflight reported 15 runnable targets, no blocked targets and no
  missing required dependencies.
- Reusing a run name now archives its previous run plan and orchestration
  manifest under `outputs/00_run_metadata/history/<run-name>/<timestamp>/`
  before writing the new records.
- The scientific-output auditor accepts an explicit run name and now checks
  Free Water, NODDI, SAF, WMQL, WMA, TractCloud, streamline-count connectomes
  and SIFT2-weighted connectomes. It also verifies that WMA and TractCloud use
  tractograms produced by the intended routes.
- DDSeg now writes a versioned `ddseg_qc.json` contract. Resume requires this
  QC record and valid normalized probabilities, preventing pre-fix score maps
  from being mistaken for current probability outputs.
- Automatic DICOM and NRRD preparation correctly falls back to Slicer's
  DWIConvert route when conversion is required.

## Inputs and Model Assets

The public `SlicerDDSurfer-models` source was downloaded into an isolated test
asset root. All 29 files in the `core` profile passed size and SHA256
verification. The downloaded tree occupies approximately 0.9 GB:

```text
/data/chengjin/SlicerDDSurfer-validation/linux_acceptance_20260813/model-assets-core
/data/chengjin/SlicerDDSurfer-validation/linux_acceptance_20260813/model-assets-core-download.log
```

Representative deidentified DICOM input passed automatic import and data
audit. The resulting DWI had shape `104 x 104 x 60 x 31`; 31 b-values, a
`3 x 31` b-vector table, finite image values and a binary mask were confirmed:

```text
/data/chengjin/SlicerDDSurfer-validation/linux_acceptance_20260813/dicom-auto-import-v1/data_audit.json
```

Representative NRRD input also passed automatic import and audit. The result
had shape `112 x 112 x 64 x 66`; 66 b-values, a `3 x 66` b-vector table,
finite values and a binary mask were confirmed:

```text
/data/chengjin/SlicerDDSurfer-validation/linux_acceptance_20260813/nrrd-auto-import-v1/data_audit.json
```

## DDSeg Revalidation

Historical DDSeg files generated before probability normalization was fixed
contained unbounded model scores. They were preserved separately for diagnosis
and removed from the reusable current-output contract:

```text
/data/chengjin/SlicerDDSurfer-validation/linux_acceptance_20260813/ddseg-legacy-20260608
```

DDSeg was then executed again through the production command-line route on
CPU. The run completed in approximately 10 minutes and produced 740,916
foreground voxels. The QC contract confirmed finite bounded probabilities,
probability/label agreement of `1.0`, and a valid tissue-probability mass for
every foreground voxel. World-space overlap between the input mask and DDSeg
foreground was `1.0`:

```text
/data/chengjin/SlicerDDSurfer-validation/linux_acceptance_20260813/ddseg-current-cli-v1
/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/03_structural/ddseg/ddseg_qc.json
```

The formal command-line result exactly matched an independent CPU rerun. The
current labels differed from the historical pre-fix labels only at 805
boundary voxels, approximately 0.02% of the volume.

## Full Scientific Route

The representative subject was executed with run name
`linux_acceptance_20260813_full`. Existing validated preprocessing,
anatomical and microstructure products were reused; seven downstream routes
were executed in approximately 78 minutes:

```text
CSD/ACT and SIFT2: approximately 2 minutes
WMQL: less than 1 minute
SAF: approximately 38 minutes
WMA: approximately 36 minutes
TractCloud: approximately 1 minute
Two connectome routes: less than 1 minute combined
```

The resulting route-level evidence included:

- 100,000 CSD/ACT streamlines;
- 127,055 SAF streamlines;
- 4 WMQL bundles;
- 74 WMA anatomical tracts;
- 18 TractCloud bundles;
- an 84-node connectome with 720 non-zero edges and 24,940 assigned
  streamlines;
- matching streamline-count and SIFT2-weighted connectome products.

The original execution manifest was preserved automatically when the same run
was resumed:

```text
/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/00_run_metadata/history/linux_acceptance_20260813_full/20260816T022530426866Z/linux_acceptance_20260813_full_orchestration_manifest.json
```

The resumed run completed validation and reused all 15 completed processing
tasks without recomputation. Its current manifest is:

```text
/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/00_run_metadata/linux_acceptance_20260813_full_orchestration_manifest.json
```

The expanded scientific audit evaluated 164 checks with no failures. Checks
cover file readability, finite values, dimensions and spatial transforms,
expected scalar ranges and identities, tractogram integrity, bundle outputs,
connectome outputs and cross-route input provenance:

```text
/data/chengjin/SlicerDDSurfer-validation/linux_acceptance_20260813/full-route-audit-v1/scientific_output_audit.json
```

Input validation reported no errors and two non-blocking acquisition warnings:
some b0 entries retained non-zero b-vectors, and no BIDS phase-encoding/readout
sidecar was available.

## Automated and Slicer Tests

The final fast regression passed:

```text
Ran 389 tests
OK (skipped=2)
```

The two skipped tests require Windows PowerShell and are outside the Linux
release scope. The top-level CMake contract ran with CMake 3.31.6. Python
compilation, `git diff --check`, extension metadata audit and release audit all
passed; the final release audit reported zero blockers and zero warnings.
`ruff` was unavailable in the local environment, so the optional `make lint`
command was not executed.

A copy-mode staged extension was loaded by a clean-profile Slicer 5.10.0
session. Module registration, logic construction, parameter nodes, dependency
paths, input preparation, model assets, onboarding, setup wizard and Demo
checks passed. The smoke test also confirmed that both `segmentation.pipeline`
and `segmentation.qc` were imported from the staged extension tree rather than
from the development repository.

## Validation Boundary

These results support a Linux x86-64 release candidate and research preview.
They establish workflow execution, resume behavior, input conversion, output
integrity, internal numerical consistency and provenance for the tested data.
They do not establish anatomical ground truth, clinical validity, or
generalization across centres, scanners, acquisition protocols and
populations. Broader manual QC and reference-method comparisons remain
scientific-study activities rather than software release checks.
