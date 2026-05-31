import numpy as np
import time

from Filters.streamlineXmesh.crop_streamlines_outside_mesh_fast import crop_streamlines_outside_mesh_fast
from Filters.streamlineXmesh.crop_streamlines_outside_mesh_complete import crop_streamlines_outside_mesh_complete
from Support.verb_msg import verb_msg


def filters_GWG(PS, DWI):
    verb_msg('Starting GWG filtering', PS)
    precision = 'fast' if PS.fastx else 'complete'
    gwgt = time.time()

    valid_sl = np.all(DWI.saf.t_gghh, axis=0) & ~DWI.saf.pg & ~DWI.saf.ml

    if (not PS.gwg_hard) or (PS.gwg_hard and PS.notrunc):
        new_streamlines = [None] * DWI.saf.t_gghh.shape[1]
        DWI.saf.t_gwg = np.zeros_like(DWI.saf.m)
    else:
        new_streamlines = []
        new_hemi_flags = []
        DWI.saf.t_gwg = np.zeros((2, 0), dtype=int)

    for hemi in ['rh', 'lh']:
        V = getattr(DWI, hemi).white
        F = getattr(DWI, hemi).faces
        F = F[~np.any(np.isin(F, np.where(~getattr(DWI, hemi).usedv)[0]), axis=1)]

        if hemi == 'rh':
            hemi_tracks = valid_sl & ~np.any(DWI.saf.h, axis=0)
        else:
            hemi_tracks = valid_sl & np.all(DWI.saf.h, axis=0)

        if not np.any(hemi_tracks):
            continue

        tracks = [t for t, keep in zip(DWI.sl_tracks, hemi_tracks) if keep]

        try:
            if precision == 'fast':
                tcn, osi, xv, xp = crop_streamlines_outside_mesh_fast(V, F, tracks, DWI.saf.m[0, hemi_tracks], not PS.gwg_hard)
            else:
                tcn, osi, xv, xp = crop_streamlines_outside_mesh_complete(V, F, tracks, DWI.saf.m[0, hemi_tracks], not PS.gwg_hard)
        except AssertionError as exc:
            if str(exc) != 'No streamlines have survived GWG filtering':
                raise
            tcn = []
            osi = np.zeros((0,), dtype=int)
            xv = np.zeros((2, 0), dtype=float)
            xp = np.zeros((2, 0), dtype=int)

        if len(osi) == 0:
            continue

        temp_idx = np.where(hemi_tracks)[0]
        osi = temp_idx[osi]

        if (not PS.gwg_hard) or (PS.gwg_hard and PS.notrunc):
            if PS.gwg_hard and PS.notrunc:
                unique, counts = np.unique(osi, return_counts=True)
                keep = unique[counts == 1]
                mask = np.isin(osi, keep)
                osi = osi[mask]
                xv = xv[:, mask]

            r_idx = ~np.all((DWI.saf.m[:, osi] > 0) | (xv > 0), axis=0)
            keep_mask = ~r_idx
            kept_streamlines = [sl for sl, keep in zip(tcn, keep_mask) if keep]
            osi = osi[keep_mask]
            xv = xv[:, keep_mask]

            xv[DWI.saf.m[:, osi] > 0] = 0
            DWI.saf.t_gwg[:, osi] = (DWI.saf.t_gghh[:, osi] > 0) * DWI.saf.m[:, osi] + xv

            if not PS.notrunc:
                for idx, sl in zip(osi, kept_streamlines):
                    new_streamlines[idx] = sl
        else:
            _, first_pos = np.unique(osi, return_index=True)
            _, reverse_first_pos = np.unique(osi[::-1], return_index=True)
            last_pos = len(osi) - 1 - reverse_first_pos
            s_idx = np.zeros(len(osi), dtype=bool)
            e_idx = np.zeros(len(osi), dtype=bool)
            u_idx = np.zeros(DWI.saf.m.shape[1], dtype=bool)
            s_idx[first_pos] = True
            e_idx[last_pos] = True
            u_idx[np.unique(osi)] = True
            r_idx = ~np.all((DWI.saf.m[:, osi] > 0) | (xv > 0), axis=0) & np.any(xv == 0, axis=0)

            ss = s_idx & (DWI.saf.m[0, osi] > 0)
            ee = e_idx & (DWI.saf.m[1, osi] > 0)
            xv[0, ss] = DWI.saf.t_gghh[0, u_idx & (DWI.saf.m[0, :] > 0)]
            xv[1, ee] = DWI.saf.t_gghh[1, u_idx & (DWI.saf.m[1, :] > 0)]

            xp[0, ss] = xp[0, ss] - 1
            xp[1, ee] = xp[1, ee] + 1

            keep_mask = ~r_idx
            kept_streamlines = [sl for sl, keep in zip(tcn, keep_mask) if keep]
            osi = osi[keep_mask]
            xv = xv[:, keep_mask]
            xp = xp[:, keep_mask]

            if DWI.saf.pre_c is None:
                DWI.saf.pre_c = osi
            else:
                DWI.saf.pre_c = np.concatenate([DWI.saf.pre_c, osi])
            if DWI.saf.pre_xp is None:
                DWI.saf.pre_xp = xp
            else:
                DWI.saf.pre_xp = np.concatenate([DWI.saf.pre_xp, xp], axis=1)
            DWI.saf.t_gwg = np.concatenate([DWI.saf.t_gwg, xv], axis=1)
            new_streamlines.extend(kept_streamlines)
            new_hemi_flags.extend([hemi == 'lh'] * len(kept_streamlines))

    if PS.gwg_hard and not PS.notrunc:
        DWI.saf.pre_h = DWI.saf.h
        DWI.saf.h = np.tile(np.asarray(new_hemi_flags, dtype=bool), (2, 1))

    if not PS.notrunc:
        DWI.sl_tracks = new_streamlines

    t = time.time() - gwgt
    PS.logt.append(['Time spent on GWG filtering:', _format_elapsed(t)])

    if (not PS.gwg_hard) or (PS.gwg_hard and PS.notrunc):
        rejn = int(np.sum(valid_sl) - np.sum(np.all(DWI.saf.t_gwg, axis=0)))
        PS.logt.append(['Number of streamlines rejected during GWG filtering:', rejn])
    else:
        PS.logt.append(['Number of streamlines after GWG filtering:', len(new_streamlines)])

    for entry in PS.logt[-2:]:
        verb_msg(f"{entry[0]} {entry[1]}", PS)

    return PS, DWI


def _format_elapsed(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f'{h:02d}:{m:02d}:{s:02d}'
