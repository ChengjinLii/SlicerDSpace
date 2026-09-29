from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Optional

import numpy as np

from .config import DDSegConfig
from .orientation import MODEL_INPUT_AXCODES, ORIENTATION_CONVENTION


DDSEG_PROBABILITY_SEMANTICS = "four_class_softmax_tissue_channels_v1"
# Schema 2: outputs are written on the brain mask's own voxel grid/affine after
# affine-based reorientation to the model's RAS input order (schema 1 outputs
# were mirrored anterior-posterior and must not be reused on --resume).
DDSEG_QC_SCHEMA_VERSION = 2


def write_ddseg_qc_record(
    cfg: DDSegConfig,
    *,
    labels: np.ndarray,
    probability_maps: np.ndarray,
    outputs: dict[str, Path],
    geometry: Optional[dict[str, object]] = None,
) -> None:
    if labels.ndim != 3 or probability_maps.shape != (*labels.shape, 4):
        raise ValueError(
            "DDSeg QC expects a 3D label map and a matching four-class probability volume; "
            f"got labels={labels.shape}, probabilities={probability_maps.shape}"
        )
    tissue_probabilities = np.stack(
        [probability_maps[..., 2], probability_maps[..., 1], probability_maps[..., 3]],
        axis=-1,
    )
    foreground = labels > 0
    foreground_mass = tissue_probabilities.sum(axis=-1)[foreground]
    finite_and_bounded = all(
        np.isfinite(array).all() and float(np.min(array)) >= -1e-6 and float(np.max(array)) <= 1.0 + 1e-6
        for array in np.moveaxis(tissue_probabilities, -1, 0)
    )
    valid_mass_fraction = (
        float(
            np.mean(
                np.isfinite(foreground_mass)
                & (foreground_mass > 0.0)
                & (foreground_mass <= 1.0 + 1e-5)
            )
        )
        if foreground_mass.size
        else 0.0
    )
    predicted_labels = np.asarray((2, 1, 3), dtype=np.int16)[
        np.argmax(tissue_probabilities, axis=-1)
    ]
    label_agreement = (
        float(np.mean(predicted_labels[foreground] == labels[foreground]))
        if np.any(foreground)
        else 0.0
    )
    if not finite_and_bounded or valid_mass_fraction < 0.999 or label_agreement < 0.999:
        raise RuntimeError(
            "DDSeg probability QC failed: "
            f"bounded={finite_and_bounded}, mass_fraction={valid_mass_fraction:.6f}, "
            f"label_agreement={label_agreement:.6f}"
        )

    record = {
        "schema_version": DDSEG_QC_SCHEMA_VERSION,
        "status": "completed",
        "orientation_convention": ORIENTATION_CONVENTION,
        "model_input_axcodes": "".join(MODEL_INPUT_AXCODES),
        "geometry": dict(geometry or {}),
        "input_mask": Path(cfg.input_mask_nii).expanduser().resolve().as_posix(),
        "source_dwi": Path(cfg.source_dwi).expanduser().resolve().as_posix() if cfg.source_dwi else None,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "probability_semantics": DDSEG_PROBABILITY_SEMANTICS,
        "label_mapping": {"0": "background", "1": "white_matter", "2": "gray_matter", "3": "csf"},
        "shape": list(labels.shape),
        "foreground_voxels": int(np.count_nonzero(foreground)),
        "device": cfg.device,
        "apply_softmax_per_view": bool(cfg.apply_softmax),
        "probability_qc": {
            "finite_and_bounded": finite_and_bounded,
            "tissue_mass_valid_fraction": valid_mass_fraction,
            "tissue_mass_min": float(np.min(foreground_mass)) if foreground_mass.size else None,
            "tissue_mass_max": float(np.max(foreground_mass)) if foreground_mass.size else None,
            "label_agreement": label_agreement,
        },
        "outputs": {key: path.resolve().as_posix() for key, path in outputs.items()},
    }
    qc_path = cfg.output_folder / "ddseg_qc.json"
    temporary_path = qc_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary_path.replace(qc_path)
