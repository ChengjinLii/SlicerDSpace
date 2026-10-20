"""Geometry parity is one-to-one, not byte identity across ASCII export."""

import unittest
from types import SimpleNamespace

import numpy as np

from scripts.diagnose_wmql_cst import author_trace_query, track_multiset_parity, trace_af_predicates


class WMQLPredicateParityTests(unittest.TestCase):
    def test_author_trace_rejects_adapted_af_and_uses_verified_snapshot(self):
        from pathlib import Path
        from unittest import mock
        from tractography.wmql import AUTHOR_ALIAS_SHA256, AUTHOR_BUNDLE_QUERY_SHA256, bundled_wmql_query_path

        dependencies = {'FreeSurfer.qry': AUTHOR_ALIAS_SHA256,
                        'freesurfer_queries.qry': AUTHOR_BUNDLE_QUERY_SHA256}
        with mock.patch('tractography.wmql.wmql_query_dependencies', return_value=dependencies):
            for preset in ('ddparcel_act', 'published_endpoints'):
                with self.assertRaisesRegex(ValueError, 'unmodified author preset'):
                    author_trace_query({'staged_query': str(bundled_wmql_query_path(preset))})
            query = bundled_wmql_query_path('author')
            manifest = {'staged_query': str(query), 'query_snapshot_dependencies': dependencies}
            actual, folders, _ = author_trace_query(manifest)
            self.assertEqual(actual, query)
            self.assertEqual(folders, [Path(query).parent])
            manifest['query_snapshot_dependencies'] = {'tampered.qry': 'bad'}
            with self.assertRaisesRegex(ValueError, 'snapshot'):
                author_trace_query(manifest)

    def test_af_trace_preserves_all_author_exclusions(self):
        names = ('inferior_frontal_gyrus', 'middle_frontal_gyrus', 'precentral', 'superiortemporal',
                 'middletemporal', 'slf_ii', 'slf_iii', 'mdlf', 'ioff', 'ilf', 'extreme_capsule',
                 'insula', 'centrum_semiovale', 'occipital', 'temporalpole',
                 'medialorbitofrontal', 'lateralorbitofrontal', 'af')
        queries = {name + '.right': SimpleNamespace(tracts=set()) for name in names}
        queries['inferior_frontal_gyrus.right'].tracts = {1, 2, 3, 4}
        queries['superiortemporal.right'].tracts = {1, 2, 3, 5}
        queries['slf_ii.right'].tracts = {1}
        queries['extreme_capsule.right'].tracts = {2}
        queries['af.right'].tracts = {3}
        trace, selected = trace_af_predicates(queries, 'right')
        self.assertEqual(selected, {3})
        self.assertEqual(trace['base_streamlines'], 3)
        self.assertTrue(trace['exact_author_set_match'])
        self.assertEqual(sum(item['removed'] for item in trace['stages']), 2)
        queries['af.right'].tracts = {2, 3}
        self.assertFalse(trace_af_predicates(queries, 'right')[0]['exact_author_set_match'])

    def setUp(self):
        self.a = np.array([[1., 2., 3.], [2., 3., 4.], [4., 5., 6.]])
        self.b = self.a + [0., .01, 0.]

    def test_ascii_precision_and_reversed_order_preserve_multiset(self):
        result = track_multiset_parity([self.a, self.b], [self.b[::-1] + 1e-5, self.a + 1e-5])
        self.assertTrue(result['passed'])
        self.assertFalse(result['exact_byte_multiset'])
        self.assertEqual(result['matched_count'], 2)
        self.assertLess(result['max_coordinate_delta_mm'], .001)

    def test_duplicate_membership_does_not_replace_a_missing_source(self):
        result = track_multiset_parity([self.a, self.b], [self.a, self.a])
        self.assertFalse(result['passed'])
        self.assertEqual(result['matched_count'], 1)

    def test_ambiguous_neighbors_use_a_one_to_one_match(self):
        result = track_multiset_parity([self.a, self.a + .0015],
                                      [self.a + .00075, self.a - .00075])
        self.assertTrue(result['passed'])

    def test_interior_motion_is_rejected_despite_identical_endpoints(self):
        changed = self.a.copy()
        changed[1, 0] += .01
        self.assertFalse(track_multiset_parity([self.a], [changed])['passed'])

    def test_nonfinite_or_different_point_count_is_rejected(self):
        bad = self.a.copy()
        bad[1, 1] = np.nan
        self.assertFalse(track_multiset_parity([self.a], [bad])['passed'])
        self.assertFalse(track_multiset_parity([self.a], [self.a[:2]])['passed'])


if __name__ == '__main__':
    unittest.main()
