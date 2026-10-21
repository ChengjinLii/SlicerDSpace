<div align="center">

# Dependency Preparation Verification

[Project](../../README.md) | [Setup](../setup/MANAGED_SETUP.md) | [Platforms](../setup/SUPPORT_MATRIX.md) | [中文](DEPENDENCY_SETUP_20261021.zh-CN.md)

</div>

---

## Delivered Behavior

The compact GUI has one selected-workflow preparation entry under Advanced,
plus explicit managed-tool repair and offline model-directory verification.
Slicer extensions remain native extensions; Python/model preparation runs in
cancellable workers. Linux x86_64 MRtrix/FSL/PNL tools use separate user-local
prefixes. Completed managed environments are checked before reuse; ordinary
preparation does not reinstall them. Repair requires confirmation and refuses
unowned environments. No algorithm selection or system driver is changed.

SlicerDMRI/PyTorch are requested as needed; UKFTractography stays optional.
Newly installed/enabled extensions or changed loaded packages require a restart.
The final dependency check, not an installer exit code alone, determines readiness.
The three product rows also show their configured algorithms and update with
Advanced settings. These are configuration labels, not scientific QC badges.

---

## Measured Checks

| Check | Observed result | Boundary |
| --- | --- | --- |
| Python regression suite | 1,256 tests: 1,253 passed, 3 skipped | Host scientific environment; not three-platform execution |
| Slicer 5.10 GUI | Selected setup, independent FSL/PNL terms gates, algorithm labels, dependency paths and process-tree cancellation passed | Isolated settings and disposable container; selected dependency responses controlled; no live user sessions changed |
| Managed PNL fresh environment | Official pinned source, three weights and template downloaded/verified; TensorFlow 2.15.1/Keras 2.15.0 and ANTs 2.3.0 installed | New prefix; existing Conda was used to create it, not a clean-machine Miniforge bootstrap test |
| PNL model checks | Three-view deserialization and finite synthetic forwards passed on H100 CUDA | Does not establish anatomical accuracy |
| Managed PNL reuse | Resource/command hashes and forward checks passed without reinstalling | Existing newly created prefix |
| Actual PNL mask, 100307 | 102.73 s; 697,375 brain voxels; binary, finite and matching native geometry | Includes hashes/b0 preparation/inference/automatic QC, excludes downloads and setup probe; human anatomical review pending |
| Offline DDSeg resources | Three weights, three SHA256 matches; no download | Trusted bundled manifest, not redistribution permission |
| Fresh Python worker | Installed packaging 24.2 into a new venv containing only pip | Compatibility installer path; no production Slicer packages changed |
| Distribution and notices | Staged archive resource audit, documentation links/style and third-party notice checks passed | Not official SDK/CPack or legal certification |

Evidence remains under `ignore/validation/selected_setup_20261021/`: setup logs,
runtime receipts, GUI logs/screenshots, mask acceptance JSON and unit-test logs.
No weights, isolated environments or patient images are added to Git.

---

## Reproduce And Limitations

Run `python3 -m unittest discover -s Testing/Python -p 'test_*.py'` in the
documented development environment. Native checks use
`scripts/slicer_acceptance.py --tests selected_setup algorithm_labels dependency_workflow setup_tree`.
The opt-in `Testing/Python/pnl_managed_acceptance.py` requires an already
authorized PNL runtime, source DWI/bval/bvec and a separate report directory.
It never writes into source subject inputs.

Slicer 5.10 lacks `slicer.packaging`; its compatibility worker was exercised.
The newer `pip_ensure` integration is feature-detected and contract-tested, not
validated against a newer installed Slicer build. Extension downloads/restarts
and full MRtrix/FSL setup were not repeated on a completely blank machine here.
Full FreeSurfer and all WMA/WMQL/TractCloud resources are not automatically
provisioned. Windows/macOS managed MRtrix/FSL/PNL setup remains unavailable.
Protected asset URLs may require authorization. Installation readiness is not
scientific QC, SDK acceptance, or redistribution permission.

The design follows Slicer's [extension management](https://slicer.readthedocs.io/en/latest/user_guide/extensions.html),
official [packaging API](https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/packaging.py)
and the [PNL author's runtime instructions](https://github.com/pnlbwh/CNN-Diffusion-MRIBrain-Segmentation/blob/d7fe0fd4976c2d5a3489526f75d2a00dae3e1fe1/docs/README.md).
