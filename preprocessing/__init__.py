"""Optional DWI preprocessing workflow for SlicerDDSurfer."""

from .pipeline import (
    DwiPreprocessingConfig,
    DwiPreprocessingResult,
    inspect_preprocessing_backend,
    run_dwi_preprocessing,
)

run_preprocessing_pipeline = run_dwi_preprocessing

__all__ = [
    "DwiPreprocessingConfig",
    "DwiPreprocessingResult",
    "inspect_preprocessing_backend",
    "run_dwi_preprocessing",
    "run_preprocessing_pipeline",
]
