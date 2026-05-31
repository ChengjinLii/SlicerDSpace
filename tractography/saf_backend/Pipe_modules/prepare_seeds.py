import numpy as np
import os

from Support.convert_coords import convert_coords
from Support.process_coords import process_coords
from Support.verb_msg import verb_msg


def prepare_seeds(PS, SD):
    native_seeds = os.path.join(PS.work_dir, 'WSM_coords.txt')
    remeshed_seeds = os.path.join(PS.work_dir, 'remeshed_seeds.txt')
    SD.DWI.sl_init = os.path.join(PS.work_dir, 'surf_tracks.tck')

    if PS.remesh_seeds and not PS.noseed and (not os.path.exists(SD.DWI.sl_init) or PS.force):
        if not os.path.exists(remeshed_seeds) or PS.force:
            output_seeds = []

            def edges(F):
                return np.vstack([F[:, 0:2], F[:, 1:3], F[:, [2, 0]]])

            def L(E, V):
                return np.sum((V[E[:, 0]] - V[E[:, 1]]) ** 2, axis=1)

            if isinstance(PS.remesh_seeds, (int, float)):
                maxlen = float(PS.remesh_seeds)
            else:
                length = []
                for hemi in ['rh', 'lh']:
                    V = SD.DWI.__dict__[hemi].white
                    F = SD.DWI.__dict__[hemi].faces
                    length.append(np.sqrt(L(edges(F), V)))
                length = np.concatenate(length)
                maxlen = np.mean(length) + np.std(length) * 3
                verb_msg(f'Edge length cut off for white surface remeshing (seed input): {round(maxlen,2)}', PS)

            maxlen = maxlen ** 2

            for hemi in ['rh', 'lh']:
                V = SD.DWI.__dict__[hemi].white
                F = SD.DWI.__dict__[hemi].faces.copy()
                F[np.sum(np.isin(F, np.where(~SD.DWI.__dict__[hemi].usedv)[0]), axis=1) > 1] = -1
                F = F[F[:, 0] >= 0]
                nv = V.shape[0]
                nf = F.shape[0]

                edges_arr = edges(F)
                long_E = L(edges_arr, V) > maxlen
                while np.any(long_E):
                    le = edges_arr[np.where(long_E)[0][0]]
                    f = np.sum(np.isin(F, le), axis=1) > 1
                    fx = F[f]
                    v3 = (fx != le[0]) & (fx != le[1])
                    nn = np.sum(v3)
                    new_v = np.mean(V[le], axis=0)

                    v1_idx = (np.where(v3.T)[0] % 3)
                    vf_idx = (v1_idx + 1) % 3
                    vr_idx = (v1_idx - 1) % 3

                    new_f = np.zeros((nn * 2, 3), dtype=int)
                    for i in range(nn):
                        new_f[i * 2] = [fx[i, v1_idx[i]], fx[i, vf_idx[i]], nv]
                        new_f[i * 2 + 1] = [nv, fx[i, vr_idx[i]], fx[i, v1_idx[i]]]

                    F = F[~f]
                    F = np.vstack([F, new_f])
                    V = np.vstack([V, new_v])
                    nv += 1
                    nf = F.shape[0]

                    edges_arr = edges(F)
                    long_E = L(edges_arr, V) > maxlen

                output_seeds.append(V)

            output_seeds = np.vstack(output_seeds)
            SD.DWI.cv_white_coord_file = remeshed_seeds
            convert_coords(output_seeds, SD.DWI.cv_white_coord_file)
        else:
            SD.DWI.cv_white_coord_file = remeshed_seeds
            if not PS.quiet:
                output_seeds = process_coords(remeshed_seeds)

        verb_msg(f'Number of coordinates added for seeding: {output_seeds.shape[0] - SD.DWI.cv.shape[0]}', PS)
    else:
        SD.DWI.cv_white_coord_file = native_seeds
        if not os.path.exists(native_seeds) or PS.force:
            convert_coords(SD.DWI.cv, SD.DWI.cv_white_coord_file)

    SD.DWI.seed_coords_file_in = SD.DWI.cv_white_coord_file
    return SD
