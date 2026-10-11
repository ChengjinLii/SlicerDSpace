# Linux Slicer Acceptance: 2026-10-07

## Scope And Evidence

This campaign tests the installed extension inside real **3D Slicer 5.10.0**
on Linux, including native **SlicerDMRI** result loading. Scientific execution
is initiated by the module's Run button, not by a mocked backend. GUI-only
lifecycle tests use controlled workers to exercise failure/cancellation paths;
they do not supply scientific results.

The tested worktree is based on `e0efc16ade9c614629c29bd794599797c3e57cfd`
and includes the pending DDSurfer synchronization to upstream
`a4ec44cf56651b411ab30b9c91cfac63cc3b2300`. Each GUI launch records the base
commit, working-tree patch hash, test-script snapshot/hash, package hash,
command, log and exit status. These changes have not been committed or pushed
as part of this acceptance task.

Local evidence is retained under
`ignore/validation/slicer_acceptance_20261006/`. Failed attempts remain there;
the final reports identify the successful corrected attempts rather than
overwriting their logs. Temporary folders, output roots and X displays are
isolated. The final harness additionally isolates both settings stores,
the cache, extension installation and DICOM database paths. Earlier attempts
isolated ordinary user settings but encountered read-only revision settings
in the shared portable Slicer installation; those failed setting writes did
not change its configuration. Existing interactive Slicer/MRI Agent sessions and
unrelated training processes were not restarted or terminated.

Real scientific inputs were copied and hashed from HCP subjects **100307**
and **149741**, plus the existing deidentified DICOM validation fixture.
The original input files were not modified. WMA uses the real, existing
100,000-streamline UKF tractogram for 149741, not a mislabeled CSD input.

## Fixes Verified During The Campaign

| Issue | Correction | Verification |
| --- | --- | --- |
| Installed batch jobs pointed at a repository-only wrapper | Use the shipped `shared/run_subject_pipeline_cli.py` entrypoint | Two actual subject jobs launched from the Slicer batch UI; independent DTI QC |
| Installer descendants survived cancellation/teardown | Retain the launch process-group identity, terminate descendants even after the leader exits, disconnect teardown callbacks | Real SIGTERM-ignoring child tests for installer cancellation and shutdown |
| Cancel followed immediately by application quit could leave children | Synchronous cleanup of pending cancelled process groups before Qt exits | Actual Slicer Cancel-then-Quit pressure test |
| Core model checksum/lockfile operations ran synchronously | Use the cancellable background setup job | Real core verification, lockfile export, sentinel download and Qt heartbeat |
| CSV/TSV results loaded but were not tracked as result nodes | Include `vtkMRMLTableNode` alongside displayable nodes | Actual CSV/TSV loading, scene save/reload, reuse, append, replacement and run clearing |
| Bundle viewing could scan unrelated outputs | Resolve only the selected successful task's declared bundle files; record explicit WMA anatomical files | Real WMQL/TractCloud/WMA scene tests and stale/failed-output regressions |
| A next run could start before a previous finish callback returned | Keep Run disabled through result loading and release the old handle before reenabling it | Consecutive real scientific runs and reentrant completion assertions |
| Reenabling Run hid the final cancelled/completed status | Refresh input validity/button state without replacing terminal status | Actual cancellation smoke rerun and status regression |
| Running another tracking backend moved prior run products to cache | Do not automatically archive alternate tractograms during normal orchestration | Recompute DTI tracking while retaining all five prior CSD outputs at unchanged paths/SHA256 |
| Resumed connectomes omitted viewable products from the run record | Include matrix and nodes paths in skipped/reused task outputs | Real resumed count/SIFT2 connectomes load four tables |
| Raw MRtrix QC confused label extent with anatomical node count | Record network `node_count` separately from `dense_node_count` | Real 84-node connectome with 2035-row label-indexed storage; dense/edge-list QC regressions |
| Independent preprocessing audit did not scan output image values | Scan every output volume for NaN/Inf, verify nonzero brain signal, spatial affine and non-negative b-values | Real output re-audit and injected NaN/Inf, empty-signal and invalid-b-value regression tests |
| FSL QC incorrectly reported that denoising was omitted | Record actual configured MRtrix/FSL operations and disclose bias-field omission; preserve mask provenance on cache reuse | Real installed-Slicer cache refresh: image, gradients and mask SHA256/mtime unchanged; correct TOPUP/denoising status |
| Preprocessing resume ignored the selected backend/settings | Match the original input/configuration/executable fingerprint in both the run plan and execution gate | Actual installed-Slicer plan: identical configuration reused; backend, eddy model and force changes scheduled for execution |
| Failed preprocessing attempts could reuse leftover files | Require a completed/cached manifest; rebuild cache misses with overwrite flags and fresh eddy scratch | Failed/running-residue regressions with a backend fixture that refuses accidental overwrite |
| Direct anatomy resolution could accept preprocessing from changed raw inputs | Validate recorded raw image/gradient/mask signatures before selecting the processed bundle | Changed-gradient and malformed-fingerprint regressions |
| CTest's hand-maintained unit list omitted suites | Register all `test_*.py` suites | CMake configuration-contract test checks every discovered suite |
| Portable Slicer revision settings bypassed `XDG_CONFIG_HOME` | Use a private runtime home through launcher additional settings; verify both actual settings filenames and writable status before each smoke test | Real startup probe and final installed-extension reruns; shared installation configuration remains untouched |

The shared postprocess target flag was also deduplicated. Its checkbox already
selected the correct route; this is a refactor, not a newly discovered dispatch
bug. A SAF test configuration needed an explicit seed image in its custom
MRtrix option string; the normal generated GUI seed configuration was intact.

## Execution And QC Results

The final unit-discovery run executed **693 tests: 691 passed and two Windows
PowerShell tests were skipped**. The configured CMake test checks registration
against a mock SDK contract; it is not a full Slicer SDK build. The final
installed-extension GUI acceptance passed **12 of 12 checks** after correcting
the Extension Manager test's stale installed-item cache, with separate real
input import, batch, model-resource and scientific-result tests.

All **10 scientific cases passed independent automatic QC**, comprising
**457 checks with no failed checks**. A fresh installed-extension instance
loaded all 10 cases successfully, with **180 MRML nodes across the separate
case scenes**, including 74 native SlicerDMRI WMA fibre bundles. Preprocessing
cases intentionally have no loaded result nodes. Execution, automatic QC and
human anatomical review are separate states; human review remains pending.
Additional scene checks confirm **127 nonempty polydata objects with finite
coordinates**, including the actual reconstructed surfaces and fibre bundles.
They record RAS bounds and streamline/point counts without altering the data.

The consolidated `final_acceptance.json` links the selected passing attempts
and hashes their source reports. It does not delete the initial installation
test failure: the fixture changed the Extension Manager settings path without
refreshing its cached installed-item list. The corrected fixture calls
`updateModel()` and verifies the private install root is empty before performing
the real local installation.

| Scientific case | Input | Evidence / interpretation |
| --- | --- | --- |
| DDSeg, DDParcel, DDSurfer and complete surface postprocessing | 100307 | All selected tasks completed, including 9/9 real FreeSurfer postprocessing stages; DDSeg/DDParcel WM overlap Dice approximately 0.861 |
| DTI, CSD-ACT, SIFT2, WMQL and Python connectomes | 100307 | 50,000 CSD streamlines; count and weighted connectomes use the 84-node grey-matter subset; original Python numerical tables/QC were snapshotted before later backend runs |
| Free-water and AMICO NODDI | 100307 | Finite maps and separate validity masks; approximately 84% free-water tissue validity and 92% NODDI validity; excluded tissue values are not silently presented as valid fits |
| TractCloud | 100307 | Real classifier output: 38 readable/nonempty bundle files containing 22,897 assigned streamlines; native SlicerDMRI loading |
| SAF | 100307 | Real surface-based filtering retains 6,436 streamlines from a 50,000-streamline candidate set; independent length/geometry/QC checks |
| Deterministic DTI tracking | 100307 | Actual 5,000-seed run, count connectome and unchanged previous CSD products |
| MRtrix count and SIFT2 connectomes | 100307 | Both recomputed with `--no-resume`; actual MRtrix backend/QC checked, not just a reused Python result |
| Connectome resume | 100307 | Both tasks explicitly skipped/reused and all four result tables available |
| DIPY preprocessing | DICOM fixture | MP-PCA, Gibbs removal, motion correction, output gradients and mask; independent QC passed |
| FSL/MRtrix preprocessing | DICOM fixture | Reverse-phase baseline pair, TOPUP and CPU eddy completed; independent image/gradient/mask QC passed; cached QC refresh does not alter scientific outputs |
| WMA | 149741 / UKF | Actual 10/10 ORG registration iterations, 800 atlas clusters, outlier removal, hemisphere separation and native-space anatomical output; 74/74 readable/nonempty bundles containing 40,338 streamlines; independent QC passed |

All WMQL outputs in this bounded smoke run are readable/nonempty, but AF has
only one streamline per hemisphere and CST has 11/14. This is **not sufficient
for anatomical accuracy or reliable bundle quantification**. The validation
checks software execution and result integrity; it does not justify using this
50,000-streamline smoke configuration as a final scientific acquisition.

Preprocessing-only cases intentionally load no MRML result nodes: the loader
leaves four-dimensional diffusion series and their gradient metadata as
disk-backed inputs for subsequent stages. Their output images, masks and
gradients are independently audited. This does not mean that the preprocessed
diffusion series is automatically opened in a Slicer diffusion viewer.

The MRtrix/FSL command sequence applies MP-PCA, Gibbs removal and eddy;
TOPUP requires the reverse-phase baseline pair. It currently does not include
bias-field correction. The QC report now explicitly records this omission
instead of falsely warning that denoising was skipped. The real FSL fixture
has approximately 0.48% slice/volume outlier flags and a maximum reported
movement RMS of approximately 0.34 mm. These are diagnostic observations,
not population-level thresholds or a substitute for visual review.

### Backend Agreement

The independently computed Python and MRtrix count matrices have identical
node ordering, nonzero edge pattern and values. Weighted edge patterns are
also identical. The initial weighted comparison has a maximum absolute
difference of approximately `0.000554` and maximum relative difference of
approximately `0.00000467`; the acceptance bounds are `rtol=1e-5`,
`atol=1e-7`. The count comparison requires exact equality.

MRtrix 3.0.8 switches to float storage when the maximum node index is at least
1024, so DDParcel's high-valued labels trigger this path even though there are
only 84 actual nodes. This interpretation is based on the matching official
[tck2connectome source](https://github.com/MRtrix3/mrtrix3/blob/3.0.8/cmd/tck2connectome.cpp)
and [matrix threshold definition](https://github.com/MRtrix3/mrtrix3/blob/3.0.8/src/dwi/tractography/connectome/matrix.h).
Small floating-point accumulation differences are not described as bitwise
agreement. Source hashes, values and tolerances are retained in
`connectome_backend_parity.json`.

### Evidence Locations

Paths below are relative to the local validation directory.

| Record | Coverage |
| --- | --- |
| `final_acceptance.json` | Consolidated 12 passing GUI checks, 10 passing scientific cases/457 independent checks, 180 loaded MRML nodes, 127 finite/nonempty geometry objects and unit-test totals; source report hashes and superseded failure retained |
| `unit_tests_isolated_release.log` | 693 tests, 691 passed, two Windows-only skips; configured CMake contract, cache invalidation, settings isolation and actual-subject DDSeg world-QC check |
| `isolated_release_gui/gui_acceptance.json` | 11 passing installed GUI/lifecycle checks; original Extension Manager fixture failure retained; private settings verified per launch |
| `isolated_install_verified_gui/gui_acceptance.json` | Corrected actual local Extension Manager installation/loading, with private settings and refreshed installed-item cache |
| `input_verified_gui/input_preparation/input_preparation.json` | Real NIfTI, diffusion NRRD and deidentified DICOM import through the GUI; NIfTI/NRRD round trips also require signed gradient-vector agreement |
| `batch_fixed/`, `batch_scientific_qc.json` | Two actual subject batch DTI jobs and independent audits |
| `models_full_gui/model_assets/model_assets.json` | 31 core files, GUI verification/lockfile, local reuse and public sentinel download/checksum |
| `cancel_then_quit_verified/gui_acceptance.json` | Latest-code rerun: quit before the delayed force-kill callback can run |
| `science_gui/real_tasks/` | Initial completed anatomy, free-water/NODDI and TractCloud case records |
| `final_science_gui/real_tasks/` | SAF and consecutive preprocessing/WMA dispatch after the completion-race correction |
| `retention_resume_gui/real_tasks/` | DTI run-retention hashes and resumed connectome loading |
| `mrtrix_qc_gui/real_tasks/` | Forced actual MRtrix execution and corrected raw matrix QC metadata |
| `final_scientific_qc/anatomy_dti_csd_wmql_connectome_18ffd181/` | Original Python tables/QC, preserved before the MRtrix routes overwrote shared numerical filenames |
| `verified_scientific_qc/` | Latest independently audited case set, including full preprocessing finite-value scans, hashed source files and QC/numerical snapshots |
| `preprocessing_cache_verified_gui/preprocessing_cache/` | Latest installed-code QC correction, preserved before/after reports, and unchanged real image/gradient/mask hashes and mtimes |
| `preprocessing_resume_verified_gui/preprocessing_cache/` | Same real FSL output, with explicit matching/changed-backend/changed-parameter/force run-plan assertions |
| `preprocessing_button_resume_gui/real_tasks/` | Actual Run-button reuse with the matching FSL configuration; preprocessing task explicitly skipped and all four scientific output hashes unchanged |
| `fsl_diagnostics_audit.json` | Independent finite-value scans of actual eddy residual/CNR and TOPUP field/coefficient images, with observed motion/outlier diagnostics |
| `release_scientific_qc/` | Final independent audit using corrected preprocessing QC records |
| `isolated_results_verified_gui/results/results.json` | Private-settings installed-extension loading: 10/10 case scenes and 180 MRML nodes; native fibre classes, loading decisions and screenshots |
| `geometry_results_gui/results/results.json` | Additional actual-loaded polydata checks for finite coordinates, nonempty geometry, streamline counts and recorded RAS bounds |
| `connectome_backend_parity.json` | Exact count agreement and explicitly bounded weighted agreement between independently executed Python and MRtrix backends |

The initial case manifests remain available even when a later route updates
the common subject-level run filename. Final case auditing records the current
on-disk products; original Python-backend comparison uses its earlier immutable
table/QC snapshots, not those subsequently overwritten files.

## Reproduction

`scripts/slicer_acceptance.py` stages a copy, packages it and launches each
configured test in its own Slicer settings/temp/X display. Example:

```bash
python3 scripts/slicer_acceptance.py \
  --report /path/to/isolated-validation/gui \
  --slicer /path/to/Slicer \
  --xvfb /path/to/xvfb-run \
  --assets /path/to/model-assets \
  --subject /path/to/isolated-subject \
  --additional-module-paths /path/to/SlicerDMRI/qt-loadable-modules \
  --tests extension_install environment_button gui_operations \
          dependency_workflow demo_workflow run_plan_panel cancel_background \
          output_tree_button surface_coordinate extension_manager_install \
          shutdown setup_tree
```

The harness asks the launcher for its runtime location, links only the
read-only runtime assets into a private home and supplies that home through
`--launcher-additional-settings`. Revision settings and installed extensions
remain private writable directories. It disables unsolicited update/dependency
installation in the test profile. A bootstrap records the resolved user and
revision settings paths/status and refuses to run a test if either is shared
or unwritable. This also handles portable builds that store revision settings
in application home rather than in `XDG_CONFIG_HOME`; see the official
[Slicer settings implementation](https://github.com/Slicer/Slicer/blob/v5.10.0/Base/QTCore/qSlicerCoreApplication.cxx).

`Testing/Python/prepare_slicer_acceptance_cases.py` copies/hashes available
real HCP/DICOM fixture inputs and writes scientific case configurations.
Inspect the external atlas, WMA and TractCloud paths for the local installation;
the helper does not download or invent missing datasets. Use
`--tests real_tasks --tasks-config /path/to/cases.json` to execute these cases.
`--cases` selects subsets; `--check-run-retention` verifies preexisting CSD
products during a new DTI run. Preparation may require substantial disk space.

`scripts/audit_slicer_acceptance.py` accepts multiple case reports, preserves
QC/numerical snapshots and independently redecodes scientific products.
`--wait-for-passing` allows corrected attempts to finish without masking
initial failures. `Testing/Python/slicer_results_smoke.py` reloads all declared
successful products into the real Slicer scene and checks native fibre-bundle
classes where SlicerDMRI is registered.

## Validation Boundary

The tested scope is Linux only, as requested. No Windows/macOS scientific
validation is claimed. Local Extension Manager installation of a staged archive
is tested; it is not a full Slicer SDK CMake/CPack build, an Extension Index
review, or a published-store installation. The full SDK is not installed.

Core model resources were verified locally and the public sentinel download
was tested. This does not imply that every optional external atlas/model was
freshly downloaded or that every possible dependency installation was tested
from an empty operating system.

The run settings, documented backends and failure paths have representative
coverage; every possible parameter combination has not been exhausted.
Auto-QC establishes file/numerical/space/topology consistency, not universal
anatomical correctness. Human anatomical review and broader multi-subject,
multi-protocol accuracy evaluation remain pending. Research results still need
visual review before interpretation or publication.
