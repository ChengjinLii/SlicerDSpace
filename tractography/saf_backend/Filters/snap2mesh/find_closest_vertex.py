import numpy as np
from scipy.spatial import cKDTree


def find_closest_vertex(p1, p2, p1_clustering):
    p1 = np.asarray(p1)
    p2 = np.asarray(p2)
    labels = np.asarray(p1_clustering).reshape(-1)
    k = int(labels.max())

    p1_groups = []
    centroids = []
    for i in range(1, k + 1):
        idx = np.where(labels == i)[0]
        if idx.size == 0:
            p1_groups.append((np.empty((0, 3)), np.empty((0,), dtype=int)))
            centroids.append(np.zeros((3,)))
            continue
        coords = p1[idx]
        p1_groups.append((coords, idx))
        centroids.append(coords.mean(axis=0))
    centroids = np.vstack(centroids)

    centroid_tree = cKDTree(centroids)
    _, centroid_i = centroid_tree.query(p2, k=1)

    I = np.zeros((p2.shape[0],), dtype=int)
    D = np.zeros((p2.shape[0],), dtype=float)

    for i in range(k):
        group_idx = np.where(centroid_i == i)[0]
        if group_idx.size == 0:
            continue
        coords, orig_idx = p1_groups[i]
        if coords.shape[0] == 0:
            continue
        tree = cKDTree(coords)
        d, ci = tree.query(p2[group_idx], k=1)
        I[group_idx] = orig_idx[ci] + 1
        D[group_idx] = d

    return I, D
