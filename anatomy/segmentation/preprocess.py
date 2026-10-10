from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import nibabel as nib
import numpy as np

from .feature_defs import FEATURES
from .orientation import axcodes, nrrd_header_affine, require_same_orientation, to_model_orientation
from .utils import normalize_vector, padding_unpadding


@dataclass(frozen=True)
class OrientedMask:
    """Brain mask in model (RAS) orientation plus the on-disk geometry to map back to."""

    model_mask: np.ndarray
    image: nib.Nifti1Image

    @property
    def affine(self) -> np.ndarray:
        return self.image.affine

    @property
    def disk_shape(self) -> tuple[int, int, int]:
        return tuple(int(v) for v in self.image.shape[:3])  # type: ignore[return-value]


def load_volume_with_affine(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load a NIfTI or NRRD volume in on-disk voxel order with its RAS+ affine."""

    if not path.exists():
        raise FileNotFoundError(f"Missing parameter map: {path}")
    suffixes = "".join(path.suffixes).lower()
    if suffixes.endswith(".nii.gz") or path.suffix.lower() == ".nii":
        img = nib.load(path.as_posix())
        return np.asarray(img.dataobj, dtype=np.float64), img.affine
    if path.suffix.lower() in {".nrrd", ".nhdr"}:
        import nrrd  # lazy: optional outside the Slicer runtime

        data, header = nrrd.read(path.as_posix())
        return np.asarray(data, dtype=np.float64), nrrd_header_affine(header)
    raise ValueError(f"Unsupported parameter map format: {path}")


def load_mask(mask_file: Path) -> OrientedMask:
    image = nib.load(Path(mask_file).as_posix())
    data = np.asarray(image.dataobj) > 0
    return OrientedMask(model_mask=to_model_orientation(data, image.affine), image=image)


def load_parameter_map(path: Path, mask: OrientedMask) -> tuple[np.ndarray, float]:
    """Load one feature map reoriented to the model orientation of ``mask``.

    The feature must be stored on the mask's voxel grid orientation; the
    reorientation uses the mask affine so features and mask always receive the
    identical permutation/flip. Returns the array and the max affine difference.
    """

    data, affine = load_volume_with_affine(path)
    affine_difference = require_same_orientation(mask.affine, mask.disk_shape, affine, data.shape, path.name)
    return to_model_orientation(data, mask.affine), affine_difference


def masking_and_normalizing(
    parameter_folder: Path,
    mask: OrientedMask,
    parameter_type: str,
) -> tuple[Dict[str, np.ndarray], dict[str, object]]:
    feature_info = FEATURES[parameter_type]
    feature_list = feature_info["list"]
    feature_range = feature_info["range"]
    brain_mask = mask.model_mask

    outputs: Dict[str, np.ndarray] = {}
    affine_differences: dict[str, float] = {}
    for feat, (low, high) in zip(feature_list, feature_range):
        param_map, affine_differences[feat] = load_parameter_map(Path(parameter_folder) / f"{feat}.nrrd", mask)
        param_map = np.array(param_map, dtype=np.float64)
        param_map[~brain_mask] = np.nan
        param_map[param_map < low] = low
        param_map[param_map > high] = high
        vec = normalize_vector(param_map[brain_mask])
        out = np.full(param_map.shape, np.nan, dtype=np.float32)
        out[brain_mask] = vec.astype(np.float32)
        outputs[feat] = out
    geometry = {
        "mask_axcodes": axcodes(mask.affine),
        "feature_affine_max_abs_difference_mm": max(affine_differences.values()) if affine_differences else 0.0,
    }
    return outputs, geometry


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
