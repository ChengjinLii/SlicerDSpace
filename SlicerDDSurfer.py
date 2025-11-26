"""SlicerDDSurfer scripted module: end-to-end cortical surface reconstruction."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Any, TYPE_CHECKING, List

import vtk

import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleWidget,
)
from slicer.parameterNodeWrapper import parameterNodeWrapper
from slicer.util import VTKObservationMixin
from qt import QSignalBlocker, QPixmap


def _ensure_torch_via_extension(min_version: str = "2.0.0", log: Optional[callable] = None):
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
        import PyTorchUtils  # provided by the PyTorch extension
    except ModuleNotFoundError as exc:  # pragma: no cover - surfaced at runtime
        raise RuntimeError(
            "未检测到 PyTorch 扩展。请在 Extension Manager 中安装 'PyTorch' 扩展并重启 Slicer。"
        ) from exc

    torch_logic = PyTorchUtils.PyTorchUtilsLogic()

    if torch_logic.torchInstalled():
        import torch  # type: ignore[import-not-found]
        _log(f"PyTorch 已安装 (版本 {torch.__version__})")
        return torch

    _log("未检测到 PyTorch，正在通过扩展安装（可能耗时数分钟）...")
    torch = torch_logic.installTorch(
        askConfirmation=False,
        torchVersionRequirement=f">={min_version}",
    )
    if torch is None:  # pragma: no cover - error surfaced at runtime
        raise RuntimeError(
            "PyTorch 扩展存在，但安装 torch 失败。请检查网络后在 'PyTorch Util' 模块中重试安装。"
        )
    _log(f"PyTorch 安装完成 (版本 {torch.__version__})")
    return torch

if TYPE_CHECKING:  # pragma: no cover
    from ddspipeline.prediction import PredictionResult  # type: ignore

LOGGER = logging.getLogger(__name__)


class SlicerDDSurfer(ScriptedLoadableModule):
    """Main module metadata presented inside Slicer."""

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "SlicerDDSurfer"
        self.parent.categories = ["Examples"]
        self.parent.dependencies = []
        self.parent.contributors = ["SlicerDDSurfer Team"]
        self.parent.helpText = (
            "Run the SlicerDDSurfer cortical surface reconstruction pipeline directly inside Slicer. "
            "Provide the diffusion-derived scalar volumes, corresponding brain mask, and registration "
            "transform; the module performs preprocessing, neural surface prediction, and transforms "
            "the meshes back to subject-native space."
        )
        self.parent.acknowledgementText = (
            "SlicerDDSurfer open-source release. Portions developed at ShanghaiTech University."
        )


@parameterNodeWrapper
class SlicerDDSurferParameterNode:
    """Parameter node definition stored in the MRML scene."""

    subjectId: str = ""
    outputDirectory: str = ""
    inputDirectory: str = ""
    predictMode: str = "all"
    device: str = "cpu"
    cleanupIntermediates: bool = False


class SlicerDDSurferWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Slicer widget glue code."""

    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)
        self.logic: SlicerDDSurferLogic | None = None
        self._parameterNode: SlicerDDSurferParameterNode | None = None
        self._parameterNodeGuiTag = None
        self._lastStatusMessage: Optional[str] = None
        self._pipelineActive: bool = False

    def setup(self) -> None:
        ScriptedLoadableModuleWidget.setup(self)
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/SlicerDDSurfer.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        uiWidget.setMRMLScene(slicer.mrmlScene)

        self.logic = SlicerDDSurferLogic()
        self.logic.logCallback = self.appendLog

        self.ui.applyButton.connect("clicked()", self.onApplyButton)
        self.ui.inputDirectoryPath.currentPathChanged.connect(self._onInputDirectoryChanged)
        self.ui.outputDirectoryPath.currentPathChanged.connect(self._onOutputDirectoryChanged)
        self.ui.predictModeComboBox.currentTextChanged.connect(self._onPredictModeChanged)
        self.ui.deviceComboBox.currentTextChanged.connect(self._onDeviceChanged)

        if hasattr(self.ui, "validateButton"):
            self.ui.validateButton.connect("clicked()", self._onValidateClicked)
        if hasattr(self.ui, "clearLogButton"):
            self.ui.clearLogButton.connect("clicked()", self._onClearLogClicked)

        self._populateDeviceCombo()
        if hasattr(self.ui, "subjectIdLineEdit"):
            self.ui.subjectIdLineEdit.setClearButtonEnabled(True)
        if hasattr(self.ui, "applyButton"):
            self.ui.applyButton.setAutoDefault(True)

        logo_label = getattr(self.ui, "logoLabel", None)
        if logo_label:
            logo_path = self.resourcePath("Icons/SlicerDDSurfer.png")
            if os.path.exists(logo_path):
                logo_label.setPixmap(QPixmap(logo_path))

        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        progress = getattr(self.ui, "statusProgressBar", None)
        if progress:
            progress.setRange(0, 100)
            progress.setValue(0)

        self._setStatus("error", "Waiting for input")
        self.initializeParameterNode()

    def cleanup(self) -> None:
        self.removeObservers()

    def enter(self) -> None:
        self.initializeParameterNode()

    def exit(self) -> None:
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)

    def onSceneStartClose(self, caller, event) -> None:
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        self.setParameterNode(self.logic.getParameterNode())

    def setParameterNode(self, inputParameterNode: Optional[SlicerDDSurferParameterNode]) -> None:
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._checkCanApply()

    def _checkCanApply(self, caller=None, event=None) -> None:
        node = self._parameterNode
        if node:
            desired_input = node.inputDirectory or ""
            if self.ui.inputDirectoryPath.currentPath != desired_input:
                blocker = QSignalBlocker(self.ui.inputDirectoryPath)
                self.ui.inputDirectoryPath.setCurrentPath(desired_input)
                del blocker
            desired_output = node.outputDirectory or ""
            if self.ui.outputDirectoryPath.currentPath != desired_output:
                blocker = QSignalBlocker(self.ui.outputDirectoryPath)
                self.ui.outputDirectoryPath.setCurrentPath(desired_output)
                del blocker
            if self.ui.predictModeComboBox.currentText != node.predictMode:
                blocker = QSignalBlocker(self.ui.predictModeComboBox)
                index = self.ui.predictModeComboBox.findText(node.predictMode)
                if index >= 0:
                    self.ui.predictModeComboBox.setCurrentIndex(index)
                del blocker
            if self.ui.deviceComboBox.currentText != node.device:
                blocker = QSignalBlocker(self.ui.deviceComboBox)
                index = self.ui.deviceComboBox.findText(node.device)
                if index >= 0:
                    self.ui.deviceComboBox.setCurrentIndex(index)
                del blocker

        self.validateInputs(manual=False)

    def _onOutputDirectoryChanged(self, newPath: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.outputDirectory = newPath or ""
        self._checkCanApply()

    def _onInputDirectoryChanged(self, newPath: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.inputDirectory = newPath or ""
        self._checkCanApply()

    def _onPredictModeChanged(self, newText: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.predictMode = newText or "all"
        self._checkCanApply()

    def _onDeviceChanged(self, newText: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.device = newText or "cpu"
        self._checkCanApply()

    def appendLog(self, text: str) -> None:
        if hasattr(self.ui, "logPlainTextEdit"):
            self.ui.logPlainTextEdit.appendPlainText(text)
            self.ui.logPlainTextEdit.ensureCursorVisible()

    def _onClearLogClicked(self) -> None:
        if hasattr(self.ui, "logPlainTextEdit"):
            self.ui.logPlainTextEdit.clear()

    def onApplyButton(self) -> None:
        if not self._parameterNode or not self.logic:
            return

        if not self.validateInputs(manual=True):
            slicer.util.showStatusMessage("Input validation failed. See log for details.", 5000)
            return

        slicer.util.showStatusMessage("SlicerDDSurfer pipeline running...", 0)
        with slicer.util.tryWithErrorDisplay("SlicerDDSurfer processing failed.", waitCursor=True):
            self._setPipelineActive(True)
            try:
                self.appendLog("Starting SlicerDDSurfer pipeline...")
                self.logic.process(self._parameterNode, logCallback=self.appendLog)
                self.appendLog("SlicerDDSurfer pipeline completed.")
                slicer.util.showStatusMessage("SlicerDDSurfer pipeline completed.", 5000)
            finally:
                self._setPipelineActive(False)

    def _setStatus(self, kind: str, message: str) -> None:
        label = getattr(self.ui, "statusLabel", None)
        if not label:
            return
        progress = getattr(self.ui, "statusProgressBar", None)
        palette = {
            "ready": "#2E7D32",
            "running": "#1565C0",
            "error": "#C62828",
        }
        color = palette.get(kind, palette["error"])
        label.setText(message)
        label.setStyleSheet(
            f"QLabel#statusLabel {{ background-color: {color}; color: white; "
            "padding: 4px 10px; border-radius: 6px; font-weight: 600; }}"
        )
        if not progress:
            return
        if kind == "running":
            progress.setRange(0, 0)
        elif kind == "ready":
            progress.setRange(0, 100)
            progress.setValue(100)
        else:
            progress.setRange(0, 100)
            progress.setValue(0)

    def _evaluateInputs(self) -> tuple[bool, List[str]]:
        node = self._parameterNode
        if not node:
            return False, ["Parameter node unavailable"]

        missing: List[str] = []
        subject_id = node.subjectId.strip()
        input_dir_str = node.inputDirectory.strip()
        output_dir_str = node.outputDirectory.strip()

        if not subject_id:
            missing.append("Subject ID")

        input_dir: Optional[Path] = None
        if not input_dir_str:
            missing.append("Input directory")
        else:
            candidate = Path(input_dir_str).expanduser()
            if not candidate.is_dir():
                missing.append("Input directory")
            else:
                input_dir = candidate

        if not output_dir_str:
            missing.append("Output directory")

        subject_dir: Optional[Path] = None
        subject_dir_token = ""
        if subject_id and input_dir:
            subject_dir = input_dir / subject_id
            subject_dir_token = f"{subject_id} directory"
            if not subject_dir.is_dir():
                missing.append(subject_dir_token)

        if subject_dir and subject_dir.is_dir():
            expected_files = [
                f"{subject_id}-dti-FractionalAnisotropy-Reg.nii.gz",
                f"{subject_id}-dti-MinEigenvalue-Reg.nii.gz",
                f"{subject_id}-dti-MidEigenvalue-Reg.nii.gz",
                f"{subject_id}-dti-MaxEigenvalue-Reg.nii.gz",
                f"{subject_id}-dti-Trace-Reg.nii.gz",
                f"{subject_id}-dti-MeanDiffusivity-Reg.nii.gz",
                f"{subject_id}-mask-Reg.nii.gz",
                f"{subject_id}-b0ToAtlasT2.tfm",
            ]
            for name in expected_files:
                if not (subject_dir / name).exists():
                    missing.append(name)

        return (len(missing) == 0), missing

    def validateInputs(self, manual: bool = False) -> bool:
        ok, missing = self._evaluateInputs()
        status_message = "Ready to run." if ok else self._summarise_missing(missing)

        if not self._pipelineActive:
            self._setStatus("ready" if ok else "error", status_message)
            if hasattr(self.ui, "applyButton"):
                tooltip = "Run the SlicerDDSurfer pipeline" if ok else "Waiting: " + ", ".join(missing)
                self.ui.applyButton.setToolTip(tooltip)

        if hasattr(self.ui, "applyButton"):
            self.ui.applyButton.enabled = ok and not self._pipelineActive
        if hasattr(self.ui, "validateButton"):
            self.ui.validateButton.enabled = not self._pipelineActive

        self._setWidgetError(getattr(self.ui, "subjectIdLineEdit", None), "Subject ID" in missing)
        subject_token = ""
        node = self._parameterNode
        if node:
            subject_token = f"{node.subjectId.strip()} directory"
        file_errors = False
        if node and node.subjectId.strip():
            prefix = f"{node.subjectId.strip()}-"
            file_errors = any(entry.startswith(prefix) for entry in missing if entry.endswith(".nii.gz") or entry.endswith(".tfm"))
        self._setWidgetError(
            getattr(self.ui, "inputDirectoryPath", None),
            any(token in missing for token in ("Input directory", subject_token)) or file_errors,
        )
        self._setWidgetError(getattr(self.ui, "outputDirectoryPath", None), "Output directory" in missing)

        if status_message != self._lastStatusMessage and not self._pipelineActive:
            self._lastStatusMessage = status_message
            self.appendLog(status_message)

        if manual:
            if ok:
                self.appendLog("Validation succeeded: all required inputs are available.")
            else:
                self.appendLog("Validation failed. Missing entries: " + ", ".join(missing))

        return ok

    def _summarise_missing(self, missing: List[str]) -> str:
        if not missing:
            return "Ready to run."
        preview = "; ".join(missing[:3])
        if len(missing) > 3:
            preview += " ..."
        return "Waiting: " + preview

    def _setWidgetError(self, widget, has_error: bool) -> None:
        if not widget:
            return
        border_style = "border: 1px solid #C62828;" if has_error else ""
        class_name = widget.metaObject().className() if hasattr(widget, "metaObject") else ""
        if class_name == "ctkPathLineEdit":
            widget.setStyleSheet(f"ctkPathLineEdit {{ {border_style} }}")
        else:
            widget.setStyleSheet(border_style)

    def _populateDeviceCombo(self) -> None:
        combo = getattr(self.ui, "deviceComboBox", None)
        if not combo:
            return
        current = combo.currentText if combo.count else "cpu"
        combo.clear()
        combo.addItem("cpu")
        try:
            import torch

            if torch.cuda.is_available():
                combo.addItem("cuda:0")
        except Exception:
            pass
        index = combo.findText(current)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _onValidateClicked(self) -> None:
        self.validateInputs(manual=True)

    def _setPipelineActive(self, active: bool) -> None:
        self._pipelineActive = active
        if active:
            if hasattr(self.ui, "applyButton"):
                self.ui.applyButton.enabled = False
            if hasattr(self.ui, "validateButton"):
                self.ui.validateButton.enabled = False
            self._setStatus("running", "Running pipeline...")
            self._lastStatusMessage = "Running pipeline..."
        else:
            self.validateInputs(manual=False)


@dataclass
class PipelineResult:
    generated_models: list[Path]


class SlicerDDSurferLogic(ScriptedLoadableModuleLogic):
    """Drive preprocessing, prediction, and post-processing."""

    METRIC_PATTERNS = {
        "FractionalAnisotropy": "{subject_id}-dti-FractionalAnisotropy-Reg.nii.gz",
        "MinEigenvalue": "{subject_id}-dti-MinEigenvalue-Reg.nii.gz",
        "MidEigenvalue": "{subject_id}-dti-MidEigenvalue-Reg.nii.gz",
        "MaxEigenvalue": "{subject_id}-dti-MaxEigenvalue-Reg.nii.gz",
        "Trace": "{subject_id}-dti-Trace-Reg.nii.gz",
        "MeanDiffusivity": "{subject_id}-dti-MeanDiffusivity-Reg.nii.gz",
    }

    def __init__(self) -> None:
        ScriptedLoadableModuleLogic.__init__(self)
        self.module_dir = Path(__file__).resolve().parent
        self._pipeline_modules: Optional[Dict[str, Any]] = None
        self.template_dir = self._resolve_template_dir()
        self.checkpoint_root = self._resolve_checkpoint_root()
        self.template_volume = self.template_dir / "100307-FA.nii.gz"
        self.logCallback = None

    def log(self, message: str) -> None:
        LOGGER.info(message)
        if self.logCallback:
            try:
                self.logCallback(message)
            except Exception:  # pragma: no cover
                LOGGER.exception("Failed to write log message via callback")

    def setupPythonRequirements(self) -> None:
        import importlib

        _ensure_torch_via_extension(min_version="2.0.0", log=self.log)

        def ensure_package(requirement: str, import_name: Optional[str] = None) -> None:
            module_name = import_name or requirement
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError:
                self.log(f"Installing Python package: {requirement}")
                slicer.util.pip_install(requirement)

        for requirement, import_name in (
            ("nibabel>=5.0", "nibabel"),
            ("SimpleITK", "SimpleITK"),
            ("trimesh", "trimesh"),
            ("tqdm", "tqdm"),
            ("networkx", "networkx"),
        ):
            ensure_package(requirement, import_name)

    def getParameterNode(self) -> SlicerDDSurferParameterNode:
        return SlicerDDSurferParameterNode(super().getParameterNode())

    def _load_pipeline_modules(self) -> Dict[str, Any]:
        if self._pipeline_modules is not None:
            return self._pipeline_modules

        if str(self.module_dir) not in sys.path:
            sys.path.insert(0, str(self.module_dir))

        import importlib

        try:
            preprocessing = importlib.import_module("ddspipeline.preprocessing")
            prediction = importlib.import_module("ddspipeline.prediction")
            postprocessing = importlib.import_module("ddspipeline.postprocessing")
        except ImportError as exc:  # pragma: no cover - surfaced at runtime
            raise RuntimeError(
                "无法导入 SlicerDDSurfer 管线代码。请确认扩展目录下存在 ddspipeline 子目录，"
                "并且其中包含 preprocessing/prediction/postprocessing 模块。"
            ) from exc

        self._pipeline_modules = {
            "preprocessing": preprocessing,
            "prediction": prediction,
            "postprocessing": postprocessing,
        }
        return self._pipeline_modules

    def _validate_resources(self) -> None:
        if not self.template_volume.exists():
            raise FileNotFoundError(
                f"Template volume missing: {self.template_volume}\n"
                "Set DDSURFER_TEMPLATE_DIR to a directory containing 100307-FA.nii.gz "
                "or place the template under Resources/Data/template."
            )
        hcp_dir = self.checkpoint_root / "hcp"
        expected = [
            hcp_dir / "DDCSR_white_lh_Full_DualStream_no_b0_Cascaded.pt",
            hcp_dir / "DDCSR_white_rh_Full_DualStream_no_b0_Cascaded.pt",
            hcp_dir / "DDCSR_pial_lh_Full_DualStream_no_b0_Cascaded.pt",
            hcp_dir / "DDCSR_pial_rh_Full_DualStream_no_b0_Cascaded.pt",
        ]
        missing = [path for path in expected if not path.exists()]
        if missing:
            missing_list = "\n".join(str(path) for path in missing)
            raise FileNotFoundError(
                "Missing SlicerDDSurfer checkpoints:\n"
                f"{missing_list}\n"
                "Set DDSURFER_CHECKPOINT_DIR or place checkpoints under Resources/Data/ckpts/hcp."
            )

    def process(self, parameters: SlicerDDSurferParameterNode, logCallback=None) -> PipelineResult:
        self._validate_resources()
        self.log("Checking Python dependencies...")
        try:
            self.setupPythonRequirements()
        except Exception as exc:
            raise RuntimeError("依赖安装失败，请检查网络或 PyTorch 扩展。") from exc
        subject_id = parameters.subjectId.strip()
        if not subject_id:
            raise ValueError("Subject identifier must be provided.")

        input_root = Path(parameters.inputDirectory).expanduser().resolve()
        if not input_root.is_dir():
            raise FileNotFoundError(f"Input directory not found: {input_root}")

        subject_dir = input_root / subject_id
        if not subject_dir.is_dir():
            raise FileNotFoundError(f"Subject directory not found: {subject_dir}")

        output_base = Path(parameters.outputDirectory).expanduser().resolve()
        output_base.mkdir(parents=True, exist_ok=True)

        preprocessed_root = output_base / "preprocessed"
        predictions_root = output_base / "pred_results_SlicerDDSurfer"
        work_root = output_base  # preprocess_subject manages raw/preprocessed under this root
        (output_base / "raw").mkdir(parents=True, exist_ok=True)
        preprocessed_root.mkdir(parents=True, exist_ok=True)
        predictions_root.mkdir(parents=True, exist_ok=True)

        self.log(f"Subject: {subject_id}")
        self.log(f"Input directory: {subject_dir}")
        self.log(f"Working root: {work_root}")
        self.log(f"Preprocessed root: {preprocessed_root}")
        self.log(f"Predictions root: {predictions_root}")

        def resolve_default(filename: str) -> Path:
            expanded = filename.replace("{subject_id}", subject_id)
            return subject_dir / expanded

        metric_paths: Dict[str, Path] = {
            metric: resolve_default(filename)
            for metric, filename in self.METRIC_PATTERNS.items()
        }
        mask_path = resolve_default("{subject_id}-mask-Reg.nii.gz")
        transform_path = resolve_default("{subject_id}-b0ToAtlasT2.tfm")

        missing_inputs = [path for path in list(metric_paths.values()) + [mask_path, transform_path] if not path.exists()]
        if missing_inputs:
            missing_list = "\n".join(str(path) for path in missing_inputs)
            raise FileNotFoundError(f"未找到以下必需的输入文件:\n{missing_list}")

        for metric, path in metric_paths.items():
            self.log(f"{metric} volume: {path}")
        self.log(f"Brain mask: {mask_path}")
        self.log(f"Transform: {transform_path}")

        modules = self._load_pipeline_modules()
        preprocessing = modules["preprocessing"]
        prediction_module = modules["prediction"]
        postprocessing_module = modules["postprocessing"]

        SubjectPreprocessingConfig = preprocessing.SubjectPreprocessingConfig
        SubjectPreprocessingResult = preprocessing.SubjectPreprocessingResult
        preprocess_subject = preprocessing.preprocess_subject

        PredictionStageConfig = prediction_module.PredictionStageConfig
        predict_subject = prediction_module.predict_subject

        PostprocessingConfig = postprocessing_module.PostprocessingConfig
        convert_meshes_to_native_space = postprocessing_module.convert_meshes_to_native_space

        preprocess_config = SubjectPreprocessingConfig(
            subject_id=subject_id,
            metric_paths=metric_paths,
            mask_path=mask_path,
            transform_path=transform_path,
            work_dir=work_root,
            template_volume_path=self.template_volume,
        )
        try:
            preprocess_result: SubjectPreprocessingResult = preprocess_subject(preprocess_config)
        except Exception as exc:  # pragma: no cover - runtime safeguard
            raise RuntimeError(
                "预处理阶段失败，请检查 NIfTI/掩模/模板是否有效，或依赖库（nibabel、SimpleITK、numpy）是否已安装。"
            ) from exc
        self.log(f"Preprocessed volumes stored in {preprocess_result.preprocessed_dir}")

        prediction_root = predictions_root

        prediction_results: list[Any] = []
        for hemisphere in ("left", "right"):
            cfg = PredictionStageConfig(
                subject_id=subject_id,
                hemisphere=hemisphere,
                predict_mode=parameters.predictMode,
                device=parameters.device,
                step_size=0.02,
                n_svf=2,
                n_res=3,
                template_dir=self.template_dir,
                checkpoint_root=self.checkpoint_root,
                input_root=preprocess_result.preprocessed_dir.parent,
                output_root=prediction_root,
            )
            self.log(f"Running prediction for {hemisphere} hemisphere...")
            try:
                prediction_results.append(predict_subject(cfg))
            except Exception as exc:  # pragma: no cover
                raise RuntimeError(
                    "预测阶段失败。请确认 PyTorch、trimesh 等依赖已安装，"
                    "以及 GPU/CPU 设备参数设置正确。"
                ) from exc

        post_config = PostprocessingConfig(
            subject_id=subject_id,
            transform_path=preprocess_result.transform_copy_path,
            predictions_root=prediction_root,
        )
        self.log("Converting meshes to subject-native space...")
        try:
            native_outputs = convert_meshes_to_native_space(post_config, prediction_results)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "后处理阶段失败。请确认 SimpleITK、trimesh 依赖存在，及变换文件/预测网格有效。"
            ) from exc

        ras_models: list[Path] = []
        for surface, paths in native_outputs.items():
            for path in paths:
                if path.name.endswith("_orig.stl"):
                    continue
                ras_models.append(path)
                self.log(f"Generated {surface} STL: {path}")
                self._load_model_node(path, surface, subject_id)

        if parameters.cleanupIntermediates:
            self._cleanup_intermediates(work_root, keep_native=True, log=self.log)

        return PipelineResult(generated_models=ras_models)

    def _load_model_node(self, stl_path: Path, surface: str, subject_id: str) -> None:
        name = f"{subject_id}_{surface}_{stl_path.stem.split('_')[-1]}"
        success, model_node = slicer.util.loadModel(stl_path.as_posix(), returnNode=True)
        if success and model_node:
            model_node.SetName(name)

    def _cleanup_intermediates(self, work_root: Path, keep_native: bool, log) -> None:
        for folder in ("_exports", "raw", "preprocessed"):
            path = work_root / folder
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                log(f"Removed intermediate directory {path}")

        predictions_dir = work_root / "predictions"
        if not predictions_dir.exists():
            return

        if keep_native:
            for child in predictions_dir.iterdir():
                if child.name == "native":
                    continue
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                    log(f"Removed intermediate directory {child}")
                else:
                    child.unlink(missing_ok=True)
                    log(f"Removed intermediate file {child}")
        else:
            shutil.rmtree(predictions_dir, ignore_errors=True)
            log(f"Removed predictions directory {predictions_dir}")

    def _resolve_template_dir(self) -> Path:
        candidates = []
        env_template = os.environ.get("DDSURFER_TEMPLATE_DIR")
        if env_template:
            candidates.append(Path(env_template))
        candidates.extend(
            [
                self.module_dir / "Resources" / "Data" / "template",
                self.module_dir / "Resources" / "template",
                self.module_dir / "ddspipeline" / "template",
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
                self.module_dir / "ddspipeline" / "ckpts",
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
