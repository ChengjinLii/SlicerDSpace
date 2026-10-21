"""The diagonal-free adapter must not change author parameters or edge cases."""

import unittest
from unittest.mock import patch

from dipy.reconst import fwdti
import numpy as np

from microstructure.freewater_wls import wls_iter
from Testing.Python import test_freewater_dispatch as fixtures


class FreeWaterWLSOptimizationTests(unittest.TestCase):
    def test_layout_dtype_and_refinement_options_match_author(self):
        author, _, signals = fixtures.FreeWaterDispatchTests().case('WLS')
        design = author.design_matrix
        strided = np.repeat(design, 2, axis=1)[:, ::2]
        for source in (design, np.asfortranarray(design), strided):
            for dtype in (np.float32, np.float64):
                for options in ({}, {'piterations': 1}, {'piterations': 2}, {'piterations': 4},
                                {'Diso': .0025}, {'mdreg': 0}, {'min_signal': .001}):
                    with self.subTest(dtype=dtype, options=options):
                        before = source.copy()
                        for observed in signals.astype(dtype):
                            s0 = observed[:6].mean()
                            expected = fwdti.wls_iter(source, observed, s0, **options)
                            actual = wls_iter(source, observed, s0, **options)
                            np.testing.assert_array_equal(actual, expected)
                        np.testing.assert_array_equal(source, before)

    def test_finite_fast_path_never_constructs_dense_diagonal(self):
        author, _, signals = fixtures.FreeWaterDispatchTests().case('WLS')
        observed = signals[0]
        with patch.object(np, 'diag', side_effect=AssertionError('dense diagonal allocated')):
            actual = wls_iter(author.design_matrix, observed, observed[:6].mean())
        expected = fwdti.wls_iter(author.design_matrix, observed, observed[:6].mean())
        np.testing.assert_array_equal(actual, expected)

    def test_rank_deficiency_and_low_signal_decisions_preserved(self):
        author, _, signals = fixtures.FreeWaterDispatchTests().case('WLS')
        design = author.design_matrix.copy()
        design[:, 1] = design[:, 0]
        for observed, s0 in ((signals[0], 1000.), (signals[0], 1e-9),
                             (np.full_like(signals[0], 1e-9), 1e-9)):
            with np.errstate(all='ignore'):
                np.testing.assert_array_equal(wls_iter(design, observed, s0), fwdti.wls_iter(design, observed, s0))

    def test_negative_observations_keep_author_floor_policy(self):
        author, _, signals = fixtures.FreeWaterDispatchTests().case('WLS')
        for scale in (.1, 1., 10.):
            observed = signals[0].copy()
            observed[10] = -100 * scale
            np.testing.assert_array_equal(wls_iter(author.design_matrix, observed, observed[:6].mean()),
                                          fwdti.wls_iter(author.design_matrix, observed, observed[:6].mean()))

    def test_nonfinite_zero_and_unqualified_dtype_fall_back(self):
        author, _, signals = fixtures.FreeWaterDispatchTests().case('WLS')
        examples = [signals[0].astype(np.float16), np.zeros_like(signals[0]),
                    np.full_like(signals[0], 1e-200), np.full_like(signals[0], 1e200)]
        for value in (0., np.nan, np.inf):
            source = signals[0].copy()
            source[10] = value
            examples.append(source)
        for source in examples:
            with patch.object(fwdti, 'wls_iter', return_value='author-fallback') as fallback:
                self.assertEqual(wls_iter(author.design_matrix, source, 1000.), 'author-fallback')
                self.assertEqual(fallback.call_count, 1)


if __name__ == '__main__':
    unittest.main()
