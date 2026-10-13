<div align="center">

# SlicerDDSurfer Documentation

**Install, run, inspect and reproduce**

[Project](../README.md) | [Quick Start](setup/QUICKSTART.md) | [Platforms](setup/SUPPORT_MATRIX.md) | [Release](release/EXTENSION_READINESS.md) | [中文](README.zh-CN.md)

</div>

Start with the compact-interface tutorial. Technical guides describe individual
routes; dated reports preserve historical evidence, not universal guarantees.

---

## User Guides

| Guide | Purpose |
| --- | --- |
| [Quick Start](setup/QUICKSTART.md) | Minimal DTI workflow and synthetic installation check |
| [Capabilities and platforms](setup/SUPPORT_MATRIX.md) | Configure only the selected backend |
| [Result review](setup/GUI_RESULT_REVIEW.md) | Run-scoped loading, cancellation and QC |
| [Brain masking](setup/brain_mask_gui_config.md) | PNL CNN default, explicit alternatives and external runtime |
| [GPU execution](setup/GPU_EXECUTION.md) | GPU-preferred neural inference, explicit CPU choices and CPU-only route boundaries |
| [Managed setup](setup/MANAGED_SETUP.md) | Selected MRtrix/FSL installation, automatic paths and default model directories |
| [Microstructure](setup/MICROSTRUCTURE.md) | DTI default, independent FW/NODDI/DKI and original MK-Curve boundary |
| [Automatic results](setup/AUTOMATIC_RESULTS.md) | Current-run loading and RAS VTK display previews |
| [Settings](setup/USER_CONFIG.md) | Persistent GUI/CLI configuration |
| [Linux](setup/LINUX_HPC.md), [Windows](setup/WINDOWS.md), [macOS](setup/MACOS.md) | Platform-specific setup and limitations |
| [Model assets](assets/MODEL_ASSETS.md) | Profiles, download and checksum verification |
| [Asset terms](assets/MODEL_ASSET_TERMS.md) | Permission review, independent of file verification |
| [Third-party notices](../THIRD_PARTY_NOTICES.md) | Bundled source licenses, provenance and distribution conditions |
| [Implementation origins](architecture/IMPLEMENTATION_PROVENANCE.md) | DDSeg/SAF/MK-Curve ports versus the external official PNL Python adapter |
| [Dependencies](setup/EXTERNAL_DEPENDENCIES.md) | External software and route prerequisites |

---

## Maintainer Guides

- [Extension readiness](release/EXTENSION_READINESS.md): packaging, SDK commands and release gates.
- [Release procedure](release/RELEASE.md): code-only archives, assets, tags and evidence.
- [Repository layout](architecture/REPOSITORY_LAYOUT.md): anatomical, microstructural and connectivity packages.
- [Product architecture](architecture/PRODUCT_ARCHITECTURE.md): native client, optional dependencies, isolated backends and release boundaries.

---

## Validation Records

[Bundle backend verification](release/BUNDLE_BACKENDS_20261013.md) separates
real WMA failures, sparse WMQL candidates and seed-verified TractCloud products.
[Module runtimes](release/MODULE_RUNTIMES_20261013.md) inventories historical and
new measurements without treating cache reuse or ROI timings as full computations.

[SAF Python verification](release/SAF_PYTHON_20261013.md) records independent
author-kernel comparisons, intentional corrections and actual tractogram geometry checks.

[Current DDSurfer synchronization](release/DDSURFER_SYNC_20261013.md) records
RAS-marked OBJ export, Python labels and batched fsaverage mapping with real-output comparisons.
[Python MK-Curve verification](release/MKCURVE_PYTHON_20261012.md) records the
native Python correction route and independent author-code comparisons.

[Masking/microstructure/scene follow-up](release/PIPELINE_MASK_MICROSTRUCTURE_20261012.md)
records the PNL default, DKI eligibility, independent Advanced switches and
current-run automatic result loading, including the unverified MATLAB boundary.

[12 October follow-up](release/DISTRIBUTION_VALIDATION_20261012.md) records
license notices, fresh-clone tests, local installation and the outstanding SDK gate.
[11 October validation](release/DISTRIBUTION_VALIDATION_20261011.md) preserves
the preceding working-tree campaign; its test count is not the scoped Git snapshot's count.

[Scientific/GUI campaign](release/SLICER_ACCEPTANCE_20261007.md),
[compact UI](release/UI_SIMPLIFICATION_20261008.md), and
[DDSurfer synchronization](release/DDSURFER_SYNC_20261005.md) are dated records.
Older Beginner/wizard descriptions are not the current interaction guide.

Documentation follows DDSurfer's centered masthead and section navigation.
Pinned upstream Markdown and third-party license texts are left unchanged
to preserve their recorded hashes and attribution.
