"""Not-applicable checks must not inflate a successful scientific audit."""

import unittest

from scripts.audit_bundle_products import applicable_checks


class BundleAuditScopeTests(unittest.TestCase):
    def test_wma_does_not_claim_endpoint_or_disjoint_partition_checks(self):
        checks, not_run = applicable_checks('wma_org_atlas', None, True, 10, None)
        self.assertEqual(len(checks), 2)
        self.assertTrue(all(checks.values()))
        self.assertEqual(set(not_run), {'tractcloud_disjoint_assignment', 'bundled_wmql_endpoint_rules'})

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
