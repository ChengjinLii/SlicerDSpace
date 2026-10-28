"""Segmentation workflow package for SlicerDSpace."""

__all__ = [
    "DDSegConfig",
    "SegmentationConfig",
    "run_ddseg",
    "run_segmentation",
]


def __getattr__(name):
    if name in __all__:
        from .config import DDSegConfig
        from .pipeline import run_ddseg

        namespace = {
            "DDSegConfig": DDSegConfig,
            "SegmentationConfig": DDSegConfig,
            "run_ddseg": run_ddseg,
            "run_segmentation": run_ddseg,
        }
        return namespace[name]
    raise AttributeError(name)
