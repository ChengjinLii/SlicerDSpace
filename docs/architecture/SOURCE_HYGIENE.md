<div align="center">

# Source Hygiene

[Project](../../README.md) | [Documentation](../README.md) | [Quick Start](../setup/QUICKSTART.md) | [Release](../release/EXTENSION_READINESS.md) | [中文索引](../README.zh-CN.md)

</div>

## Retired Sources

The 2026-10-11 cleanup was checked against source revision
`476ddb6a09dd4827c983d8bc995a10303ae0226c` and the current local working tree.
Neither the runtime entry points nor maintenance scripts import the retired
modules. A file's age alone was not used as evidence of obsolescence.

| Removed From The Current Tree | Files | Reason And Current Replacement |
| --- | ---: | --- |
| `docs/archive/legacy-copy-20260523/` | 8 | The archive identified itself as historical and inactive. Its old setup/design notes and sculpting source are not part of the current product. Current instructions live in `docs/setup/` and `docs/architecture/`. |
| `surface/models/`, `surface/networks/` | 6 | The old local model implementation is not referenced by inference. `anatomy/surface/prediction.py` and `anatomy/surface/pipeline.py` delegate to the pinned `anatomy/surface/ddsurfer_backend/`; its active model code and upstream checksums are retained unchanged. |
| `parcellation/models/losses.py`, `solver.py`, `organize_weights.sh` | 3 | The solver/loss pair belongs to training and is not used by the inference entry point. The weight-copy script hard-codes an author's local training paths. DDParcel inference still uses `networks.py`, `sub_module.py` and the manifest-based model downloader. |

These 17 files remain recoverable from Git history. A local pre-deletion backup
is stored in ignored `ignore/archives/unused_sources_20261011/retired_sources.tar.gz`.
It is not installed or uploaded. Scientific results, weights and active
upstream source files were not removed or rewritten.

---

## Retained Files

Older files can still serve an active contract:

- `SlicerDDSurfer.py`, `SlicerDDSurfer.s4ext`, `CMakeLists.txt` and `Resources/`
  are the Slicer module, extension metadata, packaging configuration and UI.
- `shared/` and the domain packages contain current GUI and pipeline code.
  Moving them all into `src/` is a separate compatibility migration, not a
  cleanup operation.
- `anatomy/parcellation/data_loader/augmentation.py` supplies `ToTensorTest` to the
  actual DDParcel inference entry point; it is not merely training residue.
- `anatomy/parcellation/conversion/` includes public conversion utilities and test
  fixtures. These support format/gradient/coordinate regression checks and
  are retained. Test fixtures are not manuscript data or model weights.
- `licenses/`, `LICENSE`, `THIRD_PARTY_NOTICES.md` and copyright headers retain
  attribution for the third-party code still distributed. Lists of derived
  files were updated after removing the training pair.
- `CITATION.cff`, `codemeta.json` and `.zenodo.json` support citation and
  release metadata. They are not Python runtime files, but that is not a
  reason to remove them.
- The root command/import compatibility entries remain supported. Root
  development configuration and `.github/` remain necessary for tests and CI.

---

## Regression Checks

`Testing/Python/test_repository_structure.py` rejects reintroduced retired
paths and checks imports, including relative imports, for dependencies on
retired implementations. Extension staging verifies that the active DDSurfer
model is packaged and the retired code is absent. Licensing tests verify the
headers and notices of every remaining FastSurfer-derived file.

Before publishing a cleanup, run `make test-fast` on an isolated snapshot of
the exact staged content and perform installed-extension smoke checks. Do not
include unrelated local algorithm, model or validation changes in the cleanup
commit, and do not rewrite published history to erase the old files.
