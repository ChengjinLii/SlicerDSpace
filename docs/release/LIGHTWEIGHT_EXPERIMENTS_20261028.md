<div align="center">

# Lightweight Setup And GUI Experiments

[Home](../../README.md) | [Usage](../setup/EXPERIMENTS.md) | [简体中文](LIGHTWEIGHT_EXPERIMENTS_20261028.zh-CN.md)

</div>

---

## Changes

The optional Slicer-native preset reuses Slicer's Python, SlicerDMRI, Python
WMQL and Python connectomes. DIPY median-Otsu provides a model-free masking
option without TensorFlow, ANTs or an external masking executable. Defaults
remain PNL/CSD until explicitly changed. The preset keeps anatomical products
and GPU preferences; their Python packages, weights and any selected native
postprocessing components remain required. Original PNL/MRtrix/FSL methods
keep their own optional dependencies.

Advanced settings now includes an opt-in Experiments & batch category. It
accepts validated CLI parameter overrides and named JSON variants for one
subject or a prepared cohort. The subject CLI and experiment planner share
analysis validation. Subjects may run concurrently; variants of one subject
run sequentially to protect shared inputs/caches. Each variant has isolated
outputs, status, timing and logs. Preview/export, live progress, cancellation
and run-specific result browsing are available. Bulk completion loads one
successful experiment rather than flooding the scene with all variants.

Parameter parsing is reused, each variant is validated once across subjects,
and preview text is bounded. Limits are 64 variants and 4,096 jobs per campaign.
Shell commands, installation flags and environment-check bypasses are rejected.

---

## Checks

| Check | Result |
| --- | --- |
| Python discovery | 1,583 tests: 1,578 passed, 5 skipped; 83.82 s |
| Real isolated Slicer | Experiments, algorithm selection, compact UI and async dependency check passed |
| GUI experiment checks | Bilingual widgets, explicit preset, cohort preview without subject ID, rejection of unsafe flags, recorded dependency failures and cancellation passed |
| Linux SDK | Configure/build, 182/182 CTest entries and CPack passed |
| Actual CPack archive | 510 runtime resources matched; Extension Manager installation passed |
| DIPY mask | Exact agreement with a direct upstream call on the test input; native affine retained; no external command used |
| Real DTI campaign | Four WLS/LS jobs completed with automatic DTI QC passing |

The imaging example uses two independent directories containing replicas of
the **same upstream Slicer DWIVolume dataset**, not two independent subjects.
Two subjects can be scheduled simultaneously while each replica's WLS and LS
variants run sequentially. The first campaign takes 66.38 s; a warm rerun takes
14.73 s using existing masks/native-DTI caches. These timings do not establish
an algorithm speedup. Matching estimators give identical FA arrays across
replicas. Human anatomical review remains pending.

The [machine-readable receipt](benchmarks/lightweight_experiments_20261028.json)
records source hashes, actual job/QC records and measurements. Full logs,
screenshots, failed attempts and packages remain in
`ignore/validation/native_experiments_20261028/`. Tests use private profiles;
existing Slicer/MRI Agent sessions are unchanged. No GitHub Actions are used.
Native Windows/macOS full scientific acceptance and blank-machine installation
of all optional backends remain separate work.
