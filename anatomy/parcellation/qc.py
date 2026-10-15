"""Decoded DDParcel output QC; integrity is not anatomical accuracy."""

import json
from pathlib import Path


def validate_outputs(subject_id: str, output_dir: Path, native_mask: Path) -> dict:
    import nibabel as nib
    import numpy as np
    from microstructure.pipeline import _file_signature, _write_json

    output_dir = Path(output_dir)
    qc_path = output_dir / "ddparcel_qc.json"
    paths = [output_dir / f"{subject_id}-DDSurfer-wmparc.nii.gz",
             output_dir / f"{subject_id}-DDSurfer-wmparc-Reg.mgz"]
    paths.extend(output_dir / f"{subject_id}-dti-{metric}-Reg-NormMasked.nii.gz"
                 for metric in ("FractionalAnisotropy", "Trace", "MinEigenvalue", "MidEigenvalue"))
    _write_json(qc_path, {"status": "running", "automatic_qc_passed": False})
    try:
        images = [nib.load(str(path)) for path in paths]
        arrays = [np.asarray(image.dataobj) for image in images]
        mask_img = nib.load(str(native_mask))
        mask_data = np.asarray(mask_img.dataobj)
        mask = mask_data > 0
        native = arrays[0]
        grid = native.shape == mask.shape and np.allclose(images[0].affine, mask_img.affine, rtol=0, atol=1e-4)
        checks = {
            "finite_nonempty_brain_mask": bool(np.isfinite(mask_data).all() and mask.any()),
            "all_products_decoded_finite_3d": all(array.ndim == 3 and bool(np.isfinite(array).all()) for array in arrays),
            "native_grid_matches_mask": bool(grid),
            "integer_nonnegative_labels": all(bool(np.all((array >= 0) & (array == np.floor(array)))) for array in arrays[:2]),
            "nonempty_labels_in_brain": bool(grid and np.any(native[mask] > 0)),
            "nonempty_registered_labels": bool(np.any(arrays[1] > 0)),
        }
        payload = {"kind": "ddparcel_output_qc", "version": 1, "subject_id": subject_id,
                   "status": "completed" if all(checks.values()) else "failed",
                   "automatic_qc_passed": all(checks.values()), "human_review": "pending",
                   "checks": checks, "source_signature": {"native_mask": _file_signature(Path(native_mask))},
                   "output_artifacts": {str(path.resolve()): _file_signature(path) for path in paths},
                   "label_ids": [int(value) for value in np.unique(native) if np.isfinite(value)],
                   "warnings": ["Decoded geometry/label integrity only. Atlas coverage and anatomical accuracy require independent review."]}
        _write_json(qc_path, payload)
        if not payload["automatic_qc_passed"]:
            raise ValueError("DDParcel output QC failed: " + ", ".join(key for key, value in checks.items() if not value))
        return payload
    except Exception as exc:
        if not qc_path.is_file() or json.loads(qc_path.read_text()).get("status") != "failed":
            _write_json(qc_path, {"kind": "ddparcel_output_qc", "status": "failed",
                                  "automatic_qc_passed": False, "subject_id": subject_id, "error": str(exc)})
        raise
