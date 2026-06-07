import os
import numpy as np

from Filters.filters_length import filters_length
from Support.read_tsf import read_tsf
from Support.write_tsf import write_tsf


def wholebrain_operations(PS, SD):
    SD.DWI.saf.ml = np.zeros((SD.DWI.saf.t_gghh.shape[1],), dtype=bool)

    if PS.sl_weights or PS.maxlen is not None:
        valid_sl = np.all(SD.DWI.saf.t_gghh, axis=0) & (SD.DWI.saf.pg == 0)

        if PS.sl_weights:
            full_weights = read_tsf(PS.sl_weights)
            SD.DWI.sl_weights = os.path.join(PS.work_dir, 'pre_GWG.wts')
            write_tsf(full_weights[valid_sl], SD.DWI.sl_weights)

        PS, sl_lenfilt = filters_length(PS)
        if sl_lenfilt is not None:
            sl_lenfilt = np.asarray(sl_lenfilt, dtype=bool).reshape(-1)
            if sl_lenfilt.size == SD.DWI.saf.ml.size:
                SD.DWI.saf.ml = sl_lenfilt
            elif sl_lenfilt.size == int(valid_sl.sum()):
                SD.DWI.saf.ml[valid_sl] = sl_lenfilt
            else:
                raise ValueError(
                    "Length-filter mask size mismatch: "
                    f"got {sl_lenfilt.size}, expected {SD.DWI.saf.ml.size} "
                    f"or {int(valid_sl.sum())}."
                )

    return PS, SD
