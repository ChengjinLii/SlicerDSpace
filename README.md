<div align="center">

# SlicerDDSurfer

**Diffusion MRI workflows in 3D Slicer**

[![CI (main)](https://github.com/ChengjinLii/SlicerDDSurfer/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/ChengjinLii/SlicerDDSurfer/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![License](https://img.shields.io/badge/License-BSD--3--Clause-4D7587)](LICENSE.txt)
[![Slicer](https://img.shields.io/badge/3D_Slicer-5.10-58728B)](https://www.slicer.org/)

[Overview](#overview) | [Install](#installation) | [Quick Start](#quick-start) | [Documentation](docs/README.md) | [Validation](#validation-and-release-status) | [Citation](#citation) | [中文](README.zh-CN.md)

[Project Website](https://chengjinlii.github.io/SlicerDDSurfer/) | [Website Publishing](https://github.com/ChengjinLii/SlicerDDSurfer/blob/main/docs/website/README.md)

</div>

SlicerDDSurfer brings diffusion-MRI anatomical reconstruction, microstructural
mapping and white-matter connectivity analysis into one Slicer module. Select
the products you need, run a traceable workflow, and review its images, QC
reports and execution records.

**Research software.** Private pre-release; not currently distributed through
the official Extensions Catalog. A completed run is not a clinical assessment
or proof of scientific correctness.

---

## Overview

One module, five workflow families:

| Workflow | Products | Main prerequisites |
| --- | --- | --- |
| Input preparation | DICOM/NIfTI/NRRD import, gradient validation, optional mask generation and preprocessing | Appropriate import/preprocessing backend |
| Anatomical reconstruction | DDSeg tissue labels, DDParcel regions, DDSurfer white/pial surfaces | Matching model assets, PyTorch and SlicerDMRI for the selected route |
| Microstructural analysis | DTI FA/MD/AD/RD, optional Free-water, NODDI and DKI, regional summaries | Route-specific packages and acquisition suitability checks |
| White-matter pathways | DTI/CSD tractography, ACT/SIFT2, SAF, WMQL/WMA/TractCloud bundles | Backend-specific tools and assets |
| Structural connectivity | Regional matrices, Slicer scene inspection, QC and provenance | Compatible parcellation and tractogram; SIFT2 weights for weighted routes |

Install dependencies **for the selected route**, not for every possible product.
MRtrix3, FSL, FreeSurfer and advanced bundle backends are optional and are not
silently installed. See the [capability and platform matrix](docs/setup/SUPPORT_MATRIX.md).

Optional cortical postprocessing can use **locally compiled original FreeSurfer
components without the full installation**, or reuse an existing installation.
Preparation is explicit; a personal activation file is still required.
See [surface component setup](docs/setup/SURFACE_COMPONENTS.md).

Large weights, templates and inference atlases are managed separately from code.
The selected-environment preparation downloads only required resource groups,
verifies SHA256 and saves their paths; existing and offline resources are reused.
See [resource layout, licensing and download policy](docs/assets/EXTERNAL_RESOURCES.md).

**Implementation origins.** DDSeg is a MATLAB-to-Python/PyTorch reimplementation;
SAF and MK-Curve are unofficial Python ports of author MATLAB methods. PNL CNN
masking invokes the author's existing Python backend, not a rewritten entire
PNL pipeline. See [implementation provenance and verification limits](docs/architecture/IMPLEMENTATION_PROVENANCE.md).

---

## Installation

**Only using the plugin?** You do not need the website source or historical
optimization reports. Runtime packages omit those materials; they stay in the
complete repository for review and reproducibility. See
[download options and lightweight source installation](docs/setup/DOWNLOADS.md).
This does not imply an available public release or official Catalog listing.

Use an authorized checkout while the repository is private. The following is
a **lightweight source/staging installation**, not an official CPack release:

```bash
git clone --filter=blob:none --no-checkout --depth 1 https://github.com/ChengjinLii/SlicerDDSurfer.git
cd SlicerDDSurfer
git show HEAD:scripts/extension_runtime/runtime_checkout.txt | git sparse-checkout set --no-cone --stdin
git checkout
python3 scripts/stage_slicer_extension.py \
  --install-root ~/SlicerDDSurfer-extension --link-mode copy --clean
```

In **Edit > Application Settings > Modules**, add the expanded absolute path
`~/SlicerDDSurfer-extension/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules`
to **Additional module paths**, then restart Slicer. Set `--slicer-version`
to your actual Slicer version when staging. Local GUI validation uses Slicer 5.10.

Install **SlicerDMRI** and **PyTorch** from Slicer's Extension Manager for routes
that need them. Updating the source requires restaging and restarting.

Model files live outside the code checkout. Choose a writable model-assets
directory in the separate **Environment and installation** section. Download only the
required profile after reviewing [asset terms](docs/assets/MODEL_ASSET_TERMS.md):

```bash
python3 scripts/download_model_assets.py --profile surface \
  --asset-root ~/SlicerDDSurfer-model-assets --source url \
  --source-id slicerdsurfer_models_git
```

The broader anatomical profile is available with
`scripts/download_model_assets.sh --profile core`.
Availability and SHA256 verification do **not** establish redistribution rights.
See [model setup](docs/assets/MODEL_ASSETS.md) and
[dependency setup](docs/assets/DEPENDENCY_SETUP_WORKFLOW.md).

---

## Quick Start

1. Select **SlicerDDSurfer** from the module selector. Choose English or Chinese in the header.
2. Enter **Subject ID**, **Subject root** and, optionally, a separate **Output directory**.
3. Select only the products you intend to run. Use **Select…** beside Microstructure, Tractography or Bundles to choose one or several algorithms.
4. Open **Environment and installation > Prepare selected analysis environment**. Confirm dependencies and terms; restart if requested, then prepare again to continue. See [managed setup and offline models](docs/setup/MANAGED_SETUP.md).
5. Click **Run SlicerDDSurfer**. Missing inputs appear in red; review the log and correct them before retrying.
6. Key results from successful stages automatically appear in the current scene. Use the separate **Results and QC** section to inspect QC, reload, replace or clear this run's nodes.

There is no visible Beginner section or automatic first-run wizard in the
default interface. Advanced settings shows one category at a time:
**Preprocessing & mask**, **Model parameters**, **Run & performance**, or
**Regions & input import**. Input conversion is in the last category; ordinary
prepared inputs do not need conversion again. Installation is separate from these parameters.

**Advanced settings > Regions & input import > Regional analysis (optional)** lets you select DDParcel
regions and reuse completed maps, full tractograms and connectivity matrices for
regional statistics, ROI streamline selection and local connectivity. It does
not refit models or alter the default workflow. See [regional analysis](docs/setup/REGIONAL_ANALYSIS.md).

Canonical input layout:

```text
sub-01/
  input/
    data.nii.gz
    bvals
    bvecs
    nodif_brain_mask.nii.gz   # optional; generation needs a supported backend
```

DWI and mask must share a voxel grid. Gradient files must match the DWI
measurements. Corrected gradients must accompany motion-corrected DWI.
An existing input mask is retained. When a mask must be generated, the default
is the **PNL diffusion CNN masking** backend, not the entire PNL preprocessing
pipeline. On Linux x86_64, preparation can install its separate Python/model/ANTs
runtime; existing runtimes remain configurable in Environment and installation.
SynthStrip, MRtrix and supplied-mask alternatives are selectable in
**Advanced settings > Preprocessing & mask**. A missing backend is reported,
never silently replaced. See [brain-mask setup](docs/setup/brain_mask_gui_config.md).

Microstructure runs **DTI only by default**. Enable Free-water, NODDI or DKI
independently with **Select…** beside Microstructure. DTI remains required preparation.
DKI checks baseline measurements, nonzero shells,
gradient directions and design rank before fitting. **MK-Curve** uses a bundled
Python port of the author's algorithm, distinct from standard DIPY WLS/OLS.
MATLAB is only an optional reference backend. See [microstructure routes](docs/setup/MICROSTRUCTURE.md).
Automatic tractography display uses a capped VTK preview, preserving the full
TCK/TRK source; a preview is not the analysis tractogram.
Tractography defaults to CSD/ACT. Select **UKFTractography** beside Tractography to invoke
the installed official Slicer extension, which can feed WMA automatically. Its
author-default parameters are editable only under Advanced; no UKF source is
vendored and no CSD streamline budget is applied to UKF. See [UKF setup and defaults](docs/setup/UKF.md).
Tracking methods can be multi-selected. They run sequentially in separate
`<run>__<backend>` variants, reusing the shared anatomical/microstructure stages.
Selected bundle methods and connectomes run for each tracking variant, without
combining streamlines or relaxing QC. Multiple methods increase runtime and disk use.
WMQL defaults to the **unmodified official multi-bundle rules**: all 48 output
queries in the pinned author's `freesurfer_queries.qry`. Under **Advanced > Model
parameters > WMQL bundles**, leave empty for all, or enter a subset such as
`AF,CST,UF,cc_4`. Rules and label aliases ship with the extension; no query editing
is needed. Numeric DDParcel/DK label compatibility is checked, but does not prove
FreeSurfer wmparc equivalence. Missing/sparse bundles are listed individually and
excluded from quantitative acceptance; successful execution is not all-bundle QC.
Historical adapted protocols are not offered in the GUI. See [WMQL protocol](docs/setup/WMQL.md).
WMA reports per-tract sampling, and MK-Curve summaries use per-metric validity.
See [root causes and one-pass cohort validation](docs/release/WORKFLOW_GENERALIZATION_20261017.md)
for actual evidence and remaining limitations, not an all-results-passed claim.
For a minimal DTI-only walkthrough and a clearly identified synthetic
installation test, see the [tutorial](docs/setup/QUICKSTART.md).

---

## Documentation

| Task | Guide |
| --- | --- |
| First workflow | [Quick Start](docs/setup/QUICKSTART.md) |
| Dependency and platform support | [Support matrix](docs/setup/SUPPORT_MATRIX.md) · [Linux](docs/setup/LINUX_HPC.md) · [Windows](docs/setup/WINDOWS.md) · [macOS](docs/setup/MACOS.md) |
| Model setup | [Assets](docs/assets/MODEL_ASSETS.md) · [Terms](docs/assets/MODEL_ASSET_TERMS.md) |
| Results, cancellation and QC | [Result review](docs/setup/GUI_RESULT_REVIEW.md) |
| Configuration and command line | [Settings](docs/setup/USER_CONFIG.md) |
| Source organization | [Repository layout](docs/architecture/REPOSITORY_LAYOUT.md) |
| Maintainer release checks | [Extension readiness](docs/release/EXTENSION_READINESS.md) · [Release procedure](docs/release/RELEASE.md) |

For a CLI input/environment check without running algorithms:

```bash
python3 run_subject_pipeline.py --subject-root /path/to/sub-01 \
  --targets validation,microstructure --microstructure-stages dti --doctor
```

Use `--plan` instead of `--doctor` to write a run plan. Execution that needs
Slicer CLI modules must use Slicer or its `PythonSlicer` environment.

---

## Validation And Release Status

Linux real-data and GUI evidence is documented in the
[acceptance campaign](docs/release/SLICER_ACCEPTANCE_20261007.md);
the compact interface has a separate
[UI validation record](docs/release/UI_SIMPLIFICATION_20261008.md).
These records describe specific checkouts, routes and datasets, not all
future configurations.

The [16 October follow-up](docs/release/QC_FOLLOWUP_20261016.md) records the
new CSD/WMA checks and real Linux SDK/CPack installation acceptance, including
the remaining WMQL sampling failure and human-review boundaries.
For this private repository, consult authenticated Actions results; the live
badge tracks main push runs and is not externally accessible without authorization.

Current release boundaries:

- CMake and staging now use one runtime resource manifest; package audits check file inclusion and source hashes.
- Fast CI and local installation checks are not substitutes for a real SDK/CTest/CPack build.
- Linux SDK/CPack, private Extension Manager installation and selected cached-DTI/bundle loading have passed; this is not a blank-machine full scientific workflow.
- Native Windows/macOS scientific workflows and three-platform SDK builds are not certified.
- The Extension Index JSON is a **Tier 1 proposal**, not acceptance by Slicer.
- Public source access, third-party licensing clearance and asset redistribution review remain release gates.

Development checks require a complete checkout, not the lightweight installation.
Run `make test-fast` and
`python3 scripts/audit_slicer_extension_metadata.py --json` for development
checks. SDK builds and independent clean installation are described in
[Extension readiness](docs/release/EXTENSION_READINESS.md).

---

## Support

Use **Advanced settings > Copy diagnostic report** to collect diagnostics.
When reporting an issue, include the Slicer version, OS, selected route,
failure message and redacted log. Remove patient identifiers and private paths.
Reports remain local unless you choose to share them; dependency and model
downloads require network access.

---

## Citation

The SlicerDDSurfer protocol manuscript is in preparation. Cite the tested
software version using [CITATION.cff](CITATION.cff), together with the methods
actually used: [DDSurfer](https://doi.org/10.1002/advs.76596),
[DDSeg](https://doi.org/10.1016/j.neuroimage.2021.117934), and
[DDParcel](https://doi.org/10.1109/TMI.2023.3331691).

---

## License

Project code is **BSD-3-Clause**: [LICENSE.txt](LICENSE.txt), the single
project license file. Bundled components retain their own licenses and notices.
Bundled third-party code has separate terms:
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Model weights, templates and subject-derived data are not relicensed by the
project license. Some component permissions remain unresolved; do not publish
asset-inclusive archives until those permissions are documented.
