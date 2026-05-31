"""ACT preparation helpers for deriving simple 5TT/GMWMI from tissue labels."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass(frozen=True)
class ACTPrepConfig:
    subject_id: str
    segmentation_path: Path
    output_dir: Path
    wm_label: int = 1
    gm_label: int = 2
    csf_label: int = 3
    execute: bool = False


@dataclass(frozen=True)
class ACTPrepResult:
    subject_id: str
    output_dir: Path
    five_tt_path: Path
    gmwmi_path: Path
    manifest_path: Path
    qc_path: Path
    executed: bool


def _file_info(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": path.as_posix(), "exists": False}
    stat = path.stat()
    return {
        "path": path.resolve().as_posix(),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _binary_dilation(mask):
    try:
        from scipy.ndimage import binary_dilation

        return binary_dilation(mask)
    except Exception:  # pragma: no cover - scipy unavailable fallback
        import numpy as np

        padded = np.pad(mask, 1, mode="constant", constant_values=False)
        out = np.zeros_like(mask, dtype=bool)
        for dx, dy, dz in (
            (1, 0, 0),
            (-1, 0, 0),
            (0, 1, 0),
            (0, -1, 0),
            (0, 0, 1),
            (0, 0, -1),
        ):
            xs = slice(1 + dx, 1 + dx + mask.shape[0])
            ys = slice(1 + dy, 1 + dy + mask.shape[1])
            zs = slice(1 + dz, 1 + dz + mask.shape[2])
            out |= padded[xs, ys, zs]
        return out


def run_act_prep(config: ACTPrepConfig, *, log: Optional[Callable[[str], None]] = None) -> ACTPrepResult:
    if not config.subject_id.strip():
        raise ValueError("subject_id is required.")
    segmentation_path = config.segmentation_path.expanduser().resolve()
    if not segmentation_path.is_file():
        raise FileNotFoundError(f"Tissue segmentation not found: {segmentation_path}")

    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    five_tt_path = output_dir / f"{config.subject_id}_5tt_from_labels.nii.gz"
    gmwmi_path = output_dir / f"{config.subject_id}_gmwmi_from_labels.nii.gz"
    manifest_path = output_dir / "act_prep_manifest.json"
    qc_path = output_dir / "act_prep_qc.json"

    manifest = {
        "kind": "act_prep",
        "version": 1,
        "subject_id": config.subject_id,
        "executed": bool(config.execute),
        "status": "planned" if not config.execute else "running",
        "labels": {"wm": config.wm_label, "gm": config.gm_label, "csf": config.csf_label},
        "inputs": {"segmentation": _file_info(segmentation_path)},
        "outputs": {"five_tt": five_tt_path.as_posix(), "gmwmi": gmwmi_path.as_posix(), "qc": qc_path.as_posix()},
        "limitations": [
            "This is a simple 5TT approximation from WM/GM/CSF labels, not a full FreeSurfer/5ttgen tissue model.",
            "Subcortical GM is not separated from cortical GM.",
        ],
    }

    qc: dict[str, object] = {
        "kind": "act_prep_qc",
        "version": 1,
        "subject_id": config.subject_id,
        "status": "planned",
        "executed": bool(config.execute),
    }

    if config.execute:
        try:
            import nibabel as nib
            import numpy as np
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("ACT prep requires nibabel and numpy.") from exc

        img = nib.load(segmentation_path.as_posix())
        labels = img.get_fdata().astype(int)
        wm = labels == int(config.wm_label)
        gm = labels == int(config.gm_label)
        csf = labels == int(config.csf_label)
        five_tt = np.zeros((*labels.shape, 5), dtype=np.float32)
        five_tt[..., 0] = gm.astype(np.float32)
        five_tt[..., 2] = wm.astype(np.float32)
        five_tt[..., 3] = csf.astype(np.float32)
        gmwmi = (gm & _binary_dilation(wm)) | (wm & _binary_dilation(gm))

        header = img.header.copy()
        header.set_data_dtype(np.float32)
        nib.save(nib.Nifti1Image(five_tt, img.affine, header), five_tt_path.as_posix())
        nib.save(nib.Nifti1Image(gmwmi.astype(np.float32), img.affine, header), gmwmi_path.as_posix())
        qc.update(
            {
                "status": "completed",
                "wm_voxels": int(wm.sum()),
                "gm_voxels": int(gm.sum()),
                "csf_voxels": int(csf.sum()),
                "gmwmi_voxels": int(gmwmi.sum()),
            }
        )
        manifest["status"] = "completed"

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    qc_path.write_text(json.dumps(qc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if log:
        log(f"[ACT Prep] Manifest: {manifest_path}")
    return ACTPrepResult(
        subject_id=config.subject_id,
        output_dir=output_dir,
        five_tt_path=five_tt_path,
        gmwmi_path=gmwmi_path,
        manifest_path=manifest_path,
        qc_path=qc_path,
        executed=bool(config.execute),
    )
