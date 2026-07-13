import numpy as np


def _deduplicate_true_rows(pairs, flags):
    """Keep one true item for each pair, matching MATLAB ``unique`` mapping."""

    flags = np.asarray(flags, dtype=bool)
    result = np.zeros(flags.shape, dtype=bool)
    if not np.any(flags):
        return result
    _, first, inverse = np.unique(
        np.asarray(pairs), axis=0, return_index=True, return_inverse=True
    )
    result[first[inverse[flags]]] = True
    return result


def _point_on_triangle(point, p1, p2, p3):
    """Return whether *point* lies on any supplied triangle, boundaries included."""

    if p1.shape[0] == 0:
        return False
    scale = max(
        1.0,
        float(np.max(np.abs(np.vstack([point[None, :], p1, p2, p3])))),
    )
    tol = np.finfo(float).eps * 64.0 * scale
    edge1 = p2 - p1
    edge2 = p3 - p1
    normal = np.cross(edge1, edge2)
    normal_norm = np.linalg.norm(normal, axis=1)
    valid = normal_norm > tol
    if not np.any(valid):
        return False

    delta = point - p1
    plane_distance = np.abs(np.einsum("ij,ij->i", delta, normal))
    on_plane = plane_distance <= tol * normal_norm

    dot00 = np.einsum("ij,ij->i", edge1, edge1)
    dot01 = np.einsum("ij,ij->i", edge1, edge2)
    dot11 = np.einsum("ij,ij->i", edge2, edge2)
    dot20 = np.einsum("ij,ij->i", delta, edge1)
    dot21 = np.einsum("ij,ij->i", delta, edge2)
    denominator = dot00 * dot11 - dot01 * dot01
    usable = valid & (np.abs(denominator) > tol)
    u = np.zeros_like(denominator)
    v = np.zeros_like(denominator)
    u[usable] = (dot11[usable] * dot20[usable] - dot01[usable] * dot21[usable]) / denominator[usable]
    v[usable] = (dot00[usable] * dot21[usable] - dot01[usable] * dot20[usable]) / denominator[usable]
    return bool(np.any(usable & on_plane & (u >= -tol) & (v >= -tol) & (u + v <= 1.0 + tol)))


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
                fx = _deduplicate_true_rows(pairs, f)
                # MATLAB ``repmat(fx, [3 1])`` creates three complete
                # blocks; ``np.repeat`` would interleave unrelated rows.
                ex = np.tile(fx, 3)

    D = lambda p1, p2: p2 - p1
    M = lambda p1, p2: np.cross(p1, D(p1, p2))
    def L(q1, q2, p):
        return np.all(np.abs(np.cross(p, D(q1, q2)) - M(q1, q2)) < np.finfo(float).eps, axis=1)
    def P(q1, q2, p):
        return np.einsum('ij,ij->i', q1 - q2, p - q2) / np.einsum('ij,ij->i', q1 - q2, q1 - q2)
    def X(q1, q2, p):
        t = P(q1, q2, p)
        return (t >= 0) & (t <= 1)

    # Match MATLAB's block-major ``repmat(..., [3 1])`` layout.
    q1 = np.tile(Q1, (3, 1))
    q2 = np.tile(Q2, (3, 1))
    p1 = np.vstack([P1, P2, P3])

    v = ~ex
    if np.any(v):
        v[v] = L(q1[v], q2[v], p1[v])
        if np.any(v):
            v[v] = X(q1[v], q2[v], p1[v])
            if np.any(v):
                pairs = np.column_stack([
                    np.tile(S, 3),
                    V.reshape(-1, order='F'),
                ])
                v = _deduplicate_true_rows(pairs, v)

    def A(p1, p2, q1, q2):
        return np.any(np.abs(np.cross(D(p1, p2), D(q1, q2))) > np.finfo(float).eps, axis=1)
    def R(p1, p2, q1, q2):
        return np.abs(np.einsum('ij,ij->i', D(p1, p2), M(q1, q2)) + np.einsum('ij,ij->i', D(q1, q2), M(p1, p2))) < np.finfo(float).eps
    def C(p1, p2, q1, q2):
        # Geometric line-line intersection equivalent to the original
        # Pluecker expression.  The earlier broadcasted translation changed
        # its dimensions and failed for valid vertex/edge intersections.
        p_direction = D(p1, p2)
        q_direction = D(q1, q2)
        cross_d = np.cross(p_direction, q_direction)
        denom = np.einsum('ij,ij->i', cross_d, cross_d)
        t = np.einsum(
            'ij,ij->i',
            np.cross(q1 - p1, q_direction),
            cross_d,
        ) / denom
        return p1 + t[:, None] * p_direction
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
                    pairs = np.column_stack([np.tile(S, 3), np.sort(fe, axis=1)])
                    e = _deduplicate_true_rows(pairs, e)

    # MATLAB reshapes these block vectors in column-major order.
    v = v.reshape(nx, 3, order='F')
    e = e.reshape(nx, 3, order='F')
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
                    # The translated per-face offsets assumed an interleaved
                    # layout even though P1/P2/P3 are block-major.  Test the
                    # intended geometry directly: the shared streamline point
                    # lies on at least one of the intersected faces.
                    x = _point_on_triangle(
                        coord,
                        P1[i_idx],
                        P2[i_idx],
                        P3[i_idx],
                    )
                if x:
                    I[i_idx] = False

    return I
