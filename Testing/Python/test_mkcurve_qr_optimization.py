"""Exact QR implementation parity; synthetic tests are not anatomical QC."""

import unittest
from unittest.mock import patch

import numpy as np
from scipy.linalg import lstsq

from microstructure import mkcurve, mkcurve_tensor as tensor
from Testing.Python.test_microstructure_dki import synthetic_case


class MKCurveQROptimizationTests(unittest.TestCase):
    def test_latest_qualified_release_enables_direct_driver(self):
        if tensor.scipy.__version__ == '1.18.1':
            self.assertTrue(tensor._DIRECT_GELSY)

    def setUp(self):
        tensor._cached_design_setup.cache_clear()
        tensor._gelsy_workspace.cache_clear()

    def case(self):
        case = synthetic_case(noisy=True)
        return case['data'].reshape(-1, len(case['bvals'])), tensor.design_matrix(case['bvals'], case['bvecs'])

    def test_direct_driver_matches_public_solver_including_rank_deficiency(self):
        rng = np.random.default_rng(2026)
        matrix = rng.normal(size=(181, 22))
        observed = rng.normal(size=181)
        for deficient in (False, True):
            if deficient:
                matrix[:, -1] = matrix[:, 0]
            for source in (matrix, np.asfortranarray(matrix)):
                before = source.copy(), observed.copy()
                expected, _, rank, _ = lstsq(source, observed, lapack_driver='gelsy')
                with patch.object(tensor, '_DIRECT_GELSY', True):
                    actual, actual_rank = tensor._weighted_qr(source, observed)
                np.testing.assert_array_equal(actual, expected)
                self.assertEqual(actual_rank, rank)
                np.testing.assert_array_equal(source, before[0])
                np.testing.assert_array_equal(observed, before[1])

    def test_public_fallback_for_unknown_versions_or_unsupported_inputs(self):
        rng = np.random.default_rng(42)
        for dtype, shape, enabled in ((np.float64, (30, 22), False),
                                     (np.float32, (30, 22), True),
                                     (np.float64, (10, 22), True)):
            matrix = rng.normal(size=shape).astype(dtype)
            observed = rng.normal(size=shape[0]).astype(dtype)
            with patch.object(tensor, '_DIRECT_GELSY', enabled), patch.object(tensor, 'lstsq', wraps=lstsq) as public:
                actual, rank = tensor._weighted_qr(matrix, observed)
            expected, _, expected_rank, _ = lstsq(matrix, observed, lapack_driver='gelsy')
            self.assertEqual(public.call_count, 1)
            np.testing.assert_array_equal(actual, expected)
            self.assertEqual(rank, expected_rank)

    def test_all_finite_nonfinite_and_extreme_signals_keep_fits_and_masks(self):
        signals, design = self.case()
        signals = np.vstack((signals, np.zeros_like(signals[0]),
                             signals[0] * 1e-100, signals[0] * 1e100,
                             np.full_like(signals[0], np.nan), np.full_like(signals[0], np.inf)))
        before = signals.copy()
        for solver in ('reference', 'batched'):
            with patch.object(tensor, '_DIRECT_GELSY', False):
                expected = tensor.fit_wlls(signals, design, solver=solver)
            with patch.object(tensor, '_DIRECT_GELSY', True):
                actual = tensor.fit_wlls(signals, design, solver=solver)
            np.testing.assert_array_equal(actual, expected)
            self.assertTrue(np.isnan(actual[-2:]).all())
        np.testing.assert_array_equal(signals, before)

    def test_design_cache_is_readonly_content_keyed_and_bounded(self):
        _, design = self.case()
        with patch.object(tensor, '_design_setup', wraps=tensor._design_setup) as prepare:
            first = tensor._prepared_design(design)
            second = tensor._prepared_design(design.copy())
            self.assertIs(first, second)
            self.assertEqual(prepare.call_count, 1)
            for array in first:
                self.assertFalse(array.flags.writeable)
            design[0, 0] += .125
            changed = tensor._prepared_design(design)
            self.assertEqual(prepare.call_count, 2)
            self.assertIsNot(first, changed)
            for actual, expected in zip(changed, tensor._design_setup(design)):
                np.testing.assert_array_equal(actual, expected)
        for index in range(8):
            tensor._prepared_design(design + index * .001)
        self.assertLessEqual(tensor._cached_design_setup.cache_info().currsize, 4)

    def test_noncontiguous_layout_keeps_original_reductions_and_bypasses_cache(self):
        _, design = self.case()
        interleaved = np.repeat(design, 2, axis=1)[:, ::2]
        for source in (np.asfortranarray(design), interleaved):
            with patch.object(tensor, '_cached_design_setup', side_effect=AssertionError('unexpected cache')):
                actual = tensor._prepared_design(source)
            for left, right in zip(actual, tensor._design_setup(source)):
                np.testing.assert_array_equal(left, right)

    def test_singular_protocol_remains_invalid(self):
        signals, design = self.case()
        design[:, -1] = design[:, 0]
        self.assertIsNone(tensor._prepared_design(design))
        self.assertTrue(np.isnan(tensor.fit_wlls(signals, design)).all())

    def test_workspace_is_cached_not_mutable_solver_inputs(self):
        matrix = np.random.default_rng(42).normal(size=(181, 22))
        with patch.object(tensor, '_DIRECT_GELSY', True), patch.object(tensor, 'dgelsy_lwork', wraps=tensor.dgelsy_lwork) as query:
            for index in range(3):
                tensor._weighted_qr(matrix, np.arange(181, dtype=float) + index)
        self.assertEqual(query.call_count, 1)
        with patch.object(tensor, 'dgelsy_lwork', return_value=(1., -1)):
            with self.assertRaisesRegex(ValueError, 'workspace query failed'):
                tensor._gelsy_workspace(182, 22)
        with patch.object(tensor, '_DIRECT_GELSY', True), patch.object(tensor, 'dgelsy', return_value=(None, None, None, 0, -1)):
            with self.assertRaisesRegex(ValueError, 'gelsy failed'):
                tensor._weighted_qr(matrix, np.zeros(181))

    def test_complete_numeric_chunk_has_exact_curves_maps_and_decisions(self):
        signals, design = self.case()
        grid = np.arange(100, 2200, 100.)
        for solver in ('reference', 'batched'):
            with patch.object(tensor, '_DIRECT_GELSY', False), patch.object(tensor, '_prepared_design', side_effect=tensor._design_setup):
                expected = mkcurve._fit_chunk((signals.copy(), design, grid, .5, solver))
            with patch.object(tensor, '_DIRECT_GELSY', True):
                actual = mkcurve._fit_chunk((signals.copy(), design, grid, .5, solver))
            for index in (0, 1, 2):
                np.testing.assert_array_equal(actual[index], expected[index])
            self.assertEqual(actual[3].keys(), expected[3].keys())
            for key in actual[3]:
                np.testing.assert_array_equal(actual[3][key], expected[3][key])


if __name__ == '__main__':
    unittest.main()
