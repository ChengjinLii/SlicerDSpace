#!/usr/bin/env python3
"""Tests for DDSurfer postprocess manifest and QC reporting."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class SurfacePostprocessReportTest(unittest.TestCase):
    @staticmethod
    def _write_stats(path: Path, *rows: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = ["# synthetic stats"]
        content.extend(rows)
        path.write_text("\n".join(content) + "\n", encoding="utf-8")

    def test_compute_stats_requires_every_mode_specific_file_to_have_data(self) -> None:
        from anatomy.surface.ddsurfer_postprocess_release.src.write_pipeline_report import stage_statuses

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject_path = root / "subjects" / "100307"
            structural_root = root / "structural"
            stats_root = root / "statistics"
            atlases = ["aparc", "aparc.a2009s"]

            for name in ("lh.wmparc.stats", "lh.aparc.stats", "lh.aparc.a2009s.stats"):
                self._write_stats(subject_path / "stats" / name, "1 region 10")

            left_status = stage_statuses(
                subject_path,
                structural_root,
                stats_root,
                ["compute_stats"],
                "left",
                atlases,
            )
            self.assertEqual(left_status["compute_stats"], "completed")

            whole_status = stage_statuses(
                subject_path,
                structural_root,
                stats_root,
                ["compute_stats"],
                "whole",
                atlases,
            )
            self.assertEqual(whole_status["compute_stats"], "running")

            for name in ("rh.wmparc.stats", "rh.aparc.stats", "rh.aparc.a2009s.stats"):
                self._write_stats(subject_path / "stats" / name, "1 region 10")
            self.assertEqual(
                stage_statuses(
                    subject_path,
                    structural_root,
                    stats_root,
                    ["compute_stats"],
                    "whole",
                    atlases,
                )["compute_stats"],
                "completed",
            )

            self._write_stats(subject_path / "stats" / "rh.aparc.stats")
            self.assertEqual(
                stage_statuses(
                    subject_path,
                    structural_root,
                    stats_root,
                    ["compute_stats"],
                    "whole",
                    atlases,
                )["compute_stats"],
                "running",
            )

    def test_qc_reports_expected_nonempty_missing_empty_and_row_counts(self) -> None:
        from anatomy.surface.ddsurfer_postprocess_release.src import write_pipeline_report

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject_path = root / "subjects" / "100307"
            structural_root = root / "structural"
            stats_root = root / "statistics"
            validation_path = structural_root / "validation.json"
            manifest_path = structural_root / "manifest.json"
            qc_path = structural_root / "qc.json"
            provenance_path = structural_root / "provenance.json"
            validation_path.parent.mkdir(parents=True)
            validation_path.write_text("{}\n", encoding="utf-8")
            self._write_stats(subject_path / "stats" / "lh.wmparc.stats", "1 region 10", "2 region 20")
            self._write_stats(subject_path / "stats" / "lh.aparc.stats")

            argv = [
                "write_pipeline_report.py",
                "--subject-id", "100307",
                "--mode", "left",
                "--input-subject-dir", str(root / "input"),
                "--structural-root", str(structural_root),
                "--stats-root", str(stats_root),
                "--subject-path", str(subject_path),
                "--log-file", str(root / "pipeline.log"),
                "--stages", "compute_stats",
                "--atlases", "aparc,aparc.a2009s",
                "--stage-mode", "copy",
                "--validation-json", str(validation_path),
                "--manifest-json", str(manifest_path),
                "--qc-json", str(qc_path),
                "--provenance-json", str(provenance_path),
            ]
            with mock.patch.object(sys, "argv", argv):
                self.assertEqual(write_pipeline_report.main(), 0)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            qc = json.loads(qc_path.read_text(encoding="utf-8"))
            stats_qc = qc["core_outputs"]
            self.assertEqual(manifest["stage_status"]["compute_stats"], "running")
            self.assertEqual(qc["status"], "partial")
            self.assertEqual(stats_qc["stats_expected_count"], 3)
            self.assertEqual(stats_qc["stats_nonempty_count"], 1)
            self.assertEqual(
                stats_qc["stats_expected_files"],
                ["lh.wmparc.stats", "lh.aparc.stats", "lh.aparc.a2009s.stats"],
            )
            self.assertEqual(stats_qc["stats_nonempty_files"], ["lh.wmparc.stats"])
            self.assertEqual(stats_qc["stats_empty_files"], ["lh.aparc.stats"])
            self.assertEqual(stats_qc["stats_missing_files"], ["lh.aparc.a2009s.stats"])
            self.assertEqual(
                stats_qc["stats_data_rows"],
                {"lh.aparc.stats": 0, "lh.wmparc.stats": 2},
            )


if __name__ == "__main__":
    unittest.main()
