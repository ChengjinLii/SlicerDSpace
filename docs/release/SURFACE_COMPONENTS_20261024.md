<div align="center">

# Local Surface Components

**24 October 2026 | DDSurfer synchronization and Linux validation**

[Project](../../README.md) | [Setup](../setup/SURFACE_COMPONENTS.md) | [Release gates](EXTENSION_READINESS.md) | [Evidence](benchmarks/surface_components_20261024.json) | [中文](SURFACE_COMPONENTS_20261024.zh-CN.md)

</div>

Synchronized DDSurfer commit `8a8699c0fda32be7e0a3cbca2903680b9f0c950b`.
The current indexed native OBJ postprocessing route no longer requires a full
FreeSurfer installation. It uses seven original C++ commands built from pinned
source, not a Python reimplementation or a replacement for the entire suite.
Existing FreeSurfer installations remain supported. This source-only update
does not change model weights or their mirror indexes.

---

## Integration

GUI and CLI now share optional component and personal activation paths. An
explicit component path takes precedence; otherwise the resolver retains an
existing FreeSurfer installation or uses the recipe-specific user cache.
The environment check verifies the runtime in a fresh subprocess and reports
missing activation separately. Neither Check nor Run downloads or compiles.

The selected-environment preparation action offers a cancellable background
source build after explicit source/data approval. Git, C/C++ compilers, system
development libraries and CMake >=3.24,<4 must already be available. Setup does
not install system compilers, alter Slicer Python, or obtain a personal key.
GUI confirmation documents these prerequisites; CLI also accepts a CMake path.

The optional 29,657,074-byte atlas archive is downloaded from a pinned DDSurfer
URL, SHA256-verified and stored outside the extension. No extracted full-suite
binary pack or activation key is added to the extension/model repository.
Runtime identity is recorded in postprocessing cache signatures; changing an
explicit runtime invalidates completion reuse. Legacy STL/shell and SynthStrip
requirements remain separate. [Setup details](../setup/SURFACE_COMPONENTS.md).

---

## Executed Evidence

| Check | Result | Boundary |
| --- | --- | --- |
| Optional atlas acquisition | Actual download and SHA256 verification passed | Pinned upstream URL; no model-mirror upload claimed |
| Independent source build | Seven commands, 67 recorded files, 89,406,503 bytes; validation passed | Fresh build directory, cached pinned Git source and dependency archives, network disabled, full suite hidden |
| Fresh scientific adapter execution | Subject 100307, left hemisphere, seed 1234; 139 checked payloads numerically/structurally equal to the existing full-FreeSurfer reference | 652.261 s; automatic integrity QC passed, human anatomy review pending |
| Native Slicer GUI | Component detection, compact bilingual UI, asynchronous environment checks, Extension Manager installation passed | Private settings, read-only runtime/code, network disabled |
| Package resources | 491 declared runtime files matched | Staging archive, not a new SDK/CPack build |
| Python regression | 1,348 discovered: 1,343 passed, 5 skipped, 0 failed; 75.935 s | Skipped tests are not passes; not all scientific backends rerun |

The scientific comparison used the upstream source-built runtime. The later
independent build used the same pinned source and recipe, then supplied the
runtime for the final GUI campaign. The 139-output scientific comparison was
not rerun against that second prefix; these are separate pieces of evidence.
The measured 652.261 s is one hemisphere's execution time, not an acceleration
ratio or bilateral/full-workflow benchmark.

A real GUI pilot initially reported missing components because directly
launching Slicer's `python-real` after environment isolation lost its standard
library. The bridge now uses its sibling `PythonSlicer` launcher. The failed
pilot is retained; the same checks pass after the fix. The final GUI preparation
test cancels the consent dialog and confirms no runtime is created; actual
compilation is covered separately by the CLI build, not claimed as a GUI build.

---

## Scope and Artifacts

Full local logs, build records, comparison output and private GUI settings are
retained under `ignore/validation/surface_components_20261024/`. The public-size
[machine record](benchmarks/surface_components_20261024.json) retains hashes and
results without activation contents or private absolute paths. The source
preparation uses the unchanged upstream builder, with only the atlas package
location adapted to the external asset layout.

Automatic preparation is validated only on Linux x86_64. Native Windows/macOS,
bilateral and multi-subject equivalence, an entirely online source build, a new
SDK build, anatomical certification and whole-workflow acceleration are not
established by this check. Existing interactive Slicer/MRI Agent sessions were
not restarted. This is not a claim that every algorithm's QC has passed.

Original FreeSurfer and third-party terms still apply; the local runtime does
not make those components MIT-licensed. Users provide their own valid activation
file. Presence checks and hash verification do not grant rights or certify
license validity. See [third-party notices](../../THIRD_PARTY_NOTICES.md).
