import numpy as np
import nibabel.freesurfer.io as fsio


def write_curv(path, data, nfaces=None):
    data = np.asarray(data).reshape(-1)
    # FreeSurfer's curvature header records the number of faces.  Omitting
    # it silently writes zero and makes the Python output differ from the
    # MATLAB ``write_curv(..., nfaces)`` product.
    fnum = 0 if nfaces is None else int(nfaces)
    fsio.write_morph_data(path, data, fnum=fnum)


def read_curv(path):
    return fsio.read_morph_data(path)
