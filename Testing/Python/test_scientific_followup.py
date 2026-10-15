"""Acceptance must fail on changed sources or numerical differences."""

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from scripts.validate_scientific_followup import compare_arrays, run_dki_audit, run_wma, run_bundle_audit


class ScientificFollowupTests(unittest.TestCase):
    def test_unfinished_bundle_is_not_a_completed_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"status": "running"}))
            args = SimpleNamespace(stage_manifest=manifest, output_dir=root, wait_seconds=0)
            with self.assertRaises(TimeoutError), patch("scripts.audit_bundle_products.audit") as audit:
                run_bundle_audit(args, {})
            audit.assert_not_called()

    def test_parity_rejects_shape_nonfinite_and_real_difference(self):
        self.assertTrue(compare_arrays([1., 2.], [1., 2.000001])["passed"])
        for actual in ([1.], [1., np.nan], [1., np.inf], [1., 2.1]):
            self.assertFalse(compare_arrays([1., 2.], actual)["passed"])

    def test_successful_wma_does_not_hide_source_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            qc = root / "qc.json"
            qc.write_text(json.dumps({"automatic_qc_passed": True}))
            args = SimpleNamespace(subject_id="test", tractogram=root / "source.tck", atlas_dir=root,
                                   output_dir=root, slicer=root / "Slicer", wma_root=root, mrtrix_bin_dir=root, threads=1)
            result = SimpleNamespace(qc_path=qc, manifest_path=root / "manifest.json", status="completed")
            with patch("tractography.wma.run_wma_org_atlas", return_value=result), patch(
                "scripts.validate_scientific_followup.fingerprint", side_effect=[{"sha256": "before"}, {"sha256": "after"}]
            ):
                record = {}
                run_wma(args, record)
            self.assertFalse(record["automatic_qc_passed"])
            self.assertFalse(record["inputs_unchanged"])

    def test_dki_independent_audit_and_upstream_sample_on_synthetic_fixture(self):
        from Testing.Python.test_microstructure_dki import synthetic_case, write_case
        from microstructure.dki import DkiConfig, run_dki
        from shared.pipeline import RawInputBundle

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = write_case(root, synthetic_case(noisy=True))
            bundle = RawInputBundle(root, "synthetic", root / "input",
                                    **{f"{key}_path": value for key, value in paths.items()})
            result = run_dki(DkiConfig("synthetic", bundle, root / "fit"))
            args = SimpleNamespace(subject_root=root, subject_id="synthetic", stage_manifest=result.manifest_path,
                                   output_dir=root / "audit", sample_voxels=5)
            args.output_dir.mkdir()
            record = {}
            run_dki_audit(args, record)
            self.assertTrue(record["automatic_qc_passed"], record)
            self.assertEqual(record["sampled_voxels"], 5)
            self.assertEqual(record["human_review"], "pending")


if __name__ == "__main__":
    unittest.main()
