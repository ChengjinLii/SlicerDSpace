<div align="center">

# Distribution Follow-up

**12 October 2026 · Licenses and install checks**

[Project](../../README.md) | [Documentation](../README.md) | [Release gates](EXTENSION_READINESS.md) | [授权说明](../assets/CODE_LICENSES.zh-CN.md)

</div>

This record separates source-notice verification, repository tests, local
Extension Manager installation and the still-blocked genuine SDK gate.
The repository remains private; no public release or Extension Index PR is
created. Unrelated algorithm/UI work in the existing working tree is not part
of this release-check change.

本轮统一根目录许可证，补齐四组第三方许可原文及固定来源，并复核安装和回归测试。
这不是“全部授权已清理”或“已完成官方上架”的声明。真实 SDK/CPack 和独立
干净机器上的 DTI/WMQL 验收仍未完成。

---

## License And Badge Changes

- The former root LICENSE and LICENSE.txt were identical copies, not different licenses. Only [LICENSE.txt](../../LICENSE.txt) is retained as the project's BSD-3-Clause license; links and resource declarations use it.
- The full BWH Conversion, MGH FreeSurfer, DDSurfer MIT and Meta PyTorch3D BSD notices are restored. [Provenance](../../licenses/provenance.json) records pinned upstream commits, complete-text SHA256 values, covered paths and conditions.
- CI checks notice integrity and runtime inclusion on Linux, Windows and macOS. This is not a legal certification or permission to redistribute model weights, templates or subject data.
- Both READMEs bind the live CI badge to main push runs. The preceding main commit, 0d31e5b, already had a successful [CI run](https://github.com/ChengjinLii/SlicerDDSurfer/actions/runs/38154045953); old failing runs are retained as history, not hidden or replaced with a static green badge.
- GitHub documents that private-repository badges are not externally accessible. Logged-in Actions results are the reference; a badge unavailable outside an authorized session is not evidence of a failed build. See the [official badge guide](https://docs.github.com/en/actions/how-tos/monitor-workflows/add-a-status-badge).

---

## Executed Evidence

| Check | Outcome | Boundary |
| --- | --- | --- |
| Fresh-clone fast suite for the scoped release-check snapshot | 705 tests: 702 passed, 3 skipped | Python 3.11.15 on Linux; excludes unrelated, uncommitted development changes |
| Fresh clone, checkout and model manifest plan | PASS | No model download or scientific inference |
| Four notice hashes and packaged paths | PASS | Offline integrity checks, not rights-holder approval |
| CPack-style TGZ/ZIP layout regression | PASS | Unit fixtures, not genuine CPack output |
| SDK zero-test regression | PASS | Mocked CTest failure stops packaging; not SDK build evidence |
| Real Slicer 5.10 Extension Manager local installation | PASS, 16.74 s | Staging archive from the current working tree; private extension root and isolated settings |
| Installed resources and imports | PASS | WMQL query, WSL files, license texts and provenance found; imports resolve inside the installed module directory |
| Genuine SDK probe | BLOCKED | SlicerConfig.cmake unavailable; no configure/build/CTest/CPack step executed |
| CPack archive on a pristine Slicer machine, followed by real DTI/WMQL execution | NOT RUN | Remains a release gate |

The fast-suite snapshot is a temporary local commit based on 0d31e5b,
92360170f1277a7dc872f57a4568f92b299e3156; it is not a release tag.
Subsequent documentation-only edits add this record and navigation links.
The staging archive used for GUI installation has SHA256
f4f5e03a5577dcbf975543fc03da6cda8951b187c86283bb2cf09ea64493bdee.
Because that archive includes existing working-tree changes, its installation
success is not evidence for the scoped Git snapshot's scientific algorithms.

Local reports and raw logs are retained under
<code>ignore/validation/release_followup_20261012/</code>:

- <code>fresh-clone/fresh_clone_smoke_report.json</code> and <code>fresh-clone/logs/</code>.
- <code>gui/gui_acceptance.json</code>, <code>gui/package_resource_audit.json</code> and <code>gui/extension_manager_install/slicer.log</code>.
- <code>sdk-probe/sdk_build_report.json</code>, with empty steps/packages and NOT_RUN clean-install/scientific fields.

The first full-suite attempt found three obsolete assertions that required a
duplicate root license or stated that the conversion license was not recorded.
Those assertions now verify the canonical license and documented BWH terms.
An intermediate local clone could not access the unreferenced validation commit;
cloning its detached validation worktree resolved that harness issue. Neither
failed attempt is counted as a pass.

---

## Reproduce And Finish

~~~bash
make test-fast
python3 scripts/audit_third_party.py
python3 scripts/audit_slicer_extension_metadata.py --json
python3 scripts/audit_documentation.py
python3 scripts/build_slicer_sdk.py --slicer-dir /path/to/real/Slicer-build \
  --build-dir ignore/sdk-clean-validation --package-generator TGZ
~~~

The application download and existing application/container installations do
not provide the required SDK configuration. No SDK stub is used to claim a
genuine build. The helper now treats an empty CTest test set as an error;
installation checks accept revision/platform-prefixed CPack layouts rather
than assuming the staging archive's literal top-level directory name.

To close the remaining gate, supply or build a genuine SDK, retain successful
CMake/CTest/CPack logs and package hashes, then install that exact archive with
no developer paths or pre-existing assets and execute authorized real-data DTI
and WMQL checks. Repeat for each claimed platform/backend.
Model/template/fixture permissions, patent review, an authorized real-data
tutorial and eventual public catalog access remain separate decisions. See
[Extension readiness](EXTENSION_READINESS.md) and
[asset terms](../assets/MODEL_ASSET_TERMS.md).
