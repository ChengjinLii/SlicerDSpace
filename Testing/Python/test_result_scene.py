import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from shared.result_scene import result_candidates, recorded_qc_summary, result_nodes, owned_nodes, clear_run
from tractography.wma import REQUIRED_MAJOR_TRACTS


class ResultSelectionTest(unittest.TestCase):
    def test_tables_are_owned_reused_and_cleared_as_result_nodes(self):
        class Node:
            def __init__(self, identity, run):
                self.identity, self.run = identity, run

            def GetID(self):
                return self.identity

            def GetAttribute(self, key):
                return self.run if key == "SlicerDDSurfer.Run" else None

        volume, table, other = Node("volume", "run"), Node("table", "run"), Node("other", "other-run")
        removed = []
        slicer = SimpleNamespace(
            util=SimpleNamespace(getNodesByClass=lambda name: [volume, other] if name == "vtkMRMLDisplayableNode" else [table]),
            mrmlScene=SimpleNamespace(RemoveNode=removed.append))
        self.assertEqual(result_nodes(slicer), [volume, other, table])
        self.assertEqual(owned_nodes(slicer, "run"), [volume, table])
        self.assertEqual(clear_run(slicer, "run"), 2)
        self.assertEqual(removed, [volume, table])

    def test_bundle_qc_files_are_loaded_without_scanning_stale_siblings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            good, stale = root / "af.trk", root / "stale.trk"
            good.touch()
            stale.touch()
            qc = root / "qc.json"
            from tractography.wmql import WMQL_QC_VERSION
            qc.write_text(json.dumps({"status": "completed", "version": WMQL_QC_VERSION, 'automatic_qc_passed': True,
                "output_summary": {"bundle_files": [str(good)], 'bundle_count': 1,
                    'bundle_readable_count': 1, 'bundle_nonempty_count': 1,
                    'bundles': [{'query_name': 'af.left', 'streamline_count': 20}]}}))
            for name in ("bundles.wmql", "bundles.tractcloud"):
                task = {"name": name, "status": "completed", "qc_path": str(qc), "outputs": {"output_dir": str(root)}}
                candidates, _ = result_candidates({"tasks": [task]})
                self.assertEqual([c["path"] for c in candidates], [str(good)])
                task["status"] = "failed"
                self.assertEqual(result_candidates({"tasks": [task]})[0], [])

    def test_current_wma_only_uses_qc_declared_directory_and_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            folder = root / "anatomical"
            folder.mkdir()
            names = list(REQUIRED_MAJOR_TRACTS) + [f'other_{index}.vtp' for index in range(68)]
            for name in names:
                (folder / name).touch()
            qc = root / "qc.json"
            qc.write_text(json.dumps({"status": "completed", "version": 2, "automatic_qc_passed": True, "output_summary": {
                "anatomical_tracts_dir": str(folder), "anatomical_tract_count": 73,
                'anatomical_tract_readable_count': 73, 'anatomical_tract_nonempty_count': 73,
                'anatomical_tract_streamline_counts': {name: 20 for name in names}}}))
            task = {"name": "bundles.wma", "status": "skipped", "reason": "completed outputs found", "qc_path": str(qc)}
            self.assertEqual(len(result_candidates({"tasks": [task]})[0]), 73)
            (folder / "unexpected.vtp").touch()
            self.assertEqual(result_candidates({"tasks": [task]})[0], [])

    def test_old_green_bundle_record_is_not_accepted_without_current_scientific_qc(self):
        with tempfile.TemporaryDirectory() as tmp:
            qc = Path(tmp) / 'qc.json'
            for name, summary in [('bundles.wmql', {'bundle_files': []}),
                                  ('bundles.wma', {'anatomical_tract_count': 74,
                                   'anatomical_tract_readable_count': 74, 'anatomical_tract_nonempty_count': 45})]:
                qc.write_text(json.dumps({'status': 'completed', 'output_summary': summary}))
                task = {'name': name, 'status': 'completed', 'qc_path': str(qc)}
                self.assertEqual(recorded_qc_summary({'tasks': [task]})['issues'], 1)
                self.assertEqual(result_candidates({'tasks': [task]})[0], [])

    def test_failed_bundle_qc_cannot_enable_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            qc = Path(tmp) / "qc.json"
            qc.write_text(json.dumps({"status": "failed", "output_summary": {"bundle_files": ["/unrelated/a.trk"]}}))
            self.assertEqual(result_candidates({"tasks": [{"name": "bundles.wmql", "status": "completed", "qc_path": str(qc)}]})[0], [])

    def test_completed_execution_does_not_imply_passed_qc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qc.json"
            path.write_text('{"status": "failed"}')
            summary = recorded_qc_summary({"tasks": [
                {"status": "completed", "qc_path": str(path)}, {"status": "completed"}]})
            self.assertEqual(summary, {"passed": 0, "issues": 1, "unavailable": 1})

    def test_failed_execution_cannot_borrow_historical_passed_qc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'qc.json'
            path.write_text(json.dumps({'status': 'completed', 'automatic_qc_passed': True}))
            summary = recorded_qc_summary({'tasks': [
                {'name': 'microstructure.dti', 'status': 'failed', 'qc_path': str(path)}]})
            self.assertEqual(summary, {'passed': 0, 'issues': 1, 'unavailable': 0})
    def test_only_successful_manifest_outputs_are_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            # result_candidates() reports str(path.resolve()); resolve here
            # too so the comparison holds under macOS's /tmp -> /private/tmp.
            tmp = str(Path(tmp).resolve())
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
            tmp = str(Path(tmp).resolve())
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
