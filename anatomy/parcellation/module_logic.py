"""Parcellation workflow logic glue for SlicerDDSurfer."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from shared import ensure_registered_dti_bundle, find_subject_root

DDPARCEL_PYTHON_REQUIREMENTS: tuple[tuple[str, str], ...] = (
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("nibabel>=5.0", "nibabel"),
    ("pynrrd", "nrrd"),
    ("scikit-image", "skimage"),
    ("h5py", "h5py"),
    ("SimpleITK", "SimpleITK"),
    ("plumbum", "plumbum"),
    ("torchvision", "torchvision"),
)


class ParcellationLogicMixin:
    """Logic entrypoints for the DDParcel workflow."""

    def setupDDParcelRequirements(self) -> None:
        self._ensure_torch_requirements(DDPARCEL_PYTHON_REQUIREMENTS)

    def runDDParcelPipeline(
        self,
        *,
        subject_id: str,
        input_root: Path,
        output_root: Optional[Path],
        atlas_t2: Path,
        flip: int = 1,
    ) -> None:
        from anatomy.parcellation import (
            DDParcelConfig,
            DDParcelRegisteredConfig,
            run_ddparcel,
            run_ddparcel_from_registered_bundle,
        )

        input_root = input_root.expanduser().resolve()
        atlas_t2 = atlas_t2.expanduser().resolve()
        output_root = output_root.expanduser().resolve() if output_root is not None else None

        inspected = self._resolve_subject_input(input_root, subject_id)
        if inspected["mode"] == "subject_root":
            raw_bundle = find_subject_root(input_root, subject_id)
            resolved_output_dir = self._resolve_optional_output_dir(
                output_root,
                subject_root=raw_bundle.subject_root,
                task_name="ddparcel",
            )
            registered = ensure_registered_dti_bundle(
                raw_bundle,
                atlas_t2=atlas_t2,
                fit_method="wls",
                reuse=True,
                log=self.log,
            )
            config = DDParcelRegisteredConfig(
                subject_id=subject_id,
                registered_bundle=registered,
                output_dir=resolved_output_dir,
                native_mask=raw_bundle.mask_path,
                flip=flip,
            )
            run_ddparcel_from_registered_bundle(config, log=self.log)
            return

        if output_root is None:
            raise ValueError("Output root is required for legacy DDParcel inputs.")

        config = DDParcelConfig(
            subject_id=subject_id,
            input_root=input_root,
            output_root=output_root,
            atlas_t2=atlas_t2,
            flip=flip,
        )
        run_ddparcel(config, log=self.log)
