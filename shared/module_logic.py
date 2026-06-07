"""Common scripted-module logic glue for SlicerDDSurfer."""

from __future__ import annotations

import logging
import os
import sys
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import slicer

from shared import (
    EnvironmentDoctorConfig,
    EnvironmentDoctorResult,
    InputValidationConfig,
    InputValidationResult,
    ProductOrchestratorConfig,
    ProductOrchestratorResult,
    RunPlanResult,
    default_task_output_dir,
    inspect_subject_directory,
    plan_subject_products,
    run_environment_doctor,
    run_subject_products,
    subject_layout,
    summarize_environment_doctor,
    validate_subject_inputs,
    write_environment_report,
)

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
                self._install_python_requirement(requirement)

        for requirement, import_name in requirements:
            ensure_package(requirement, import_name)

    def _install_python_requirement(self, requirement: str) -> None:
        """Install one Python requirement in the active Slicer Python environment."""

        try:
            import slicer.packaging as slicer_packaging  # type: ignore[import-not-found]

            if hasattr(slicer_packaging, "pip_ensure"):
                self.log(f"[Environment] Ensuring Python requirement with slicer.packaging: {requirement}")
                slicer_packaging.pip_ensure(requirement, requester="SlicerDDSurfer")
                return
            if hasattr(slicer_packaging, "pip_install"):
                self.log(f"[Environment] Installing Python requirement with slicer.packaging: {requirement}")
                try:
                    slicer_packaging.pip_install(requirement, show_progress=True)
                except TypeError:
                    slicer_packaging.pip_install(requirement)
                return
        except Exception as exc:
            self.log(f"[Environment] slicer.packaging unavailable or failed for {requirement}: {exc}")

        self.log(f"[Environment] Installing Python requirement with slicer.util.pip_install: {requirement}")
        slicer.util.pip_install(requirement)

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

    def runEnvironmentDoctor(
        self,
        *,
        targets: tuple[str, ...],
        subject_root: Path,
        output_root: Optional[Path] = None,
        preprocessing_backend: str = "dipy",
        tractography_backend: str = "csd_act",
        connectome_backend: str = "python",
        ddseg_device: str = "cpu",
        surface_device: str = "cpu",
        tractcloud_device: str = "auto",
        microstructure_run_free_water: bool = False,
        microstructure_run_noddi: bool = False,
        mrtrix_bin_dir: Optional[Path] = None,
        preprocessing_mrtrix_bin_dir: Optional[Path] = None,
        preprocessing_fsl_bin_dir: Optional[Path] = None,
        postprocess_freesurfer_home: Optional[Path] = None,
        wma_root: Optional[Path] = None,
        wma_atlas_dir: Optional[Path] = None,
        slicer_executable: Optional[Path] = None,
        fiber_tract_measurements_cli: Optional[Path] = None,
        tract_querier_root: Optional[Path] = None,
        tractcloud_root: Optional[Path] = None,
        tractcloud_python_executable: Optional[Path] = None,
        tractcloud_data_dir: Optional[Path] = None,
    ) -> EnvironmentDoctorResult:
        layout = subject_layout(subject_root.expanduser().resolve(), output_root=output_root)
        result = run_environment_doctor(
            EnvironmentDoctorConfig(
                targets=targets,
                repo_root=self.module_dir,
                output_dir=layout.run_metadata / "environment",
                preprocessing_backend=preprocessing_backend,
                tractography_backend=tractography_backend,
                connectome_backend=connectome_backend,
                ddseg_device=ddseg_device,
                surface_device=surface_device,
                tractcloud_device=tractcloud_device,
                run_free_water=bool(microstructure_run_free_water),
                run_noddi=bool(microstructure_run_noddi),
                mrtrix_bin_dir=mrtrix_bin_dir,
                preprocessing_mrtrix_bin_dir=preprocessing_mrtrix_bin_dir,
                preprocessing_fsl_bin_dir=preprocessing_fsl_bin_dir,
                postprocess_freesurfer_home=postprocess_freesurfer_home,
                wma_root=wma_root,
                wma_atlas_dir=wma_atlas_dir,
                slicer_executable=slicer_executable,
                fiber_tract_measurements_cli=fiber_tract_measurements_cli,
                tract_querier_root=tract_querier_root,
                tractcloud_root=tractcloud_root,
                tractcloud_python_executable=tractcloud_python_executable,
                tractcloud_data_dir=tractcloud_data_dir,
            )
        )
        written = write_environment_report(result, layout.run_metadata / "environment")
        self.log("[Environment] " + summarize_environment_doctor(result).replace("\n", "\n[Environment] "))
        self.log(f"[Environment] Report: {written['json']}")
        self.log(f"[Environment] Python install helper: {written['python_sh']}")
        self.log(f"[Environment] External tool notes: {written['external_notes']}")
        return result

    def runEnvironmentDependencyCheck(
        self,
        *,
        targets: tuple[str, ...],
        subject_root: Optional[Path] = None,
        output_root: Optional[Path] = None,
        preprocessing_backend: str = "dipy",
        tractography_backend: str = "csd_act",
        connectome_backend: str = "python",
        ddseg_device: str = "auto",
        surface_device: str = "auto",
        tractcloud_device: str = "auto",
        microstructure_run_free_water: bool = False,
        microstructure_run_noddi: bool = False,
        mrtrix_bin_dir: Optional[Path] = None,
        preprocessing_mrtrix_bin_dir: Optional[Path] = None,
        preprocessing_fsl_bin_dir: Optional[Path] = None,
        postprocess_freesurfer_home: Optional[Path] = None,
        wma_root: Optional[Path] = None,
        wma_atlas_dir: Optional[Path] = None,
        slicer_executable: Optional[Path] = None,
        fiber_tract_measurements_cli: Optional[Path] = None,
        tract_querier_root: Optional[Path] = None,
        tractcloud_root: Optional[Path] = None,
        tractcloud_python_executable: Optional[Path] = None,
        tractcloud_data_dir: Optional[Path] = None,
    ) -> EnvironmentDoctorResult:
        """Check environment dependencies without requiring subject inputs."""

        if subject_root is not None and subject_root.expanduser().exists():
            report_dir = subject_layout(subject_root.expanduser().resolve(), output_root=output_root).run_metadata / "environment"
        elif output_root is not None:
            report_dir = output_root.expanduser().resolve() / "00_run_metadata" / "environment"
        else:
            report_dir = Path(str(slicer.app.temporaryPath)) / "SlicerDDSurfer" / "00_run_metadata" / "environment"

        result = run_environment_doctor(
            EnvironmentDoctorConfig(
                targets=targets,
                repo_root=self.module_dir,
                output_dir=report_dir,
                preprocessing_backend=preprocessing_backend,
                tractography_backend=tractography_backend,
                connectome_backend=connectome_backend,
                ddseg_device=ddseg_device,
                surface_device=surface_device,
                tractcloud_device=tractcloud_device,
                run_free_water=bool(microstructure_run_free_water),
                run_noddi=bool(microstructure_run_noddi),
                mrtrix_bin_dir=mrtrix_bin_dir,
                preprocessing_mrtrix_bin_dir=preprocessing_mrtrix_bin_dir,
                preprocessing_fsl_bin_dir=preprocessing_fsl_bin_dir,
                postprocess_freesurfer_home=postprocess_freesurfer_home,
                wma_root=wma_root,
                wma_atlas_dir=wma_atlas_dir,
                slicer_executable=slicer_executable,
                fiber_tract_measurements_cli=fiber_tract_measurements_cli,
                tract_querier_root=tract_querier_root,
                tractcloud_root=tractcloud_root,
                tractcloud_python_executable=tractcloud_python_executable,
                tractcloud_data_dir=tractcloud_data_dir,
            )
        )
        written = write_environment_report(result, report_dir)
        self.log("[Environment] " + summarize_environment_doctor(result).replace("\n", "\n[Environment] "))
        self.log(f"[Environment] Report: {written['json']}")
        self.log(f"[Environment] Python install helper: {written['python_sh']}")
        self.log(f"[Environment] External tool notes: {written['external_notes']}")
        return result

    def installMissingPythonDependencies(self, packages: tuple[str, ...]) -> None:
        """Install missing Python packages in the active Slicer Python environment."""

        unique_packages = tuple(dict.fromkeys(pkg for pkg in packages if pkg and pkg.strip()))
        if not unique_packages:
            self.log("[Environment] No missing Python packages to install.")
            return

        torch_requested = any(pkg == "torch" or pkg.startswith("torch>") or pkg.startswith("torch=") for pkg in unique_packages)
        if torch_requested:
            self.log("[Environment] Installing/checking torch through the Slicer PyTorch extension...")
            _ensure_torch_via_extension(min_version="2.0.0", log=self.log)

        for package in unique_packages:
            if package == "torch" or package.startswith("torch>") or package.startswith("torch="):
                continue
            self.log(f"[Environment] Installing Python package: {package}")
            self._install_python_requirement(package)

    def _default_task_output_dir(self, subject_root: Path, task_name: str) -> Path:
        return default_task_output_dir(subject_root, task_name)

    def runSelectedProductOrchestration(
        self,
        *,
        subject_id: str,
        subject_root: Path,
        targets: tuple[str, ...],
        output_root: Optional[Path] = None,
        run_name: str = "csd_act",
        tractography_backend: str = "csd_act",
        bundle_backend: str = "wmql",
        execute: bool = False,
        resume: bool = True,
        microstructure_run_free_water: bool = False,
        microstructure_run_noddi: bool = False,
        select_streamlines: int = 100000,
        atlas_t2: Optional[Path] = None,
        ddseg_device: str = "auto",
        surface_device: str = "auto",
        mrtrix_bin_dir: Optional[Path] = None,
        preprocessing_mrtrix_bin_dir: Optional[Path] = None,
        preprocessing_fsl_bin_dir: Optional[Path] = None,
        tract_querier_root: Optional[Path] = None,
        connectome_backend: str = "python",
        connectome_compress_mrtrix_dense: bool = False,
        preflight_blocked_targets: Optional[dict[str, str]] = None,
    ) -> ProductOrchestratorResult:
        result = run_subject_products(
            ProductOrchestratorConfig(
                subject_id=subject_id,
                subject_root=subject_root,
                targets=targets,
                output_root=output_root,
                run_name=run_name,
                tractography_backend=tractography_backend,
                bundle_backend=bundle_backend,
                execute=execute,
                resume=resume,
                microstructure_run_free_water=microstructure_run_free_water,
                microstructure_run_noddi=microstructure_run_noddi,
                preprocessing_mrtrix_bin_dir=preprocessing_mrtrix_bin_dir,
                preprocessing_fsl_bin_dir=preprocessing_fsl_bin_dir,
                atlas_t2=atlas_t2,
                ddseg_device=ddseg_device,
                surface_device=surface_device,
                select_streamlines=select_streamlines,
                mrtrix_bin_dir=mrtrix_bin_dir,
                tract_querier_root=tract_querier_root,
                connectome_backend=connectome_backend,
                connectome_compress_mrtrix_dense=connectome_compress_mrtrix_dense,
                preflight_blocked_targets=preflight_blocked_targets or {},
            ),
            log=self.log,
        )
        self.log(f"[Orchestrator] Manifest: {result.run_manifest_path}")
        for task in result.tasks:
            detail = f" ({task.reason})" if task.reason else ""
            self.log(f"[Orchestrator] {task.name}: {task.status}{detail}")
        return result

    def planSelectedProductOrchestration(
        self,
        *,
        subject_id: str,
        subject_root: Path,
        targets: tuple[str, ...],
        output_root: Optional[Path] = None,
        run_name: str = "csd_act",
        tractography_backend: str = "csd_act",
        bundle_backend: str = "wmql",
        resume: bool = True,
        microstructure_run_free_water: bool = False,
        microstructure_run_noddi: bool = False,
        select_streamlines: int = 100000,
        atlas_t2: Optional[Path] = None,
        ddseg_device: str = "auto",
        surface_device: str = "auto",
        mrtrix_bin_dir: Optional[Path] = None,
        preprocessing_mrtrix_bin_dir: Optional[Path] = None,
        preprocessing_fsl_bin_dir: Optional[Path] = None,
        tract_querier_root: Optional[Path] = None,
        connectome_backend: str = "python",
        connectome_compress_mrtrix_dense: bool = False,
        preflight_blocked_targets: Optional[dict[str, str]] = None,
    ) -> RunPlanResult:
        plan = plan_subject_products(
            ProductOrchestratorConfig(
                subject_id=subject_id,
                subject_root=subject_root,
                targets=targets,
                output_root=output_root,
                run_name=run_name,
                tractography_backend=tractography_backend,
                bundle_backend=bundle_backend,
                execute=True,
                resume=resume,
                microstructure_run_free_water=microstructure_run_free_water,
                microstructure_run_noddi=microstructure_run_noddi,
                preprocessing_mrtrix_bin_dir=preprocessing_mrtrix_bin_dir,
                preprocessing_fsl_bin_dir=preprocessing_fsl_bin_dir,
                atlas_t2=atlas_t2,
                ddseg_device=ddseg_device,
                surface_device=surface_device,
                select_streamlines=select_streamlines,
                mrtrix_bin_dir=mrtrix_bin_dir,
                tract_querier_root=tract_querier_root,
                connectome_backend=connectome_backend,
                connectome_compress_mrtrix_dense=connectome_compress_mrtrix_dense,
                preflight_blocked_targets=preflight_blocked_targets or {},
            ),
            write=True,
        )
        self.log(f"[Orchestrator] Run plan: {plan.run_plan_path}")
        for item in plan.items:
            detail = f" ({item.reason})" if item.reason else ""
            self.log(f"[Orchestrator] plan {item.target}: {item.status}{detail}")
        return plan

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

    def _load_model_node(self, stl_path: Path, surface: str, subject_id: str) -> bool:
        name = f"{subject_id}_{surface}_{stl_path.stem.split('_')[-1]}"
        success, model_node = slicer.util.loadModel(stl_path.as_posix(), returnNode=True)
        if success and model_node:
            model_node.SetName(name)
            return True
        return False

    def _load_scalar_volume_node(self, volume_path: Path, node_name: str) -> bool:
        success, volume_node = slicer.util.loadVolume(
            volume_path.as_posix(),
            properties={"name": node_name, "show": False},
            returnNode=True,
        )
        if success and volume_node:
            volume_node.SetName(node_name)
            return True
        return False

    def _load_table_node(self, table_path: Path, node_name: str) -> bool:
        table_node = slicer.util.loadTable(table_path.as_posix())
        if table_node:
            table_node.SetName(node_name)
            return True
        return False

    def _load_fiber_bundle_node(self, fiber_path: Path, node_name: str) -> bool:
        if not fiber_path.is_file():
            return False
        loader = getattr(slicer.util, "loadFiberBundle", None)
        if loader is None:
            self.log(f"[Slicer] FiberBundle loader is unavailable; skipped loading {fiber_path}")
            return False
        if not hasattr(slicer.modules, "tractographydisplay"):
            self.log(f"[Slicer] SlicerDMRI TractographyDisplay is unavailable; skipped loading {fiber_path}")
            return False
        try:
            fiber_node = loader(fiber_path.as_posix())
        except Exception as exc:  # pragma: no cover - depends on SlicerDMRI extension availability
            self.log(f"[Slicer] Failed to load FiberBundle {fiber_path}: {exc}")
            return False
        if fiber_node:
            fiber_node.SetName(node_name)
            return True
        return False

    def loadKeyResultsFromManifest(self, manifest_path: Path, *, max_items: int = 40) -> dict[str, Any]:
        """Load key product outputs from an orchestration manifest into the MRML scene."""

        manifest_path = manifest_path.expanduser().resolve()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        output_root = Path(str(manifest.get("output_root") or manifest_path.parents[1])).expanduser()
        run_name = str(manifest.get("run_name") or "csd_act")
        loaded: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        seen: set[str] = set()

        def add_candidate(path_text: object, label: str) -> None:
            if len(loaded) >= max_items:
                return
            if not path_text:
                return
            path = Path(str(path_text)).expanduser()
            if not path.is_file():
                return
            suffix = "".join(path.suffixes).lower()
            if suffix not in {".nii.gz", ".mgz", ".csv", ".tsv", ".stl", ".vtk", ".vtp", ".trk", ".tck"}:
                return
            key = path.resolve().as_posix()
            if key in seen:
                return
            seen.add(key)
            name = f"{manifest.get('subject_id') or 'subject'}_{label}_{path.stem}".replace(".nii", "")
            try:
                if suffix in {".nii.gz", ".mgz"}:
                    success = self._load_scalar_volume_node(path, name)
                elif suffix in {".csv", ".tsv"}:
                    success = self._load_table_node(path, name)
                elif suffix == ".stl":
                    success = self._load_model_node(path, label, str(manifest.get("subject_id") or "subject"))
                elif suffix in {".vtk", ".vtp", ".trk", ".tck"}:
                    success = self._load_fiber_bundle_node(path, name)
                else:
                    success = False
                if success:
                    loaded.append({"path": path.as_posix(), "label": label})
                else:
                    skipped.append(
                        {
                            "path": path.as_posix(),
                            "label": label,
                            "reason": "Slicer loader unavailable or returned no node",
                        }
                    )
            except Exception as exc:  # pragma: no cover - loader availability depends on Slicer extensions
                skipped.append({"path": path.as_posix(), "label": label, "reason": str(exc)})

        for task in manifest.get("tasks", []) or []:
            if not isinstance(task, dict):
                continue
            task_name = str(task.get("name") or "task")
            if task_name.startswith("preprocessing."):
                continue
            for key, value in (task.get("outputs") or {}).items():
                add_candidate(value, f"{task_name}_{key}")

        # Some backends do not put every product in task.outputs; scan compact,
        # user-facing folders only and avoid cache/log directories.
        scan_roots = [
            output_root / "02_microstructure",
            output_root / "03_structural",
            output_root / "04_tractography" / "saf" / run_name,
            output_root / "04_tractography" / "bundles" / "wmql" / run_name,
            output_root / "04_tractography" / "connectome" / run_name,
        ]
        preferred_suffixes = (".nii.gz", ".mgz", ".csv", ".tsv", ".stl", ".vtk", ".vtp", ".trk", ".tck")
        for root in scan_roots:
            if len(loaded) >= max_items or not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if len(loaded) >= max_items:
                    break
                if "cache" in path.parts or not path.is_file():
                    continue
                if not any(path.name.endswith(suffix) for suffix in preferred_suffixes):
                    continue
                add_candidate(path, root.name)

        self.log(f"[Slicer] Auto-loaded {len(loaded)} key result node(s) from {manifest_path}")
        return {
            "loaded": loaded,
            "skipped": skipped,
            "manifest_path": manifest_path.as_posix(),
        }

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
