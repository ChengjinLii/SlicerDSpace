"""Common scripted-module logic glue for SlicerDDSurfer."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import slicer

from shared import InputValidationConfig, InputValidationResult, inspect_subject_directory, validate_subject_inputs

LOGGER = logging.getLogger(__name__)

COMMON_PYTHON_REQUIREMENTS: tuple[tuple[str, str], ...] = (
    ("nibabel>=5.0", "nibabel"),
    ("SimpleITK", "SimpleITK"),
    ("trimesh", "trimesh"),
    ("tqdm", "tqdm"),
    ("networkx", "networkx"),
)


def _ensure_torch_via_extension(
    min_version: str = "2.0.0",
    log: Optional[Callable[[str], None]] = None,
):
    """Ensure that PyTorch is available via the official Slicer extension."""

    def _log(message: str) -> None:
        if log:
            try:
                log(message)
            except Exception:  # pragma: no cover
                LOGGER.exception("Failed to forward log message: %s", message)
        else:
            LOGGER.info(message)

    try:
        import PyTorchUtils
    except ModuleNotFoundError as exc:  # pragma: no cover - surfaced at runtime
        raise RuntimeError(
            "PyTorch extension not detected. Please install the 'PyTorch' extension via Extension Manager and restart Slicer."
        ) from exc

    torch_logic = PyTorchUtils.PyTorchUtilsLogic()

    if torch_logic.torchInstalled():
        import torch  # type: ignore[import-not-found]

        _log(f"PyTorch detected (version {torch.__version__})")
        return torch

    _log("PyTorch not found, installing via extension (may take several minutes)...")
    torch = torch_logic.installTorch(
        askConfirmation=False,
        torchVersionRequirement=f">={min_version}",
    )
    if torch is None:  # pragma: no cover - error surfaced at runtime
        raise RuntimeError(
            "PyTorch extension present, but torch installation failed. Please check network and retry in 'PyTorch Util'."
        )
    _log(f"PyTorch installed (version {torch.__version__})")
    return torch


class SharedLogicMixin:
    """Shared non-product-specific helpers for the unified module logic."""

    def _initialize_shared_logic_state(self) -> None:
        self.module_dir = Path(__file__).resolve().parent.parent
        self.segmentation_dir = self.module_dir / "segmentation"
        self._pipeline_modules: Optional[Dict[str, Any]] = None
        self.template_dir = self._resolve_template_dir()
        self.checkpoint_root = self._resolve_checkpoint_root()
        self.template_volume = self.template_dir / "100307-FA.nii.gz"
        self.registration_atlas = self._resolve_registration_atlas()
        self.logCallback = None

    def log(self, message: str) -> None:
        LOGGER.info(message)
        if self.logCallback:
            try:
                self.logCallback(message)
            except Exception:  # pragma: no cover
                LOGGER.exception("Failed to write log message via callback")

    def _ensure_python_packages(self, requirements: tuple[tuple[str, str], ...]) -> None:
        import importlib

        def ensure_package(requirement: str, import_name: Optional[str] = None) -> None:
            module_name = import_name or requirement
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError:
                self.log(f"Installing Python package: {requirement}")
                slicer.util.pip_install(requirement)

        for requirement, import_name in requirements:
            ensure_package(requirement, import_name)

    def _ensure_torch_requirements(self, requirements: tuple[tuple[str, str], ...]) -> None:
        _ensure_torch_via_extension(min_version="2.0.0", log=self.log)
        self._ensure_python_packages(requirements)

    def setupPythonRequirements(self) -> None:
        self._ensure_torch_requirements(COMMON_PYTHON_REQUIREMENTS)

    def _load_pipeline_modules(self) -> Dict[str, Any]:
        if self._pipeline_modules is not None:
            return self._pipeline_modules

        if str(self.module_dir) not in sys.path:
            sys.path.insert(0, str(self.module_dir))

        import importlib

        try:
            preprocessing = importlib.import_module("surface.preprocessing")
            prediction = importlib.import_module("surface.prediction")
            postprocessing = importlib.import_module("surface.postprocessing")
        except ImportError as exc:  # pragma: no cover - surfaced at runtime
            raise RuntimeError(
                "Failed to import SlicerDDSurfer surface workflow code. Ensure surface preprocessing, prediction, and postprocessing modules are available."
            ) from exc

        self._pipeline_modules = {
            "preprocessing": preprocessing,
            "prediction": prediction,
            "postprocessing": postprocessing,
        }
        return self._pipeline_modules

    def _ensure_ddseg_on_path(self) -> None:
        if str(self.module_dir) not in sys.path:
            sys.path.insert(0, str(self.module_dir))

    def _resolve_subject_input(self, base_path: Path, subject_id: str) -> dict[str, Any]:
        inspected = inspect_subject_directory(base_path, subject_id)
        if inspected["mode"] == "missing":
            raise FileNotFoundError(
                f"Unable to resolve subject '{subject_id}' from {base_path}. "
                "Expected either a new-style subject root with input/data.nii.gz or a legacy registered directory."
            )
        return inspected

    def runInputValidation(
        self,
        *,
        subject_id: str,
        input_root: Path,
        output_dir: Optional[Path] = None,
        t1w_path: Optional[Path] = None,
        bids_metadata_path: Optional[Path] = None,
        dependency_groups: tuple[str, ...] = ("core",),
        require_phase_encoding: bool = False,
    ) -> InputValidationResult:
        config = InputValidationConfig(
            subject_id=subject_id,
            input_root=input_root,
            output_dir=output_dir,
            t1w_path=t1w_path,
            bids_metadata_path=bids_metadata_path,
            dependency_groups=dependency_groups,
            require_phase_encoding=require_phase_encoding,
        )
        result = validate_subject_inputs(config)
        report = result.report_path.as_posix() if result.report_path else "not written"
        self.log(
            f"[Validation] {result.status}: {result.error_count} error(s), "
            f"{result.warning_count} warning(s). Report: {report}"
        )
        return result

    def _default_task_output_dir(self, subject_root: Path, task_name: str) -> Path:
        return subject_root / "outputs" / task_name

    def _resolve_optional_output_dir(
        self,
        output_dir: Optional[Path],
        *,
        subject_root: Optional[Path],
        task_name: str,
    ) -> Path:
        if output_dir is not None:
            resolved = output_dir.expanduser().resolve()
            resolved.mkdir(parents=True, exist_ok=True)
            return resolved
        if subject_root is None:
            raise ValueError(f"Output directory is required for {task_name} when no subject root is available.")
        resolved = self._default_task_output_dir(subject_root, task_name)
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def _load_model_node(self, stl_path: Path, surface: str, subject_id: str) -> None:
        name = f"{subject_id}_{surface}_{stl_path.stem.split('_')[-1]}"
        success, model_node = slicer.util.loadModel(stl_path.as_posix(), returnNode=True)
        if success and model_node:
            model_node.SetName(name)

    def _load_scalar_volume_node(self, volume_path: Path, node_name: str) -> None:
        success, volume_node = slicer.util.loadVolume(
            volume_path.as_posix(),
            properties={"name": node_name, "show": False},
            returnNode=True,
        )
        if success and volume_node:
            volume_node.SetName(node_name)

    def _load_table_node(self, table_path: Path, node_name: str) -> None:
        table_node = slicer.util.loadTable(table_path.as_posix())
        if table_node:
            table_node.SetName(node_name)

    def _resolve_template_dir(self) -> Path:
        candidates = []
        env_template = os.environ.get("DDSURFER_TEMPLATE_DIR")
        if env_template:
            candidates.append(Path(env_template))
        candidates.extend(
            [
                self.module_dir / "Resources" / "Data" / "template",
                self.module_dir / "Resources" / "template",
                self.module_dir / "surface" / "template",
                self.module_dir / "template",
                self.module_dir.parent / "template",
            ]
        )
        for candidate in candidates:
            if candidate and candidate.exists():
                template_file = candidate / "100307-FA.nii.gz"
                if template_file.exists():
                    return candidate
        raise FileNotFoundError(
            "Unable to locate SlicerDDSurfer template directory. "
            "Provide DDSURFER_TEMPLATE_DIR or ensure template assets are bundled with the module."
        )

    def _resolve_checkpoint_root(self) -> Path:
        candidates = []
        env_ckpt = os.environ.get("DDSURFER_CHECKPOINT_DIR")
        if env_ckpt:
            candidates.append(Path(env_ckpt))
        candidates.extend(
            [
                self.module_dir / "Resources" / "Data" / "ckpts",
                self.module_dir / "Resources" / "ckpts",
                self.module_dir / "surface" / "ckpts",
                self.module_dir / "ckpts",
                self.module_dir.parent / "ckpts",
            ]
        )
        for candidate in candidates:
            hcp_dir = candidate / "hcp"
            if candidate and hcp_dir.exists():
                return candidate
        raise FileNotFoundError(
            "Unable to locate SlicerDDSurfer checkpoint directory. "
            "Provide DDSURFER_CHECKPOINT_DIR or ensure checkpoints are bundled with the module."
        )

    def _resolve_registration_atlas(self) -> Path:
        candidates = []
        env_atlas = os.environ.get("DDSURFER_REGISTRATION_ATLAS")
        if env_atlas:
            candidates.append(Path(env_atlas))
        candidates.extend(
            [
                self.module_dir / "Resources" / "Data" / "100HCP-population-mean-T2.nii.gz",
                self.module_dir / "Resources" / "100HCP-population-mean-T2.nii.gz",
            ]
        )
        for candidate in candidates:
            if candidate and candidate.exists():
                return candidate
        raise FileNotFoundError(
            "Unable to locate the registration atlas for raw-input DDSurfer execution. "
            "Provide DDSURFER_REGISTRATION_ATLAS or bundle 100HCP-population-mean-T2.nii.gz under Resources/Data."
        )
