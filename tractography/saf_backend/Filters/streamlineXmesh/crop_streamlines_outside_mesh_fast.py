import numpy as np

from .trintersect_fast import trintersect_fast


def crop_streamlines_outside_mesh_fast(V, F, tract, inside=None, outer_intersection=False):
    nsl = len(tract)
    rsl = [None] * nsl
    rxf = [None] * nsl
    osi = [None] * nsl
    slp = [None] * nsl

    if inside is None:
        inside = np.zeros((nsl,), dtype=bool)
    elif np.isscalar(inside) and nsl > 1:
        inside = np.repeat(bool(inside), nsl)

    F_VC = lambda d: np.column_stack([V[F[:, 0], d], V[F[:, 1], d], V[F[:, 2], d]])
    FBB_max = np.column_stack([np.max(F_VC(0), axis=1), np.max(F_VC(1), axis=1), np.max(F_VC(2), axis=1)])
    FBB_min = np.column_stack([np.min(F_VC(0), axis=1), np.min(F_VC(1), axis=1), np.min(F_VC(2), axis=1)])

    for i in range(nsl):
        sl = tract[i]
        xS = np.array([], dtype=int)
        xF = np.array([], dtype=int)

        SBB_min = np.min(sl, axis=0)
        SBB_max = np.max(sl, axis=0)

        xFBB = np.all((FBB_max >= SBB_min) & (FBB_min <= SBB_max), axis=1)

        if np.any(xFBB):
            F_max = FBB_max[xFBB]
            F_min = FBB_min[xFBB]
            SLE = np.hstack([sl[:-1], sl[1:]])
            SLE = SLE[:, [0, 3, 1, 4, 2, 5]]
            S_min = np.column_stack([np.min(SLE[:, 0:2], axis=1), np.min(SLE[:, 2:4], axis=1), np.min(SLE[:, 4:6], axis=1)])
            S_max = np.column_stack([np.max(SLE[:, 0:2], axis=1), np.max(SLE[:, 2:4], axis=1), np.max(SLE[:, 4:6], axis=1)])

            X = (F_max[:, [0]] >= S_min[:, 0]) & (F_min[:, [0]] <= S_max[:, 0])
            Y = (F_max[:, [1]] >= S_min[:, 1]) & (F_min[:, [1]] <= S_max[:, 1])
            Z = (F_max[:, [2]] >= S_min[:, 2]) & (F_min[:, [2]] <= S_max[:, 2])
            BBFX = X & Y & Z

            if np.any(BBFX):
                xFBB_idx = np.where(xFBB)[0]
                xF, xS = np.where(BBFX)
                P = V[F[xFBB_idx[xF]]]
                I = trintersect_fast(
                    P[:, 0, :],
                    P[:, 1, :],
                    P[:, 2, :],
                    sl[xS],
                    sl[xS + 1],
                )
                xF = xF[I]
                xS = xS[I]
                xF = xFBB_idx[xF]

        xP = xS + 1
        xF = xF
        if inside[i]:
            xP = np.concatenate([[0], xP])
            xF = np.concatenate([[np.nan], xF])
        if xP.size % 2 == 1:
            xP = np.concatenate([xP, [sl.shape[0] - 1]])
            xF = np.concatenate([xF, [np.nan]])
        if outer_intersection and xF.size > 0:
            if xP.size > 2:
                xP = np.concatenate([[xP[0]], [xP[-1]]])
                xF = np.concatenate([[xF[0]], [xF[-1]]])

        xI = xP.reshape(-1, 2)
        xI[xI[:, 1] < sl.shape[0] - 1, 1] -= 1
        xIF = xF.reshape(2, -1)

        tsl = [sl[int(xI[j, 0]):int(xI[j, 1]) + 1] for j in range(xI.shape[0])]
        lmask = [t.shape[0] > 1 for t in tsl]
        rsl[i] = [t for t, keep in zip(tsl, lmask) if keep]
        slp[i] = xI[lmask].T if xI.size else np.zeros((2, 0), dtype=int)
        rxf[i] = xIF[:, lmask] if xIF.size else np.zeros((2, 0))
        osi[i] = np.repeat(i, sum(lmask))

    rsl = [t for sub in rsl if sub for t in sub]
    if not rsl:
        raise AssertionError('No streamlines have survived GWG filtering')
    tract_out = rsl
    orig_sl_ind = _concat_1d(osi, dtype=int)
    end_faces = _concat_2d(rxf, dtype=float)
    xpoints = _concat_2d(slp, dtype=int)

    if len(end_faces.shape) == 1:
        end_faces = end_faces.reshape(2, -1)

    xverts = None
    if end_faces.size > 0:
        ef = end_faces.T
        xf = ~np.isnan(ef)
        pts = []
        for sl in tract_out:
            pts.append(sl[[0, -1], :])
        pts = np.stack(pts, axis=0)
        pts = np.concatenate([pts[:, 0, :], pts[:, 1, :]], axis=0)
        pts = pts[xf.T.ravel()]
        ef_valid = ef[xf]
        ef_valid = ef_valid.astype(int)
        v1 = np.sum((pts - V[F[ef_valid, 0]]) ** 2, axis=1)
        v2 = np.sum((pts - V[F[ef_valid, 1]]) ** 2, axis=1)
        v3 = np.sum((pts - V[F[ef_valid, 2]]) ** 2, axis=1)
        cfv = np.argmin(np.column_stack([v1, v2, v3]), axis=1)
        fi = F[ef_valid]
        fi = fi[np.arange(fi.shape[0]), cfv]
        xverts = np.zeros_like(ef, dtype=float)
        xverts[xf] = fi + 1
        xverts = xverts.T

    return tract_out, orig_sl_ind, xverts, xpoints


def _concat_1d(values, dtype=float):
    valid = [np.asarray(v) for v in values if v is not None and len(v) > 0]
    if not valid:
        return np.zeros((0,), dtype=dtype)
    return np.concatenate(valid).astype(dtype, copy=False)


def _concat_2d(values, dtype=float):
    valid = [np.asarray(v) for v in values if v is not None and np.asarray(v).size > 0]
    if not valid:
        return np.zeros((2, 0), dtype=dtype)
    return np.concatenate(valid, axis=1).astype(dtype, copy=False)
