"""Tests for Nature Protocols-oriented benchmark aggregation."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    path = REPO_ROOT / "scripts" / "generate_protocol_benchmarks.py"
    spec = importlib.util.spec_from_file_location("generate_protocol_benchmarks_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ProtocolBenchmarkTest(unittest.TestCase):
    def test_completed_and_reused_runtime_are_separated(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "Test1_orchestration_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "kind": "slicerddsurfer_product_orchestration",
                        "subject_id": "sub-01",
                        "run_name": "Test1",
                        "execute": True,
                        "resume": True,
                        "elapsed_seconds": 13.0,
                        "targets": ["validation", "microstructure"],
                        "tasks": [
                            {"name": "validation", "status": "completed", "runtime_seconds": 3.0},
                            {"name": "microstructure.dti", "status": "completed", "runtime_seconds": 10.0},
                            {"name": "tractography.dti", "status": "skipped", "runtime_seconds": 0.02},
                        ],
                        "performance_profile": {
                            "top_dirs": [{"path": "02_microstructure", "size_bytes": 1073741824, "file_count": 4}],
                            "largest_task_outputs": [
                                {
                                    "name": "microstructure.dti",
                                    "declared_output_bytes": 1024,
                                    "declared_output_files": 2,
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            for subject, elapsed in (("sub-01", 60.0), ("sub-02", 120.0)):
                stage_dir = root / subject / "02_microstructure" / "noddi"
                stage_dir.mkdir(parents=True)
                (stage_dir / "noddi_progress.json").write_text(
                    json.dumps(
                        {
                            "stage": "noddi",
                            "status": "completed",
                            "elapsed_seconds": elapsed,
                        }
                    ),
                    encoding="utf-8",
                )
            output_dir = root / "report"
            with mock.patch.object(module, "_plot_figures", return_value=[]):
                summary = module.generate_benchmark_report([root], output_dir)

            runs_text = (output_dir / "runs.csv").read_text(encoding="utf-8")
            tasks_text = (output_dir / "tasks.csv").read_text(encoding="utf-8")
            stage_summary_text = (output_dir / "stage_summary.csv").read_text(encoding="utf-8")

        self.assertEqual(summary["run_count"], 1)
        self.assertEqual(summary["task_status_counts"]["completed"], 2)
        self.assertEqual(summary["task_status_counts"]["skipped"], 1)
        self.assertEqual(summary["completed_task_runtime_seconds"]["median"], 6.5)
        self.assertAlmostEqual(summary["resume_check_runtime_seconds"]["median"], 0.02)
        self.assertEqual(summary["output_snapshot_run_count"], 1)
        self.assertEqual(summary["authoritative_stage_wall_time"]["NODDI"]["n"], 2)
        self.assertEqual(summary["authoritative_stage_wall_time"]["NODDI"]["median_seconds"], 90.0)
        self.assertIn("completed_task_runtime_seconds", runs_text)
        self.assertIn("output_snapshot_available", runs_text)
        self.assertIn("is_compute_runtime", tasks_text)
        self.assertIn("NODDI,2,2", stage_summary_text)


if __name__ == "__main__":
    unittest.main()
