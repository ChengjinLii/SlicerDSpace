"""Protocol reuse preserves author arithmetic and never caches voxel fits."""

import unittest

import numpy as np
from dipy.reconst import fwdti

from microstructure.freewater_protocol import prepare_wls_protocol, WLSProtocol
from microstructure.freewater_wls import wls_iter
from Testing.Python import test_freewater_dispatch as fixtures


class FreeWaterProtocolTests(unittest.TestCase):
    def test_all_supported_options_layouts_and_parameters_match_author(self):
        author, _, signals = fixtures.FreeWaterDispatchTests().case("WLS")
        for design in (author.design_matrix, np.asfortranarray(author.design_matrix), author.design_matrix[:, ::-1][:, ::-1]):
            prepared = prepare_wls_protocol(wls_iter, design)
            for dtype in (np.float32, np.float64):
                for options in ({}, {"piterations": 1}, {"piterations": 4}, {"Diso": .0025},
                                {"mdreg": 0}, {"min_signal": .001}):
                    for sig in signals.astype(dtype):
                        with self.subTest(dtype=dtype, options=options):
                            s0 = sig[:6].mean()
                            np.testing.assert_array_equal(prepared(design, sig, s0, **options),
                                                          fwdti.wls_iter(design, sig, s0, **options))

    def test_caches_are_private_bounded_and_hold_no_observations(self):
        author, _, signals = fixtures.FreeWaterDispatchTests().case("WLS")
        a = prepare_wls_protocol(wls_iter, author.design_matrix)
        b = prepare_wls_protocol(wls_iter, author.design_matrix)
        self.assertIsNot(a.__globals__["_protocol_context"], b.__globals__["_protocol_context"])
        before = signals.copy()
        for _ in range(2):
            for sig in signals:
                a(author.design_matrix, sig, sig[:6].mean())
        np.testing.assert_array_equal(signals, before)
        context = a.__globals__["_protocol_context"]
        self.assertGreater(context.hits, 0)
        self.assertLessEqual(context.bytes, context.max_bytes)
        tiny = WLSProtocol(author.design_matrix, .003, max_bytes=10000)
        for i in range(100):
            tiny.grid(i / 1000, i / 1000 + .2, .01, 19)
        self.assertLessEqual(tiny.bytes, tiny.max_bytes)
        self.assertIsNone(wls_iter.__globals__["_protocol_context"])

    def test_mutated_protocol_recomputes_instead_of_using_stale_arrays(self):
        author, _, signals = fixtures.FreeWaterDispatchTests().case("WLS")
        design = author.design_matrix.copy()
        prepared = prepare_wls_protocol(wls_iter, design)
        alternate = np.asfortranarray(design)
        self.assertFalse(prepared.__globals__["_protocol_context"].matches(alternate, .003))
        sig = signals[0]
        np.testing.assert_array_equal(prepared(alternate, sig, sig[:6].mean()),
                                      fwdti.wls_iter(alternate, sig, sig[:6].mean()))
        design[7, 0] *= 1.1
        np.testing.assert_array_equal(prepared(design, sig, sig[:6].mean()),
                                      fwdti.wls_iter(design, sig, sig[:6].mean()))

    def test_zero_negative_and_low_signals_keep_author_behavior(self):
        author, _, signals = fixtures.FreeWaterDispatchTests().case("WLS")
        prepared = prepare_wls_protocol(wls_iter, author.design_matrix)
        for sig in (np.zeros_like(signals[0]), np.full_like(signals[0], 1e-9), -signals[0]):
            with np.errstate(all="ignore"):
                np.testing.assert_array_equal(prepared(author.design_matrix, sig, max(sig[:6].mean(), 1e-9)),
                    fwdti.wls_iter(author.design_matrix, sig, max(sig[:6].mean(), 1e-9)))

    def test_unqualified_matrix_keeps_existing_callable(self):
        author, _, _ = fixtures.FreeWaterDispatchTests().case("WLS")
        self.assertIs(prepare_wls_protocol(wls_iter, author.design_matrix.astype(np.float32)), wls_iter)

    def test_qualified_dispatch_enables_reuse_but_can_retain_previous_path(self):
        from microstructure.freewater_dispatch import configure_freewater_dispatch

        author, prepared, signals = fixtures.FreeWaterDispatchTests().case("WLS")
        record = configure_freewater_dispatch(prepared, "WLS", "serial")
        self.assertTrue(record["protocol_reuse_enabled"])
        self.assertEqual(record["protocol_grid_cache_budget_bytes"], 2 * 1024 * 1024)
        np.testing.assert_array_equal(prepared.fit(signals).model_params, author.fit(signals).model_params)
        _, previous, _ = fixtures.FreeWaterDispatchTests().case("WLS")
        record = configure_freewater_dispatch(previous, "WLS", "serial", reuse_protocol=False)
        self.assertFalse(record["protocol_reuse_enabled"])
        np.testing.assert_array_equal(prepared.fit(signals).model_params, previous.fit(signals).model_params)
