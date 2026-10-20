"""Per-map/per-tract validity must not inherit an unrelated green aggregate."""

import unittest
import numpy as np
from microstructure.mkcurve import metric_validity
from tractography.wma import tract_sampling_eligibility


class ScientificEligibilityTests(unittest.TestCase):
    def test_radial_failure_does_not_erase_valid_mean_kurtosis(self):
        maps = {'mk': np.array([1., 1., 1., np.nan]), 'rk': np.array([8., 1., 1., 1.]),
                'e1': np.full(4, .002), 'e2': np.full(4, .001), 'e3': np.array([.001, -.001, .001, .001])}
        before = {key: value.copy() for key, value in maps.items()}
        valid = metric_validity(maps, np.ones(4, dtype=bool), np.array([True, True, False, True]), np.zeros(4))
        np.testing.assert_array_equal(valid['mk'], [True, False, False, False])
        np.testing.assert_array_equal(valid['rk'], [False, False, False, True])
        for key in maps:
            np.testing.assert_array_equal(maps[key], before[key])

    def test_major_tract_success_does_not_certify_sparse_small_tract(self):
        result = tract_sampling_eligibility({'T_CST_left.vtp': 337, 'T_EC_left.vtp': 8, 'broken.vtp': None})
        self.assertFalse(result['all_tract_sampling_passed'])
        self.assertEqual(result['excluded_from_quantification'], ['T_EC_left.vtp', 'broken.vtp'])
        self.assertTrue(result['tracts']['T_CST_left.vtp']['sampling_passed'])
        self.assertFalse(result['tracts']['T_CST_left.vtp']['quantification_eligible'])
        self.assertFalse(tract_sampling_eligibility({})['all_tract_sampling_passed'])

    def test_stale_green_wma_cannot_reenable_gui_loading(self):
        from shared.bundle_qc import bundle_record_error
        from tractography.wma import REQUIRED_MAJOR_TRACTS, WMA_QC_VERSION
        counts = {f'T_{index}.vtp': 100 for index in range(69)}
        counts.update({key: 100 for key in REQUIRED_MAJOR_TRACTS})
        summary = dict(anatomical_tract_count=74, anatomical_tract_readable_count=74,
                       anatomical_tract_nonempty_count=74, anatomical_tract_streamline_counts=counts)
        record = dict(status='completed', automatic_qc_passed=True, version=WMA_QC_VERSION, output_summary=summary)
        self.assertIsNone(bundle_record_error('bundles.wma', record))
        counts['T_0.vtp'] = 5
        self.assertIn('T_0.vtp', bundle_record_error('bundles.wma', record))
        counts['T_0.vtp'] = 100
        record['version'] = 1
        self.assertIn('Legacy WMA', bundle_record_error('bundles.wma', record))


if __name__ == '__main__':
    unittest.main()
