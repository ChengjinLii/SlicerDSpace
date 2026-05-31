import numpy as np

from .process_coords import process_coords
from .mrtrix_tracks import write_mrtrix_tracks


def pts_to_tck(pts, output_tck, *extra):
    pts = process_coords(pts)
    sizes = [pts.shape[0]]
    mats = [pts]
    for e in extra:
        em = process_coords(e)
        mats.append(em)
        sizes.append(em.shape[0])
    if max(sizes) == 0:
        return
    if any(s != max(sizes) for s in sizes):
        raise ValueError('matrix sizes are different')

    arr = np.stack(mats, axis=0)
    if np.isnan(arr).any():
        print('Warning: values contain nans, this is known to cause errors')

    streamlines = [arr[i] for i in range(arr.shape[0])]
    write_mrtrix_tracks({'data': streamlines}, output_tck)
