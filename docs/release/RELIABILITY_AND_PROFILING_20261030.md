<div align="center">

# Input Safety, Cache Integrity And Timing

**30 October 2026 · Verification and repair of the external review findings**

[Project](../../README.md) | [Performance Plan](PERFORMANCE_BOTTLENECKS_AND_PLAN.zh-CN.md) | [Measurements](benchmarks/workflow_overheads_20261030.json) | [中文](RELIABILITY_AND_PROFILING_20261030.zh-CN.md)

</div>

---

## Repairs

The baseline is `558a497` plus the local working tree. Existing website and figure edits remain intact.

| Finding | Repair | Regression |
| --- | --- | --- |
| Gradient count did not match DWI volumes | Validate a nonempty 4D header, spatial geometry and volume/gradient counts | Four volumes with three gradients and 3D inputs are rejected |
| Infinite b-values raised before reporting | Summarize finite shells and report nonfinite gradients structurally | `inf`, `-inf` and `nan` produce failed JSON records |
| Failed validation did not prevent computation | Automatically validate DWI-consuming execution targets and block their dependencies | Invalid masks/gradients never reach DTI or DDSeg in fresh and resume modes |
| Corrupt DDSeg outputs were reused | Store SHA256 receipts for all four outputs and re-read content on reuse | Replacement of any map is rejected even with unchanged size/mtime |
| Batch success ignored blocked child tasks | Read fresh child manifests and aggregate subject/task states | An actual WMA-only blocked CLI becomes `completed_with_blocks`; batch exits 2 by default |

Independent existing bundle products and surface postprocessing remain eligible for their own checks.
Metadata errors block preprocessing that consumes that metadata. Missing legacy DDSeg receipts require recomputation;
old green QC records are not automatically signed. Strict output checks reuse the shared artifact-record implementation
without its metadata-only digest cache.

Batch records include `subject_status_counts`, `task_status_counts`, child manifest paths and status sources.
Single-subject partial-execution semantics remain unchanged. Explicit `--allow-partial-success` allows a zero
batch exit code while preserving the blocked status. Custom runners without the child-manifest contract can
only provide a process-level `process_completed` result.

---

## Timing

Legacy `elapsed_seconds` and `orchestration_elapsed_seconds` retain their pre-report meaning.

| Field | Scope |
| --- | --- |
| `wall_time_seconds` | Orchestrator planning through execution, reporting and directory refresh; before the final telemetry write |
| `phase_timings_seconds` | Planning, input preparation/validation, product execution, metadata/profile, tree report, subject reporting/refresh |
| `cli_timing.main_wall_seconds` | CLI main entry through preflight, planning and orchestration return; excludes interpreter startup and final response writes |
| Batch `results[].elapsed_seconds` | Child process launch through exit, including interpreter startup and child reporting |
| `directory_statistics` | Declared output queries, file counts and top-level scan times |

Reporting failures retain timing data. A regression injects a 30 ms report delay to verify inclusive timing.
Overlapping task intervals are not summed as wall time. GPU-memory and process-tree RSS sampling remain future work.

### Pilot

`scripts/benchmark_workflow_overheads.py` performs nine isolated calls: three small synthetic shapes, each
with a fresh output directory, a repeated request and a gradient change. Only validation and reporting run.
The median times below are milliseconds, not MRI fitting or model-cache benchmarks.

| Scenario | API call | Legacy pre-report | Inclusive orchestrator | Directory statistics |
| --- | ---: | ---: | ---: | ---: |
| Fresh output directory | 12.63 | 7.23 | 12.10 | 0.38 |
| Same settings repeated | 14.98 | 7.70 | 14.44 | 0.73 |
| Gradient modified | 15.32 | 7.65 | 14.80 | 0.81 |

[Raw measurements](benchmarks/workflow_overheads_20261030.json) include source hashes, affinity, thread settings
and host load. OS caches were not flushed. These measurements establish timing boundaries, not algorithm speedup.
For these small directories the scan cost does not justify a more complex cache; larger real-output trees need profiling.

---

## Acceptance And Deployment

The [acceptance record](benchmarks/reliability_acceptance_20261030.json) is generated from logs and the tested installation:

| Check | Result |
| --- | --- |
| Python suite | 1742 tests, 8 skipped, no failures; 83.057 s |
| Isolated Slicer extension loading | PASS; 18.84 s |
| Isolated Slicer input interaction | PASS; 16.94 s |
| Package resources | 521 declared files; no missing, changed, unexpected or unsafe entries |
| Source/install identity | SHA256 matches for all 9 checked core files |

Slicer times measure the test processes, not scientific algorithms. The package originates from the staging helper.
Regressions use real tiny NIfTI inputs, the actual single-subject CLI and concurrent batch tests.
Full logs, staged packages, resource audits and isolated Slicer screenshots live locally under
`ignore/validation/reliability_20261030/`; final records and failed attempts remain distinguishable.
Earlier reused-fixture and source-during-packaging failures are retained. Final acceptance uses frozen source and a fresh directory.

The isolated Slicer checks use their own installation, settings and display. Existing MRI Agent and Slicer sessions
are untouched. The running `slicerdsurfer-current-20260928` container still uses its old installation and is not
counted as this revision's acceptance. Loading/input tests do not replace whole-brain or anatomical review.

The new website-localization generator is excluded from extension runtime packaging.
Repository visibility, GitHub Actions and remote commits are unchanged.

## Next Decisions

The review's reliability-first sequence is adopted. Current full-module MK-Curve/DKI/WMA pairs, shared connectome
endpoints, FOD caching, shared mmap and global GPU/RAM admission remain candidates. No new speedup is attributed
to them. Both H100s were busy at inspection; no new long whole-brain/GPU benchmark runs in this round.
