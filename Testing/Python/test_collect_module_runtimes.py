"""Timing reports preserve unsuccessful runs without promoting them to benchmarks."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.collect_module_runtimes import collect_device_measurements, device_table, select


class ModuleRuntimeInventoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def save(self, relative, payload):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def mask(self, seconds, requested="auto", resolved="cuda"):
        return {"status": "pass", "seconds": seconds, "anatomical_review": "pending",
                "supplied_mask_unchanged": True,
                "result": {"status": "completed", "runtime_seconds": seconds - 1,
                           "device_execution": {"requested": requested, "resolved": resolved,
                                                "tensorflow_package_version": "test-version"},
                           "signature": {"inputs": [{"sha256": "test-input"}]},
                           "qc": {"geometry_pass": True, "binary": True, "finite": True}}}

    def row(self, records, module="brainmask.pnl_cnn"):
        return next(row for row in select(records) if row["module"] == module)

    def test_missing_files_do_not_become_zero_seconds(self):
        self.assertEqual(collect_device_measurements(self.root), [])
        row = self.row([])
        self.assertIsNone(row["seconds"])
        self.assertEqual(row["measurement_status"], "MISSING")

    def test_default_run_selected_not_fastest_cpu_or_cuda_repeat(self):
        self.save("cpu/pnl_cnn_acceptance.json", self.mask(10, "cpu", "cpu"))
        source = self.save("gpu/pnl_cnn_acceptance.json", self.mask(20))
        self.save("gpu_warm/pnl_cnn_acceptance.json", self.mask(5, "cuda"))
        records = collect_device_measurements(self.root)
        row = self.row(records)
        self.assertEqual(row["seconds"], 20)
        self.assertEqual(row["source_field"], "seconds")
        self.assertEqual(row["device"], "cuda")
        self.assertEqual(row["requested_device"], "auto")
        self.assertEqual(row["anatomical_review"], "pending")
        self.assertEqual(row["source_record_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["runtime_environment"]["tensorflow_package_version"], "test-version")
        self.assertEqual(records[0]["input_records"][0]["sha256"], "test-input")

    def test_failure_duration_retained_but_not_selected(self):
        self.save("synthstrip_gpu/synthstrip_acceptance.json", {"status": "fail", "seconds": 949, "error": "incompatible GPU"})
        self.save("synthstrip_modern_gpu/synthstrip_acceptance.json", self.mask(9))
        records = collect_device_measurements(self.root)
        failed = next(r for r in records if r["status"] == "fail")
        self.assertEqual(failed["runtime_seconds"], 949)
        self.assertEqual(failed["failure_reason"], "incompatible GPU")
        self.assertIsNone(failed["device"])
        self.assertEqual(self.row(records, "brainmask.synthstrip")["seconds"], 9)
        self.assertIn("949.000", device_table(records))
        self.assertIn("fail", device_table(records, chinese=True))

    def test_green_status_cannot_hide_failed_integrity_or_reused_result(self):
        for failure in ("geometry_pass", "binary", "finite", "supplied_mask_unchanged", "reused"):
            with self.subTest(failure=failure):
                payload = self.mask(3)
                if failure == "reused":
                    payload["result"]["status"] = "reused"
                elif failure == "supplied_mask_unchanged":
                    payload[failure] = False
                else:
                    payload["result"]["qc"][failure] = False
                self.save("gpu/pnl_cnn_acceptance.json", payload)
                records = collect_device_measurements(self.root)
                self.assertEqual(records[0]["status"], "integrity_contract_failed")
                self.assertEqual(self.row(records)["measurement_status"], "MISSING")

    def test_skipped_and_nonfinite_times_never_supply_compute_timing(self):
        for status, seconds in (("skipped", 3), ("reused", 3), ("pass", float("nan")), ("pass", -1), ("pass", True)):
            with self.subTest(status=status, seconds=seconds):
                payload = self.mask(seconds)
                payload["status"] = status
                self.save("gpu/pnl_cnn_acceptance.json", payload)
                self.assertEqual(self.row(collect_device_measurements(self.root))["measurement_status"], "MISSING")

    def test_eddy_acceptance_is_whole_route_with_all_checks_required(self):
        payload = {"status": "PASS", "runtime_seconds": 719,
                   "checks": {"pipeline_completed": True, "cuda_selected": True},
                   "device_execution": {"resolved": "cuda"}, "manual_scientific_review": "pending"}
        self.save("eddy_cuda_fixed/acceptance.json", payload)
        records = collect_device_measurements(self.root)
        row = self.row(records, "preprocessing.mrtrix_fsl")
        self.assertEqual(row["seconds"], 719)
        self.assertIn("not eddy-only", row["scope"])
        self.assertEqual(row["subject_id"], "sub-dicom")
        for checks in ({}, {"pipeline_completed": False}, {"pipeline_completed": "true"}):
            payload["checks"] = checks
            self.save("eddy_cuda_fixed/acceptance.json", payload)
            self.assertEqual(self.row(collect_device_measurements(self.root), "preprocessing.mrtrix_fsl")["measurement_status"], "MISSING")

    def test_phase_diagnostics_preserve_measured_and_rounded_timings_separately(self):
        payload = self.mask(84)
        payload["result"].update(phase_seconds={"external_process": 63.123},
                                 thread_environment={"OMP_NUM_THREADS": "4"},
                                 stdout_tail="Pre-Processing Time Taken : 0.47 min\nMasking Time Taken : 0.47 min\nTotal Time Taken : 1.02 min")
        self.save("pnl_phase_gpu/pnl_cnn_acceptance.json", payload)
        records = collect_device_measurements(self.root)
        self.assertEqual(records[0]["phase_seconds"]["external_process"], 63.123)
        self.assertEqual(records[0]["thread_environment"]["OMP_NUM_THREADS"], "4")
        self.assertAlmostEqual(records[0]["rounded_upstream_phase_seconds"]["cnn_models"], 28.2)
        self.assertEqual(self.row(records)["seconds"], 84)
        self.assertFalse(records[0]["representative"])

    def test_tractcloud_device_receipt_and_decoded_output_contract(self):
        payload = {"status": "completed", "elapsed_seconds": 18.5, "executed": True,
                   "return_code": 0, "human_review": "pending",
                   "output_summary": {"bundle_count": 39, "bundle_readable_count": 39, "bundle_nonempty_count": 39}}
        self.save("tractcloud/tractcloud_qc.json", payload)
        device = self.save("tractcloud/tractcloud_device.json", {"requested": "cuda", "resolved": "cuda", "torch_version": "test-torch"})
        records = collect_device_measurements(self.root)
        self.assertEqual(self.row(records, "bundles.tractcloud")["device"], "cuda")
        self.assertEqual(records[0]["device_source_sha256"], hashlib.sha256(device.read_bytes()).hexdigest())
        self.assertEqual(records[0]["runtime_environment"]["torch_version"], "test-torch")
        payload["output_summary"]["bundle_readable_count"] = 38
        self.save("tractcloud/tractcloud_qc.json", payload)
        self.assertEqual(self.row(collect_device_measurements(self.root), "bundles.tractcloud")["measurement_status"], "MISSING")


if __name__ == "__main__":
    unittest.main()
