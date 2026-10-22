"""Source fingerprints are reproducible without running downloaded Python/pickle."""

import hashlib
from pathlib import Path
import pickle
import tempfile
import unittest

from scripts.audit_performance_upstreams import amico_config_version, source_functions
from scripts.benchmark_complete_models import numerical_environment


class PerformanceUpstreamTests(unittest.TestCase):
    def test_function_fingerprint_includes_decorators(self):
        source = '@adapter\ndef fit(x):\n    return x\n\ndef other():\n    pass\n'
        expected = hashlib.sha256('@adapter\ndef fit(x):\n    return x\n'.encode()).hexdigest()
        self.assertEqual(source_functions(source, ['fit']), {'fit': expected})
        with self.assertRaises(ValueError):
            source_functions(source, ['unknown'])

    def test_recorded_amico_version_is_read_without_unpickling(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'config.pickle'
            path.write_bytes(pickle.dumps({'version': '2.1.1', 'private_path': '/not/published'}, protocol=2))
            result = amico_config_version(path)
            self.assertEqual(result['version'], '2.1.1')
            self.assertNotIn('private_path', str(result))
            path.write_bytes(pickle.dumps({'version': 'not-a-version'}))
            with self.assertRaises(ValueError):
                amico_config_version(path)

    def test_complete_worker_records_installed_versions(self):
        record = numerical_environment()
        self.assertEqual(set(record['packages']), {'dipy', 'scipy', 'numpy', 'nibabel', 'dmri-amico'})
        self.assertTrue(record['python'])


if __name__ == '__main__':
    unittest.main()
