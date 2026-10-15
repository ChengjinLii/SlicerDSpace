"""Synthetic rule semantics only; these are not anatomical accuracy evidence."""

from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


class PublishedCSTDefinitionTests(unittest.TestCase):
    def test_provenance_checks_aliases_and_does_not_attribute_absent_af(self):
        from tractography.wmql import bundled_wmql_query_path, wmql_query_provenance

        published = bundled_wmql_query_path().with_name('CST_WMQL2016.qry')
        self.assertEqual(wmql_query_provenance(published)['preset'], 'published_cst_endpoints')
        self.assertNotIn('AF', wmql_query_provenance(published))
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / published.name
            copy.write_bytes(published.read_bytes())
            (copy.parent / 'FreeSurfer.qry').write_text('brain_stem |= 999\n')
            self.assertEqual(wmql_query_provenance(copy)['preset'], 'published_statement_custom_aliases')

    def evaluate(self, terminal_label):
        sys.path.insert(0, str(ROOT / 'third_party/tract_querier'))
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
        for path in (bundled_wmql_query_path(), bundled_wmql_query_path().with_name('CST_WMQL2016.qry')):
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
