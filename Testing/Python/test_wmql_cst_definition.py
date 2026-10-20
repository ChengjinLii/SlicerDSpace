"""Synthetic rule semantics only; these are not anatomical accuracy evidence."""

from pathlib import Path
import ast
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


class PublishedCSTDefinitionTests(unittest.TestCase):
    def test_ddparcel_act_preserves_original_af_and_imports_cst_without_override(self):
        from tractography.wmql import bundled_wmql_query_path
        def assignments(path, name):
            return [ast.dump(node, include_attributes=False) for node in ast.parse(path.read_text()).body
                    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name) and target.value.id == name for target in node.targets)]
        adapted = bundled_wmql_query_path('ddparcel_act')
        self.assertEqual(assignments(adapted, 'AF'), assignments(bundled_wmql_query_path('published_endpoints'), 'AF'))
        self.assertFalse(assignments(adapted, 'CST'))
        imports = [node.names[0].name for node in ast.parse(adapted.read_text()).body if isinstance(node, ast.Import)]
        self.assertEqual(imports, ['freesurfer_queries.qry'])
        self.assertEqual(bundled_wmql_query_path(), adapted)

    def test_adapted_provenance_never_claims_unchanged_author_af(self):
        from tractography.wmql import (AUTHOR_ALIAS_SHA256, AUTHOR_BUNDLE_QUERY_SHA256,
                                       bundled_wmql_query_path, wmql_query_provenance)
        dependencies = {'FreeSurfer.qry': AUTHOR_ALIAS_SHA256,
                        'freesurfer_queries.qry': AUTHOR_BUNDLE_QUERY_SHA256}
        provenance = wmql_query_provenance(bundled_wmql_query_path('ddparcel_act'), dependencies)
        self.assertEqual(provenance['preset'], 'ddparcel_af_candidates_author_cst')
        self.assertIn('not the author crossing/exclusion', provenance['AF'])
        custom = wmql_query_provenance(bundled_wmql_query_path('ddparcel_act'), dict(dependencies, **{'FreeSurfer.qry': 'modified'}))
        self.assertEqual(custom['preset'], 'ddparcel_act_custom_aliases')

    def test_provenance_checks_aliases_and_does_not_attribute_absent_af(self):
        from tractography.wmql import AUTHOR_ALIAS_SHA256, bundled_wmql_query_path, wmql_query_provenance

        published = bundled_wmql_query_path().with_name('CST_WMQL2016.qry')
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch('tractography.wmql._default_query_data_dir', return_value=None):
                verified = {'/isolated/backend/FreeSurfer.qry': AUTHOR_ALIAS_SHA256}
                provenance = wmql_query_provenance(published, verified)
                self.assertEqual(provenance['preset'], 'published_cst_endpoints')
                self.assertNotIn('AF', provenance)
                self.assertIn('aliases_reference', provenance)
                copy = Path(temporary) / published.name
                copy.write_bytes(published.read_bytes())
                (copy.parent / 'FreeSurfer.qry').write_text('Brain_Stem |= 999\n')
                self.assertEqual(wmql_query_provenance(copy)['preset'], 'published_statement_custom_aliases')

    def test_local_modified_reference_cannot_certify_itself(self):
        from tractography.wmql import bundled_wmql_query_path, wmql_query_provenance

        with tempfile.TemporaryDirectory() as temporary:
            reference = Path(temporary)
            (reference / 'FreeSurfer.qry').write_text('Brain_Stem |= 999\n')
            with mock.patch('tractography.wmql._default_query_data_dir', return_value=reference):
                provenance = wmql_query_provenance(bundled_wmql_query_path('published_endpoints'))
            self.assertEqual(provenance['preset'], 'published_statement_custom_aliases')

    def test_author_definition_is_distinct_from_endpoint_preset(self):
        from tractography.wmql import AUTHOR_ALIAS_SHA256, AUTHOR_BUNDLE_QUERY_SHA256, wmql_query_provenance

        digest = mock.Mock()
        digest.hexdigest.return_value = AUTHOR_BUNDLE_QUERY_SHA256
        with mock.patch('tractography.wmql.hashlib.sha256', return_value=digest):
            provenance = wmql_query_provenance(Path(__file__), {'FreeSurfer.qry': AUTHOR_ALIAS_SHA256,
                                                              'freesurfer_queries.qry': AUTHOR_BUNDLE_QUERY_SHA256})
            self.assertEqual(provenance['preset'], 'author_repository_crossing_exclusion')
            custom = wmql_query_provenance(Path(__file__), {'FreeSurfer.qry': 'unverified',
                                                          'freesurfer_queries.qry': AUTHOR_BUNDLE_QUERY_SHA256})
            self.assertEqual(custom['preset'], 'author_statement_custom_aliases')

    def test_missing_aliases_are_rejected_not_certified_as_published(self):
        from tractography.wmql import bundled_wmql_query_path, wmql_query_provenance

        with mock.patch('tractography.wmql._default_query_data_dir', return_value=None):
            with self.assertRaisesRegex(FileNotFoundError, 'FreeSurfer.qry'):
                wmql_query_provenance(bundled_wmql_query_path('published_endpoints'))

    def evaluate(self, terminal_label):
        backend = ROOT / 'third_party/tract_querier'
        if not (backend / 'tract_querier/__init__.py').is_file():
            self.skipTest('Optional author TractQuerier source is not installed; rule integration test only')
        sys.path.insert(0, str(backend))
        self.addCleanup(sys.path.pop, 0)
        import tract_querier as tq
        from tractography.wmql import bundled_wmql_query_path

        labels = np.full((101, 3, 3), 2, dtype=np.int16)
        labels[0] = 16
        labels[-1] = terminal_label
        track = np.column_stack([np.arange(101), np.ones(101), np.ones(101)])
        index = tq.TractographySpatialIndexing([track], labels, np.eye(4), 0, 2.0)
        data = ROOT / 'third_party/tract_querier/tract_querier/data'
        results = []
        for path in (bundled_wmql_query_path('published_endpoints'), bundled_wmql_query_path().with_name('CST_WMQL2016.qry')):
            queries = tq.queries_preprocess(path.read_text(), include_folders=[str(data)])
            results.append(tq.eval_queries(queries, index))
        return results, index

    def test_true_endpoints_do_not_require_two_percent_region_crossing(self):
        results, index = self.evaluate(1024)
        self.assertNotIn(0, index.crossing_labels_tracts.get(16, set()))
        self.assertNotIn(0, index.crossing_labels_tracts.get(1024, set()))
        for result in results:
            self.assertEqual(result['cst.left'], {0})
            self.assertEqual(result['cst.right'], set())

    def test_original_aliases_also_accept_real_regional_white_matter(self):
        results, _ = self.evaluate(3024)
        self.assertEqual(results[0]['cst.left'], results[1]['cst.left'])
        self.assertEqual(results[0]['cst.left'], {0})


if __name__ == '__main__':
    unittest.main()
