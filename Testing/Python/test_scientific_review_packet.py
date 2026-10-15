"""Review preparation must preserve native data and cannot approve its own work."""

from argparse import Namespace
import json
from pathlib import Path
import tempfile
import unittest

import nibabel as nib
import numpy as np

from scripts.prepare_scientific_review import prepare, fingerprint


class ScientificReviewPacketTest(unittest.TestCase):
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
