"""Chunk-local signal reuse must retain the unmodified WLLS decisions."""

import unittest
from unittest.mock import patch

import numpy as np

from microstructure import mkcurve, mkcurve_tensor as tensor
from Testing.Python.test_microstructure_dki import synthetic_case


class SignalReuseTests(unittest.TestCase):
    def case(self):
        case = synthetic_case(noisy=True)
        return (case['data'].reshape(-1, len(case['bvals'])),
                tensor.design_matrix(case['bvals'], case['bvecs']))

    def test_dynamic_baselines_and_invalid_nonbaseline_rows(self):
        signals, design = self.case()
        signals[0, 0] = np.nan
        signals[1, 4] = np.inf
        signals[2, 5] = np.nan
        signals[3] = 0
        signals[4] *= 1e-100
        signals[5] *= 1e100
        before = signals.copy()
        for solver in ('reference', 'batched'):
            fitter = tensor._SyntheticB0Fitter(signals, design, solver=solver)
            baselines = [signals[:, 0].copy(), np.full(len(signals), 700.0),
                         np.zeros(len(signals)), np.full(len(signals), -3.0)]
            baselines[1][7:9] = [np.nan, np.inf]
            for b0 in baselines:
                changed = signals.copy()
                changed[:, 0] = b0
                with np.errstate(all='ignore'):
                    expected = tensor.fit_wlls(changed, design, solver=solver)
                    actual = fitter.fit(b0)
                np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(signals, before)

    def test_context_owns_logs_and_only_prepares_design_once(self):
        signals, design = self.case()
        expected = tensor.fit_wlls(signals, design)
        with patch.object(tensor, '_prepared_design', wraps=tensor._prepared_design) as setup:
            fitter = tensor._SyntheticB0Fitter(signals, design)
            self.assertFalse(np.shares_memory(fitter.logs, signals))
            for _ in range(3):
                np.testing.assert_array_equal(fitter.fit(signals[:, 0]), expected)
            self.assertEqual(setup.call_count, 1)
        b0 = signals[:, 0].copy()
        signals[:, 1:] = 0
        np.testing.assert_array_equal(fitter.fit(b0), expected)

    def test_bad_protocol_empty_and_bad_options(self):
        signals, design = self.case()
        bad_design = design.copy()
        bad_design[:, -1] = bad_design[:, 0]
        self.assertTrue(np.isnan(tensor._SyntheticB0Fitter(signals, bad_design).fit(signals[:, 0])).all())
        self.assertEqual(tensor._SyntheticB0Fitter(signals[:0], design).fit(np.empty(0)).shape, (0, 22))
        with self.assertRaisesRegex(ValueError, 'solver'):
            tensor._SyntheticB0Fitter(signals, design, solver='fast')
        with self.assertRaisesRegex(ValueError, 'measurements'):
            tensor._SyntheticB0Fitter(signals[:, :-1], design)
        with self.assertRaisesRegex(ValueError, 'one value'):
            tensor._SyntheticB0Fitter(signals, design).fit(np.ones(len(signals) + 1))

    def test_complete_chunk_all_outputs_match_uncached_path(self):
        signals, design = self.case()
        signals[0, 0] = np.nan
        signals[1, 3] = np.nan
        grid = np.arange(100.0, 2200.0, 100.0)
        for solver in ('reference', 'batched'):
            with np.errstate(all='ignore'):
                baseline = mkcurve._fit_chunk((signals.copy(), design, grid, .5, solver), reuse_signal_logs=False)
                candidate = mkcurve._fit_chunk((signals.copy(), design, grid, .5, solver))
            for left, right in zip(baseline[:3], candidate[:3]):
                np.testing.assert_array_equal(left, right)
            self.assertEqual(baseline[3].keys(), candidate[3].keys())
            for key in baseline[3]:
                np.testing.assert_array_equal(baseline[3][key], candidate[3][key])


if __name__ == '__main__':
    unittest.main()
