<div align="center">

# Official Slicer Integration Checks

**22 October 2026 | Linux x86-64 | Slicer 5.10.0**

[Project](../../README.md) | [Documentation](../README.md) | [Release gates](EXTENSION_READINESS.md) | [Evidence](benchmarks/official_slicer_20261022.json) | [中文](OFFICIAL_SLICER_VALIDATION_20261022.zh-CN.md)

</div>

The current working-tree candidate passed the official SDK's generated module
test, the project's native parameter tests, all registered CTests, CPack and
local-file installation through the real Extension Manager. This is **not**
Slicer approval, all-platform acceptance or scientific/anatomical certification.
The repository remains private; no catalog submission or publication occurred.

---

## What Was Tested

Official Slicer provides testing mechanisms and generated module contracts, not
a universal diffusion-MRI accuracy test. The distinction matters:

| Check | Actual result | Scope |
| --- | --- | --- |
| Official SDK-generated GenericTest | 12/12 passed | Application, metadata, logic/widget access and MRML scene binding |
| Native parameter contracts | 3/3 passed | Defaults, rejected invalid values, private-scene XML persistence |
| SDK CTest | 161/161 entries passed | Two native entries and 159 project backend test files |
| Backend cases inside CTest | 1,317 passed, 3 skipped | 1,320 discovered cases; these are project tests, not 1,320 Slicer-authored tests |
| Extension configure/build/CPack | Passed | Genuine existing Slicer SDK; not a new Slicer core build |
| Runtime archive audit | 469/469 files matched | No missing, modified, unexpected or unsafe resources |
| Actual CPack package installation | Passed, 14.04 s | Private Extension Manager install, no developer module paths |
| Self Tests on installed package | Passed | Registered `slicer.selfTests` entry; scene node count preserved |
| Additional project GUI scenarios | 7/7 passed | Real Qt/Slicer processes with isolated settings and no network |
| Metadata and third-party notice audits | Passed | Local consistency/integrity, not public reachability or legal clearance |

The module unittest loader reports four cases because it also discovers an
inherited base entry. There are three explicit parameter contracts, not four
independent scientific tests. The Self Tests callback invokes all three. The
interactive Reload & Test button itself was not separately clicked.

The three backend skips were one opt-in real-subject DDSeg world-QC test and
two PowerShell-dependent installer tests. They were not changed into passes.

The seven GUI scenarios covered staged module loading and EN/ZH settings;
compact layout; scene-owned result reuse, replacement, clearing and portable
MRB persistence; algorithm multi-selection; asynchronous environment checks
and stale-result rejection; cancellation; and shutdown during background work.
Some scenarios use synthetic inputs/mocked scientific execution. They do not
establish successful neural inference or tract anatomy.

---

## Problems Found And Fixed

The original native test only checked a few defaults. It now exercises official
`parameterNodeWrapper` validators, confirms failed writes preserve previous
values, and saves/restores parameters through XML in private MRML scenes.
It never clears the user's scene.

Fresh-file CTest execution exposed a VTK import crash hidden by the previous
combined Python test process. `fiber_conversion_support` loaded VTK even for
unverified/missing WMA source. In mocked dispatch tests, restoring `sys.modules`
removed these newly imported native modules and a later reimport crashed.
Source qualification now precedes the optional import, matching the existing
transform guard. Unqualified source retains the author's implementation; the
qualified numerical conversion is unchanged. A fresh-process CI regression
and a no-VTK-import guard test were added.

Two fixture assumptions were also corrected: synthetic FreeSurfer geometry
no longer needs a system username or timestamp, and the local FreeSurfer
discovery fixture no longer accidentally selects `/opt/freesurfer` or PATH
from the test host. A missing Pillow dependency was installed only into the
isolated test environment, not Slicer's Python or the user's backend.

CMake now requests `ConfigurePrerequisites` before `project()`, as recommended
by Slicer for matching macOS SDK architecture/sysroot settings. This was
configured on Linux; native macOS acceptance is still outstanding.

The GUI harness now accepts `--extension-archive` and records its SHA256/origin.
The Extension Manager case uses that supplied CPack archive rather than silently
substituting the staging helper's archive. Other GUI cases remain explicitly
staged-copy tests.

---

## Evidence And Reproduction

Machine-readable results, tested-file hashes and original step durations are in
[the evidence record](benchmarks/official_slicer_20261022.json). Full local logs,
test snapshots, screenshots, isolated settings and packages are under
`ignore/validation/official_slicer_20261022/`; interrupted/failed attempts remain
there alongside the final `release/` result.

The candidate is based on `7808a0c8391d` plus the recorded working-tree patch,
not an unmodified checkout of that commit. The SDK and installed application
both correspond to Slicer source `a2b6d082be04274a849884fbb1e85634a9df90fb`.
The local SDK's numeric revision is 3838; the installed binary uses 34045.
The local-file installer test supplies target metadata. This is not a catalog
server revision-matching test or an uploaded official binary.

Extension configure/build/CTest/CPack took 3.22/0.77/143.65/1.18 seconds on this
already configured shared host. These are engineering test timings, not model
runtime or clean-machine installation benchmarks.

```bash
xvfb-run -a python3 scripts/build_slicer_sdk.py \
  --slicer-dir /path/to/Slicer-build \
  --build-dir ignore/official-check-new \
  --unit-test-python /path/to/test-env/bin/python

python3 scripts/slicer_acceptance.py \
  --report ignore/official-package-install \
  --slicer /path/to/Slicer/Slicer --xvfb /usr/bin/xvfb-run \
  --assets /path/to/authorized/model-assets --subject /path/to/subject \
  --extension-archive /path/to/the-cpack-package.tar.gz \
  --tests extension_manager_install
```

Use a fresh build directory and isolated profiles. The recorded runs disabled
networking and did not restart the existing DDSurfer or MRI Agent sessions.

---

## Remaining Gates

SDK logs retain upstream CMP0148/CMP0177 CMake warnings and missing optional
SlicerDMRI/PyTorch CMake configuration warnings. No warnings were hidden by
removing dependencies. The generated no-main-window/CLI-disabled test also
emits upstream CropVolume/toolbar warnings; its contracts pass.

Native Windows/macOS builds, other Slicer versions, an all-backend blank-machine
setup and full scientific workflow were not validated here. Human anatomical
review remains independent. The official public URLs/topic, authorized Sample
Data tutorial, patent disclosure and model/template redistribution review are
not completed by passing these automated checks. Remote Actions results for
these local changes were not checked.

The code uses native module classes, typed MRML parameters, separated UI/logic,
scene lifecycle observers and cancellable processes. This is a targeted review
of those integration contracts, not an exhaustive coding-style certification.
In particular, Tier 3 UI conventions discourage unnecessary custom styling;
visual review and platform-specific layout checks remain necessary.

---

## Official References

- [Extension development, build and distribution](https://slicer.readthedocs.io/en/latest/developer_guide/extensions.html)
- [Self Tests discovery and execution](https://slicer.readthedocs.io/en/latest/developer_guide/modules/selftests.html)
- [Typed parameter nodes and persistence](https://slicer.readthedocs.io/en/latest/developer_guide/parameter_nodes/overview.html)
- [Current Extensions Index checklist](https://github.com/Slicer/ExtensionsIndex/blob/main/.github/PULL_REQUEST_TEMPLATE.md)
