"""Keep endpoint coordinates and crossed faces in the same indexing layout."""

import numpy as np


def closest_endpoint_vertices(vertices, faces, tracks, end_faces):
    # Use [start_0, end_0, start_1, end_1, ...] for both coordinates and faces.
    # Mixing this with MATLAB's [all starts; all ends] changes vertex assignment.
    paired_faces = np.asarray(end_faces).T
    valid = ~np.isnan(paired_faces)
    paired_points = np.stack([sl[[0, -1]] for sl in tracks])
    points = paired_points[valid]
    crossed_faces = faces[paired_faces[valid].astype(int)]
    squared_distances = np.sum((points[:, None, :] - vertices[crossed_faces]) ** 2, axis=2)
    nearest = np.argmin(squared_distances, axis=1)
    indices = crossed_faces[np.arange(len(crossed_faces)), nearest]
    result = np.zeros_like(paired_faces, dtype=float)
    result[valid] = indices + 1  # SAF surface indices retain the 1-based convention.
    return result.T
