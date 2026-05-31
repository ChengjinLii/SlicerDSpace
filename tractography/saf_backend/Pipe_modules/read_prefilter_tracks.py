from Support.verb_msg import verb_msg
from Support.mrtrix_tracks import read_mrtrix_tracks


def read_prefilter_tracks(PS, SD):
    verb_msg('Loading streamlines', PS)
    SD.DWI.sl_info = read_mrtrix_tracks(PS.final_init)
    SD.DWI.sl_tracks = SD.DWI.sl_info['data']
    SD.DWI.sl_info = {k: v for k, v in SD.DWI.sl_info.items() if k != 'data'}
    return PS, SD
