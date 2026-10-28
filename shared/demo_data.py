"""Safe synthetic demo subject helpers for first-run onboarding."""

from __future__ import annotations

import shutil
from pathlib import Path


DEMO_SUBJECT_ID = "slicerdsurfer-demo"


def create_synthetic_demo_subject(root: Path, *, subject_id: str = DEMO_SUBJECT_ID, overwrite: bool = False) -> Path:
    """Create a tiny synthetic DWI subject root with no human subject data.

    The synthetic data is intended for validation, dependency checks, run-plan
    review, and very small DTI-oriented smoke tests. It is not a scientific
    example and should not be used for method evaluation.
    """

    import nibabel as nib
    import numpy as np

    subject_root = root.expanduser().resolve() / subject_id
    input_dir = subject_root / "input"
    if input_dir.exists() and not overwrite:
        return subject_root
    if overwrite:
        for managed_dir in (input_dir, subject_root / "cache", subject_root / "outputs"):
            if managed_dir.exists():
                shutil.rmtree(managed_dir)
    input_dir.mkdir(parents=True, exist_ok=True)

    bvals = np.array([0, 1000, 1000, 1000, 1000, 1000, 1000], dtype=float)
    bvecs = np.array(
        [
            [0, 1, 0, 0, 1 / np.sqrt(2), 1 / np.sqrt(2), 0],
            [0, 0, 1, 0, 1 / np.sqrt(2), 0, 1 / np.sqrt(2)],
            [0, 0, 0, 1, 0, 1 / np.sqrt(2), 1 / np.sqrt(2)],
        ],
        dtype=float,
    )
    tensor = np.diag([0.0015, 0.0003, 0.0003])
    # The principal tensor axis spans enough physical distance to exercise the
    # production 10 mm minimum streamline filter while remaining lightweight.
    data = np.zeros((24, 8, 8, len(bvals)), dtype=np.float32)
    data[..., 0] = 1000.0
    for index, (bval, gradient) in enumerate(zip(bvals[1:], bvecs.T[1:]), start=1):
        attenuation = np.exp(-bval * float(gradient @ tensor @ gradient))
        data[..., index] = 1000.0 * attenuation
    mask = np.ones((24, 8, 8), dtype=np.uint8)

    nib.save(nib.Nifti1Image(data, np.eye(4)), str(input_dir / "data.nii.gz"))
    nib.save(nib.Nifti1Image(mask, np.eye(4)), str(input_dir / "nodif_brain_mask.nii.gz"))
    (input_dir / "bvals").write_text(" ".join(f"{value:g}" for value in bvals) + "\n", encoding="utf-8")
    (input_dir / "bvecs").write_text(
        "\n".join(" ".join(f"{value:.10g}" for value in row) for row in bvecs) + "\n",
        encoding="utf-8",
    )
    (input_dir / "README.txt").write_text(
        "Synthetic SlicerDSpace demo DWI. This is generated test data, not human subject data.\n",
        encoding="utf-8",
    )
    return subject_root
