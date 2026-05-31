import numpy as np


def extract_faces(usedv, F):
    usedv = np.asarray(usedv, dtype=bool)
    F = np.asarray(F, dtype=int)
    fe = np.all(usedv[F], axis=1)
    F_e = F[fe]

    old_to_new = np.full(usedv.shape[0], -1, dtype=int)
    old_to_new[np.flatnonzero(usedv)] = np.arange(np.count_nonzero(usedv))
    F_v = old_to_new[F_e]
    return F_v, F_e
