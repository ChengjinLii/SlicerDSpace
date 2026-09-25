import os
import time

from Support.verb_msg import verb_msg
from Support.sys_exec import sys_exec
from Support.pts_to_tck import pts_to_tck
from Support.shell_quote import shell_quote
from .read_prefilter_tracks import read_prefilter_tracks


def tractography_mrtrix(PS, SD):
    SD.DWI.seed_coords_file_out = os.path.join(PS.work_dir, 'DWI_seeds_out.txt')

    if PS.noseed and os.path.exists(PS.noseed):
        SD.DWI.sl_init = PS.noseed
        PS.final_init = PS.noseed
    elif os.path.exists(SD.DWI.sl_init) and not PS.force:
        PS.final_init = SD.DWI.sl_init
    elif (not os.path.exists(SD.DWI.sl_init)) or PS.force:
        verb_msg('Running mrtrix tckgen', PS)
        tstart = time.time()

        seed_str = ''
        if PS.surfseed:
            seed_str = f" -seed_coordinates_global {shell_quote(SD.DWI.seed_coords_file_in)}"

        command = (
            f"{PS.mrtrix_prefix} tckgen{seed_str} "
            f"-output_seeds {shell_quote(SD.DWI.seed_coords_file_out)} {PS.tckgen} "
            f"{shell_quote(PS.fod)} {shell_quote(SD.DWI.sl_init)} -force"
        )
        verb_msg('tckgen string:', PS)
        verb_msg(command, PS)
        sys_exec(command, PS)

        t = time.time() - tstart
        PS.logt.append(['Time spent on initial tractogram generation:', _format_elapsed(t)])

        if PS.dgn:
            pts_to_tck(SD.DWI.seed_coords_file_out, os.path.join(PS.work_dir, 'DWI_seeds_out.tck'))

        PS.final_init = SD.DWI.sl_init
    else:
        raise RuntimeError('tckgen input wrong')

    PS, SD = read_prefilter_tracks(PS, SD)
    return PS, SD


def _format_elapsed(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f'{h:02d}:{m:02d}:{s:02d}'
