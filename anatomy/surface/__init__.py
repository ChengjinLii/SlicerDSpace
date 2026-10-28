"""Surface workflow package for SlicerDSpace.

This package is imported by the Slicer GUI at module discovery time. Keep heavy
model dependencies, especially torch/CUDA, out of import-time code paths.
"""

from __future__ import annotations

PLANNED_EXPORTS = {
    "SubjectPreprocessingConfig",
    "SubjectPreprocessingResult",
    "preprocess_subject",
    "PredictionStageConfig",
    "SurfacePredictor",
    "discover_subject_directories",
    "predict_subject",
    "PostprocessingConfig",
    "convert_meshes_to_native_space",
    "SurfacePreprocessingConfig",
    "SurfacePredictionConfig",
    "SurfacePostprocessingConfig",
    "run_surface_preprocessing",
    "run_surface_prediction",
    "run_surface_postprocessing",
    "SurfaceConfig",
    "SurfaceResult",
    "inspect_surface_resources",
    "run_surface",
    "DDSurferPostprocessConfig",
    "DDSurferPostprocessResult",
    "run_ddsurfer_postprocess",
}

__all__ = sorted(PLANNED_EXPORTS)


def __getattr__(name: str):
    if name in {
        "SubjectPreprocessingConfig",
        "SubjectPreprocessingResult",
        "preprocess_subject",
        "SurfacePreprocessingConfig",
        "run_surface_preprocessing",
    }:
        from .preprocessing import SubjectPreprocessingConfig, SubjectPreprocessingResult, preprocess_subject

        namespace = {
            "SubjectPreprocessingConfig": SubjectPreprocessingConfig,
            "SubjectPreprocessingResult": SubjectPreprocessingResult,
            "preprocess_subject": preprocess_subject,
            "SurfacePreprocessingConfig": SubjectPreprocessingConfig,
            "run_surface_preprocessing": preprocess_subject,
        }
        return namespace[name]

    if name in {
        "PredictionStageConfig",
        "SurfacePredictor",
        "discover_subject_directories",
        "predict_subject",
        "SurfacePredictionConfig",
        "run_surface_prediction",
    }:
        from .prediction import PredictionStageConfig, SurfacePredictor, discover_subject_directories, predict_subject

        namespace = {
            "PredictionStageConfig": PredictionStageConfig,
            "SurfacePredictor": SurfacePredictor,
            "discover_subject_directories": discover_subject_directories,
            "predict_subject": predict_subject,
            "SurfacePredictionConfig": PredictionStageConfig,
            "run_surface_prediction": predict_subject,
        }
        return namespace[name]

    if name in {
        "PostprocessingConfig",
        "convert_meshes_to_native_space",
        "SurfacePostprocessingConfig",
        "run_surface_postprocessing",
    }:
        from .postprocessing import PostprocessingConfig, convert_meshes_to_native_space

        namespace = {
            "PostprocessingConfig": PostprocessingConfig,
            "convert_meshes_to_native_space": convert_meshes_to_native_space,
            "SurfacePostprocessingConfig": PostprocessingConfig,
            "run_surface_postprocessing": convert_meshes_to_native_space,
        }
        return namespace[name]

    if name in {"SurfaceConfig", "SurfaceResult", "inspect_surface_resources", "run_surface"}:
        from .pipeline import SurfaceConfig, SurfaceResult, inspect_surface_resources, run_surface

        namespace = {
            "SurfaceConfig": SurfaceConfig,
            "SurfaceResult": SurfaceResult,
            "inspect_surface_resources": inspect_surface_resources,
            "run_surface": run_surface,
        }
        return namespace[name]

    if name in {"DDSurferPostprocessConfig", "DDSurferPostprocessResult", "run_ddsurfer_postprocess"}:
        from .postprocess_release import DDSurferPostprocessConfig, DDSurferPostprocessResult, run_ddsurfer_postprocess

        namespace = {
            "DDSurferPostprocessConfig": DDSurferPostprocessConfig,
            "DDSurferPostprocessResult": DDSurferPostprocessResult,
            "run_ddsurfer_postprocess": run_ddsurfer_postprocess,
        }
        return namespace[name]

    raise AttributeError(name)
