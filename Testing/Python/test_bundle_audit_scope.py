"""Not-applicable checks must not inflate a successful scientific audit."""

import unittest
from pathlib import Path
import tempfile
from unittest import mock

from scripts.audit_bundle_products import applicable_checks, endpoint_rule_check


class BundleAuditScopeTests(unittest.TestCase):
    def test_wma_does_not_claim_endpoint_or_disjoint_partition_checks(self):
        checks, not_run = applicable_checks('wma_org_atlas', None, True, 10, None, wma_sampling=True)
        self.assertEqual(len(checks), 3)
        self.assertTrue(all(checks.values()))
        self.assertEqual(set(not_run), {'tractcloud_disjoint_assignment', 'bundled_wmql_endpoint_rules'})

    def test_wma_sparse_or_unknown_small_tract_sampling_is_not_green(self):
        for sampling in (None, False):
            checks, _ = applicable_checks('wma_org_atlas', None, True, 0, None, wma_sampling=sampling)
            self.assertFalse(checks['wma_all_tract_sampling'])
            self.assertFalse(all(checks.values()))

    def test_external_wmql_rules_are_explicitly_not_checked(self):
        checks, not_run = applicable_checks('wmql_bundle_segmentation', None, True, 1,
                                            {'status': 'not_checked', 'reason': 'External query'})
        self.assertNotIn('bundled_wmql_endpoint_rules', checks)
        self.assertEqual(not_run['bundled_wmql_endpoint_rules'], 'External query')

    def test_applicable_failure_is_never_demoted_to_not_run(self):
        checks, not_run = applicable_checks('wmql_bundle_segmentation', None, True, 1, {'status': 'failed'})
        self.assertIs(checks['bundled_wmql_endpoint_rules'], False)
        self.assertNotIn('bundled_wmql_endpoint_rules', not_run)
        checks, not_run = applicable_checks('tractcloud_parcellation', None, True, 1, None)
        self.assertIs(checks['tractcloud_disjoint_assignment'], False)
        self.assertNotIn('tractcloud_disjoint_assignment', not_run)

    def test_legacy_endpoint_rules_are_audited_after_default_protocol_change(self):
        import nibabel as nib
        import numpy as np
        from tractography.wmql import AUTHOR_ALIAS_SHA256, bundled_wmql_query_path

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            labels = np.zeros((2, 2, 2), dtype=np.int16)
            labels[0, 0, 0], labels[1, 1, 1] = 16, 1024
            atlas = root / 'atlas.nii.gz'
            nib.save(nib.Nifti1Image(labels, np.eye(4)), atlas)
            dependencies = {str(root / 'FreeSurfer.qry'): AUTHOR_ALIAS_SHA256}
            with mock.patch('tractography.wmql.wmql_query_dependencies', return_value=dependencies), \
                 mock.patch('scripts.audit_bundle_products.tracks_from_file') as tracks:
                for query in (bundled_wmql_query_path('published_endpoints'),
                              bundled_wmql_query_path().with_name('CST_WMQL2016.qry')):
                    manifest = {'query_path': str(query), 'atlas_path': str(atlas)}
                    tracks.return_value = [np.array([[0., 0., 0.], [1., 1., 1.]])]
                    self.assertEqual(endpoint_rule_check(manifest, [root / 'x_desc-wmql_CST.left.trk'])['status'], 'passed')
                    tracks.return_value = [np.array([[0., 0., 0.], [0., 0., 1.]])]
                    result = endpoint_rule_check(manifest, [root / 'x_desc-wmql_CST.left.trk'])
                    self.assertEqual(result['status'], 'failed')
                    self.assertEqual(result['bundles'][0]['violations'], 1)

    def test_author_crossing_rules_are_not_certified_as_endpoint_rules(self):
        from tractography.wmql import bundled_wmql_query_path
        result = endpoint_rule_check({'query_path': str(bundled_wmql_query_path('author'))}, [])
        self.assertEqual(result['status'], 'not_checked')

    def test_ddparcel_act_audits_af_without_claiming_cst_endpoint_parity(self):
        import nibabel as nib
        import numpy as np
        from tractography.wmql import AUTHOR_ALIAS_SHA256, AUTHOR_BUNDLE_QUERY_SHA256, bundled_wmql_query_path

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            labels = np.zeros((2, 2, 2), dtype=np.int16)
            labels[0, 0, 0], labels[1, 1, 1] = 1024, 1030
            atlas = root / 'atlas.nii.gz'
            nib.save(nib.Nifti1Image(labels, np.eye(4)), atlas)
            manifest = {'query_path': str(bundled_wmql_query_path('ddparcel_act')), 'atlas_path': str(atlas)}
            dependencies = {str(root / 'FreeSurfer.qry'): AUTHOR_ALIAS_SHA256,
                            str(root / 'freesurfer_queries.qry'): AUTHOR_BUNDLE_QUERY_SHA256}
            af, cst = (root / ('x_desc-wmql_' + name + '.trk') for name in ('AF.left', 'CST.left'))
            with mock.patch('tractography.wmql.wmql_query_dependencies', return_value=dependencies), \
                 mock.patch('scripts.audit_bundle_products.tracks_from_file') as tracks:
                tracks.return_value = [np.array([[0., 0., 0.], [1., 1., 1.]])]
                result = endpoint_rule_check(manifest, [af, cst])
                self.assertEqual(result['status'], 'passed')
                self.assertEqual([r['query'] for r in result['bundles']], ['af.left'])
                self.assertEqual(result['checks_not_run'][0]['query'], 'cst.left')
                self.assertEqual(tracks.call_count, 1)
                self.assertEqual(endpoint_rule_check(manifest, [cst])['status'], 'not_checked')
                tracks.return_value = [np.array([[0., 0., 0.], [0., 0., 1.]])]
                self.assertEqual(endpoint_rule_check(manifest, [af, cst])['status'], 'failed')
