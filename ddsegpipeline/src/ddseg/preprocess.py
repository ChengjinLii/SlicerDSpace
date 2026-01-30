from __future__ import annotations

import numpy as np
import nibabel as nib
import nrrd
from pathlib import Path
from typing import Dict

from .feature_defs import FEATURES
from .utils import padding_unpadding, normalize_vector, load_nii_matlab_like


def load_parameter_map(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(f"Missing parameter map: {path}")
    suffixes = "".join(path.suffixes).lower()
    if suffixes.endswith(".nii.gz") or path.suffix.lower() == ".nii":
        img = load_nii_matlab_like(path)
        return img.get_fdata()
    if path.suffix.lower() in {".nrrd", ".nhdr"}:
        data, _ = nrrd.read(path.as_posix())
        data = np.fliplr(data)
        data = np.flipud(data)
        return data
    raise ValueError(f"Unsupported parameter map format: {path}")


def masking_and_normalizing(parameter_folder: Path, mask_file: Path, parameter_type: str) -> Dict[str, np.ndarray]:
    feature_info = FEATURES[parameter_type]
    feature_list = feature_info["list"]
    feature_range = feature_info["range"]

    mask_img = load_nii_matlab_like(mask_file)
    brain_mask = mask_img.get_fdata() > 0

    outputs = {}
    for feat, (low, high) in zip(feature_list, feature_range):
        path = parameter_folder / f"{feat}.nrrd"
        param_map = load_parameter_map(path)
        param_map[~brain_mask] = np.nan
        param_map[param_map < low] = low
        param_map[param_map > high] = high
        vec = param_map[brain_mask]
        vec = normalize_vector(vec)
        out = np.full_like(param_map, np.nan, dtype=np.float32)
        out[brain_mask] = vec.astype(np.float32)
        outputs[feat] = out
    return outputs


def stack_features(feature_maps: Dict[str, np.ndarray], parameter_type: str) -> np.ndarray:
    feature_list = FEATURES[parameter_type]["list"]
    stacked = np.stack([feature_maps[f] for f in feature_list], axis=-1)
    stacked = padding_unpadding(stacked, (112, 144, 96), "padding")
    stacked[np.isnan(stacked)] = -100.0
    return stacked.astype(np.float32)


def split_views(stacked: np.ndarray) -> Dict[str, list[np.ndarray]]:
    views = {"axial": [], "coronal": [], "sagittal": []}
    for i in range(stacked.shape[2]):
        views["axial"].append(stacked[:, :, i, :])
    for i in range(stacked.shape[1]):
        views["coronal"].append(stacked[:, i, :, :])
    for i in range(stacked.shape[0]):
        views["sagittal"].append(stacked[i, :, :, :])
    return views
