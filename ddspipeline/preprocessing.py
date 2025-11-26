"""Subject-level preprocessing for the DDSurfer Slicer module."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

LOGGER = logging.getLogger(__name__)

try:
    import nibabel as nib
    import numpy as np
except ImportError as exc:  # pragma: no cover - handled at runtime inside Slicer
    nib = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

try:
    import SimpleITK as sitk
except ImportError as exc:  # pragma: no cover
    sitk = None  # type: ignore[assignment]
    ITK_IMPORT_ERROR = exc
else:
    ITK_IMPORT_ERROR = None


METRIC_OUTPUT_SUFFIX = {
    "FractionalAnisotropy": "FA",
    "MinEigenvalue": "MinEigenvalue",
    "MidEigenvalue": "MidEigenvalue",
    "MaxEigenvalue": "MaxEigenvalue",
    "Trace": "Trace",
    "MeanDiffusivity": "MD",
}


@dataclass(frozen=True)
class SubjectPreprocessingConfig:
    """Container for preprocessing inputs."""

    subject_id: str
    metric_paths: Dict[str, Path]
    mask_path: Path
    transform_path: Path
    work_dir: Path
    template_volume_path: Path


@dataclass(frozen=True)
class SubjectPreprocessingResult:
    """Summary of preprocessing outputs."""

    subject_id: str
    raw_dir: Path
    preprocessed_dir: Path
    resampled_mask_path: Path
    transform_copy_path: Path


def _ensure_imports_ready() -> None:
    if IMPORT_ERROR is not None:
        raise RuntimeError(
            "Nibabel and NumPy are required for preprocessing. "
            "Please install them in the Slicer Python environment."
        ) from IMPORT_ERROR
    if ITK_IMPORT_ERROR is not None:
        raise RuntimeError(
            "SimpleITK is required for preprocessing. "
            "Please install it in the Slicer Python environment."
        ) from ITK_IMPORT_ERROR


def _copy_if_needed(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dest.resolve():
        LOGGER.debug("Source and destination identical, skipping copy: %s", src)
        return
    LOGGER.debug("Copying %s -> %s", src, dest)
    shutil.copy2(src, dest)


def _skull_strip(source: Path, mask: Path, dest: Path) -> None:
    LOGGER.debug("Skull stripping %s using mask %s", source.name, mask.name)

    volume_img = nib.load(str(source))
    mask_img = nib.load(str(mask))

    volume_data = volume_img.get_fdata(dtype=np.float32)
    mask_data = mask_img.get_fdata().astype(bool)

    if mask_data.shape != volume_data.shape:
        raise ValueError(
            f"Mask shape {mask_data.shape} does not match volume shape {volume_data.shape} "
            f"for {source.name}"
        )

    stripped = np.where(mask_data, volume_data, 0.0)
    out_img = nib.Nifti1Image(stripped, volume_img.affine, volume_img.header)
    out_img.set_data_dtype(np.float32)
    dest.parent.mkdir(parents=True, exist_ok=True)
    nib.save(out_img, str(dest))


def _resample_to_template(source: Path, template: Path, dest: Path) -> None:
    LOGGER.debug("Resampling %s into template space -> %s", source.name, dest.name)
    moving = sitk.ReadImage(str(source))
    fixed = sitk.ReadImage(str(template))

    resampler = sitk.ResampleImageFilter()
    resampler.SetReferenceImage(fixed)
    resampler.SetInterpolator(sitk.sitkLinear)

    resampled = resampler.Execute(moving)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(resampled, str(dest))


def _zscore_inplace(volume_path: Path, mask_path: Path | None) -> None:
    LOGGER.debug("Z-score normalising %s", volume_path.name)
    img = nib.load(str(volume_path))
    data = img.get_fdata(dtype=np.float32)

    if mask_path is not None and mask_path.exists():
        mask = nib.load(str(mask_path)).get_fdata().astype(bool)
        if mask.shape != data.shape:
            raise ValueError(
                f"Resampled mask shape {mask.shape} does not match volume shape {data.shape}"
            )
        values = data[mask]
    else:
        mask = None
        values = data[np.isfinite(data)]

    if values.size == 0:
        raise ValueError(f"No valid voxels found when computing statistics for {volume_path.name}")

    mean = float(np.mean(values))
    std = float(np.std(values))
    if std < 1e-6:
        LOGGER.warning("Standard deviation extremely small (%.3e); clamping to 1e-6", std)
        std = 1e-6

    data = (data - mean) / std
    if mask is not None:
        data[~mask] = 0.0

    out_img = nib.Nifti1Image(data.astype(np.float32), img.affine, img.header)
    out_img.set_data_dtype(np.float32)
    nib.save(out_img, str(volume_path))


def preprocess_subject(config: SubjectPreprocessingConfig) -> SubjectPreprocessingResult:
    """Run skull stripping, resampling, and z-scoring for a single subject."""

    _ensure_imports_ready()

    subject = config.subject_id
    LOGGER.info("Starting preprocessing for subject %s", subject)

    raw_dir = config.work_dir / "raw" / subject
    preprocessed_dir = config.work_dir / "preprocessed" / subject
    raw_dir.mkdir(parents=True, exist_ok=True)
    preprocessed_dir.mkdir(parents=True, exist_ok=True)

    transform_copy_path = preprocessed_dir / f"{subject}-b0ToAtlasT2.tfm"
    _copy_if_needed(config.transform_path, transform_copy_path)

    mask_copy_path = raw_dir / f"{subject}-mask-Reg.nii.gz"
    _copy_if_needed(config.mask_path, mask_copy_path)

    masked_cache: Dict[str, Path] = {}

    for metric_key, source_path in config.metric_paths.items():
        if metric_key not in METRIC_OUTPUT_SUFFIX:
            raise ValueError(f"Unexpected metric key '{metric_key}'")

        raw_name = f"{subject}-dti-{metric_key}-Reg.nii.gz"
        masked_name = f"{subject}-dti-{metric_key}-Reg-masked.nii.gz"

        raw_path = raw_dir / raw_name
        masked_path = raw_dir / masked_name

        _copy_if_needed(source_path, raw_path)
        _skull_strip(raw_path, mask_copy_path, masked_path)
        masked_cache[metric_key] = masked_path

    resampled_mask_path = preprocessed_dir / f"{subject}-brainmask_resampled.nii.gz"
    _resample_to_template(mask_copy_path, config.template_volume_path, resampled_mask_path)

    for metric_key, masked_path in masked_cache.items():
        suffix = METRIC_OUTPUT_SUFFIX[metric_key]
        resampled_path = preprocessed_dir / f"{subject}-{suffix}.nii.gz"
        _resample_to_template(masked_path, config.template_volume_path, resampled_path)
        _zscore_inplace(resampled_path, resampled_mask_path)

    LOGGER.info("Preprocessing finished for subject %s", subject)

    return SubjectPreprocessingResult(
        subject_id=subject,
        raw_dir=raw_dir,
        preprocessed_dir=preprocessed_dir,
        resampled_mask_path=resampled_mask_path,
        transform_copy_path=transform_copy_path,
    )
