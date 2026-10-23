"""Timing reports preserve unsuccessful runs without promoting them to benchmarks."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.collect_module_runtimes import collect, collect_device_measurements, collect_completion_measurements, collect_cst_definition_followup, collect_scientific_closure, collect_one_pass_cohort, collect_wma_acceptance, device_table, select, bundle_timing_status


class ModuleRuntimeInventoryTests(unittest.TestCase):
    def test_new_subject_timing_does_not_inherit_100307_or_ukf_input_claims(self):
        campaign = self.root / 'campaign'
        manifest = self.save('campaign/new_orchestration_manifest.json', {
            'kind': 'slicerddsurfer_product_orchestration', 'execute': True, 'subject_id': '100206',
            'tasks': [{'name': 'segmentation.ddseg', 'status': 'completed', 'runtime_seconds': 50}],
        })
        with patch('scripts.collect_module_runtimes.ROOT', self.root):
            rows = collect(campaign, self.root / 'absent')
        result = next(item for item in rows if item['source_record'] == str(manifest.resolve()))
        self.assertIn('100206', result['input_scope'])
        self.assertNotIn('100307', result['input_scope'])
        self.assertNotIn('UKF', result['input_scope'])

    def test_cst_followup_counts_come_from_decoded_products(self):
        from tractography.wmql import WMQL_QC_VERSION

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            stage = directory / 'default_v4_paired'
            stage.mkdir()
            counts = {'af.left': 21, 'af.right': 22, 'cst.left': 23, 'cst.right': 24}
            qc = dict(subject_id='fixture', version=WMQL_QC_VERSION, status='completed', automatic_qc_passed=True,
                      elapsed_seconds=12.3, output_summary=dict(bundle_count=4, bundle_readable_count=4, bundle_nonempty_count=4,
                          bundles=[dict(query_name=key, streamline_count=value) for key, value in counts.items()]))
            (stage / 'wmql_qc.json').write_text(json.dumps(qc))
            (stage / 'wmql_manifest.json').write_text('{}')
            audit = directory / 'default_v4_paired_audit.json'
            audit.write_text(json.dumps(dict(input_streamlines=100, checks={'source_membership': True})))
            with patch('tractography.wmql.wmql_query_cache_current', return_value=True):
                records = collect_cst_definition_followup(directory)
                self.assertIn('CST 23/24', records[0]['input_scope'])
                self.assertIn('100 CSD', records[0]['input_scope'])
                self.assertEqual(records[0]['runtime_seconds'], 12.3)
                audit.write_text(json.dumps(dict(checks={'source_membership': False})))
                self.assertEqual(collect_cst_definition_followup(directory)[0]['status'], 'current_acceptance_failed')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def save(self, relative, payload):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_one_pass_times_require_finished_immutable_independent_acceptance(self):
        manifest = dict(execute=True, status='completed', subject_id='new-subject', tasks=[{
            'name': 'surface.ddsurfer', 'status': 'completed', 'runtime_seconds': 42}])
        path = self.save('subject/manifest.json', manifest)
        subject = dict(subject_id='new-subject', status='passed', attempt=1, return_code=0,
                       inputs_unchanged=True, independent_audit_passed=True, manifest=str(path))
        payload = dict(kind='one_pass_cohort_acceptance', status='failed', runtime_unchanged=True,
                       backend_unchanged=True, subjects=[subject])
        # Another subject's failure must remain visible, not invalidate this
        # independently accepted timing or turn the whole cohort green.
        self.save('acceptance.json', payload)
        records = collect_one_pass_cohort(self.root)
        self.assertEqual(self.row(records, 'surface.ddsurfer')['seconds'], 42)
        self.assertEqual(records[0]['cohort_status'], 'failed')
        for key, value in (('attempt', 2), ('inputs_unchanged', False),
                           ('independent_audit_passed', False), ('return_code', 2), ('status', 'failed')):
            self.save('acceptance.json', dict(payload, subjects=[dict(subject, **{key: value})]))
            records = collect_one_pass_cohort(self.root)
            self.assertEqual(records[0]['runtime_seconds'], 42)
            self.assertEqual(self.row(records, 'surface.ddsurfer')['measurement_status'], 'MISSING')
        self.save('acceptance.json', dict(payload, subjects=[dict(subject, status='running')]))
        self.assertEqual(collect_one_pass_cohort(self.root), [])
        self.save('acceptance.json', payload)
        self.save('subject/manifest.json', dict(manifest, tasks=manifest['tasks'] * 2))
        self.assertEqual(self.row(collect_one_pass_cohort(self.root), 'surface.ddsurfer')['measurement_status'], 'MISSING')

    def test_fresh_wma_times_require_all_current_checks_not_only_execution(self):
        qc = self.save('qc.json', {})
        audit = {'checks': {'membership': True}, 'input_streamlines': 123,
                 'source_sha256': 'same-source', 'manifest': str(self.root / 'manifest.json')}
        independent = self.save('independent.json', audit)
        payload = dict(subject_id='new-subject', status='passed', automatic_qc_passed=True,
                       source_unchanged=True, runtime_unchanged=True, wma_seconds=420,
                       wma_qc=str(qc), independent_audit=str(independent), source_sha256='same-source',
                       wma_manifest=str(self.root / 'manifest.json'), independent_audit_return_code=0)
        self.save('acceptance.json', payload)
        with patch('scripts.collect_module_runtimes.bundle_timing_status', return_value='completed'):
            row = self.row(collect_wma_acceptance(self.root), 'bundles.wma')
            self.assertEqual(row['seconds'], 420)
            self.assertIn('123 source tracks', row['input_scope'])
            for key in ('source_unchanged', 'runtime_unchanged', 'automatic_qc_passed'):
                self.save('acceptance.json', dict(payload, **{key: False}))
                self.assertEqual(self.row(collect_wma_acceptance(self.root), 'bundles.wma')['measurement_status'], 'MISSING')
            self.save('acceptance.json', payload)
            self.save('independent.json', dict(audit, checks={'membership': False}))
            self.assertEqual(self.row(collect_wma_acceptance(self.root), 'bundles.wma')['measurement_status'], 'MISSING')
            for key, value in (('source_sha256', 'other-source'), ('manifest', str(self.root / 'old.json'))):
                self.save('independent.json', dict(audit, **{key: value}))
                self.assertEqual(self.row(collect_wma_acceptance(self.root), 'bundles.wma')['measurement_status'], 'MISSING')
            self.save('independent.json', audit)
        with patch('scripts.collect_module_runtimes.bundle_timing_status', return_value='scientific_contract_failed'):
            records = collect_wma_acceptance(self.root)
            self.assertEqual(records[0]['runtime_seconds'], 420)
            self.assertEqual(self.row(records, 'bundles.wma')['measurement_status'], 'MISSING')

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

    def test_full_brain_dki_uses_fit_not_audit_duration(self):
        payload = {"status": "passed", "automatic_qc_passed": True, "subject_id": "fixture",
                   "checks": {"inputs_unchanged": True}, "independent_checks": [{"passed": True}],
                   "runtime_seconds": 4, "full_fit_runtime_seconds": 400,
                   "mask_voxels": 200, "valid_voxels": 190, "human_review": "pending"}
        self.save("dki_independent/acceptance.json", payload)
        records = collect_completion_measurements(self.root)
        row = self.row(records, "microstructure.dki")
        self.assertEqual(row["seconds"], 400)
        self.assertEqual(row["measurement_status"], "READY")
        self.assertIn("200 voxels", row["input_scope"])
        for key, value in (("independent_checks", [{"passed": False}]),
                           ("checks", {"inputs_unchanged": False}), ("status", "running")):
            invalid = dict(payload, **{key: value})
            self.save("dki_independent/acceptance.json", invalid)
            self.assertEqual(self.row(collect_completion_measurements(self.root), "microstructure.dki")["measurement_status"], "MISSING")

    def test_full_brain_mkcurve_timing_requires_reference_parity_not_all_voxels_valid(self):
        payload = dict(status='passed', automatic_integrity_qc_passed=True, inputs_unchanged=True,
                       reference_parity={'maps': {'passed': True}}, checks=[{'passed': True}],
                       mask_voxels=200, corrected_valid_voxels=190, runtime_seconds=15,
                       quantitative_domain_all_voxels_valid=False)
        path = 'mkcurve_fullbrain/acceptance.json'
        self.save(path, payload)
        row = self.row(collect_scientific_closure(self.root), 'microstructure.mkcurve')
        self.assertEqual(row['seconds'], 15)
        self.assertEqual(row['measurement_status'], 'READY')
        self.assertIn('not all voxels valid', row['input_scope'])
        payload['reference_parity']['maps']['passed'] = False
        self.save(path, payload)
        self.assertEqual(self.row(collect_scientific_closure(self.root), 'microstructure.mkcurve')['measurement_status'], 'MISSING')

    def test_legacy_bundle_green_status_cannot_supply_successful_compute_time(self):
        self.assertEqual(bundle_timing_status("bundles.wmql", {"status": "completed"}), "scientific_contract_failed")
        self.assertEqual(bundle_timing_status("bundles.wma", {"status": "completed", "output_summary": {
            "anatomical_tract_count": 74, "anatomical_tract_readable_count": 74,
            "anatomical_tract_nonempty_count": 64, "anatomical_tract_streamline_counts": {"T_CST_left.vtp": 1},
        }}), "scientific_contract_failed")

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

    def test_latest_policy_rerun_is_selected_even_if_slower(self):
        payload = {"status": "PASS", "runtime_seconds": 719,
                   "checks": {"pipeline_completed": True, "cuda_selected": True},
                   "device_execution": {"resolved": "cuda"}}
        self.save("eddy_cuda_fixed/acceptance.json", payload)
        payload["runtime_seconds"] = 900
        self.save("eddy_cuda_fresh/acceptance.json", payload)
        self.assertEqual(self.row(collect_device_measurements(self.root), "preprocessing.mrtrix_fsl")["seconds"], 900)

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
