import tempfile
import unittest
from pathlib import Path

from shared.result_scene import result_candidates, recorded_qc_summary


class ResultSelectionTest(unittest.TestCase):
    def test_completed_execution_does_not_imply_passed_qc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qc.json"
            path.write_text('{"status": "failed"}')
            summary = recorded_qc_summary({"tasks": [
                {"status": "completed", "qc_path": str(path)}, {"status": "completed"}]})
            self.assertEqual(summary, {"passed": 0, "issues": 1, "unavailable": 1})
    def test_only_successful_manifest_outputs_are_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "fa.nii.gz"
            good.touch()
            old = Path(tmp) / "old.nii.gz"
            old.touch()
            manifest = {"tasks": [
                {"name": "microstructure.dti", "status": "completed", "outputs": {"fa": str(good)}},
                {"name": "microstructure.noddi", "status": "failed", "outputs": {"ndi": str(old)}},
                {"name": "microstructure.other", "status": "skipped", "outputs": {"fa": str(old)}},
            ]}
            candidates, skipped = result_candidates(manifest)
            self.assertEqual([item["path"] for item in candidates], [str(good)])
            self.assertEqual(len(skipped), 2)

    def test_no_directory_fallback_and_missing_paths_are_explained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "stale.nii.gz").touch()
            manifest = {"output_root": tmp, "tasks": [{"name": "dti", "status": "completed",
                        "outputs": {"missing": str(root / "missing.nii.gz"), "relative": "fa.nii.gz"}}]}
            candidates, skipped = result_candidates(manifest)
            self.assertEqual(candidates, [])
            self.assertEqual(len(skipped), 2)

    def test_unique_files_prioritize_scalars_over_tractograms(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / name for name in ("all.tck", "fa.nii.gz")]
            for path in paths:
                path.touch()
            candidates, _ = result_candidates({"tasks": [{"name": "result", "status": "reused",
                "outputs": {"tractogram": str(paths[0]), "fa": str(paths[1]), "duplicate": str(paths[1])}}]})
            self.assertEqual([item["path"] for item in candidates], [str(paths[1]), str(paths[0])])

    def test_pipeline_resume_is_accepted_but_unselected_skip_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fa.nii.gz"
            path.touch()
            for reason, expected in (("completed DTI microstructure outputs found", 1), ("not selected", 0)):
                candidates, _ = result_candidates({"tasks": [{"name": "microstructure.dti", "status": "skipped",
                    "reason": reason, "outputs": {"fa": str(path)}}]})
                self.assertEqual(len(candidates), expected)
