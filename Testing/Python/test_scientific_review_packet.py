"""Review preparation must preserve native data and cannot approve its own work."""

from argparse import Namespace
import json
from pathlib import Path
import tempfile
import unittest

import nibabel as nib
import numpy as np

from scripts.prepare_scientific_review import prepare, fingerprint, bundle_review_context


class ScientificReviewPacketTest(unittest.TestCase):
    def test_query_controls_and_failed_status_are_distinguishable_on_plates(self):
        failed = dict(kind='wmql_bundle_segmentation', status='failed', query_path='/rules/AF_CST.qry',
                      query_sha256='abc123', query_provenance={'preset': 'af_candidates_published_cst'})
        context = bundle_review_context(failed, Path('/reports/endpoint/wmql_manifest.json'))
        self.assertIn('recorded status: failed', context['caption'])
        self.assertIn('AF_CST.qry', context['caption'])
        self.assertIn('af_candidates_published_cst', context['caption'])
        self.assertIn('run endpoint', context['caption'])
        self.assertEqual(context['recorded_stage_status'], 'failed')
        author = dict(failed, status='completed', query_path='/author/freesurfer_queries.qry',
                      query_provenance={'preset': 'author_repository_crossing_exclusion'})
        self.assertNotEqual(context['caption'], bundle_review_context(author, Path('/reports/author/wmql_manifest.json'))['caption'])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.reference = self.root / 'fa.nii.gz'
        self.scalar = self.root / 'scalar.nii.gz'
        nib.save(nib.Nifti1Image(np.ones((5, 6, 7)), np.eye(4)), self.reference)
        nib.save(nib.Nifti1Image(np.zeros((5, 6, 7)), np.eye(4)), self.scalar)
        self.args = Namespace(reference=self.reference, brain_mask=None, volume=[f'zero scalar={self.scalar}'],
                              label=[], bundle_manifest=[], mkcurve_record=None, surface_qc=None, max_tracks=5,
                              output_dir=self.root / 'packet')

    def test_zero_valued_tissue_retained_and_review_never_auto_approved(self):
        before = fingerprint(self.scalar)
        prepare(self.args)
        record = json.loads((self.args.output_dir / 'review_packet.json').read_text())
        self.assertEqual(record['status'], 'review_pending')
        self.assertIs(record['scientific_accepted'], False)
        self.assertIsNone(record['reviewer'])
        self.assertTrue(record['sources_unchanged'])
        self.assertEqual(fingerprint(self.scalar), before)
        self.assertEqual(record['plates'][0]['interpolation'], 'nearest')
        form = json.loads((self.args.output_dir / 'manual_review.json').read_text())
        self.assertTrue(all(item['accepted'] is None for item in form['decisions']))
        self.assertTrue((self.args.output_dir / 'review_plates.pdf').is_file())

    def test_misaligned_map_rejected_instead_of_silent_resampling(self):
        affine = np.eye(4)
        affine[0, 3] = 10
        nib.save(nib.Nifti1Image(np.ones((5, 6, 7)), affine), self.scalar)
        with self.assertRaisesRegex(ValueError, 'Unmatched review grid'):
            prepare(self.args)

    def test_existing_packet_not_overwritten(self):
        self.args.output_dir.mkdir()
        with self.assertRaises(FileExistsError):
            prepare(self.args)
