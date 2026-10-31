"""Regression tests for ACT tissue semantics and diagnostic coverage."""

import json
from pathlib import Path
import tempfile
import unittest

import nibabel as nib
import numpy as np

from scripts.diagnose_csd_act import tissue_region_summary, track_coverage
from scripts.audit_scientific_outputs import _audit_act_preparation
from shared.orchestrator import _act_inputs_current
from tractography.act_prep import ACT_PREP_VERSION


class CSDActDiagnosticTest(unittest.TestCase):
    def test_point_crossing_is_not_mistaken_for_endpoint_certification(self):
        atlas = np.zeros((6, 3, 3), dtype=np.int16)
        atlas[1, 1, 1] = 16
        atlas[4, 1, 1] = 1024
        track = np.array([[0, 1, 1], [1, 1, 1], [4, 1, 1], [5, 1, 1]], dtype=np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'tracks.tck'
            nib.streamlines.save(nib.streamlines.Tractogram([track], affine_to_rasmm=np.eye(4)), str(path))
            summary = track_coverage(path, atlas, np.eye(4))
        self.assertEqual(summary['counts']['brainstem_motor_crossing_left'], 1)
        self.assertEqual(summary['counts']['brainstem_motor_opposite_endpoints_left'], 0)

    def test_absent_anatomy_is_reported_not_given_green_state(self):
        summary = tissue_region_summary(np.zeros((2, 2, 2, 5)), np.zeros((2, 2, 2)))
        self.assertEqual(summary['16']['voxels'], 0)
        self.assertIsNone(summary['16']['mean_5tt'])

    def test_old_v2_act_cannot_reuse_csd_even_when_files_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dependencies = {}
            for key in ('five_tt', 'gmwmi'):
                path = root / f'{key}.nii.gz'
                path.write_bytes(b'test fixture, not imaging data')
                stat = path.stat()
                dependencies[key] = dict(path=str(path), size=stat.st_size, mtime_ns=stat.st_mtime_ns)
            manifest = root / 'csd_act_manifest.json'
            manifest.write_text(json.dumps(dict(dependencies=dependencies)))
            prior = root / 'source_parcellation.nii.gz'
            prior.write_bytes(b'recorded DDParcel fixture')
            stat = prior.stat()
            (root / 'act_prep_manifest.json').write_text(json.dumps(dict(inputs={'parcellation': {
                'path': str(prior), 'exists': True, 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}})))
            qc = root / 'act_prep_qc.json'
            qc.write_text(json.dumps(dict(status='completed', version=2)))
            self.assertFalse(_act_inputs_current(manifest))
            checks = []
            _audit_act_preparation({'tasks': [{'name': 'tractography.csd_act',
                'manifest_path': str(manifest), 'status': 'completed'}]}, checks)
            self.assertEqual(len(checks), 1)
            self.assertFalse(checks[0]['passed'])
            qc.write_text(json.dumps(dict(status='completed', version=ACT_PREP_VERSION, sgm_from_ddparcel=True,
                five_tt_stats={'channel_volume_voxel_units': {'sgm': 1.0}})))
            self.assertTrue(_act_inputs_current(manifest))


if __name__ == '__main__':
    unittest.main()
