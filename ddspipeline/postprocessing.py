"""Convert DDSurfer predictions into subject-native STL meshes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

LOGGER = logging.getLogger(__name__)

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover
    np = None  # type: ignore[assignment]
    NUMPY_IMPORT_ERROR = exc
else:
    NUMPY_IMPORT_ERROR = None

try:
    import SimpleITK as sitk
except ImportError as exc:  # pragma: no cover
    sitk = None  # type: ignore[assignment]
    ITK_IMPORT_ERROR = exc
else:
    ITK_IMPORT_ERROR = None

try:
    import trimesh
except ImportError as exc:  # pragma: no cover
    trimesh = None  # type: ignore[assignment]
    TRIMESH_IMPORT_ERROR = exc
else:
    TRIMESH_IMPORT_ERROR = None

from .prediction import PredictionResult


@dataclass(frozen=True)
class PostprocessingConfig:
    subject_id: str
    transform_path: Path
    predictions_root: Path


def _ensure_imports_ready() -> None:
    if NUMPY_IMPORT_ERROR is not None:
        raise RuntimeError("NumPy is required for DDSurfer post-processing.") from NUMPY_IMPORT_ERROR
    if ITK_IMPORT_ERROR is not None:
        raise RuntimeError("SimpleITK is required for DDSurfer post-processing.") from ITK_IMPORT_ERROR
    if TRIMESH_IMPORT_ERROR is not None:
        raise RuntimeError("trimesh is required for DDSurfer post-processing.") from TRIMESH_IMPORT_ERROR


def _flip_lps_to_ras(vertices: np.ndarray) -> np.ndarray:
    return vertices * np.array([-1.0, -1.0, 1.0], dtype=np.float64)


def _flip_ras_to_lps(vertices: np.ndarray) -> np.ndarray:
    return vertices * np.array([-1.0, -1.0, 1.0], dtype=np.float64)


def _apply_transform(mesh: trimesh.Trimesh, transform_path: Path) -> np.ndarray:
    transform = sitk.ReadTransform(str(transform_path))
    vertices_ras = _flip_lps_to_ras(mesh.vertices.astype(np.float64))
    transformed = np.asarray(
        [transform.TransformPoint(tuple(vertex)) for vertex in vertices_ras],
        dtype=np.float64,
    )
    return transformed


def convert_meshes_to_native_space(
    config: PostprocessingConfig,
    predictions: Iterable[PredictionResult],
) -> Dict[str, List[Path]]:
    """Convert predicted OBJ meshes into native-space STL files."""

    _ensure_imports_ready()

    subject = config.subject_id
    native_dir = config.predictions_root / "native" / subject
    native_dir.mkdir(parents=True, exist_ok=True)

    outputs: Dict[str, List[Path]] = {}
    hemi_short = {"left": "lh", "right": "rh"}

    for result in predictions:
        meshes_to_process = {"wm": result.wm_mesh_path}
        if result.pial_mesh_path is not None:
            meshes_to_process["pial"] = result.pial_mesh_path

        for surface, mesh_path in meshes_to_process.items():
            if not mesh_path.exists():
                LOGGER.warning("Predicted mesh missing for %s (%s)", surface, mesh_path)
                continue

            LOGGER.info(
                "Transforming %s hemisphere %s surface for subject %s",
                result.hemisphere,
                surface,
                subject,
            )
            mesh_lps = trimesh.load(mesh_path.as_posix(), process=False)
            transformed_ras = _apply_transform(mesh_lps, config.transform_path)

            mesh_ras = trimesh.Trimesh(vertices=transformed_ras, faces=mesh_lps.faces, process=False)
            ras_path = native_dir / f"{subject}_predicted_{surface}_{hemi_short[result.hemisphere]}.stl"
            mesh_ras.export(ras_path.as_posix())

            mesh_lps_out = trimesh.Trimesh(
                vertices=_flip_ras_to_lps(transformed_ras),
                faces=mesh_lps.faces,
                process=False,
            )
            lps_path = native_dir / f"{subject}_predicted_{surface}_{hemi_short[result.hemisphere]}_orig.stl"
            mesh_lps_out.export(lps_path.as_posix())

            outputs.setdefault(surface, []).extend([ras_path, lps_path])

    return outputs
