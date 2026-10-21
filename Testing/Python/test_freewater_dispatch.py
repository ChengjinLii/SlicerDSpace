"""The optimized dispatcher must execute the unchanged original DIPY estimator."""

import inspect
import unittest
from unittest.mock import patch

import dipy
from dipy.core.gradients import gradient_table
from dipy.reconst import fwdti
import numpy as np

from microstructure.freewater_dispatch import configure_freewater_dispatch


class FreeWaterDispatchTests(unittest.TestCase):
    def test_direct_tensor_helpers_are_source_guarded_and_instance_private(self):
        author, first, signals = self.case('WLS')
        _, second, _ = self.case('WLS')
        original = fwdti.decompose_tensor
        for model in (first, second):
            record = configure_freewater_dispatch(model, 'WLS', 'serial')
            self.assertTrue(record['tensor_helpers_enabled'])
            proxy = model.fit_method.__globals__['fwdti']
            self.assertIs(proxy.decompose_tensor, inspect.unwrap(original))
            np.testing.assert_array_equal(model.fit(signals).model_params, author.fit(signals).model_params)
        self.assertIsNot(first.fit_method.__globals__['fwdti'], second.fit_method.__globals__['fwdti'])
        self.assertIs(fwdti.decompose_tensor, original)

    def test_unqualified_tensor_source_retains_original_helpers(self):
        author, model, signals = self.case('WLS')
        with patch('microstructure.freewater_dispatch._TENSOR_SHA256', {'decompose_tensor': 'unqualified'}):
            record = configure_freewater_dispatch(model, 'WLS', 'serial')
        self.assertTrue(record['enabled'])
        self.assertFalse(record['tensor_helpers_enabled'])
        self.assertIs(model.fit_method.__globals__['fwdti'], fwdti)
        np.testing.assert_array_equal(model.fit(signals).model_params, author.fit(signals).model_params)

    def case(self, method='NLS', **kwargs):
        rng = np.random.default_rng(42)
        bvals = np.r_[np.zeros(6), np.full(30, 1000.), np.full(30, 2000.)]
        bvecs = rng.normal(size=(len(bvals), 3))
        bvecs /= np.linalg.norm(bvecs, axis=1, keepdims=True)
        bvecs[:6] = 0
        gtab = gradient_table(bvals, bvecs=bvecs)
        author = fwdti.FreeWaterTensorModel(gtab, fit_method=method, **kwargs)
        optimized = fwdti.FreeWaterTensorModel(gtab, fit_method=method, **kwargs)
        tissue = np.exp(-bvals * np.sum(bvecs ** 2 * np.array([.0016, .0006, .0003]), axis=1))
        signals = np.stack([1000 * ((1-f) * tissue + f * np.exp(-bvals * .003))
                            for f in (.01, .2, .6, .9, 1.)])
        signals[:4] += rng.normal(0, 2, size=signals[:4].shape)
        return author, optimized, signals

    def test_raw_fit_and_derived_maps_exact_without_modifying_dipy(self):
        author, optimized, signals = self.case()
        functions = {name: getattr(fwdti, name) for name in ('nls_iter', 'wls_iter', '_nls_err_func', '_nls_jacobian_func')}
        before = signals.copy()
        record = configure_freewater_dispatch(optimized, 'NLS', 'serial')
        self.assertTrue(record['enabled'])
        self.assertEqual(author.fit_method, functions['nls_iter'])
        expected, actual = author.fit(signals), optimized.fit(signals)
        for name in ('model_params', 'f', 'fa', 'md', 'evals', 'evecs'):
            np.testing.assert_array_equal(getattr(actual, name), getattr(expected, name))
        np.testing.assert_array_equal(signals, before)
        for name, function in functions.items():
            self.assertIs(getattr(fwdti, name), function)
        self.assertIs(optimized.fit_method.__code__, inspect.unwrap(functions['nls_iter']).__code__)

    def test_defaults_keywords_and_supported_optional_loss_paths_preserved(self):
        for kwargs in ({}, {'f_transform': False}, {'cholesky': True},
                       {'weighting': 'sigma', 'sigma': 2.}, {'weighting': 'gmm'}):
            with self.subTest(kwargs=kwargs):
                author, optimized, signals = self.case(**kwargs)
                configure_freewater_dispatch(optimized, 'NLS', 'serial')
                np.testing.assert_array_equal(optimized.fit(signals).model_params, author.fit(signals).model_params)
                self.assertEqual(optimized.fit_method.__kwdefaults__, inspect.unwrap(fwdti.nls_iter).__kwdefaults__)

    def test_parallel_engines_retain_public_method(self):
        for method, engine in (('WLS', 'joblib'), ('NLS', 'joblib'), ('NLS', 'dask'), ('NLS', 'ray')):
            _, model, _ = self.case(method)
            original = model.fit_method
            self.assertFalse(configure_freewater_dispatch(model, method, engine)['enabled'])
            self.assertIs(model.fit_method, original)

    def test_unknown_releases_or_source_fall_back(self):
        _, model, _ = self.case()
        original = model.fit_method
        with patch.object(dipy, '__version__', '9.0.0'):
            self.assertFalse(configure_freewater_dispatch(model, 'NLS', 'serial')['enabled'])
        with patch('microstructure.freewater_dispatch.inspect.getsource', return_value='changed source'):
            self.assertFalse(configure_freewater_dispatch(model, 'NLS', 'serial')['enabled'])
        with patch('microstructure.freewater_dispatch.inspect.getsource', side_effect=OSError('no source')):
            self.assertFalse(configure_freewater_dispatch(model, 'NLS', 'serial')['enabled'])
        self.assertIs(model.fit_method, original)

    def test_custom_models_and_methods_are_never_replaced(self):
        _, model, _ = self.case()
        model.fit_method = lambda *args, **kwargs: None
        self.assertFalse(configure_freewater_dispatch(model, 'NLS', 'serial')['enabled'])
        self.assertFalse(configure_freewater_dispatch(object(), 'NLS', 'serial')['enabled'])

    def test_wls_raw_parameters_and_maps_exact(self):
        author, optimized, signals = self.case('WLS')
        record = configure_freewater_dispatch(optimized, 'WLS', 'serial')
        self.assertTrue(record['enabled'])
        first, second = author.fit(signals), optimized.fit(signals)
        for name in ('model_params', 'f', 'fa', 'md', 'evals', 'evecs'):
            np.testing.assert_array_equal(getattr(first, name), getattr(second, name))

    def test_zero_low_and_nonfinite_signals_keep_original_behavior(self):
        author, optimized, signals = self.case()
        configure_freewater_dispatch(optimized, 'NLS', 'serial')
        for source in (np.zeros_like(signals), np.full_like(signals, 1e-9)):
            np.testing.assert_array_equal(author.fit(source).model_params, optimized.fit(source).model_params)
        for invalid in (np.nan, np.inf):
            source = signals[0].copy()
            source[10] = invalid
            with np.errstate(all='ignore'):
                for model in (author, optimized):
                    with self.assertRaises(np.linalg.LinAlgError):
                        model.fit(source)


if __name__ == '__main__':
    unittest.main()
