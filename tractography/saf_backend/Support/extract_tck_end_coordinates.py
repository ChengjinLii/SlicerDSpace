import numpy as np


def extract_tck_end_coordinates(tck):
    if isinstance(tck, dict) and 'data' in tck:
        tck = tck['data']
    empty = [len(sl) == 0 for sl in tck]
    pts_list = []
    for sl, is_empty in zip(tck, empty):
        if is_empty:
            continue
        pts_list.append(sl[[0, -1], :].T)
    if not pts_list:
        return np.zeros((0, 3)), np.zeros((0,), dtype=bool)
    pts = np.concatenate(pts_list, axis=1)
    pts = pts.reshape(3, -1, 2)
    pts = np.concatenate([pts[:, :, 0], pts[:, :, 1]], axis=1).T
    se = np.zeros((pts.shape[0],), dtype=bool)
    se[pts.shape[0] // 2:] = True
    return pts, se
