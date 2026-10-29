<h1 align="center">Installation And Workflow Refinements</h1>
<p align="center"><a href="../../README.md">Home</a> · <a href="../setup/QUICKSTART.md">Quick start</a> · <a href="PRODUCT_POLISH_20261028.zh-CN.md">简体中文</a></p>

---

## Scope

This October 28, 2026 update improves installation verification, selected-backend
dependency checks and real-data onboarding. It also includes the recent CLI,
manuscript, figure and website changes. Existing scientific QC gates remain in
place.

## Reference Projects

| Reference | Pattern applied here |
| --- | --- |
| [SlicerTotalSegmentator](https://github.com/lassoan/SlicerTotalSegmentator) | A small first-use example and preparation of selected capabilities |
| [SlicerNNUnet](https://github.com/KitwareMedical/SlicerNNUnet) | Separation of native Slicer integration from model/runtime preparation |
| [SlicerDMRI](https://github.com/SlicerDMRI/SlicerDMRI) | Reuse of native diffusion modules and diffusion-image metadata |
| [Official Self Tests](https://slicer.readthedocs.io/en/latest/developer_guide/modules/selftests.html) | Verify the registered module test inside the actual application |

These are integration patterns; their algorithm implementations are not copied
or renamed in this update.

---

## Changes

**Agent-assisted installation.** The portable
[installation Skill](../../.agents/skills/slicerdspace/SKILL.md)
uses the runtime-resource staging tool, checks the actual installed import path,
opens the widget and runs its registered native Self Tests. Persistent activation
preserves other module paths and rejects conflicting DDSurfer installations.
Dependency preparation follows the user's selected analyses. Downloads, license
acceptance and restarts remain explicit user decisions.

**Backend-specific readiness.** Multi-backend checks retain a blocker map for
each tracking route. A missing MRtrix installation no longer blocks an available
UKF variant in a partial CLI run. Identical dependency probes share one result
within a check; target-specific reporting remains separate. GUI readiness still
requires all selected capabilities.

**Explicit CLI bundle source.** `--bundle-tractography-backend` selects
`csd_act`, `ukf` or `dti_det` as the source for the requested bundle backends.
Multiple tracking variants keep separate outputs; bundles run on the selected
variant. Input/parameter provenance and existing QC checks remain active.
The quick-start guide and manuscript describe subject-level `--jobs` separately
from within-subject microstructure `--max-parallel-models`.

**Lossless diffusion NRRD import.** A real upstream sample exposes DWIConvert's
unsupported `unsigned_short` input. A checked fallback converts uint16 to int16
only when all values fit, preserves diffusion/spatial metadata and records the
original failure. It does not enable lossy conversion. Larger values are rejected.
Import also refuses existing inputs unless `--force` is supplied; a dry run
does not create the subject's input directory.

**Runnable first example.** The bilingual
[Slicer Sample Data tutorial](../setup/SLICER_SAMPLE_DTI.md) uses the upstream
DWIVolume dataset through Slicer's existing Sample Data module. No imaging data
are added to this repository. The support matrix links dated Linux SDK evidence
and keeps Windows/macOS scientific acceptance separate.

**Smaller runtime package.** Figure-generation scripts and website-logo tooling
stay in the source checkout, outside the installed extension. An actual CPack
audit exposed a recursive-glob exclusion difference between CMake versions;
explicit development-directory exclusions restore Python/CMake resource parity
at 505 files. Their sources remain available for manuscript reproduction.

---

## Validation

| Check | Result |
| --- | --- |
| Python discovery | 1,571 tests: 1,566 passed, 5 skipped; final run 80.17 s |
| Real Slicer, isolated profiles | Four cases passed: asynchronous environment check, algorithm picker, compact UI and Agent installation |
| Agent installation details | Session-only activation, persistent/idempotent activation, other-path preservation and conflict rejection passed |
| Website | 131 browser checks plus guide-bot desktop/mobile cases passed; 14 static checks passed |
| Publication inventory | 197 files, 33 raster source materials; inventory check passed |
| Real Linux SDK | Configure/build, 180/180 CTest entries and CPack passed; 505 resource hashes matched |
| Actual CPack archive | Extension Manager installation passed, 20.34 s; Agent activation on the final staged resources passed, 12.43 s |
| Official diffusion example | Import and DTI completed; independent geometry, voxel, gradient and scalar-integrity audit passed |

The sample is 128 × 128 × 94 × 43, with 42 b=1,000 directions and one b0.
Import takes 15.48 s; validation/mask preparation takes 10.66 s; the native
SlicerDMRI DTI task takes 9.46 s on this configured Linux host. These are measured
step times, not a first-install benchmark or a whole-workflow speedup.

The [sample audit](benchmarks/slicer_sample_dti_20261028.json) retains source
SHA256 values, exact voxel equality after orientation, zero affine error, gradient
checks and AD/MD/RD relations. Ten raw-Trace clamp-boundary voxels are recorded;
the original values remain available. Automatic DTI QC passes; human review is
pending.

Full logs, failed attempts, isolated settings and packages remain under
`ignore/validation/product_polish_20261028/` and
`ignore/validation/slicer_sample_20261028/`. Existing Slicer and MRI Agent
sessions are not restarted. No GitHub Actions are used for this campaign.

The SDK build uses the existing genuine Slicer build tree. This host's missing
OpenGL headers and X11 development-library search paths are supplied through
process-local `CMAKE_INCLUDE_PATH` and `CMAKE_LIBRARY_PATH` pointing to the
existing development environment. No system package or user runtime is changed.
The SDK's local revision is 3838 and the installed application's revision is
34045; the installer test supplies target metadata for a local package. Catalog
server revision matching and an official package upload are outside this check.

Compact results and tested-source hashes are in the
[campaign receipt](benchmarks/product_polish_20261028.json).

## Release Boundary

The native installation check does not install every scientific backend or run
all algorithms. Windows/macOS full scientific acceptance, blank-machine setup
of all optional runtimes and human anatomical review remain separate gates.
The repository stays private.
