"""Public measurements remain traceable and never inherit private evidence paths."""

import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_performance_site import build_evidence, render

ROOT = Path(__file__).resolve().parents[2]


class PerformanceSiteTests(unittest.TestCase):
    def test_public_measurements_match_checked_evidence(self):
        evidence = build_evidence()
        saved = json.loads((ROOT / 'docs/site/assets/data/performance.json').read_text())
        self.assertEqual(saved, evidence)
        self.assertEqual(len(evidence['records']), 7)
        for row in evidence['records']:
            self.assertTrue(math.isclose(row['speed_ratio'], row['reference_seconds'] / row['optimized_seconds']))
            self.assertTrue(row['scope'] and row['baseline'] and row['limitation'])
        self.assertEqual(next(row for row in evidence['records'] if row['id'] == 'noddi')['category'], 'parallel')
        self.assertEqual(next(row for row in evidence['records'] if row['id'] == 'mkcurve')['category'], 'port')
        self.assertEqual(next(row for row in evidence['records'] if row['id'] == 'dki')['category'], 'integration')
        self.assertTrue(all(row['upstream_reference'] for row in evidence['records']))
        self.assertEqual(evidence['upstream_review']['stable_versions']['dipy'], '1.12.1')
        serialized = json.dumps(evidence)
        for private in ('/data/', '/home/', '/Users/', '/Volumes/', 'snapshot_hashes', 'source_path'):
            self.assertNotIn(private, serialized)
        page = (ROOT / 'docs/site/index.html').read_text()
        self.assertIn(render(evidence), page)
        stub = (ROOT / 'docs/site/performance.html').read_text()
        self.assertIn('url=index.html#performance', stub)
        self.assertNotIn('perf-table', stub)

    def test_unverified_full_brain_result_is_not_publishable(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ('freewater_latest_stable_full_20261022.json', 'complete_models_20261020.json'):
                shutil.copy2(ROOT / 'docs/release/benchmarks' / name, folder / name)
            file = folder / 'freewater_latest_stable_full_20261022.json'
            record = json.loads(file.read_text())
            record['qc_equal'] = False
            file.write_text(json.dumps(record))
            with patch('scripts.build_performance_site.BENCHMARKS', folder), self.assertRaises(ValueError):
                build_evidence()


if __name__ == '__main__':
    unittest.main()
