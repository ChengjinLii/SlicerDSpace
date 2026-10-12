<div align="center">

# Masking, Microstructure And Scene Validation

[Project](../../README.md) | [Documentation](../README.md) | [Brain Masking](../setup/brain_mask_gui_config.md) | [Microstructure](../setup/MICROSTRUCTURE.md)

</div>

---

## Scope

Private working-tree follow-up on 12 October 2026, based on commit `755150d`
with preserved existing local changes. This is not a new SDK/CPack release,
public catalog submission, Windows/macOS certification, or clinical validation.
Evidence is retained under `ignore/validation/brain_mask_backends_20261012/`.
No running MRI Agent or interactive Slicer session was restarted for these tests.

---

## Changes

- PNL diffusion CNN is the default missing-mask generator; alternatives remain explicit Advanced choices. Supplied masks are protected, geometry is checked and no silent backend fallback is used.
- DTI remains the default microstructure model. FW/NODDI/DKI have independent Advanced switches; GUI/CLI/user-JSON settings use the same choices.
- Standard DIPY DKI produces MK/AK/RK/KFA/MKT/RTK, separate raw and bounded-display maps, fit/validity masks and residual QC. Eligibility checks precede fitting.
- Original MATLAB MK-Curve has a separate configured external adapter. Its corrected estimates are not substituted by clipped standard MK or mislabeled WLS maps.
- GUI checkpoints load only key results from successful/current-run records. TCK/TRK are converted to capped RAS VTK previews with provenance and source preservation; unchanged scene nodes are reused.

---

## Measured Evidence

| Check | Actual evidence |
| --- | --- |
| Fast suite | 866 tests: 863 passed, 3 skipped; see `unit-verified.log` |
| GUI select/save | 86 checks passed in an isolated Slicer 5.10 process |
| GUI restart/restore | 51 checks passed in a second isolated process |
| Automatic loading | 12 real run-record cases passed, including native SlicerDMRI FiberBundle and generic-Model fallback campaigns |
| Coordinates and deduplication | Persisted preview headers declare RAS; loaded points match preview geometry; repeated polls create no duplicate owned nodes |
| Real PNL masking | HCP100307 completed in 346.698 s using the cached external PNL/ANTs container runtime; supplied source mask unchanged |
| Mask comparison | PNL/input-mask Dice 0.962966; this is agreement, not ground-truth accuracy or evidence of superiority |
| Real DKI | Unsmooth 4 x 4 x 4 HCP100307 ROI, 64 fitted/valid voxels, two selected nonzero shells, design rank 22 |
| DKI reference comparison | Six raw maps agreed with direct DIPY to maximum absolute difference below 3.2e-8; median NRMSE 0.0239265 |
| Independent DKI audit | Actual stage geometry, raw/display relationship, validity counts and residual checks passed; artifact-corruption tests fail as intended |
| Staging/package contract | Resource inclusion and source-hash audit passed; this is a staging archive, not official CPack provenance |

Reference-library agreement checks integration correctness, not an independent
validation of the mathematical model. The small ROI is not a full-brain fit.
No smoothing, resampling or invented parameter maps were used for this evidence.
Raw negative/nonfinite/invalid estimates remain visible in files and QC.

---

## Remaining Gates

MATLAB is not installed here: **actual MK-Curve fitting is NOT_RUN**. The adapter
has configuration/path/input/quoting/no-fallback tests, but scientific acceptance
requires a configured MATLAB runtime, the original author checkout and real data.
PNL success in the cached container does not install that runtime into the host
or Slicer's Python environment. Users must configure an external PNL environment
or explicitly select another available masking method.

Human anatomical review remains pending. Full-brain DKI, broader acquisition
validation, cross-platform external backends and SDK packaging are separate gates.
Large scene loading can still occupy the GUI thread; the display cap is not a
promise of zero loading latency. Running installed copies need redeployment and
restart to use the updated source.

---

## 中文

本轮完成 PNL 脑掩膜默认选择、Advanced 替代路线、DTI 默认与独立 FW/NODDI/DKI
开关，以及当前运行的关键结果自动加载、TCK/TRK 的 RAS VTK 预览和去重。
真实 PNL、真实小 ROI DKI、原生 SlicerDMRI 与通用 Model 回退均有对应证据。
自动 QC/执行成功不等于人工解剖核验；未安装 MATLAB 的 MK-Curve 不标记为已跑通。
没有公开仓库、推送未提交修改，或重启 MRI Agent。
# Follow-up

The original MATLAB-only adapter status recorded above is historical. The
subsequent [Python port verification](MKCURVE_PYTHON_20261012.md) documents the
native Python route and actual independent author-code comparisons.
