import numpy as np


def discretise_surface_function(vert_area, func, nbins=5):
    vert_area = np.asarray(vert_area).reshape(-1)
    func = np.asarray(func).reshape(-1)
    bin_area = np.sum(vert_area) / nbins
    sort_ind = np.argsort(func)
    area_sort = vert_area[sort_ind]
    nverts = np.zeros((nbins,), dtype=int)
    bin_edges = np.zeros((nbins,), dtype=float)
    ind = np.ones_like(vert_area, dtype=int) * nbins
    y = np.cumsum(area_sort)
    for i in range(nbins):
        y = y - bin_area
        nverts[i] = np.argmin(np.abs(y)) + 1
        bin_edges[i] = func[sort_ind[np.sum(nverts) - 1]]
        shift = np.sum(nverts[:i])
        ind[sort_ind[shift:shift + nverts[i]]] = i + 1
        y = y[nverts[i]:]
    bin_edges = bin_edges[:-1]
    return ind, bin_area, bin_edges
