# Derived from dipy/reconst/fwdti.py::wls_iter, DIPY 1.11.0/1.12.1.
# Copyright (c) 2008-2025, dipy developers. All rights reserved.
# Modified for SlicerDSpace, 2026: avoid a dense diagonal weight matrix.
# BSD-3-Clause; see licenses/DIPY.txt. Not an upstream DIPY release.
"""Author WLS with identical arithmetic after a diagonal-free column scaling."""

from dipy.reconst import fwdti
import numpy as np


def wls_iter(design_matrix, sig, S0, *, Diso=3e-3, mdreg=2.7e-3,
             min_signal=1.0e-6, piterations=3):
    """Retain the author's grid refinement, pseudoinverse and tensor outputs.

    Dispatch must first verify the original author source. Unusual dtypes,
    nonfinite/zero weights or invalid protocols retain original behavior.
    """
    options = dict(Diso=Diso, mdreg=mdreg, min_signal=min_signal, piterations=piterations)
    W = design_matrix
    if (type(W) is not np.ndarray or type(sig) is not np.ndarray
            or W.ndim != 2 or sig.ndim != 1 or W.shape != (len(sig), 7)
            or W.dtype != np.float64 or sig.dtype not in (np.float32, np.float64)
            or not np.isfinite(W).all()):
        return fwdti.wls_iter(W, sig, S0, **options)
    with np.errstate(over='ignore', invalid='ignore', under='ignore'):
        weights = sig**2
    if not np.isfinite(weights).all() or np.any(weights <= 0):
        return fwdti.wls_iter(W, sig, S0, **options)
    log_s = np.log(np.maximum(sig, min_signal))
    # W.T @ diag(sig**2): one nonzero term per output entry, not a change
    # to the normal matrix or pseudoinverse. Match dot's C-order/zero output.
    WTS2 = np.multiply(W.T, weights[None, :], order='C')
    WTS2[WTS2 == 0] = 0.
    inv_WT_S2_W = np.linalg.pinv(np.dot(WTS2, W))
    invWTS2W_WTS2 = np.dot(inv_WT_S2_W, WTS2)
    params = np.dot(invWTS2W_WTS2, log_s)
    md = (params[0] + params[2] + params[5]) / 3
    if md < mdreg and np.mean(sig) > min_signal and S0 > min_signal:
        fwsig = np.exp(np.dot(W, np.array([Diso, 0, Diso, 0, 0, Diso, 0])))
        df, flow, fhig, ns = 1, 0, 1, 9
        for _ in range(piterations):
            df = df * 0.1
            fs = np.linspace(flow + df, fhig - df, num=ns)
            SFW = np.array([fwsig] * ns)
            FS, SI = np.meshgrid(fs, sig)
            SA = SI - FS * S0 * SFW.T
            SA[SA <= 0] = min_signal
            y = np.log(SA / (1 - FS))
            all_new_params = np.dot(invWTS2W_WTS2, y)
            SIpred = (1 - FS) * np.exp(np.dot(W, all_new_params)) + FS * S0 * SFW.T
            F2 = np.sum(np.square(SI - SIpred), axis=0)
            Mind = np.argmin(F2)
            params = all_new_params[:, Mind]
            f = fs[Mind]
            flow, fhig, ns = f - df, f + df, 19
        evals, evecs = fwdti.decompose_tensor(fwdti.from_lower_triangular(params))
        return np.concatenate((evals, evecs[0], evecs[1], evecs[2], np.array([f])))
    fw_params = np.zeros(13)
    if md > mdreg:
        fw_params[12] = 1.0
    return fw_params
