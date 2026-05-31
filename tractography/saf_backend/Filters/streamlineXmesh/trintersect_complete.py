import numpy as np


def trintersect_complete(P1, P2, P3, Q1, Q2, V, F, S):
    nx = P1.shape[0]
    ex = np.zeros((nx * 3,), dtype=bool)

    def signed_volume(a, b, d, c):
        return (1.0 / 6.0) * np.einsum('ij,ij->i', np.cross(b - a, c - a), d - a)

    f = np.sign(signed_volume(Q1, P1, P2, P3)) != np.sign(signed_volume(Q2, P1, P2, P3))
    if np.any(f):
        f_idx = f.copy()
        f[f_idx] = np.sign(signed_volume(Q1[f_idx], Q2[f_idx], P2[f_idx], P3[f_idx])) == np.sign(
            signed_volume(Q1[f_idx], Q2[f_idx], P1[f_idx], P2[f_idx])
        )
        if np.any(f):
            f_idx = f.copy()
            f[f_idx] = np.sign(signed_volume(Q1[f_idx], Q2[f_idx], P2[f_idx], P3[f_idx])) == np.sign(
                signed_volume(Q1[f_idx], Q2[f_idx], P3[f_idx], P1[f_idx])
            )
            if np.any(f):
                pairs = np.column_stack([S, F])
                _, idx = np.unique(pairs, axis=0, return_index=True)
                fx = np.zeros((nx,), dtype=bool)
                fx[idx[np.isin(idx, np.where(f)[0])]] = True
                ex = np.repeat(fx, 3)

    D = lambda p1, p2: p2 - p1
    M = lambda p1, p2: np.cross(p1, D(p1, p2))
    def L(q1, q2, p):
        return np.all(np.abs(np.cross(p, D(q1, q2)) - M(q1, q2)) < np.finfo(float).eps, axis=1)
    def P(q1, q2, p):
        return np.einsum('ij,ij->i', q1 - q2, p - q2) / np.einsum('ij,ij->i', q1 - q2, q1 - q2)
    def X(q1, q2, p):
        t = P(q1, q2, p)
        return (t >= 0) & (t <= 1)

    q1 = np.repeat(Q1, 3, axis=0)
    q2 = np.repeat(Q2, 3, axis=0)
    p1 = np.vstack([P1, P2, P3])

    v = ~ex
    if np.any(v):
        v[v] = L(q1[v], q2[v], p1[v])
        if np.any(v):
            v[v] = X(q1[v], q2[v], p1[v])
            if np.any(v):
                pairs = np.column_stack([np.repeat(S, 3), V.reshape(-1)])
                _, idx = np.unique(pairs, axis=0, return_index=True)
                v0 = np.zeros((nx * 3,), dtype=bool)
                v0[idx[np.isin(idx, np.where(v)[0])]] = True
                v = v0

    def A(p1, p2, q1, q2):
        return np.any(np.abs(np.cross(D(p1, p2), D(q1, q2))) > np.finfo(float).eps, axis=1)
    def R(p1, p2, q1, q2):
        return np.abs(np.einsum('ij,ij->i', D(p1, p2), M(q1, q2)) + np.einsum('ij,ij->i', D(q1, q2), M(p1, p2))) < np.finfo(float).eps
    def C(p1, p2, q1, q2):
        cross_d = np.cross(D(p1, p2), D(q1, q2))
        denom = np.einsum('ij,ij->i', cross_d, cross_d)
        term1 = np.einsum('ij,ij->i', M(p1, p2), D(q1, q2))[:, None]
        term2 = np.einsum('ij,ij->i', M(q1, q2), D(p1, p2))[:, None]
        return (np.cross(term1 * np.eye(3)[None, :, :], cross_d[:, None, :]) +
                np.cross(D(p1, p2)[:, None, :], term2 * np.eye(3)[None, :, :]) -
                np.cross(D(q1, q2)[:, None, :], term1 * np.eye(3)[None, :, :]))[:, 0, :] / denom[:, None]
    def Z(q1, q2, p):
        t = P(q1, q2, p)
        eps = np.finfo(float).eps
        return (t > eps) & (t < 1 - eps)

    p2 = np.vstack([P2, P3, P1])
    e = ~ex
    if np.any(e):
        e[e] = A(p1[e], p2[e], q1[e], q2[e])
        if np.any(e):
            e[e] = R(p1[e], p2[e], q1[e], q2[e])
            if np.any(e):
                e2 = C(p1[e], p2[e], q1[e], q2[e])
                e[e] = Z(p1[e], p2[e], e2) & X(q1[e], q2[e], e2)
                if np.any(e):
                    fe = np.vstack([V[:, [0, 1]], V[:, [1, 2]], V[:, [2, 0]]])
                    pairs = np.column_stack([np.repeat(S, 3), np.sort(fe, axis=1)])
                    _, idx = np.unique(pairs, axis=0, return_index=True)
                    e0 = np.zeros((nx * 3,), dtype=bool)
                    e0[idx[np.isin(idx, np.where(e)[0])]] = True
                    e = e0

    v = v.reshape(nx, 3)
    e = e.reshape(nx, 3)
    I = f | np.any(e | v, axis=1)

    us = np.unique(S[I])
    if np.any(I) and us.size > 1:
        cons = np.diff(us) == 1
        if np.any(cons):
            cons_idx = np.where(cons)[0]
            for ci in cons_idx:
                first_in_pair = us[ci]
                i_idx = I & (S == first_in_pair)
                coord = Q2[np.where(i_idx)[0][0]]
                i_idx2 = I & (S == first_in_pair + 1)
                if not (np.any(f[i_idx]) and np.any(f[i_idx2])) and \
                   not (np.any(e[i_idx]) and np.any(e[i_idx2])) and \
                   not (np.any(v[i_idx]) and np.any(v[i_idx2])):
                    continue
                if np.any(np.any(v, axis=1) & i_idx):
                    vertices = np.unique(np.vstack([P1[i_idx], P2[i_idx], P3[i_idx]]), axis=0)
                    x = np.any(np.all(vertices == coord, axis=1))
                elif np.any(np.any(e, axis=1) & i_idx):
                    edges1 = np.vstack([P1[i_idx], P2[i_idx], P3[i_idx]])
                    edges2 = np.vstack([P2[i_idx], P3[i_idx], P1[i_idx]])
                    cc = np.repeat(coord[None, :], edges1.shape[0], axis=0)
                    x = np.any(L(edges1, edges2, cc) & Z(edges1, edges2, cc))
                else:
                    nf = np.sum(i_idx)
                    edges1 = np.vstack([P1[i_idx], P2[i_idx], P3[i_idx]])
                    edges2 = np.vstack([P2[i_idx], P3[i_idx], P1[i_idx]])
                    c1 = np.vstack([edges1 - coord, edges1[(np.arange(nf) * 3) + 1] - edges1[(np.arange(nf) * 3)]])
                    c2 = np.vstack([edges2 - coord, edges1[(np.arange(nf) * 3) + 2] - edges1[(np.arange(nf) * 3)]])
                    cc = np.sqrt(np.sum(np.cross(c1, c2) ** 2, axis=1))
                    cc = cc[:nf * 3].reshape(-1, 3) / cc[nf * 3:].reshape(-1, 1)
                    x = np.any(np.all((0 <= cc) & (cc <= 1), axis=1))
                if x:
                    I[i_idx] = False

    return I
