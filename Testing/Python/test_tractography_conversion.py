"""Whole-tractogram conversion must not silently become a display preview."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import nibabel as nib
import numpy as np

from tractography.conversion import ensure_vtk_tractogram
from connectome.pipeline import _iter_streamlines


class ConversionTest(unittest.TestCase):
    def test_all_points_ras_and_cache_invalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / 'source.trk', root / 'out.vtk'
            tracks = [np.array([[13.5, -20.25, 60.5], [12.5, -19.25, 58.0], [10., -18., 55.]], np.float32),
                      np.array([[-30., 6., 8.], [-29., 7., 10.]], np.float32)]
            nib.streamlines.save(nib.streamlines.Tractogram(tracks, affine_to_rasmm=np.eye(4)), str(source))
            record = ensure_vtk_tractogram(source, target)
            self.assertEqual(record['streamline_count'], 2)
            for original, restored in zip(tracks, _iter_streamlines(target)):
                np.testing.assert_allclose(original, restored, atol=1e-4, rtol=0)
            with mock.patch('nibabel.streamlines.load', side_effect=AssertionError('cache should avoid decoding')):
                self.assertEqual(ensure_vtk_tractogram(source, target), record)
            target.write_text('corrupted export')
            self.assertEqual(ensure_vtk_tractogram(source, target)['vtk_sha256'], record['vtk_sha256'])
            tracks[0][0, 0] += 5
            nib.streamlines.save(nib.streamlines.Tractogram(tracks, affine_to_rasmm=np.eye(4)), str(source))
            updated = ensure_vtk_tractogram(source, target)
            self.assertNotEqual(updated['source_sha256'], record['source_sha256'])
            self.assertNotEqual(updated['vtk_sha256'], record['vtk_sha256'])
            self.assertEqual(json.loads(target.with_suffix('.conversion.json').read_text()), updated)

    def test_empty_and_degenerate_sources_are_not_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for tracks in ([], [np.ones((3, 3), np.float32)]):
                source, target = root / 'source.trk', root / 'out.vtk'
                nib.streamlines.save(nib.streamlines.Tractogram(tracks, affine_to_rasmm=np.eye(4)), str(source))
                with self.assertRaises(ValueError):
                    ensure_vtk_tractogram(source, target)
                self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
