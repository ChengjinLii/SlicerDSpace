import os
import numpy as np
import nibabel.freesurfer.io as fsio

from .get_surface_transform import get_surface_transform
from Filters.filters_label import filters_label
from .Supp_gz_fileparts import Supp_gz_fileparts


def process_FS_surfaces(RS, LS, PS):
    if getattr(PS, 'dgn', False):
        VR1, FR = fsio.read_geometry(RS)
        VL1, FL = fsio.read_geometry(LS)
    else:
        VR1, FR = fsio.read_geometry(RS)
        VL1, FL = fsio.read_geometry(LS)

    tfmatrix = get_surface_transform(RS)
    VR = VR1 + tfmatrix[:, 3]
    VL = VL1 + tfmatrix[:, 3]

    if PS.slab != '-1':
        try:
            pp, nn, _ = Supp_gz_fileparts(RS)
            label_dir = os.path.join(os.path.dirname(pp), 'label')
            LR = os.path.join(label_dir, 'rh.' + PS.slab + '.label')
            LL = os.path.join(label_dir, 'lh.' + PS.slab + '.label')
            LR = filters_label(VR, LR)
            LL = filters_label(VL, LL)
        except Exception as e:
            raise RuntimeError('rh, lh not in a standard -recon_all environment, or the label file is wrong') from e
    else:
        LR = np.ones((VR.shape[0],), dtype=bool)
        LL = np.ones((VL.shape[0],), dtype=bool)

    return VR, VL, FR, FL, LR.astype(bool), LL.astype(bool)
