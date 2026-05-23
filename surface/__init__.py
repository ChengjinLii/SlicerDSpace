"""Surface workflow package for SlicerDDSurfer."""

from __future__ import annotations

from .preprocessing import preprocess_subject, SubjectPreprocessingConfig, SubjectPreprocessingResult
from .prediction import (
    PredictionStageConfig,
    SurfacePredictor,
    discover_subject_directories,
    predict_subject,
)
from .postprocessing import (
    PostprocessingConfig,
    convert_meshes_to_native_space,
)

__all__ = [
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
    "SurfaceSculptorWidget",
]

SurfacePreprocessingConfig = SubjectPreprocessingConfig
SurfacePredictionConfig = PredictionStageConfig
SurfacePostprocessingConfig = PostprocessingConfig
run_surface_preprocessing = preprocess_subject
run_surface_prediction = predict_subject
run_surface_postprocessing = convert_meshes_to_native_space


def __getattr__(name):
    if name == "SurfaceSculptorWidget":
        from .sculpting.surface_sculptor import SurfaceSculptorWidget

        return SurfaceSculptorWidget
    raise AttributeError(name)
