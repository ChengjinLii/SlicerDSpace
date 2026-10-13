<div align="center">

# Managed Setup

[Project](../../README.md) | [Documentation](../README.md) | [Quick Start](QUICKSTART.md) | [GPU](GPU_EXECUTION.md) | [中文](MANAGED_SETUP.zh-CN.md)

</div>

---

## Inside Slicer

Select your analyses, then open **Advanced > Environment and models** and choose
**Set up selected external tools**. The installer prepares only the selected
MRtrix/FSL routes and fills their paths automatically after verification. Missing
MRtrix/FSL rows in the dependency report also offer **Install and configure**.
The report's combined install action sequences missing Python packages, required
model profiles and supported external tools; it is not an installation of every
optional backend.

No terminal, administrator account, shell activation or manual executable-path
selection is needed for these managed routes. If Conda is unavailable, a pinned
Miniforge bootstrap is downloaded from conda-forge's official GitHub release and
SHA256-verified before execution. Installation happens in a user-local directory,
not in Slicer's Python or the system CUDA installation. FSL requires explicit
license confirmation; GPU eddy is selected by default when NVIDIA tools are
detected, with a CPU installation option. Actual GPU usability is checked when
running the selected backend, not certified by package installation.

Setup runs in a background process with a Cancel control and an install log.
Cancellation/failed verification does not replace configured paths. Successfully
installed packages and partial downloads may remain for retry. A verified,
unchanged managed runtime is reused without reinstalling it.

---

## Models And Existing Installations

Model download uses the configured asset root or the default user data directory;
it no longer requires a folder picker. A missing-model row downloads that product's
profile rather than all three anatomical products. The explicit core download
action still downloads the core profile. Checksums are verified before the asset
path is saved. Authorization and model quality are separate from checksums.

Advanced external-path fields remain available for existing installations, offline
environments and administrator-managed clusters. Managed setup is opt-in and does
not silently replace an explicitly configured environment while an analysis runs.
User-local defaults live alongside model assets under `SlicerDDSurfer/runtimes`.

---

## Current Coverage

| Component | Managed path |
| --- | --- |
| MRtrix3 3.0.8 | Linux x86_64, official MRtrix3 Conda channel |
| FSL eddy 2602.0 / topup 2203.5 | Linux x86_64, official FSL channel; explicit license approval |
| CUDA eddy 2602.0 | Optional FSL profile; NVIDIA driver required; no full CUDA Toolkit installation |
| DDSurfer / DDSeg / DDParcel assets | Existing background download with profile-specific selection and default directory |
| Python scientific packages | Existing dependency installer; PyTorch remains managed by the Slicer PyTorch extension |
| PNL CNN, full FreeSurfer, WMA/WMQL/TractCloud resources | Not yet fully provisioned by this managed installer; current configured adapters remain available |
| Windows/macOS managed MRtrix/FSL setup | Not yet implemented/accepted; existing platform setup and Advanced paths remain |

Installation verification checks command availability, selected package versions,
ELF libraries and executable hashes, and saves an explicit environment lockfile.
It does not establish scientific correctness or replace real clean-install,
SDK/package and platform acceptance. See the dated
[GPU verification](../release/GPU_POLICY_20261013.md).

---

## Maintainer Interface

`scripts/setup_managed_runtime.py` plans by default; `--execute` performs setup.
FSL profiles additionally require `--accept-fsl-license`. `--root` and
`SLICERDDSURFER_RUNTIME_ROOT` support isolated test environments. The worker returns
verified settings; the GUI applies them only after successful completion.
It never modifies the user's shell, GPU driver or an unmanaged Conda prefix.
