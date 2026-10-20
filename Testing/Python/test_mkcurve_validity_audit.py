"""Read-only audit must verify the masks consumed by regional statistics."""

import json
from pathlib import Path
import tempfile
import unittest

import nibabel as nib
import numpy as np

from scripts.audit_mkcurve_validity import audit


class MKCurveValidityAuditTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.mask = np.zeros((2, 3, 2), dtype=np.uint8)
        self.mask[0, 0, 0] = self.mask[1, 0, 1] = self.mask[0, 2, 1] = 1
        self.mask_path = self.write('brain', self.mask)
        maps = {}
        for key in ('fa', 'md', 'ad', 'rd', 'mk', 'ak', 'rk', 'e1', 'e2', 'e3'):
            values = self.mask * (.5 if key == 'fa' else (1. if key in {'mk', 'ak', 'rk'} else .001))
            maps['corrected_' + key] = str(self.write('corrected_' + key, values))
            maps['corrected_' + key + '_valid_mask'] = str(self.write('corrected_' + key + '_valid_mask', self.mask))
        for key in ('curve_valid_mask', 'corrected_valid_mask'):
            maps[key] = str(self.write(key, self.mask))
        maps['corrected_nrmse'] = str(self.write('corrected_nrmse', np.zeros(self.mask.shape)))
        coefficients = self.root / 'coefficients.npy'
        np.save(coefficients, np.zeros((3, 22)))
        self.record = {'backend': {'port_version': 2}, 'inputs': {'mask': {'path': str(self.mask_path)}},
                       'maps': maps, 'auxiliary_files': {'corrected_coefficients': str(coefficients)},
                       'metric_valid_voxels': {key: 3 for key in ('fa', 'md', 'ad', 'rd', 'mk', 'ak', 'rk')}}
        self.record_path = self.root / 'record.json'
        self.save_record()

    def write(self, name, values):
        path = self.root / (name + '.nii.gz')
        nib.save(nib.Nifti1Image(values, np.eye(4)), path)
        return path

    def save_record(self):
        self.record_path.write_text(json.dumps(self.record))

    def test_current_masks_are_verified_not_just_recomputed(self):
        result = audit(self.record_path)
        self.assertTrue(result['validity_audit_passed'])
        self.assertTrue(result['source_unchanged'])
        self.assertTrue(all(item['matches_recomputed'] for item in result['saved_metric_masks'].values()))

    def test_wrong_binary_mask_cannot_pass_using_the_correct_joint_mask(self):
        bad = self.mask.copy()
        bad[1, 0, 1] = 0
        self.write('corrected_mk_valid_mask', bad)
        result = audit(self.record_path)
        self.assertTrue(result['joint_mask_reproduced'])
        self.assertFalse(result['validity_audit_passed'])
        self.assertEqual(result['saved_metric_masks']['mk']['mismatched_voxels'], 1)

    def test_missing_current_mask_is_not_accepted_as_legacy(self):
        del self.record['maps']['corrected_mk_valid_mask']
        self.save_record()
        self.assertFalse(audit(self.record_path)['validity_audit_passed'])

    def test_nonbinary_or_outside_brain_masks_are_rejected(self):
        for coordinate, value in (((0, 0, 0), 2), ((1, 2, 0), 1)):
            bad = self.mask.copy()
            bad[coordinate] = value
            self.write('corrected_mk_valid_mask', bad)
            self.assertFalse(audit(self.record_path)['validity_audit_passed'])

    def test_incorrect_recorded_coverage_is_rejected(self):
        self.record['metric_valid_voxels']['mk'] = 2
        self.save_record()
        result = audit(self.record_path)
        self.assertFalse(result['validity_audit_passed'])
        self.assertFalse(result['saved_metric_masks']['mk']['record_count_matches'])

    def test_legacy_can_only_claim_raw_bounds_audit(self):
        self.record['backend']['port_version'] = 1
        for key in list(self.record['maps']):
            if key.startswith('corrected_') and key.endswith('_valid_mask') and key != 'corrected_valid_mask':
                del self.record['maps'][key]
        self.save_record()
        result = audit(self.record_path)
        self.assertTrue(result['validity_audit_passed'])
        self.assertFalse(result['saved_metric_masks_required'])
        self.assertFalse(result['saved_metric_masks']['mk']['present'])


if __name__ == '__main__':
    unittest.main()
