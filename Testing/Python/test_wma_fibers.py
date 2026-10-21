"""Author parity for point selection, state, fallback and method binding."""
from pathlib import Path
import importlib.util
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk

from tractography.wma_fibers import AuthorCompatibleFiberArrayConverter, fiber_conversion_support


class WMAFibersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]/'third_party/whitematteranalysis'
        if not (root/'whitematteranalysis/fibers.py').is_file():
            raise unittest.SkipTest('Optional pinned WMA author source unavailable')
        # Load the unchanged author module without unrelated optional Excel/
        # rendering imports from WMA's package-level __init__.
        spec = importlib.util.spec_from_file_location('author_fibers_parity', root/'whitematteranalysis/fibers.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.author = module.FiberArray

    def source(self, dtype=np.float32):
        coordinates = np.random.default_rng(42).normal(size=(1024, 3)).astype(dtype)
        points = vtk.vtkPoints()
        points.SetData(numpy_to_vtk(coordinates, deep=True))
        lines = vtk.vtkCellArray()
        for length in range(1, 513):
            ids = vtk.vtkIdList()
            # Shared, reversed and nonconsecutive point IDs are intentional.
            for index in ((np.arange(length)*3+length) % len(coordinates))[::-1]:
                ids.InsertNextId(int(index))
            lines.InsertNextCell(ids)
        source = vtk.vtkPolyData()
        source.SetPoints(points)
        source.SetLines(lines)
        return source

    def test_exact_arrays_hemispheres_rounding_and_traversal(self):
        for dtype in (np.float32, np.float64):
            source = self.source(dtype)
            for count in (2, 3, 10, 15, 30):
                left, right = self.author(), self.author()
                for obj in (left, right):
                    obj.hemispheres = True
                    obj.hemisphere_percent_threshold = .95
                left.convert_from_polydata(source, count)
                before = source.GetMTime()
                fast = AuthorCompatibleFiberArrayConverter(self.author, block_size=17)
                fast(right, source, count)
                for name in vars(left):
                    np.testing.assert_equal(getattr(right, name), getattr(left, name), err_msg=name)
                self.assertEqual(source.GetMTime(), before)
                self.assertEqual(source.GetLines().GetTraversalCellId(), 512)
                self.assertEqual(fast.calls, 1)

    def test_method_binding_and_default_points(self):
        source = self.source()
        fast = AuthorCompatibleFiberArrayConverter(self.author)
        original = self.author.convert_from_polydata
        left, right = self.author(), self.author()
        left.points_per_fiber = right.points_per_fiber = 13
        left.convert_from_polydata(source)
        with patch.object(self.author, 'convert_from_polydata', fast.method):
            right.convert_from_polydata(source)
        self.assertIs(self.author.convert_from_polydata, original)
        np.testing.assert_array_equal(left.fiber_array_r, right.fiber_array_r)
        self.assertEqual(fast.calls, 1)

    def test_unsupported_cases_keep_author_errors_and_verbose_output(self):
        source = self.source()
        for budget, count in ((0, 10), (1024**2, 1)):
            fast = AuthorCompatibleFiberArrayConverter(self.author, max_aux_bytes=budget)
            if count == 1:
                with self.assertRaises(ZeroDivisionError):
                    fast(self.author(), source, count)
            else:
                left, right = self.author(), self.author()
                left.convert_from_polydata(source, count)
                fast(right, source, count)
                np.testing.assert_array_equal(left.fiber_array_r, right.fiber_array_r)
            self.assertEqual(fast.bypassed, 1)
        class Custom(self.author):
            pass
        fast = AuthorCompatibleFiberArrayConverter(self.author)
        fast(Custom(), source, 10)
        self.assertEqual(fast.bypassed, 1)

    def test_source_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(fiber_conversion_support(root)['supported'])
            (root/'fibers.py').write_text('changed author source', encoding='utf-8')
            self.assertFalse(fiber_conversion_support(root)['supported'])
        with self.assertRaises(ValueError):
            AuthorCompatibleFiberArrayConverter(self.author, block_size=0)


if __name__ == '__main__':
    unittest.main()
