import numpy as np
import nibabel.freesurfer.io as fsio


def write_curv(path, data, nfaces=None):
    data = np.asarray(data).reshape(-1)
    fsio.write_morph_data(path, data)


def read_curv(path):
    return fsio.read_morph_data(path)
