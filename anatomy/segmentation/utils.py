from __future__ import annotations

import numpy as np


def padding_unpadding(img: np.ndarray, target_size: tuple[int, int, int], mode: str) -> np.ndarray:
    image_size = img.shape
    if mode == "padding":
        target_sizes = np.array(
            [
                [144, 144, 96],
                [256, 256, 96],
                [256, 256, 128],
                [256, 256, 160],
            ],
            dtype=int,
        )
        for candidate in target_sizes:
            if (candidate >= image_size[:3]).all():
                target_size = tuple(int(x) for x in candidate)
                break
        padded = np.full((*target_size, image_size[3]), np.nan, dtype=img.dtype)
        padded[: image_size[0], : image_size[1], : image_size[2], :] = img
        return padded
    if mode == "unpadding":
        new_size = np.minimum(np.array(image_size[:3]), np.array(target_size))
        return img[: new_size[0], : new_size[1], : new_size[2], :]
    raise ValueError("mode must be 'padding' or 'unpadding'")


def normalize_vector(vec: np.ndarray) -> np.ndarray:
    mean = np.nanmean(vec)
    if vec.size <= 1:
        std = 0.0
    else:
        std = np.nanstd(vec, ddof=1)
    if std < 1e-6:
        std = 1e-6
    return (vec - mean) / std
