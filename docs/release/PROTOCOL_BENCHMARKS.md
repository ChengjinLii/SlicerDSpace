# Protocol Benchmark Tables and Figures

SlicerDDSurfer orchestration manifests record run-level elapsed time, task
status, task runtime and output-size snapshots. The benchmark generator turns
these records into descriptive CSV tables and publication-oriented figures.

## Generate A Report

```bash
python3 scripts/generate_protocol_benchmarks.py \
  --input /path/to/cohort-or-output-tree \
  --output-dir /path/to/protocol_benchmarks
```

Repeat `--input` to combine several subjects or computing environments.

Generated files:

- `runs.csv`: one row per orchestration manifest.
- `tasks.csv`: one row per task with status and runtime.
- `output_directories.csv`: storage footprint by product directory.
- `stage_metrics.csv`: authoritative wall times read directly from stage
  `*_qc.json` and `*_progress.json` files.
- `stage_summary.csv`: per-stage sample count, median, quartiles, range and p95
  across all discovered measurements.
- `summary.json`: descriptive statistics and interpretation notes.
- `task_runtime.png` and `.svg`: median completed runtime by task.
- `task_status_distribution.png` and `.svg`: completed/skipped/blocked/failed
  task records.
- `output_storage.png` and `.svg`: output storage by product directory.
- `stage_wall_time.png` and `.svg`: median stage wall time with interquartile
  ranges from authoritative QC and progress files.

## Interpretation Rules

- Successful task records (`completed`, `passed` or `success`) are treated as
  algorithm computation time.
- `skipped` or `reused` runtimes measure resume detection overhead, not the
  original algorithm runtime.
- Output size is a snapshot at manifest creation time.
- Runs without an output-size snapshot are recorded as missing, not as zero
  bytes.
- `summary.json` records the report-generation host only. Confirm the actual
  execution hardware against run provenance before quoting it.
- Before manuscript use, report subject count, acquisition characteristics,
  CPU, RAM, GPU, operating system, Slicer version, dependency versions and the
  exact selected targets/backends.
- A single-subject report is useful for feasibility and protocol timing, but it
  is not a cohort performance claim. Use multiple independent subjects and
  repeated runs for inferential comparisons.
