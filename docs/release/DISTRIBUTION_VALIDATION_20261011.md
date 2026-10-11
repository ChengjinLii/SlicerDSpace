<div align="center">

# Distribution Validation

**11 October 2026 · Local engineering evidence**

[Project](../../README.md) | [Documentation](../README.md) | [Release gates](EXTENSION_READINESS.md) | [中文](EXTENSION_READINESS.zh-CN.md)

</div>

This record covers the private working tree based on commit
`37a543cd0450fe570f0e1b0ab63b8dbfc8babc89`, not a new release tag.
Existing scientific/backend changes were preserved. The repository was not made
public and no Index submission, release upload or Git push was performed.

本轮修复分发资源、安装包检查和文档入口；不等于已通过官方上架验收，
也没有重新验证全部算法的科学正确性。当前状态请结合发布门禁阅读。

---

## Changes Verified

- One manifest drives CMake and local staging. WMQL queries, WSL bridge code/runtime requirements, LUTs and license notices are included.
- Local staging no longer copies entire development directories. Tests, reference-only sources and local weights/templates are excluded.
- Package audits check source hashes, missing/unexpected files, duplicate module roots, unsafe paths and archive links.
- A Tier 1 catalog JSON draft, LICENSE.txt, icon/screenshot metadata and real compact-UI captures are provided.
- English/Chinese project and user entry points follow the compact interface; dependencies are selected by route rather than installed wholesale.
- Normal CI has three-platform resource-contract checks. A separate manual workflow requires genuine Slicer SDK runners for configure/build/CTest/CPack.

---

## Executed Checks

| Check | Outcome | Scope |
| --- | --- | --- |
| Fast regression in the existing CI Python environment | 724 tests: 721 passed, 3 skipped | Includes shared resource selection and CMake install-rule contracts |
| Slicer Python regression | 724 tests: 721 passed, 3 skipped | Same suite, separate Slicer Python runtime |
| Extension source/staging installation | PASS | Module registration and isolated settings |
| Extension Manager local archive installation | PASS | Real Slicer 5.10 installation API, not a catalog download |
| Compact UI and synthetic workflow | PASS / PASS | EN/ZH controls, generated synthetic DTI/tractography and loading |
| Enhanced installed-resource smoke | PASS | Packaged WMQL path, WSL files and imports resolving under the installed module directory |
| Metadata and active-document audits | PASS | Local declarations/links only; private raw URLs are not publicly usable |
| Workflow YAML parsing and git diff whitespace check | PASS | Syntax/whitespace, not execution on remote runners |
| Genuine SDK/CPack probe | BLOCKED | Application directory has no SlicerConfig.cmake; no build/package claimed |

Local evidence is retained under
`ignore/validation/extension_distribution_20261011/`:
`unit_tests_final.log`, `slicer_python_tests_final.log`,
`gui/gui_acceptance.json`, `final_install/gui_acceptance.json`,
`repository_audit.json` and `sdk-probe/sdk_build_report.json`.
GUI reports include script snapshots, command lines, source revision/patch hashes,
logs and settings-isolation checks. An earlier run used the system Python lacking
scientific packages; the existing CI environment was then used without installing
or replacing packages. Slicer Python used the native CMake executable, avoiding
the unrelated Python wrapper's inherited PYTHONHOME mismatch.

---

## Reproduce

From an authorized source checkout, using the appropriate configured Python:

~~~bash
make test-fast PYTHON=/path/to/configured/python
python3 scripts/audit_slicer_extension_metadata.py --json
python3 scripts/audit_documentation.py
python3 scripts/release_audit.py --json
python3 scripts/build_slicer_sdk.py --slicer-dir /path/to/real/Slicer-build \
  --build-dir ignore/sdk-clean-validation
~~~

The real SDK command intentionally fails when the SDK is absent. The unit-test
SDK stub checks CMake install rules only and must not be cited as an official
build. The local GUI test installed a staging-generated TGZ; it did not install
a CPack-generated package on a pristine machine.

---

## Remaining Gates

Real SDK builds and independently clean installations remain required, including
separate Windows/macOS evidence for any support claims. Model/template
redistribution and unresolved third-party code permissions still need maintainer
clearance. An authorized real-data tutorial and Sample Data registration remain
unfinished. Public repository access and externally resolvable catalog URLs are
deferred by the maintainer's instruction.

`release_audit.py` now labels its scope as repository checks; its legacy
`release_ready` JSON field is a compatibility alias, not certification. Passing
CI or these local checks cannot close the independent release gates.

See the [readiness checklist](EXTENSION_READINESS.md) and the
[official submission checklist](https://github.com/Slicer/ExtensionsIndex/blob/main/.github/PULL_REQUEST_TEMPLATE.md).
