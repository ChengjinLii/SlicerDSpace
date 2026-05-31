import os
import numpy as np
import nibabel as nib


def read_mrtrix_tracks(path):
    trk = nib.streamlines.load(path)
    streamlines = list(trk.streamlines)
    return {'data': streamlines, 'count': str(len(streamlines)), 'header': trk.header}


def write_mrtrix_tracks(slinfo, path):
    streamlines = slinfo.get('data', [])
    tractogram = nib.streamlines.Tractogram(streamlines, affine_to_rasmm=np.eye(4))
    nib.streamlines.save(tractogram, path)
