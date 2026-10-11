<div align="center">

# Capabilities And Platforms

**Install what the selected route needs**

[Project](../../README.md) | [Documentation](../README.md) | [Quick Start](QUICKSTART.md) | [Release](../release/EXTENSION_READINESS.md) | [中文](SUPPORT_MATRIX.zh-CN.md)

</div>

Capability checks detect packages, executables and assets. They do not certify
numerical accuracy for every acquisition or platform.

---

## Dependency Levels

| Level | Products | Prerequisites |
| --- | --- | --- |
| Inspect/plan | Input preview, validation, plans | Basic imaging runtime; converter for DICOM/NRRD |
| Minimal DTI | Tensor scalars, optional deterministic tracks | SlicerDMRI or supported DTI route and Python packages |
| Anatomical models | DDSurfer/DDSeg/DDParcel | PyTorch, matching assets, route-specific preparation |
| Microstructure | Free-water/NODDI | Configured DIPY/AMICO and suitable acquisition |
| Advanced pathways | CSD/ACT/SIFT2/SAF/bundles | External backend only as selected |
| Connectome | Regional matrices, scene QC | Tractogram/parcellation; weights only for weighted routes |

Install only selected dependencies. Review external-tool and model terms
separately from runtime readiness.

---

## Evidence By Platform

| Check | Linux | Windows | macOS |
| --- | --- | --- | --- |
| Resource/CMake contract | Local evidence; CI configured | CI configured; execution evidence needed | CI configured; execution evidence needed |
| Real Slicer GUI/source install | Dated local records | Not certified | Not certified |
| Real SDK/CTest/CPack | Requires real SDK acceptance | Requires real SDK acceptance | Requires real SDK acceptance |
| Scientific workflows | Only recorded routes/data | Native not certified; WSL setup is not native acceptance | Not certified |
| Advanced backends | Only recorded routes | Tool/WSL limitations | Tool-specific limitations |

Resource checks are not three-platform Slicer builds. The opt-in SDK workflow
needs separately provisioned runners and does not claim success before execution.
See the [release gate](../release/EXTENSION_READINESS.md).
