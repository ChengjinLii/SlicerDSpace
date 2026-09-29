"""World-space QC gate: DDSeg tissue labels versus DDParcel anatomy.

A DDSeg map that is mirrored, shifted or otherwise mis-registered against the
DWI still passes every per-voxel probability check, which is how an
anterior-posterior mirrored segmentation reached ACT unnoticed. This gate
compares DDSeg WM with DDParcel WM *in world space* (DDParcel is resampled into
the DDSeg grid through both affines, never by raw array indexing) and fails
loudly when the overlap is implausibly low.

Measured on HCP 100307 / PPMI 3124: mirrored outputs 0.515 / 0.486, corrected
outputs 0.861 / 0.794. The default hard threshold (0.70) sits between those
bands; the acceptance target used for validation reports is 0.80.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from shared.world_space import dice, resample_nearest_to_grid

WORLD_QC_SCHEMA_VERSION = 1
DEFAULT_MIN_WM_DICE = 0.70
ACCEPTANCE_TARGET_WM_DICE = 0.80
DDPARCEL_WM_LABELS = (2, 41, 7, 46, 16, 28, 60, 77, 251, 252, 253, 254, 255)
DDPARCEL_WM_RANGE = (3000, 5003)  # wmparc WM parcels 3000-4999 plus 5001/5002 unsegmented WM
DDPARCEL_GM_LABELS = (3, 42, 8, 47, 10, 49, 11, 50, 12, 51, 13, 52, 17, 53, 18, 54, 26, 58)
DDPARCEL_GM_RANGE = (1000, 3000)
DDPARCEL_LATERAL_VENTRICLES = (4, 43)


def _file_info(path: Path) -> dict[str, object]:
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        return {"path": resolved.as_posix(), "exists": False}
    stat = resolved.stat()
    return {"path": resolved.resolve().as_posix(), "exists": True, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def ddparcel_tissue_masks(labels: np.ndarray) -> dict[str, np.ndarray]:
    labels = np.asarray(labels)
    wm = np.isin(labels, DDPARCEL_WM_LABELS) | ((labels >= DDPARCEL_WM_RANGE[0]) & (labels < DDPARCEL_WM_RANGE[1]))
    gm = np.isin(labels, DDPARCEL_GM_LABELS) | ((labels >= DDPARCEL_GM_RANGE[0]) & (labels < DDPARCEL_GM_RANGE[1]))
    ventricles = np.isin(labels, DDPARCEL_LATERAL_VENTRICLES)
    return {"wm": wm, "gm": gm, "lateral_ventricles": ventricles}


def compute_world_agreement(
    segmentation: np.ndarray,
    segmentation_affine: np.ndarray,
    parcellation: np.ndarray,
    parcellation_affine: np.ndarray,
    *,
    wm_label: int = 1,
    gm_label: int = 2,
    csf_label: int = 3,
) -> dict[str, Optional[float]]:
    """Overlap metrics between DDSeg labels and DDParcel labels mapped through world space."""

    seg = np.rint(np.asarray(segmentation)).astype(np.int32)
    parc = resample_nearest_to_grid(
        np.rint(np.asarray(parcellation)).astype(np.int32),
        parcellation_affine,
        seg.shape,
        segmentation_affine,
    )
    masks = ddparcel_tissue_masks(parc)
    ventricles = masks["lateral_ventricles"]
    return {
        "wm_dice": dice(seg == wm_label, masks["wm"]),
        "gm_dice": dice(seg == gm_label, masks["gm"]),
        "lateral_ventricle_csf_fraction": float(np.mean(seg[ventricles] == csf_label)) if ventricles.any() else None,
        "ddparcel_wm_voxels": int(masks["wm"].sum()),
        "ddseg_wm_voxels": int((seg == wm_label).sum()),
    }


def evaluate_ddseg_world_qc(
    segmentation_path: Path,
    parcellation_path: Path,
    *,
    min_wm_dice: float = DEFAULT_MIN_WM_DICE,
) -> dict[str, object]:
    import nibabel as nib

    if not 0.0 <= float(min_wm_dice) <= 1.0:
        raise ValueError("min_wm_dice must be within [0, 1].")
    seg_img = nib.load(Path(segmentation_path).as_posix())
    parc_img = nib.load(Path(parcellation_path).as_posix())
    metrics = compute_world_agreement(
        np.asarray(seg_img.dataobj),
        seg_img.affine,
        np.asarray(parc_img.dataobj),
        parc_img.affine,
    )
    passed = float(metrics["wm_dice"] or 0.0) >= float(min_wm_dice)
    return {
        "kind": "ddseg_world_space_qc",
        "schema_version": WORLD_QC_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "passed" if passed else "failed",
        "method": "DDParcel wmparc resampled into the DDSeg grid through both affines (nearest neighbour)",
        "thresholds": {"min_wm_dice": float(min_wm_dice), "acceptance_target_wm_dice": ACCEPTANCE_TARGET_WM_DICE},
        "meets_acceptance_target": float(metrics["wm_dice"] or 0.0) >= ACCEPTANCE_TARGET_WM_DICE,
        "metrics": metrics,
        "inputs": {"segmentation": _file_info(Path(segmentation_path)), "parcellation": _file_info(Path(parcellation_path))},
    }


def write_ddseg_world_qc(
    segmentation_path: Path,
    parcellation_path: Path,
    output_path: Path,
    *,
    min_wm_dice: float = DEFAULT_MIN_WM_DICE,
) -> dict[str, object]:
    record = evaluate_ddseg_world_qc(segmentation_path, parcellation_path, min_wm_dice=min_wm_dice)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    return record
