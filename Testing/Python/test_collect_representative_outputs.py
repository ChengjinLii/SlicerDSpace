from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.collect_representative_outputs import collect_representative_outputs, write_reports


class CollectRepresentativeOutputsTest(unittest.TestCase):
    def test_collects_examples_and_timing_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "outputs"
            (root / "01_segmentation").mkdir(parents=True)
            (root / "04_tractography").mkdir(parents=True)
            (root / "00_run_metadata").mkdir(parents=True)
            (root / "01_segmentation" / "SegmentationMap_GMWMCSF.nii.gz").write_bytes(b"not-a-real-nifti")
            (root / "04_tractography" / "subject_ifod2.tck").write_bytes(b"not-a-real-tck")
            (root / "00_run_metadata" / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "kind": "slicerddsurfer_product_orchestration",
                        "tasks": [{"name": "segmentation", "elapsed_seconds": 12.5}],
                    }
                ),
                encoding="utf-8",
            )
            report = collect_representative_outputs(root)
            summary = report["summary"]
            self.assertGreaterEqual(summary["categories_with_examples"], 3)
            self.assertGreaterEqual(summary["example_file_count"], 3)
            self.assertEqual(summary["timing_record_count"], 1)

            written = write_reports(report, Path(tmp) / "report")
            self.assertTrue(written["json"].is_file())
            self.assertTrue(written["source_csv"].is_file())
            self.assertTrue(written["timing_json"].is_file())
            with written["source_csv"].open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(any(row["category"] == "segmentation" for row in rows))
            self.assertTrue(any(row["category"] == "tractography" for row in rows))


if __name__ == "__main__":
    unittest.main()
