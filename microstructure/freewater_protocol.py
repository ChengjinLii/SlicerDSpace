"""Bounded per-model reuse of protocol-only arrays in source-qualified FW WLS."""

from collections import OrderedDict
from types import FunctionType

import numpy as np


class WLSProtocol:
    """Exact grids, not a fitted-parameter cache; no voxel observations are stored."""

    def __init__(self, design, diso, max_bytes=2 * 1024 * 1024):
        self.design = np.array(design, copy=True)
        self.strides = design.strides
        self.diso = diso
        self.max_bytes = max_bytes
        self.grids = OrderedDict()
        self.bytes = 0
        self.hits = self.misses = 0
        self.fwsig = np.exp(np.dot(design, np.array([diso, 0, diso, 0, 0, diso, 0])))
        self.spectra = {size: np.array([self.fwsig] * size) for size in (9, 19)}
        self.design.flags.writeable = False
        self.fwsig.flags.writeable = False
        for array in self.spectra.values():
            array.flags.writeable = False

    def matches(self, design, diso):
        return (type(diso) in (float, np.float64) and diso == self.diso
                and design.strides == self.strides and np.array_equal(design, self.design))

    def grid(self, flow, fhig, df, size):
        key = flow, fhig, df, size
        cached = self.grids.pop(key, None)
        if cached is not None:
            self.hits += 1
            self.grids[key] = cached
            return cached
        self.misses += 1
        fs = np.linspace(flow + df, fhig - df, num=size)
        FS = np.meshgrid(fs, np.empty(len(self.design)))[0]
        fs.flags.writeable = FS.flags.writeable = False
        result = fs, FS, self.spectra[size]
        cost = fs.nbytes + FS.nbytes
        while self.grids and self.bytes + cost > self.max_bytes:
            old = self.grids.popitem(last=False)[1]
            self.bytes -= old[0].nbytes + old[1].nbytes
        if cost <= self.max_bytes:
            self.grids[key] = result
            self.bytes += cost
        return result


def prepare_wls_protocol(function, design, *, diso=3e-3):
    """Preserve function code, helpers and keywords in a model-private namespace."""
    if (type(design) is not np.ndarray or design.dtype != np.float64 or design.ndim != 2
            or design.shape[1] != 7 or not np.isfinite(design).all()
            or type(diso) not in (float, np.float64) or not np.isfinite(diso)):
        return function
    context = WLSProtocol(design, diso)
    namespace = {**function.__globals__, "_protocol_context": context}
    result = FunctionType(function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__)
    result.__kwdefaults__ = dict(function.__kwdefaults__ or {})
    return result
