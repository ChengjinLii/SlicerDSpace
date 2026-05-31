import numpy as np


def trintersect_fast(P1, P2, P3, Q1, Q2):
    def signed_volume(a, b, d, c):
        return (1.0 / 6.0) * np.einsum('ij,ij->i', np.cross(b - a, c - a), d - a)

    repside = np.sign(signed_volume(Q1, Q2, P2, P3))
    I = np.sign(signed_volume(Q1, P1, P2, P3)) != np.sign(signed_volume(Q2, P1, P2, P3))
    if np.any(I):
        I = I & (repside == np.sign(signed_volume(Q1, Q2, P1, P2)))
    if np.any(I):
        I = I & (repside == np.sign(signed_volume(Q1, Q2, P3, P1)))
    return I
