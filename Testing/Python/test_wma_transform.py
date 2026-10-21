"""Exact VTK batching with bounded memory; real author optimizer tests are separate."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import vtk

from tractography.wma_transform import AuthorCompatibleFiberTransform, registration_transform_support


def converter(vector, *, scaled=True, mode=(1, 1, 1, 1)):
    transform = vtk.vtkTransform()
    transform.Translate(*vector[:3])
    transform.RotateX(vector[3])
    transform.RotateY(vector[4])
    transform.RotateZ(vector[5])
    transform.Scale(*vector[6:9])
    return transform


def original(array, vector, mode=(1, 1, 1, 1)):
    # Literal point-call/copy structure of the pinned author implementation.
    output = np.zeros(array.shape)
    transform = converter(vector, scaled=True, mode=mode)
    for line in range(array.shape[1]):
        for index in range(array.shape[2]):
            point = transform.TransformPoint(array[0, line, index], array[1, line, index], array[2, line, index])
            output[:, line, index] = point
    return output


class WMATransformTests(unittest.TestCase):
    def test_all_points_exact_for_dtype_and_memory_layout(self):
        rng = np.random.default_rng(2026)
        for dtype in (np.float32, np.float64):
            data = rng.normal(size=(3, 31, 15)).astype(dtype)
            strided = np.repeat(data, 2, axis=-1)[..., ::2]
            for source in (data, np.asfortranarray(data), strided, data[..., ::-1]):
                before = source.copy()
                vector = np.r_[rng.normal(size=6), [1.1, .95, 1.05]]
                fast = AuthorCompatibleFiberTransform(original, converter)
                actual = fast(source, vector)
                np.testing.assert_array_equal(actual, original(source, vector))
                np.testing.assert_array_equal(source, before)
                self.assertTrue(actual.flags.c_contiguous)
                self.assertEqual(actual.dtype, np.float64)
                self.assertEqual(fast.calls, 1)
                self.assertEqual(fast.bypassed, 0)
                self.assertFalse(np.shares_memory(actual, source))

    def test_oversized_empty_and_nonfinite_inputs_retain_author(self):
        vector = np.r_[np.zeros(6), np.ones(3)]
        for data, budget in ((np.zeros((3, 10, 2)), 0),
                             (np.zeros((3, 0, 10)), 1024),
                             (np.full((3, 2, 2), np.nan), 1024)):
            with patch(__name__+'.original', return_value='author-fallback') as fallback:
                fast = AuthorCompatibleFiberTransform(fallback, converter, max_bytes=budget)
                self.assertEqual(fast(data, vector), 'author-fallback')
                self.assertEqual(fast.calls, 0)
                self.assertEqual(fast.bypassed, 1)
                self.assertEqual(fallback.call_count, 1)

    def test_source_and_vtk_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertFalse(registration_transform_support(root)['supported'])
            path = root/'register_two_subjects.py'
            path.write_bytes(b'not the author source')
            self.assertFalse(registration_transform_support(root)['supported'])
            import hashlib
            with patch('tractography.wma_transform.AUTHOR_SHA256', hashlib.sha256(path.read_bytes()).hexdigest()):
                with patch.object(vtk, 'vtkVersion') as version:
                    version.GetVTKVersion.return_value = 'other-version'
                    self.assertFalse(registration_transform_support(root)['supported'])

    def test_invalid_budget_rejected(self):
        with self.assertRaises(ValueError):
            AuthorCompatibleFiberTransform(original, converter, max_bytes=-1)


if __name__ == '__main__':
    unittest.main()
