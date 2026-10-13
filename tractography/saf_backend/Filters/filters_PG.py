import numpy as np
import time

from Filters.streamlineXmesh.crop_streamlines_outside_mesh_fast import crop_streamlines_outside_mesh_fast
from Filters.streamlineXmesh.crop_streamlines_outside_mesh_complete import crop_streamlines_outside_mesh_complete
from Support.verb_msg import verb_msg


def _pial_escape_mask(xpoints, original_indices, tracks):
    """Identify cropped chains that do not span their source streamline."""

    original_indices = np.asarray(original_indices, dtype=int)
    last_points = np.asarray(
        [tracks[index].shape[0] - 1 for index in original_indices],
        dtype=int,
    )
    # crop_streamlines_outside_mesh uses native zero-based NumPy indices.
    return (xpoints[0] > 0) | (xpoints[1] != last_points)


def filters_PG(PS, DWI):
    if hasattr(DWI.saf, 'pg') and DWI.saf.pg is not None and np.any(DWI.saf.pg) and not PS.force:
        return PS, DWI

    DWI.saf.pg = np.zeros((DWI.saf.t_gghh.shape[1],), dtype=bool)
    pial_sl_wb = np.zeros_like(DWI.saf.pg)

    if not PS.pialfilter:
        return PS, DWI

    verb_msg('Starting PG filtering', PS)
    pialt = time.time()
    precision = 'fast' if PS.fastx else 'complete'

    for hemi in ['rh', 'lh']:
        V = getattr(DWI, hemi).pial
        F = getattr(DWI, hemi).faces
        F = F[~np.any(np.isin(F, np.where(~getattr(DWI, hemi).usedv)[0]), axis=1)]

        if hemi == 'rh':
            hemi_tracks = np.all(DWI.saf.t_gghh, axis=0) & ~np.any(DWI.saf.h, axis=0)
        else:
            hemi_tracks = np.all(DWI.saf.t_gghh, axis=0) & np.all(DWI.saf.h, axis=0)

        tracks = [t for t, keep in zip(DWI.sl_tracks, hemi_tracks) if keep]
        if not tracks:
            continue
        try:
            if precision == 'fast':
                _, osi, _, xp = crop_streamlines_outside_mesh_fast(V, F, tracks, True, True)
            else:
                _, osi, _, xp = crop_streamlines_outside_mesh_complete(V, F, tracks, True, True)
        except AssertionError as exc:
            if str(exc) != 'No streamlines have survived GWG filtering':
                raise
            pial_sl_wb[hemi_tracks] = True
            continue

        # ``osi`` indexes the hemisphere-filtered ``tracks`` collection and
        # can be shorter than it when some streamlines do not survive.  Use it
        # before mapping back to whole-brain indices, just as MATLAB indexes
        # DWI.sl_tracks(osi) after its equivalent mapping.
        local_osi = np.asarray(osi, dtype=int)
        xx = _pial_escape_mask(xp, local_osi, tracks)
        temp_idx = np.where(hemi_tracks)[0]
        whole_brain_osi = temp_idx[local_osi]
        pial_sl_wb[whole_brain_osi[xx]] = True

    DWI.saf.pg = pial_sl_wb

    t = time.time() - pialt
    PS.logt.append(['Time spent on pial streamlines removal:', _format_elapsed(t)])
    verb_msg(f"{PS.logt[-1][0]} {PS.logt[-1][1]}", PS)
    PS.logt.append(['Number of streamlines rejected due to intersection with the pia:', int(np.sum(pial_sl_wb))])
    verb_msg(f"{PS.logt[-1][0]} {PS.logt[-1][1]}", PS)

    return PS, DWI


def _format_elapsed(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f'{h:02d}:{m:02d}:{s:02d}'
