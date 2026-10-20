"""Never publish WMA speedups without checking its actual inputs."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.summarize_complete_models import wma_input_audit


class CompleteModelEvidenceTest(unittest.TestCase):
    def fixture(self, root):
        atlas=root/'atlas'
        author=root/'author'
        atlas.mkdir()
        author.mkdir()
        (atlas/'registration.vtk').write_bytes(b'fixed geometry')
        (author/'fit.py').write_text('# author source\n')
        tractogram=root/'subject.vtk'
        tractogram.write_bytes(b'moving geometry')
        return dict(settings=dict(stages='wma',wma_input=str(tractogram),
                                  wma_atlas=str(atlas),wma_root=str(author)))

    def test_whole_atlas_subject_and_author_checked_outside_timing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            current=self.fixture(root)
            initial=wma_input_audit(root/'campaign.json',current)
            self.assertTrue(initial['captured_before_wma'])
            self.assertEqual(initial['status'],'pending')
            record=json.loads((root/'wma_input_audit.json').read_text())
            self.assertEqual(len(record['before']),3)
            (root/'wma').mkdir()
            (root/'wma/comparison.json').write_text('{}')
            final=wma_input_audit(root/'campaign.json',current)
            self.assertEqual(final['status'],'passed')
            self.assertTrue(final['inputs_unchanged'])

    def test_modified_atlas_fails_instead_of_publishing_a_speedup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            current=self.fixture(root)
            wma_input_audit(root/'campaign.json',current)
            (root/'atlas/registration.vtk').write_bytes(b'changed geometry')
            (root/'wma').mkdir()
            (root/'wma/comparison.json').write_text('{}')
            final=wma_input_audit(root/'campaign.json',current)
            self.assertEqual(final['status'],'failed')
            self.assertFalse(final['inputs_unchanged'])

    def test_late_hash_capture_is_not_a_before_after_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            current=self.fixture(root)
            (root/'wma').mkdir()
            (root/'wma/comparison.json').write_text('{}')
            final=wma_input_audit(root/'campaign.json',current)
            self.assertEqual(final['status'],'failed')
            self.assertFalse(final['captured_before_wma'])


if __name__=='__main__':
    unittest.main()
