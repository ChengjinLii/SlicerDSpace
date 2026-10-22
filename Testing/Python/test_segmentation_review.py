"""Reject unrelated or stale sources before creating any editable scene node."""

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock

from shared.segmentation_review import editable_tissue_copy


class SegmentationReviewTests(unittest.TestCase):
    def test_scalar_and_parcellation_nodes_are_not_tissue_labels(self):
        slicer = SimpleNamespace(mrmlScene=Mock())
        for is_labelmap, product in ((False, 'segmentation.ddseg'), (True, 'parcellation.ddparcel')):
            source = SimpleNamespace(IsA=lambda name: is_labelmap, GetAttribute=lambda name: product)
            with self.assertRaises(ValueError):
                editable_tissue_copy(slicer, source)
        slicer.mrmlScene.AddNewNodeByClass.assert_not_called()

    def test_stale_file_refuses_scene_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'tissue.nii.gz'
            path.write_bytes(b'synthetic file, not read')
            attributes = {'SlicerDDSurfer.Product': 'segmentation.ddseg',
                          'SlicerDDSurfer.SourcePath': str(path), 'SlicerDDSurfer.SourceStamp': 'stale'}
            source = SimpleNamespace(IsA=lambda name: True, GetAttribute=attributes.get)
            slicer = SimpleNamespace(mrmlScene=Mock())
            with self.assertRaisesRegex(ValueError, 'source product changed'):
                editable_tissue_copy(slicer, source)
            slicer.mrmlScene.AddNewNodeByClass.assert_not_called()


if __name__ == '__main__':
    unittest.main()
