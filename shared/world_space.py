"""World-space helpers shared by DDSeg QC and ACT preparation.

Images produced by different tools in this pipeline are not stored in the same
voxel order (for example, the DWI and DDParcel may be LAS-stored while another
producer writes RAS). Combining them by raw array indexing silently mirrors
one against the other. Every cross-image operation must therefore go through
the images' affines, which is what these helpers do.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def voxel_world_coordinates(shape: Sequence[int], affine: np.ndarray) -> np.ndarray:
    """Return the RAS+ world coordinate (mm) of every voxel centre, shape (N, 3)."""

    ijk = np.indices(tuple(int(value) for value in shape[:3])).reshape(3, -1).T
    return ijk @ np.asarray(affine, dtype=np.float64)[:3, :3].T + np.asarray(affine, dtype=np.float64)[:3, 3]


def resample_nearest_to_grid(
    source: np.ndarray,
    source_affine: np.ndarray,
    target_shape: Sequence[int],
    target_affine: np.ndarray,
    *,
    fill_value: float = 0,
) -> np.ndarray:
    """Nearest-neighbour resample ``source`` onto a target grid through world space.

    Voxels of the target grid whose centre falls outside the source volume get
    ``fill_value``. Only the first three axes are spatial; trailing axes are kept.
    """

    source = np.asarray(source)
    if source.ndim < 3:
        raise ValueError(f"Expected a volume with at least three spatial axes, got shape {source.shape}")
    world = voxel_world_coordinates(target_shape, target_affine)
    inverse = np.linalg.inv(np.asarray(source_affine, dtype=np.float64))
    source_ijk = np.rint(world @ inverse[:3, :3].T + inverse[:3, 3]).astype(np.int64)
    inside = np.all((source_ijk >= 0) & (source_ijk < np.asarray(source.shape[:3])), axis=1)
    trailing = source.shape[3:]
    output = np.full((source_ijk.shape[0], *trailing), fill_value, dtype=source.dtype)
    output[inside] = source[tuple(source_ijk[inside].T)]
    return output.reshape((*tuple(int(value) for value in target_shape[:3]), *trailing))


def same_voxel_grid(
    affine_a: np.ndarray,
    shape_a: Sequence[int],
    affine_b: np.ndarray,
    shape_b: Sequence[int],
    *,
    atol_mm: float = 1e-3,
) -> bool:
    """True when two images share shape and voxel-to-world mapping (within ``atol_mm``)."""

    if tuple(int(v) for v in shape_a[:3]) != tuple(int(v) for v in shape_b[:3]):
        return False
    return bool(np.allclose(np.asarray(affine_a, dtype=np.float64), np.asarray(affine_b, dtype=np.float64), atol=atol_mm))


def dice(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """Sørensen-Dice overlap of two boolean masks on the same grid (0 when both are empty)."""

    a = np.asarray(mask_a, dtype=bool)
    b = np.asarray(mask_b, dtype=bool)
    denominator = int(a.sum()) + int(b.sum())
    if denominator == 0:
        return 0.0
    return 2.0 * float(np.count_nonzero(a & b)) / float(denominator)
