# Validation Report: 2026-08-12

This report records the Linux release-focused validation performed on a Linux
x86-64 workstation using 3D Slicer 5.10.0. The tested release changes were
developed on top of commit `8cddb96` and are included with this report.

The release scope documented here is Linux x86-64. Windows and macOS retain
portable discovery/install-plan code, but their complete scientific workflows
are outside this release gate and are not release blockers.

## Resolved Defects

- The beginner Demo now clears every non-Demo target, regenerates its private
  synthetic input and resets its streamline budget. A previous
  `surface_postprocess` selection can no longer block the DTI-only Demo.
- Tractograms load as SlicerDMRI fiber bundles when that reader is available and
  fall back to `vtkMRMLModelNode` when it is not. The fallback was exercised in
  a Slicer session without TractographyDisplay.
- The environment-dialog smoke test now distinguishes a fully ready environment
  from one that legitimately exposes per-item install buttons.
- A rooted, clean extension archive can be installed through Slicer's real
  `qSlicerExtensionsManagerModel`; the module is then registered, loaded and
  available.
- An explicit MRtrix bin directory is propagated through optional brain-mask
  generation and input validation.
- DDParcel uses the selected logical CUDA device instead of hard-coding GPU 0.
  This closed two failures observed while running a subject on `cuda:1`.
- A failed orchestration now writes a final `status=failed` manifest containing
  the exception type/message and the tasks completed before failure.
- DTI deterministic tracking now applies an explicit, configurable
  `10–250 mm` saved-streamline filter. DIPY 1.11 point-count limits and DIPY
  1.12 millimetre limits are translated separately. The previously accepted
  but unimplemented `probabilistic` label is rejected instead of silently
  producing deterministic output.
- Scientific-output auditing follows the structural tasks selected in the
  orchestration manifest. A DDSeg-only run no longer fails because DDParcel or
  DDSurfer was not selected.

## Automated Regression

The complete Python test matrix passed with no skips:

```text
Ran 376 tests
OK
```

The local regression used CMake 3.31 and also exercised the existing portable
dependency-plan unit tests. GitHub Actions remains an Ubuntu release gate for
the supported Linux x86-64 scope.

The final unified release report is:

```text
/tmp/sdd-release-final-20260812-v2/release_validation_report.json
```

It contains 24 steps: 23 executed and passed; only the in-report fresh-clone
step was skipped because the fixes were uncommitted. A separate fresh clone of
an exact temporary Git snapshot of the working tree then passed. Passed steps
include:

- single-subject all-target planning and WMQL/WMA/TractCloud backend plans;
- eight-subject batch validation planning;
- output-tree and representative-output generation;
- repository, core/all asset and independent core/all mirror verification;
- top-level CMake contract, copy staging and rooted archive packaging;
- staged-module and real Extension Manager installation;
- dependency setup, Demo, environment dialog, run-plan, output-tree and cancel
  Slicer smokes.

The real Extension Manager smoke confirmed a clean rooted archive, successful
installation, module registration, module loading and module availability.
The binary Slicer distribution on this host does not include
`SlicerConfig.cmake`; a full CMake/CPack build against a Slicer SDK therefore
remains separate from the validated package-install path.

## Slicer Demo

The final headless Slicer Demo completed exactly these tasks:

```text
validation: passed
microstructure.dti: completed
tractography.dti_det: completed
```

The FA map loaded into the scene. Without SlicerDMRI TractographyDisplay, the
TRK file loaded through the model-node fallback. A separate earlier smoke with
SlicerDMRI available loaded it as a fiber-bundle node.

## Multi-subject Input and Scientific Checks

Eight PPMI-derived subject fixtures passed real input validation after missing
masks were generated with the explicitly configured MRtrix installation:

```text
3124, 3161, 3166, 3185, 3387, 3390, 3551, 4037
```

The generated masks were binary, finite and matched their DWI shape and affine.
Evidence is under:

```text
/data/chengjin/SlicerDDSurfer-test/ppmi-multisubject-validation-v2-20260812
```

Four subjects (`3124`, `3161`, `3166`, `3185`) then completed DTI scalar
generation and deterministic tractography with the new length filter. All four
passed the automated scientific audit:

```text
/data/chengjin/SlicerDDSurfer-test/ppmi-dti-tractography-filtered-20260812/00_batch_metadata/scientific_output_audit.json
```

The saved tractograms retained 2,473–2,683 streamlines per subject. Their
minimum lengths were approximately 10 mm, maximum lengths were 144–186 mm, all
points were finite and within DWI world-space bounds, and the saved TRK counts
and length extrema matched QC. DTI maps were finite and spatially aligned; FA
was within `[0,1]`, eigenvalues were ordered and scalar identities passed.

Two subjects (`3124`, `3161`) completed DDSeg, DDParcel and DDSurfer. Both
passed the structural audit:

```text
/data/chengjin/SlicerDDSurfer-test/ppmi-anatomy-20260812/00_batch_metadata/scientific_output_audit.json
```

Each DDParcel output contained 101 non-zero labels. DDSeg foreground overlap
with the native mask after world-space resampling was 1.0, and all four
white/pial surfaces per subject passed finite geometry, extent and mesh-size
checks.

The earlier representative Linux closure remains valid for DICOM import,
MRtrix/FSL preprocessing, DDSurfer post-processing, Free Water, NODDI,
CSD/ACT, SIFT2, SAF, WMQL, WMA, TractCloud and connectome. See
`VALIDATION_20260725.md` in the local validation evidence directory referenced
by `RELEASE_CANDIDATE_VALIDATION.md`.

## Model Assets and Fresh Clone

The independent local model mirror passed SHA256 and size verification for all
34 manifest files. The public sentinel download and checksum test also passed.
A public Git fresh-clone smoke passed separately against the then-current
remote `main`. An exact temporary Git snapshot of this working tree also passed
clone, checkout, sentinel download, checksum verification and all 376 fast
tests; its report is:

```text
/tmp/sdd-final-snapshot-VFcoP7/fresh/fresh_clone_smoke_report.json
```

The temporary snapshot is not a published revision, so hosted CI must still
rerun after the real commit is pushed.

Four optional conversion-test NIfTI files were published to the independent
`SlicerDDSurfer-models` repository in commit `ffc0ff4`. A clean URL download of
the `test-fixtures` profile retrieved all four files from GitHub and passed
their size and SHA256 checks. The public manifest `all` profile is therefore
complete at the time of this validation.

## Remaining Validation Boundary

This version is a Linux x86-64 release candidate and research preview. It must
not be described as scientifically validated for every scanner or population.
Remaining release evidence is:

- run GitHub Actions on the committed revision and confirm the Ubuntu checks
  are green;
- rerun fresh-clone smoke on that same revision;
- build with a complete Slicer SDK/CMake environment if CPack-generated
  Extension Index packaging is required;
- perform broader multi-centre, multi-scanner and population-level manual QC
  and reference-method comparisons.

The current automated checks establish execution integrity, file readability,
finite values, spatial consistency, internal scalar identities, deterministic
reproducibility and output provenance. They do not establish anatomical ground
truth or clinical validity.
