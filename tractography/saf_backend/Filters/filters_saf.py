import os
import numpy as np

from Support.read_tsf import read_tsf
from Support.write_tsf import write_tsf
from Support.mrtrix_tracks import write_mrtrix_tracks


def filters_saf(PS, DWI):
    DWI.saf.saf_file = os.path.join(PS.work_dir, 'SAF.tck')
    DWI.saf.t = DWI.saf.t_gwg.copy()

    exist_saf = np.all(DWI.saf.t_gwg, axis=0)
    acc_tck = [sl for sl, keep in zip(DWI.sl_tracks, exist_saf) if keep]
    PS.logt.append(['Total number of SAF streamlines:', int(np.sum(exist_saf))])

    slinf = DWI.sl_info
    slinf['data'] = acc_tck
    slinf['count'] = str(len(acc_tck))
    write_mrtrix_tracks(slinfo=slinf, path=DWI.saf.saf_file)

    if getattr(DWI, 'sl_weights', None):
        part_weights = read_tsf(DWI.sl_weights)
        if hasattr(DWI.saf, 'pre_c') and DWI.saf.pre_c is not None and len(DWI.saf.pre_c) > 0:
            saf_weights = part_weights[DWI.saf.pre_c]
        else:
            valid_sl = np.all(DWI.saf.t_gghh, axis=0) & ~DWI.saf.pg
            full_weights = np.zeros_like(DWI.saf.t[0, :], dtype=float)
            full_weights[valid_sl] = part_weights
            saf_weights = full_weights[exist_saf]
        saf_wtfile = os.path.join(PS.work_dir, 'SAF.wts')
        write_tsf(saf_weights, saf_wtfile)
        DWI.saf.w = saf_weights
        PS.logt.append(['SAF streamline weights saved in:', saf_wtfile])

    DWI.saf.t[:, ~exist_saf] = 0
    DWI.saf.l = np.zeros_like(DWI.saf.t[0, :], dtype=float)
    def sl_length(sl):
        return np.sum(np.sqrt(np.sum(np.diff(sl, axis=0) ** 2, axis=1)))
    DWI.saf.l[exist_saf] = np.array([sl_length(sl) for sl in acc_tck])

    return PS, DWI
