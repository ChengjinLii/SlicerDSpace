"\"\"\"Surface prediction utilities for DDSurfer.\"\"\""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

LOGGER = logging.getLogger(__name__)

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover
    np = None  # type: ignore[assignment]
    NUMPY_IMPORT_ERROR = exc
else:
    NUMPY_IMPORT_ERROR = None

try:
    import torch
except ImportError as exc:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    TORCH_IMPORT_ERROR = exc
else:
    TORCH_IMPORT_ERROR = None

try:
    import nibabel as nib
except ImportError as exc:  # pragma: no cover
    nib = None  # type: ignore[assignment]
    NIBABEL_IMPORT_ERROR = exc
else:
    NIBABEL_IMPORT_ERROR = None

try:
    import trimesh
except ImportError as exc:  # pragma: no cover
    trimesh = None  # type: ignore[assignment]
    TRIMESH_IMPORT_ERROR = exc
else:
    TRIMESH_IMPORT_ERROR = None

try:
    from .networks.tanet import TANet
except Exception as exc:  # pragma: no cover - handled at runtime
    TANet = None  # type: ignore[assignment]
    TANET_IMPORT_ERROR = exc
else:
    TANET_IMPORT_ERROR = None


VOLUME_MODALITIES: Sequence[str] = (
    "FA",
    "MidEigenvalue",
    "MinEigenvalue",
    "MaxEigenvalue",
    "MD",
)


@dataclass(frozen=True)
class PredictionStageConfig:
    """Model configuration for a single hemisphere."""

    subject_id: str
    hemisphere: str
    predict_mode: str
    device: str
    step_size: float
    n_svf: int
    n_res: int
    template_dir: Path
    checkpoint_root: Path
    input_root: Path
    output_root: Path


@dataclass(frozen=True)
class PredictionResult:
    """Records mesh files generated during prediction."""

    subject_id: str
    hemisphere: str
    wm_mesh_path: Path
    pial_mesh_path: Path | None


def _ensure_imports_ready() -> None:
    if NUMPY_IMPORT_ERROR is not None:
        raise RuntimeError("NumPy is required for DDSurfer prediction.") from NUMPY_IMPORT_ERROR
    if TORCH_IMPORT_ERROR is not None:
        raise RuntimeError("PyTorch is required for DDSurfer prediction.") from TORCH_IMPORT_ERROR
    if NIBABEL_IMPORT_ERROR is not None:
        raise RuntimeError("Nibabel is required for DDSurfer prediction.") from NIBABEL_IMPORT_ERROR
    if TRIMESH_IMPORT_ERROR is not None:
        raise RuntimeError("trimesh is required for DDSurfer prediction.") from TRIMESH_IMPORT_ERROR
    if TANET_IMPORT_ERROR is not None:
        raise RuntimeError("DDSurfer neural network definition could not be imported.") from TANET_IMPORT_ERROR


def _taubin_smooth(
    vertices: torch.Tensor,
    faces: torch.Tensor,
    *,
    n_iters: int = 10,
    lambd: float = 0.5,
    mu: float = -0.53,
) -> torch.Tensor:
    """Apply Taubin smoothing using the degree-normalised graph Laplacian."""

    def _normalised_laplacian(face_tensor: torch.Tensor) -> torch.Tensor:
        nv = int(face_tensor.max()) + 1
        edges = torch.cat(
            [
                face_tensor[:, [0, 1]],
                face_tensor[:, [1, 2]],
                face_tensor[:, [2, 0]],
            ],
            dim=0,
        ).t()

        weights = torch.ones(edges.shape[1], device=face_tensor.device, dtype=torch.float32)
        adjacency = torch.sparse_coo_tensor(edges, weights, size=(nv, nv))
        degree = torch.sparse.sum(adjacency, dim=1).to_dense().clamp_min_(1.0)

        normalised_weights = weights / degree[edges[0]]
        adjacency_norm = torch.sparse_coo_tensor(edges, normalised_weights, size=(nv, nv))

        diag_idx = torch.arange(nv, device=face_tensor.device)
        identity = torch.sparse_coo_tensor(
            torch.stack([diag_idx, diag_idx]),
            torch.ones(nv, device=face_tensor.device, dtype=torch.float32),
            size=(nv, nv),
        )
        return (identity - adjacency_norm).coalesce()

    laplacian = _normalised_laplacian(faces[0])
    for _ in range(n_iters):
        delta = torch.sparse.mm(laplacian, vertices[0]).unsqueeze(0)
        vertices = vertices - mu * delta
        delta = torch.sparse.mm(laplacian, vertices[0]).unsqueeze(0)
        vertices = vertices - lambd * delta
    return vertices


class SurfacePredictor:
    """Wraps the DDSurfer TANet model for inference."""

    def __init__(self, cfg: PredictionStageConfig) -> None:
        _ensure_imports_ready()

        self.cfg = cfg
        self.device = torch.device(cfg.device)

        self.template_mesh_path = cfg.template_dir / f"hcp_hemi-{cfg.hemisphere}_init_160k.obj"
        LOGGER.info("Loading template mesh: %s", self.template_mesh_path)
        mesh_init = trimesh.load(self.template_mesh_path.as_posix(), process=False)
        vertices = mesh_init.vertices
        if cfg.hemisphere == "right":
            vertices = vertices.copy()
            vertices[:, 0] -= 64.0
        self.vert_init = vertices
        self.face_init = mesh_init.faces

        self.wm_model = self._load_model("white")
        self.pial_model = self._load_model("pial") if cfg.predict_mode == "all" else None

    def _checkpoint_path(self, surface: str) -> Path:
        suffix = "lh" if self.cfg.hemisphere == "left" else "rh"
        return self.cfg.checkpoint_root / "hcp" / f"DDCSR_{surface}_{suffix}_Full_DualStream_no_b0_Cascaded.pt"

    def _load_model(self, surface: str) -> TANet:
        LOGGER.info("Loading %s surface network for hemisphere %s", surface, self.cfg.hemisphere)
        if surface == "pial":
            hidden = [16, 32, 32, 32, 32]
        else:
            hidden = [16, 32, 64, 128, 256]

        model = TANet(
            C_in=5,
            C_hid=hidden,
            inshape=[112, 224, 176],
            step_size=self.cfg.step_size,
            M=self.cfg.n_svf,
            R=self.cfg.n_res,
            device=self.device,
        )

        ckpt_path = self._checkpoint_path(surface)
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Model checkpoint not found: {ckpt_path}")

        state_dict = torch.load(ckpt_path, map_location=self.device)
        model.load_state_dict(state_dict)
        model.to(self.device)
        model.eval()
        return model

    @property
    def translation_vector(self) -> np.ndarray:
        if self.cfg.hemisphere == "right":
            return np.array([21.0, 132.0, 70.0], dtype=np.float32)
        return np.array([85.0, 132.0, 70.0], dtype=np.float32)

    @property
    def x_slice(self) -> slice:
        if self.cfg.hemisphere == "left":
            return slice(0, 112)
        if self.cfg.hemisphere == "right":
            return slice(64, None)
        raise ValueError(f"Unsupported hemisphere '{self.cfg.hemisphere}'")

    def _load_subject_volumes(self, subject_dir: Path) -> torch.Tensor:
        volumes: List[np.ndarray] = []
        for modality in VOLUME_MODALITIES:
            volume_path = subject_dir / f"{subject_dir.name}-{modality}.nii.gz"
            if not volume_path.exists():
                raise FileNotFoundError(f"Missing modality '{modality}' at {volume_path}")
            data = nib.load(volume_path.as_posix()).get_fdata()
            data = data[self.x_slice, :, :]
            volumes.append(data)

        stacked = np.stack(volumes, axis=0).astype(np.float32)
        return torch.from_numpy(stacked).unsqueeze(0).to(self.device)

    def predict(self, subject_dir: Path) -> PredictionResult:
        LOGGER.info(
            "Predicting %s hemisphere for subject %s",
            self.cfg.hemisphere,
            subject_dir.name,
        )

        volumes = self._load_subject_volumes(subject_dir)
        vertices_init = torch.tensor(self.vert_init[None], device=self.device, dtype=torch.float32)
        faces = torch.tensor(self.face_init[None], device=self.device, dtype=torch.long)

        with torch.no_grad():
            vertices_wm = self.wm_model(vertices_init, volumes)
            vertices_wm = _taubin_smooth(vertices_wm, faces, n_iters=10)
            verts_wm_np = vertices_wm[0].cpu().numpy()

            verts_pial_np = None
            if self.cfg.predict_mode == "all":
                if self.pial_model is None:
                    raise RuntimeError("Pial model requested but not loaded.")
                wm_tensor = torch.tensor(verts_wm_np[None], device=self.device, dtype=torch.float32)
                vertices_pial = self.pial_model(wm_tensor, volumes)
                verts_pial_np = vertices_pial[0].cpu().numpy()

        translation = self.translation_vector

        mni_dir = self.cfg.output_root / "mni" / subject_dir.name
        mni_dir.mkdir(parents=True, exist_ok=True)

        transformed_wm = verts_wm_np - translation
        mesh_wm = trimesh.Trimesh(vertices=transformed_wm, faces=self.face_init, process=False)
        wm_path = mni_dir / f"{subject_dir.name}_predicted_wm_surface_{self.cfg.hemisphere}.obj"
        mesh_wm.export(wm_path.as_posix())

        pial_path = None
        if self.cfg.predict_mode == "all" and verts_pial_np is not None:
            transformed_pial = verts_pial_np - translation
            mesh_pial = trimesh.Trimesh(vertices=transformed_pial, faces=self.face_init, process=False)
            pial_path = mni_dir / f"{subject_dir.name}_predicted_pial_surface_{self.cfg.hemisphere}.obj"
            mesh_pial.export(pial_path.as_posix())

        return PredictionResult(
            subject_id=subject_dir.name,
            hemisphere=self.cfg.hemisphere,
            wm_mesh_path=wm_path,
            pial_mesh_path=pial_path,
        )


def discover_subject_directories(input_root: Path, subjects: Iterable[str]) -> Dict[str, Path]:
    """Resolve subject identifiers to directories."""
    resolved: Dict[str, Path] = {}
    for subject in subjects:
        subject_dir = input_root / subject
        if subject_dir.is_dir():
            resolved[subject] = subject_dir
        else:
            LOGGER.warning("Preprocessed directory missing: %s", subject_dir)
    return resolved


def predict_subject(config: PredictionStageConfig) -> PredictionResult:
    """Run DDSurfer prediction for a single hemisphere."""
    predictor = SurfacePredictor(config)
    subject_dir = config.input_root / config.subject_id
    if not subject_dir.is_dir():
        raise FileNotFoundError(f"Preprocessed subject directory not found: {subject_dir}")
    return predictor.predict(subject_dir)
