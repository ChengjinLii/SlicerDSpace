"""Exact-order grouping and immutable MK quadrature, not accuracy benchmarks."""

from itertools import combinations_with_replacement
import json
from math import factorial
from pathlib import Path
import tempfile
import unittest

import nibabel as nib
import numpy as np

from microstructure.pipeline import _compute_roi_stats
from microstructure.mkcurve_tensor import (
    _integration_bases, _tensor_terms, integration_directions, mean_kurtosis, tensor_basis,
)


def original_basis(directions, order):
    indices = list(combinations_with_replacement(range(3), order))
    counts = [factorial(order) / np.prod([factorial(index.count(j)) for j in range(3)]) for index in indices]
    return np.stack([np.prod(directions[..., index], axis=-1) * count
                     for index, count in zip(indices, counts)], axis=-1)


class ComputeOptimizationTests(unittest.TestCase):
    def test_tensor_terms_do_not_cache_mutable_direction_arrays(self):
        rng = np.random.default_rng(42)
        directions = rng.normal(size=(20, 3))
        for order in (1, 2, 4):
            np.testing.assert_array_equal(tensor_basis(directions, order), original_basis(directions, order))
            directions *= .75
            np.testing.assert_array_equal(tensor_basis(directions, order), original_basis(directions, order))
        self.assertLessEqual(_tensor_terms.cache_info().currsize, 8)

    def test_quadrature_bases_are_bounded_and_read_only(self):
        _integration_bases.cache_clear()
        bases = _integration_bases()
        self.assertIs(bases, _integration_bases())
        for order, basis in zip((2, 4), bases):
            np.testing.assert_array_equal(basis, original_basis(integration_directions(), order).T)
            with self.assertRaises(ValueError):
                basis[0, 0] = 99
        self.assertEqual(_integration_bases.cache_info().currsize, 1)
        self.assertEqual(sum(basis.nbytes for basis in bases), 43008)

    def test_mean_kurtosis_exact_for_finite_zero_and_nonfinite_coefficients(self):
        rng = np.random.default_rng(3407)
        coefficients = rng.normal(size=(64, 22))
        coefficients[0] = 0
        coefficients[1, 3] = np.nan
        with np.errstate(all='ignore'):
            directions = integration_directions()
            adc = coefficients[:, 1:7] @ original_basis(directions, 2).T
            fourth = coefficients[:, 7:22] @ original_basis(directions, 4).T
            reference = np.mean(fourth / adc ** 2, axis=1)
            md_squared = np.mean(coefficients[:, [1, 4, 6]], axis=1) ** 2
            reference[(md_squared == 0) | ~np.isfinite(md_squared)] = np.nan
            np.testing.assert_array_equal(mean_kurtosis(coefficients), reference)
            coefficients[2:] *= 2
            self.assertFalse(np.shares_memory(mean_kurtosis(coefficients), reference))

    def test_grouped_statistics_match_boolean_reference_in_original_order(self):
        rng = np.random.default_rng(2026)
        shape = (7, 5, 9)
        labels = rng.choice([0, 1, 8, 2001, 5002], size=shape).astype(np.float32)
        scalar = rng.normal(size=shape).astype(np.float32)
        scalar.flat[::17] = np.nan
        scalar.flat[::29] = np.inf
        validity = rng.integers(0, 2, size=shape).astype(bool)
        brain = rng.integers(0, 2, size=shape).astype(np.float32)
        for array in (scalar, labels, brain):
            self.assertTrue(np.isfinite(array).any())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def volume(name, array):
                path = root / (name + '.nii.gz')
                nib.save(nib.Nifti1Image(array, np.eye(4)), path)
                return path
            scalar_path, atlas, mask = volume('fa', scalar), volume('atlas', labels), volume('brain', brain)
            for order in ('C', 'F'):
                _compute_roi_stats(metric_paths={'fa': scalar_path}, roi_label_map=atlas, lut_path=None,
                                   csv_path=root/'stats.csv', json_path=root/'stats.json',
                                   validity_masks={'fa': np.array(validity, order=order)}, brain_mask_path=mask)
                payload = json.loads((root/'stats.json').read_text())
                for row in payload['rows']:
                    label_mask = labels == row['label_id']
                    values = scalar[label_mask & np.isfinite(scalar) & validity & (brain > 0)]
                    self.assertEqual(row['roi_voxel_count'], int(label_mask.sum()))
                    self.assertEqual(row['fa_valid_voxel_count'], len(values))
                    for key, operation in (('mean', np.mean), ('std', np.std), ('min', np.min), ('max', np.max)):
                        self.assertEqual(row['fa_'+key], float(operation(values)) if len(values) else None)

    def test_background_only_atlas_produces_no_phantom_regions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atlas, scalar = root/'atlas.nii.gz', root/'fa.nii.gz'
            nib.save(nib.Nifti1Image(np.zeros((2, 3, 4), dtype=np.float32), np.eye(4)), atlas)
            nib.save(nib.Nifti1Image(np.ones((2, 3, 4), dtype=np.float32), np.eye(4)), scalar)
            self.assertEqual(_compute_roi_stats(metric_paths={'fa': scalar}, roi_label_map=atlas, lut_path=None,
                                               csv_path=root/'stats.csv', json_path=root/'stats.json'), 0)
            self.assertEqual(json.loads((root/'stats.json').read_text())['rows'], [])


if __name__ == '__main__':
    unittest.main()
