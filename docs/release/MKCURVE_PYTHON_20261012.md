<div align="center">

# MK-Curve Python Port

[Project](../../README.md) | [Microstructure](../setup/MICROSTRUCTURE.md) | [中文使用说明](../setup/MICROSTRUCTURE.zh-CN.md)

</div>

---

## Implementation

`MKCURVE` now selects the bundled Python translation, with no MATLAB runtime.
`MKCURVE_MATLAB` is an optional external author-code reference. Default analysis
remains DTI only; optional DKI and its method stay under Advanced.

Upstream: [Fan Zhang's MK-Curve](https://github.com/zhangfanmark/MK-Curve),
commit `9a213e1a5850fe50c998793f31ed852df00242f8`. No ready-to-use Python port with
verifiable source, license and algorithm compatibility was found in this search.
This project-maintained translation is not an official upstream Python release.
The complete BWH and DKI MPL-2.0 licenses ship with the extension.

The port preserves predicted-signal WLLS weights, the author's 256 directions,
numerical MK, synthetic-b0 curves, abnormal-voxel detection and correction at
threshold 0.5. Raw original/corrected FA/MD/AD/RD, MK/AK/RK and eigenvalues are
retained; no scalar-map clipping or cosmetic hole filling is applied. Nonpositive
signal repair is counted separately and performed only in a working copy.

Selected signals are staged as disk-backed float64 volumes; compressed source
data are expanded once. Fits are chunked. Curves, grid, coefficients, masks,
residuals and hashes are retained. Regional corrected statistics use the corrected
validity mask. Cache integrity also covers curve arrays and the provenance record.

---

## Independent Verification

Unmodified author numeric routines were actually executed in an isolated
GNU Octave 7.3.0 container, not mocked or replaced by another Python fit.
The production plugin does not depend on Octave. Verification includes original
and corrected parameter maps, complete b0 curves, zero/max curve locations,
abnormal/unusual masks and corrected b0.

The maximum absolute real-ROI parameter-map difference was `1.67e-8`;
the synthetic case was below `2.60e-7`. Within the curve domain `0 <= MK <= 5`,
differences were below `2.59e-12`. Implausible extreme curve samples can reach
very large MK values: full-curve maximum scaled difference was below `8.52e-8`,
not a claim that every extreme sample has a tiny absolute difference.

| Case | Scope | Correction comparison |
| --- | --- | --- |
| Real HCP 100307 | Eight ROI voxels, two selected nonzero shells | Masks and corrected b0 match; no voxel flagged by either implementation |
| Noisy synthetic b0 perturbation | Eleven toy voxels, explicit artificial b0 artifact | Both implementations flag eleven voxels; masks and corrected b0 match |

The synthetic case establishes algorithm parity, **not** clinical accuracy or a
promise that correction only affects deliberately perturbed voxels. It is not
presented as acquired data. Actual author outputs for four synthetic voxels are
retained as a regression fixture in `Testing/Python/fixtures/`.

A separate real 64-voxel CLI run passed multi-shell preflight and independent
geometry, validity, correction and artifact-hash QC. All 64 corrected estimates
were numerically valid; neither fitting route flagged a voxel for b0 correction.
Real Slicer 5.10 sessions verified method selection/persistence and automatically
loaded six DIPY reference maps plus three distinct corrected maps without duplicate
nodes. These are real small-ROI and GUI checks, not a full-brain acceptance claim.

Local numerical evidence: `ignore/validation/mkcurve_python_20261012/`, including
`author_parity.json`, `scientific_audit.json`, reference MAT inputs/outputs,
CLI logs and isolated GUI reports. Unit and package audits are recorded there.

Final checks: 877 Python tests, 874 passed and three explicitly skipped
(heavy DDSeg and two unavailable PowerShell checks); no failures. The package
resource audit verified 377 files, including the fixed integration directions
and both license texts. License provenance/byte-preservation checks passed.
An independent staged-copy CLI run also completed from `/tmp`, with only the
installed module directory on `PYTHONPATH`, not the development source package
or external author checkout. This verifies bundled Python execution, not a
fresh OS environment or official Slicer SDK/CPack provenance.

---

## Explicit Boundaries

- The adaptive author integer b0 grid is explicit and independent of directory names; unusable normalized signal scales fail rather than silently rescale.
- The radial plane is well-defined at principal-axis poles, fixing an upstream division-by-zero edge case. Nonfinite curves are invalid rather than automatically corrected.
- These checks validate numeric implementation and native geometry, not clinical suitability, biological correctness, or an optimal threshold for every acquisition.
- MATLAB itself, full-brain processing, independent subjects and Windows/macOS scientific execution have not been validated here.
- Source and installed interactive Slicer copies are distinct. Isolated tests do not update or restart the user's interactive session or MRI Agent.
