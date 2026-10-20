"""Bulk copying must match unmodified author WMA, not a previous plugin."""

import importlib
import inspect
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

from tractography.wma_preprocessing import AuthorCompatibleLengthFilter
from tractography.wma_registration import RegistrationPreprocessCache


class WMAPreprocessingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import vtk
            from vtk.util.numpy_support import vtk_to_numpy
        except ImportError:
            raise unittest.SkipTest('Optional VTK is not available')
        cls.vtk, cls.array = vtk, staticmethod(vtk_to_numpy)
        directory = Path(__file__).resolve().parents[2] / 'third_party/whitematteranalysis/whitematteranalysis'
        if not (directory/'filter.py').is_file():
            raise unittest.SkipTest('Pinned author source is not present; no author comparison claimed')
        # Execute the real filter module without unrelated optional Excel/UI imports.
        package = types.ModuleType('whitematteranalysis')
        package.__path__ = [str(directory)]
        with patch.dict(sys.modules, {'whitematteranalysis': package}):
            for name in list(sys.modules):
                if name.startswith('whitematteranalysis.'):
                    del sys.modules[name]
            cls.author = importlib.import_module('whitematteranalysis.filter')

    def polydata(self, *, double=True):
        points = self.vtk.vtkPoints()
        if double:
            points.SetDataTypeToDouble()
        for index in range(40):
            points.InsertNextPoint(index * .25, index * .125 + .0123456789, index * -.0625)
        cells = self.vtk.vtkCellArray()
        for ids in ([0,1,2,3,4], [4,3,2,1,0], [2,2,3,4,5,6], range(10,30), [0,1,2]):
            cell = self.vtk.vtkIdList()
            for index in ids:
                cell.InsertNextId(index)
            cells.InsertNextCell(cell)
        result = self.vtk.vtkPolyData()
        result.SetPoints(points)
        result.SetLines(cells)
        return result

    def assert_same(self, left, right):
        self.assertEqual(left.GetNumberOfLines(), right.GetNumberOfLines())
        self.assertEqual(left.GetNumberOfPoints(), right.GetNumberOfPoints())
        self.assertEqual(left.GetPoints().GetDataType(), right.GetPoints().GetDataType())
        np.testing.assert_array_equal(self.array(left.GetPoints().GetData()), self.array(right.GetPoints().GetData()))
        np.testing.assert_array_equal(self.array(left.GetLines().GetData()), self.array(right.GetLines().GetData()))
        self.assertEqual(left.GetPointData().GetNumberOfArrays(), right.GetPointData().GetNumberOfArrays())
        self.assertEqual(left.GetCellData().GetNumberOfArrays(), right.GetCellData().GetNumberOfArrays())

    def test_shared_reversed_points_and_block_boundaries_match_author_exactly(self):
        for double in (False, True):
            source = self.polydata(double=double)
            before = self.array(source.GetPoints().GetData()).copy()
            for block in (1, 3, 7, 262144):
                fast = AuthorCompatibleLengthFilter(self.author.preprocess, block_points=block)
                expected = self.author.preprocess(source, .25, verbose=False)
                actual = fast(source, .25, verbose=False)
                self.assert_same(expected, actual)
                self.assertEqual(fast.calls, 1)
                self.assertLessEqual(fast.peak_block_points, block)
            np.testing.assert_array_equal(self.array(source.GetPoints().GetData()), before)

    def test_thresholds_empty_selection_and_32bit_connectivity(self):
        source = self.polydata()
        source.GetLines().ConvertTo32BitStorage()
        for minimum, maximum in ((0, None), (.9, 2.8), (999, None), (-1, 0), (.25, .5)):
            fast = AuthorCompatibleLengthFilter(self.author.preprocess, block_points=4)
            self.assert_same(self.author.preprocess(source, minimum, max_length_mm=maximum, verbose=False),
                             fast(source, minimum, max_length_mm=maximum, verbose=False))

    def test_attribute_and_index_requests_bypass_without_changing_result(self):
        source = self.polydata()
        fast = AuthorCompatibleLengthFilter(self.author.preprocess)
        expected, indices = self.author.preprocess(source, 1, verbose=False, return_indices=True)
        actual, actual_indices = fast(source, 1, verbose=False, return_indices=True)
        self.assert_same(expected, actual)
        np.testing.assert_array_equal(indices, actual_indices)
        for argument in ('preserve_point_data', 'preserve_cell_data', 'remove_u', 'remove_brainstem'):
            options = {argument: True, 'verbose': False}
            self.assert_same(self.author.preprocess(source, 1, **options), fast(source, 1, **options))
        self.assertEqual(fast.calls, 0)
        self.assertEqual(fast.bypassed, 5)

    def test_empty_and_degenerate_input_keeps_author_behavior(self):
        source = self.vtk.vtkPolyData()
        fast = AuthorCompatibleLengthFilter(self.author.preprocess)
        self.assertIs(fast(source, 1, verbose=False), source)
        source = self.polydata()
        source.GetPoints().GetData().Fill(0)
        for function in (self.author.preprocess, fast):
            with self.assertRaises((ZeroDivisionError, ValueError, OverflowError)):
                function(source, 1, verbose=False)

    def test_signature_and_existing_cache_still_work(self):
        fast = AuthorCompatibleLengthFilter(self.author.preprocess)
        self.assertEqual(inspect.signature(fast), inspect.signature(self.author.preprocess))
        cache = RegistrationPreprocessCache(fast)
        source = self.polydata()
        first = cache(source, 1, verbose=False)
        self.assertIs(cache(source, 1, verbose=False), first)
        self.assertEqual(fast.calls, 1)
        self.assertEqual(cache.hits, 1)

    def test_runtime_includes_implementation_license_and_benchmark_tables(self):
        from scripts.extension_runtime.runtime_resources import runtime_files
        selected = set(runtime_files(Path(__file__).resolve().parents[2]))
        self.assertTrue({'tractography/wma_preprocessing.py', 'licenses/WMA.txt',
                         'docs/release/benchmarks/compute_optimizations_20261020.csv'} <= selected)

    def test_fast_filter_preserves_complete_random_state(self):
        previous = np.random.get_state()
        try:
            np.random.seed(3407)
            np.random.normal()
            before = np.random.get_state()
            AuthorCompatibleLengthFilter(self.author.preprocess)(self.polydata(), 1, verbose=False)
            after = np.random.get_state()
            self.assertEqual(before[0], after[0])
            np.testing.assert_array_equal(before[1], after[1])
            self.assertEqual(before[2:], after[2:])
        finally:
            np.random.set_state(previous)


if __name__ == '__main__':
    unittest.main()
