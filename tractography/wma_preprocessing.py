"""Bulk implementation of the pinned author's attribute-free length filter.

Modified implementation of SlicerDMRI/whitematteranalysis filter.py,
commit 4532b911386d2d1bc7ebba63fdd13e65b1660623. Not an upstream release.
All or portions of this licensed product (such portions are the "Software")
have been obtained under license from The Brigham and Women's Hospital, Inc.
See licenses/WMA.txt for the applicable terms and conditions.
"""

from __future__ import annotations

import inspect
import time


class AuthorCompatibleLengthFilter:
    """Preserve the author's length estimator, copying order and float32 output.

    Install only after registration_cache_support verifies the author sources.
    Unsupported signatures, attributes, filters and VTK layouts run unchanged.
    The only retained state is diagnostic counters, not subject geometry.
    """

    def __init__(self, original, block_points=262144):
        if block_points < 1:
            raise ValueError("block_points must be positive")
        self.__wrapped__ = original
        self.signature = inspect.signature(original)
        self.block_points = block_points
        self.calls = self.bypassed = self.points_copied = self.peak_block_points = 0
        self.seconds = 0.0

    def __call__(self, *args, **kwargs):
        values = self.signature.bind(*args, **kwargs)
        values.apply_defaults()
        values = values.arguments
        expected = {"inpd", "min_length_mm", "max_length_mm", "remove_u", "remove_u_endpoint_dist",
                    "remove_brainstem", "return_indices", "return_lengths", "preserve_point_data",
                    "preserve_cell_data", "verbose"}
        flags = ("remove_u", "remove_brainstem", "return_indices", "return_lengths",
                 "preserve_point_data", "preserve_cell_data", "verbose")
        if set(values) != expected or any(values[name] for name in flags):
            self.bypassed += 1
            return self.__wrapped__(*args, **kwargs)
        started = time.monotonic()
        result = self._bulk(values['inpd'], values['min_length_mm'], values['max_length_mm'])
        if result is None:
            self.bypassed += 1
            return self.__wrapped__(*args, **kwargs)
        self.seconds += time.monotonic() - started
        self.calls += 1
        self.points_copied += result.GetNumberOfPoints()
        return result

    def _bulk(self, polydata, minimum, maximum):
        import numpy as np
        import vtk
        from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtkIdTypeArray

        if not isinstance(polydata, vtk.vtkPolyData) or not np.isfinite(minimum):
            return None
        if maximum is not None and not np.isfinite(maximum):
            return None
        lines, points = polydata.GetLines(), polydata.GetPoints()
        if points is None or polydata.GetNumberOfLines() == 0 or points.GetNumberOfPoints() == 0:
            return None
        if not hasattr(lines, 'GetOffsetsArray') or not hasattr(lines, 'GetConnectivityArray'):
            return None
        offsets = vtk_to_numpy(lines.GetOffsetsArray())
        connectivity = vtk_to_numpy(lines.GetConnectivityArray())
        coordinates = vtk_to_numpy(points.GetData())
        sizes = np.diff(offsets)
        if (len(offsets) != polydata.GetNumberOfLines() + 1 or offsets[0] != 0
                or offsets[-1] != len(connectivity) or np.any(sizes < 0)
                or coordinates.shape != (points.GetNumberOfPoints(), 3)
                or coordinates.dtype.kind != 'f' or not len(connectivity)
                or connectivity.min() < 0 or connectivity.max() >= len(coordinates)):
            return None
        candidates = np.flatnonzero(sizes >= 5)
        if not len(candidates):
            return None
        first = int(candidates[0])
        start, size = int(offsets[first]), int(sizes[first])
        step, count = 0.0, 0.0
        # Literal author accumulation: not true per-streamline arc lengths.
        for index in range(1, size - 1):
            point0 = points.GetPoint(int(connectivity[start + index]))
            point1 = points.GetPoint(int(connectivity[start + index + 1]))
            step += np.sqrt(np.sum(np.power(np.subtract(point0, point1), 2)))
            count += 1
        step /= count
        if not np.isfinite(step) or step <= 0:
            return None
        keep = sizes > round(minimum / float(step))
        if maximum is not None:
            keep &= sizes * step <= maximum
        selected = np.flatnonzero(keep)
        id_dtype = np.int64 if vtk.vtkIdTypeArray().GetDataTypeSize() == 8 else np.int32
        output_offsets = np.empty(len(selected) + 1, dtype=id_dtype)
        output_offsets[0] = 0
        np.cumsum(sizes[selected], out=output_offsets[1:])
        total = int(output_offsets[-1])
        output_points = vtk.vtkPoints()  # Author mask() defaults to float32.
        output_points.SetNumberOfPoints(total)
        output_coordinates = vtk_to_numpy(output_points.GetData())
        output_ids = vtk.vtkIdTypeArray()
        output_ids.SetNumberOfValues(total)
        output_connectivity = vtk_to_numpy(output_ids)
        for begin in range(0, total, self.block_points):
            end = min(total, begin + self.block_points)
            first_line = int(np.searchsorted(output_offsets, begin, side='right') - 1)
            last_line = int(np.searchsorted(output_offsets, end - 1, side='right') - 1)
            group = selected[first_line:last_line + 1]
            repeats = sizes[group].copy()
            repeats[0] -= begin - output_offsets[first_line]
            repeats[-1] -= output_offsets[last_line + 1] - end
            positions = np.arange(begin, end, dtype=id_dtype)
            original_positions = positions + np.repeat(offsets[group] - output_offsets[first_line:last_line + 1], repeats)
            output_coordinates[begin:end] = coordinates[connectivity[original_positions]]
            output_connectivity[begin:end] = positions
            self.peak_block_points = max(self.peak_block_points, end - begin)
        output_lines = vtk.vtkCellArray()
        output_lines.SetData(numpy_to_vtkIdTypeArray(output_offsets, deep=True), output_ids)
        output = vtk.vtkPolyData()
        output.SetPoints(output_points)
        output.SetLines(output_lines)
        return output

    def summary(self):
        return {'bulk_calls': self.calls, 'author_bypasses': self.bypassed,
                'points_copied': self.points_copied, 'block_points': self.block_points,
                'peak_block_points': self.peak_block_points, 'bulk_seconds': self.seconds,
                'scope': 'Author length rule and float32 point-copy semantics; bounded bulk copying; no transform, sampling or classification changes'}
