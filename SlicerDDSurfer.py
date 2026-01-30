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
from qt import QSignalBlocker, QPixmap, QPushButton, QFrame, QHBoxLayout, QLabel
from ddsurferpipeline.sculpting.surface_sculptor import SurfaceSculptorWidget


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

if TYPE_CHECKING:  # pragma: no cover
    from ddsurferpipeline.prediction import PredictionResult  # type: ignore

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
    postprocessSubjectId: str = ""
    postprocessNativeDir: str = ""
    postprocessMriDir: str = ""
    postprocessRepoDir: str = ""
    postprocessLicensePath: str = ""
    postprocessMode: str = "whole"
    postprocessDockerImage: str = ""
    postprocessForce: bool = True
    ddparcelSubjectId: str = ""
    ddparcelInputRoot: str = ""
    ddparcelOutputRoot: str = ""
    ddparcelAtlasPath: str = ""
    ddparcelFlip: int = 1
    ddsegMaskPath: str = ""
    ddsegDwiPath: str = ""
    ddsegBvalPath: str = ""
    ddsegBvecPath: str = ""
    ddsegOutputDir: str = ""
    ddsegWeightsDir: str = ""
    ddsegSlicerBase: str = ""
    ddsegSlicerExt: str = ""
    ddsegDevice: str = "cpu"
    ddsegApplySoftmax: bool = False


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
        self._sculptWidget: SurfaceSculptorWidget | None = None

    def setup(self) -> None:
        ScriptedLoadableModuleWidget.setup(self)
        self._add_navigation_panel()
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
        if hasattr(self.ui, "postprocessSubjectLineEdit"):
            self.ui.postprocessSubjectLineEdit.textChanged.connect(self._onPostprocessSubjectChanged)
        if hasattr(self.ui, "postprocessNativePath"):
            self.ui.postprocessNativePath.currentPathChanged.connect(self._onPostprocessNativeDirChanged)
        if hasattr(self.ui, "postprocessMriPath"):
            self.ui.postprocessMriPath.currentPathChanged.connect(self._onPostprocessMriDirChanged)
        if hasattr(self.ui, "postprocessRepoPath"):
            self.ui.postprocessRepoPath.currentPathChanged.connect(self._onPostprocessRepoChanged)
        if hasattr(self.ui, "postprocessLicensePath"):
            self.ui.postprocessLicensePath.currentPathChanged.connect(self._onPostprocessLicenseChanged)
        if hasattr(self.ui, "postprocessModeComboBox"):
            self.ui.postprocessModeComboBox.currentTextChanged.connect(self._onPostprocessModeChanged)
        if hasattr(self.ui, "postprocessImageLineEdit"):
            self.ui.postprocessImageLineEdit.textChanged.connect(self._onPostprocessImageChanged)
        if hasattr(self.ui, "postprocessForceCheckBox"):
            self.ui.postprocessForceCheckBox.toggled.connect(self._onPostprocessForceToggled)
        if hasattr(self.ui, "runPostprocessButton"):
            self.ui.runPostprocessButton.connect("clicked()", self._onRunDockerPostprocess)
        if hasattr(self.ui, "ddparcelSubjectLineEdit"):
            self.ui.ddparcelSubjectLineEdit.textChanged.connect(self._onDDParcelSubjectChanged)
        if hasattr(self.ui, "ddparcelInputRootPath"):
            self.ui.ddparcelInputRootPath.currentPathChanged.connect(self._onDDParcelInputRootChanged)
        if hasattr(self.ui, "ddparcelOutputRootPath"):
            self.ui.ddparcelOutputRootPath.currentPathChanged.connect(self._onDDParcelOutputRootChanged)
        if hasattr(self.ui, "ddparcelAtlasPath"):
            self.ui.ddparcelAtlasPath.currentPathChanged.connect(self._onDDParcelAtlasChanged)
        if hasattr(self.ui, "ddparcelFlipSpinBox"):
            self.ui.ddparcelFlipSpinBox.valueChanged.connect(self._onDDParcelFlipChanged)
        if hasattr(self.ui, "runDDParcelButton"):
            self.ui.runDDParcelButton.connect("clicked()", self._onRunDDParcelPipeline)
        if hasattr(self.ui, "ddsegMaskPath"):
            self.ui.ddsegMaskPath.currentPathChanged.connect(self._onDDSegMaskChanged)
        if hasattr(self.ui, "ddsegDwiPath"):
            self.ui.ddsegDwiPath.currentPathChanged.connect(self._onDDSegDwiChanged)
        if hasattr(self.ui, "ddsegBvalPath"):
            self.ui.ddsegBvalPath.currentPathChanged.connect(self._onDDSegBvalChanged)
        if hasattr(self.ui, "ddsegBvecPath"):
            self.ui.ddsegBvecPath.currentPathChanged.connect(self._onDDSegBvecChanged)
        if hasattr(self.ui, "ddsegOutputPath"):
            self.ui.ddsegOutputPath.currentPathChanged.connect(self._onDDSegOutputChanged)
        if hasattr(self.ui, "ddsegWeightsPath"):
            self.ui.ddsegWeightsPath.currentPathChanged.connect(self._onDDSegWeightsChanged)
        if hasattr(self.ui, "ddsegSlicerBasePath"):
            self.ui.ddsegSlicerBasePath.currentPathChanged.connect(self._onDDSegSlicerBaseChanged)
        if hasattr(self.ui, "ddsegSlicerExtPath"):
            self.ui.ddsegSlicerExtPath.currentPathChanged.connect(self._onDDSegSlicerExtChanged)
        if hasattr(self.ui, "ddsegDeviceComboBox"):
            self.ui.ddsegDeviceComboBox.currentTextChanged.connect(self._onDDSegDeviceChanged)
        if hasattr(self.ui, "ddsegSoftmaxCheckBox"):
            self.ui.ddsegSoftmaxCheckBox.toggled.connect(self._onDDSegSoftmaxChanged)
        if hasattr(self.ui, "runDDSegButton"):
            self.ui.runDDSegButton.connect("clicked()", self._onRunDDSegPipeline)

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

        # Topology-preserving surface sculptor (parallel to main pipeline)
        try:
            self._sculptWidget = SurfaceSculptorWidget(parent=self.parent)
            self.layout.addWidget(self._sculptWidget.widget)
        except Exception as exc:  # pragma: no cover - ui instantiation safeguard
            LOGGER.exception("Failed to initialize sculptor widget: %s", exc)

    def _add_navigation_panel(self) -> None:
        """Add top-level navigation buttons for quick jumps to related modules."""
        frame = QFrame()
        frame.setObjectName("navigationFrame")
        frame.setStyleSheet(
            "QFrame#navigationFrame { background: #f7f9fc; border: 1px solid #d7dce5; border-radius: 8px; padding: 8px; } "
            "QPushButton.navBtn { background-color: #1565C0; color: white; border-radius: 6px; padding: 6px 10px; } "
            "QPushButton.navBtn:hover { background-color: #0d47a1; } "
            "QPushButton.navBtn:disabled { background-color: #9e9e9e; } "
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        label = QLabel("Choose workflow:")
        label.setStyleSheet("font-weight: 600; color: #263238;")
        layout.addWidget(label)

        buttons = [
            ("101-region parcellation (DDParcel)", "DDParcel"),
            ("WM/GM/CSF segmentation (DDSeg)", "DDSeg"),
            ("WM & Pial Surface (DDSurfer)", "LOCAL_DDSURFER"),
            ("Surface post-process", "SurfacePost"),
        ]
        for text, target in buttons:
            btn = QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setProperty("class", "navBtn")
            btn.setToolTip("Jump to module")
            btn.setStyleSheet("")
            btn.clicked.connect(lambda _=False, tgt=target: self._jump_to_module(tgt))
            layout.addWidget(btn)
        layout.addStretch(1)
        self.layout.insertWidget(0, frame)

    def cleanup(self) -> None:
        self.removeObservers()
        if self._sculptWidget:
            self._sculptWidget.cleanup()
        # Navigation cleanup not required

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
        if self._parameterNode and not (self._parameterNode.ddparcelAtlasPath or "").strip():
            atlas_path = self.resourcePath("Data/100HCP-population-mean-T2.nii.gz")
            if atlas_path and os.path.exists(atlas_path):
                self._parameterNode.ddparcelAtlasPath = atlas_path

    def _jump_to_module(self, target: str) -> None:
        """Handle navigation button clicks."""
        if target == "DDSeg":
            try:
                slicer.util.selectModule("SlicerDDSurfer")
                panel = getattr(self.ui, "ddsegCollapsibleButton", None)
                if panel:
                    panel.collapsed = False
                    panel.raise_()
            except Exception:
                pass
            slicer.util.showStatusMessage("DDSeg pipeline is available in this module", 3000)
            return
        if target == "SurfacePost":
            try:
                slicer.util.selectModule("SlicerDDSurfer")
                if self._sculptWidget:
                    self._sculptWidget.widget.setCollapsed(False)
                docker_panel = getattr(self.ui, "dockerPostprocessCollapsibleButton", None)
                if docker_panel:
                    docker_panel.collapsed = False
                    docker_panel.raise_()
            except Exception:
                pass
            slicer.util.showStatusMessage("Jumped to surface post-process area", 3000)
            return

        if target == "LOCAL_DDSURFER":
            try:
                slicer.util.selectModule("SlicerDDSurfer")
                if hasattr(self, "ui") and getattr(self.ui, "configurationCollapsibleButton", None):
                    self.ui.configurationCollapsibleButton.collapsed = False
            except Exception:
                pass
            slicer.util.showStatusMessage("Jumped to DDSurfer configuration", 3000)
            return

        try:
            slicer.util.selectModule(target)
            slicer.util.showStatusMessage(f"Jumped to {target}", 3000)
        except Exception:
            slicer.util.infoDisplay(f"Module {target} not installed or not yet implemented. Coming soon.")

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
            if hasattr(self.ui, "postprocessSubjectLineEdit"):
                current = self.ui.postprocessSubjectLineEdit.text()
                desired = node.postprocessSubjectId or ""
                if current != desired:
                    blocker = QSignalBlocker(self.ui.postprocessSubjectLineEdit)
                    self.ui.postprocessSubjectLineEdit.setText(desired)
                    del blocker
            if hasattr(self.ui, "postprocessNativePath"):
                desired = node.postprocessNativeDir or ""
                if self.ui.postprocessNativePath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.postprocessNativePath)
                    self.ui.postprocessNativePath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "postprocessMriPath"):
                desired = node.postprocessMriDir or ""
                if self.ui.postprocessMriPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.postprocessMriPath)
                    self.ui.postprocessMriPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "postprocessRepoPath"):
                desired = node.postprocessRepoDir or ""
                if self.ui.postprocessRepoPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.postprocessRepoPath)
                    self.ui.postprocessRepoPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "postprocessLicensePath"):
                desired = node.postprocessLicensePath or ""
                if self.ui.postprocessLicensePath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.postprocessLicensePath)
                    self.ui.postprocessLicensePath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "postprocessModeComboBox"):
                desired_mode = node.postprocessMode or "whole"
                if self.ui.postprocessModeComboBox.currentText != desired_mode:
                    blocker = QSignalBlocker(self.ui.postprocessModeComboBox)
                    idx = self.ui.postprocessModeComboBox.findText(desired_mode)
                    if idx >= 0:
                        self.ui.postprocessModeComboBox.setCurrentIndex(idx)
                    del blocker
            if hasattr(self.ui, "postprocessImageLineEdit"):
                desired = node.postprocessDockerImage or ""
                if self.ui.postprocessImageLineEdit.text() != desired:
                    blocker = QSignalBlocker(self.ui.postprocessImageLineEdit)
                    self.ui.postprocessImageLineEdit.setText(desired)
                    del blocker
            if hasattr(self.ui, "postprocessForceCheckBox"):
                desired = bool(node.postprocessForce)
                if self.ui.postprocessForceCheckBox.isChecked() != desired:
                    blocker = QSignalBlocker(self.ui.postprocessForceCheckBox)
                    self.ui.postprocessForceCheckBox.setChecked(desired)
                    del blocker
            if hasattr(self.ui, "ddparcelSubjectLineEdit"):
                desired = node.ddparcelSubjectId or ""
                if self.ui.ddparcelSubjectLineEdit.text() != desired:
                    blocker = QSignalBlocker(self.ui.ddparcelSubjectLineEdit)
                    self.ui.ddparcelSubjectLineEdit.setText(desired)
                    del blocker
            if hasattr(self.ui, "ddparcelInputRootPath"):
                desired = node.ddparcelInputRoot or ""
                if self.ui.ddparcelInputRootPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.ddparcelInputRootPath)
                    self.ui.ddparcelInputRootPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "ddparcelOutputRootPath"):
                desired = node.ddparcelOutputRoot or ""
                if self.ui.ddparcelOutputRootPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.ddparcelOutputRootPath)
                    self.ui.ddparcelOutputRootPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "ddparcelAtlasPath"):
                desired = node.ddparcelAtlasPath or ""
                if self.ui.ddparcelAtlasPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.ddparcelAtlasPath)
                    self.ui.ddparcelAtlasPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "ddparcelFlipSpinBox"):
                desired = int(node.ddparcelFlip)
                if self.ui.ddparcelFlipSpinBox.value != desired:
                    blocker = QSignalBlocker(self.ui.ddparcelFlipSpinBox)
                    self.ui.ddparcelFlipSpinBox.value = desired
                    del blocker
            if hasattr(self.ui, "ddsegMaskPath"):
                desired = node.ddsegMaskPath or ""
                if self.ui.ddsegMaskPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.ddsegMaskPath)
                    self.ui.ddsegMaskPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "ddsegDwiPath"):
                desired = node.ddsegDwiPath or ""
                if self.ui.ddsegDwiPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.ddsegDwiPath)
                    self.ui.ddsegDwiPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "ddsegBvalPath"):
                desired = node.ddsegBvalPath or ""
                if self.ui.ddsegBvalPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.ddsegBvalPath)
                    self.ui.ddsegBvalPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "ddsegBvecPath"):
                desired = node.ddsegBvecPath or ""
                if self.ui.ddsegBvecPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.ddsegBvecPath)
                    self.ui.ddsegBvecPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "ddsegOutputPath"):
                desired = node.ddsegOutputDir or ""
                if self.ui.ddsegOutputPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.ddsegOutputPath)
                    self.ui.ddsegOutputPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "ddsegWeightsPath"):
                desired = node.ddsegWeightsDir or ""
                if self.ui.ddsegWeightsPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.ddsegWeightsPath)
                    self.ui.ddsegWeightsPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "ddsegSlicerBasePath"):
                desired = node.ddsegSlicerBase or ""
                if self.ui.ddsegSlicerBasePath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.ddsegSlicerBasePath)
                    self.ui.ddsegSlicerBasePath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "ddsegSlicerExtPath"):
                desired = node.ddsegSlicerExt or ""
                if self.ui.ddsegSlicerExtPath.currentPath != desired:
                    blocker = QSignalBlocker(self.ui.ddsegSlicerExtPath)
                    self.ui.ddsegSlicerExtPath.setCurrentPath(desired)
                    del blocker
            if hasattr(self.ui, "ddsegDeviceComboBox"):
                desired = node.ddsegDevice or "cpu"
                if self.ui.ddsegDeviceComboBox.currentText != desired:
                    blocker = QSignalBlocker(self.ui.ddsegDeviceComboBox)
                    self.ui.ddsegDeviceComboBox.setCurrentText(desired)
                    del blocker
            if hasattr(self.ui, "ddsegSoftmaxCheckBox"):
                desired = bool(node.ddsegApplySoftmax)
                if self.ui.ddsegSoftmaxCheckBox.isChecked() != desired:
                    blocker = QSignalBlocker(self.ui.ddsegSoftmaxCheckBox)
                    self.ui.ddsegSoftmaxCheckBox.setChecked(desired)
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

    def _onPostprocessSubjectChanged(self, newText: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.postprocessSubjectId = newText or ""

    def _onPostprocessNativeDirChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.postprocessNativeDir = path or ""

    def _onPostprocessMriDirChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.postprocessMriDir = path or ""

    def _onPostprocessRepoChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.postprocessRepoDir = path or ""

    def _onPostprocessLicenseChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.postprocessLicensePath = path or ""

    def _onPostprocessModeChanged(self, text: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.postprocessMode = text or "whole"

    def _onPostprocessImageChanged(self, text: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.postprocessDockerImage = text or ""

    def _onPostprocessForceToggled(self, state: bool) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.postprocessForce = bool(state)

    def _onDDParcelSubjectChanged(self, newText: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddparcelSubjectId = newText or ""

    def _onDDParcelInputRootChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddparcelInputRoot = path or ""

    def _onDDParcelOutputRootChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddparcelOutputRoot = path or ""

    def _onDDParcelAtlasChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddparcelAtlasPath = path or ""

    def _onDDParcelFlipChanged(self, value: int) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddparcelFlip = int(value)

    def _onDDSegMaskChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddsegMaskPath = path or ""

    def _onDDSegDwiChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddsegDwiPath = path or ""

    def _onDDSegBvalChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddsegBvalPath = path or ""

    def _onDDSegBvecChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddsegBvecPath = path or ""

    def _onDDSegOutputChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddsegOutputDir = path or ""

    def _onDDSegWeightsChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddsegWeightsDir = path or ""

    def _onDDSegSlicerBaseChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddsegSlicerBase = path or ""

    def _onDDSegSlicerExtChanged(self, path: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddsegSlicerExt = path or ""

    def _onDDSegDeviceChanged(self, value: str) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddsegDevice = value or "cpu"

    def _onDDSegSoftmaxChanged(self, value: bool) -> None:
        if not self._parameterNode:
            return
        with slicer.util.NodeModify(self._parameterNode):
            self._parameterNode.ddsegApplySoftmax = bool(value)

    def _onRunDDSegPipeline(self) -> None:
        if not self._parameterNode or not self.logic:
            return

        mask_path = (self._parameterNode.ddsegMaskPath or "").strip()
        dwi_path = (self._parameterNode.ddsegDwiPath or "").strip()
        bval_path = (self._parameterNode.ddsegBvalPath or "").strip()
        bvec_path = (self._parameterNode.ddsegBvecPath or "").strip()
        output_dir = (self._parameterNode.ddsegOutputDir or "").strip()
        weights_dir = (self._parameterNode.ddsegWeightsDir or "").strip()
        slicer_base = (self._parameterNode.ddsegSlicerBase or "").strip()
        slicer_ext = (self._parameterNode.ddsegSlicerExt or "").strip()
        device = (self._parameterNode.ddsegDevice or "cpu").strip()
        apply_softmax = bool(self._parameterNode.ddsegApplySoftmax)

        missing: List[str] = []
        for label, value in (
            ("Mask NIfTI", mask_path),
            ("DWI NIfTI", dwi_path),
            ("bval", bval_path),
            ("bvec", bvec_path),
            ("DDSeg output", output_dir),
            ("DDSeg weights", weights_dir),
            ("Slicer base", slicer_base),
            ("SlicerDMRI extension", slicer_ext),
        ):
            if not value:
                missing.append(label)

        if missing:
            slicer.util.errorDisplay(
                "Cannot run DDSeg. Please provide the following:\n- " + "\n- ".join(sorted(set(missing))),
                parent=self.parent,
            )
            return

        self.appendLog("Starting DDSeg pipeline...")
        self._setStatus("running", "DDSeg pipeline in progress")
        slicer.util.showStatusMessage("DDSeg pipeline running...", 0)

        with slicer.util.tryWithErrorDisplay("DDSeg pipeline failed.", waitCursor=True):
            self.logic.setupDDSegRequirements()
            self.logic.runDDSegPipeline(
                mask_path=Path(mask_path).expanduser(),
                dwi_path=Path(dwi_path).expanduser(),
                bval_path=Path(bval_path).expanduser(),
                bvec_path=Path(bvec_path).expanduser(),
                output_dir=Path(output_dir).expanduser(),
                weights_dir=Path(weights_dir).expanduser(),
                slicer_base=Path(slicer_base).expanduser(),
                slicer_ext=Path(slicer_ext).expanduser(),
                device=device,
                apply_softmax=apply_softmax,
            )

        self.appendLog("DDSeg pipeline completed.")
        self._setStatus("ready", "Pipeline ready")
        slicer.util.showStatusMessage("DDSeg pipeline completed.", 5000)

    def appendLog(self, text: str) -> None:
        if hasattr(self.ui, "logPlainTextEdit"):
            self.ui.logPlainTextEdit.appendPlainText(text)
            self.ui.logPlainTextEdit.ensureCursorVisible()

    def _onClearLogClicked(self) -> None:
        if hasattr(self.ui, "logPlainTextEdit"):
            self.ui.logPlainTextEdit.clear()

    def _onRunDockerPostprocess(self) -> None:
        if not self._parameterNode or not self.logic:
            return

        subject = (self._parameterNode.postprocessSubjectId or self._parameterNode.subjectId or "").strip()
        native_dir = (self._parameterNode.postprocessNativeDir or "").strip()
        mri_dir = (self._parameterNode.postprocessMriDir or "").strip()
        repo_dir = (self._parameterNode.postprocessRepoDir or "").strip()
        license_path = (self._parameterNode.postprocessLicensePath or "").strip()
        mode = (self._parameterNode.postprocessMode or "whole").strip() or "whole"
        image_tag = (self._parameterNode.postprocessDockerImage or "").strip()
        force = bool(self._parameterNode.postprocessForce)

        missing: List[str] = []
        if not subject:
            missing.append("Subject ID")
        paths_to_check: List[tuple[str, str, bool]] = [
            (native_dir, "Native output directory", False),
            (mri_dir, "MRI directory", False),
            (repo_dir, "postprocess-release directory", False),
            (license_path, "FreeSurfer license", True),
        ]
        resolved_paths: dict[str, Path] = {}
        for path_str, label, require_file in paths_to_check:
            if not path_str:
                missing.append(label)
                continue
            path = Path(path_str).expanduser()
            if require_file and not path.is_file():
                missing.append(label)
                continue
            if not require_file and not path.is_dir():
                missing.append(label)
                continue
            resolved_paths[label] = path

        if missing:
            slicer.util.errorDisplay(
                "Cannot run Docker postprocess. Please provide the following:\n- " + "\n- ".join(missing),
                parent=self.parent,
            )
            return

        def docker_log(message: str) -> None:
            self.appendLog(f"[Docker] {message}")

        slicer.util.showStatusMessage("Running Docker postprocess...", 0)
        self._setStatus("running", "Docker postprocess in progress")
        with slicer.util.tryWithErrorDisplay("Docker postprocess failed.", waitCursor=True):
            self.appendLog("Starting Docker postprocess...")
            self.logic.runDockerPostprocess(
                subject_id=subject,
                native_dir=resolved_paths["Native output directory"],
                mri_dir=resolved_paths["MRI directory"],
                repo_path=resolved_paths["postprocess-release directory"],
                license_path=resolved_paths["FreeSurfer license"],
                mode=mode,
                docker_image=image_tag or None,
                force=force,
                log_callback=docker_log,
            )
            self.appendLog("Docker postprocess completed.")
            slicer.util.showStatusMessage("Docker postprocess completed.", 5000)
        self._setStatus("ready", "Pipeline ready")

    def _onRunDDParcelPipeline(self) -> None:
        if not self._parameterNode or not self.logic:
            return

        subject = (self._parameterNode.ddparcelSubjectId or self._parameterNode.subjectId or "").strip()
        input_root = (self._parameterNode.ddparcelInputRoot or "").strip()
        output_root = (self._parameterNode.ddparcelOutputRoot or "").strip()
        atlas_path = (self._parameterNode.ddparcelAtlasPath or "").strip()
        flip = int(self._parameterNode.ddparcelFlip or 1)

        missing: List[str] = []
        if not subject:
            missing.append("Subject ID")
        if not input_root:
            missing.append("DDParcel input root")
        if not output_root:
            missing.append("DDParcel output root")
        if not atlas_path:
            missing.append("Atlas T2")

        input_root_path = Path(input_root).expanduser() if input_root else None
        output_root_path = Path(output_root).expanduser() if output_root else None
        atlas_path_obj = Path(atlas_path).expanduser() if atlas_path else None
        if input_root_path and not input_root_path.is_dir():
            missing.append("DDParcel input root")
        if output_root_path and not output_root_path.exists():
            missing.append("DDParcel output root")
        if atlas_path_obj and not atlas_path_obj.is_file():
            missing.append("Atlas T2")

        if missing:
            slicer.util.errorDisplay(
                "Cannot run DDParcel. Please provide the following:\n- " + "\n- ".join(sorted(set(missing))),
                parent=self.parent,
            )
            return

        self.appendLog("Starting DDParcel pipeline...")
        self._setStatus("running", "DDParcel pipeline in progress")
        slicer.util.showStatusMessage("DDParcel pipeline running...", 0)

        from ddparcpipeline import DDParcelConfig, run_ddparcel

        with slicer.util.tryWithErrorDisplay("DDParcel pipeline failed.", waitCursor=True):
            self.logic.setupDDParcelRequirements()
            config = DDParcelConfig(
                subject_id=subject,
                input_root=input_root_path,
                output_root=output_root_path,
                atlas_t2=atlas_path_obj,
                flip=flip,
            )
            run_ddparcel(config, log=self.appendLog)

        self.appendLog("DDParcel pipeline completed.")
        self._setStatus("ready", "Pipeline ready")
        slicer.util.showStatusMessage("DDParcel pipeline completed.", 5000)

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
            f"background-color: {color}; color: white; padding: 4px 10px; border-radius: 6px; font-weight: 600;"
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
        self.ddseg_root = self.module_dir / "ddsegpipeline"
        self.ddseg_src = self.ddseg_root / "src"
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

    def setupDDParcelRequirements(self) -> None:
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
            ("numpy", "numpy"),
            ("scipy", "scipy"),
            ("nibabel>=5.0", "nibabel"),
            ("pynrrd", "nrrd"),
            ("scikit-image", "skimage"),
            ("h5py", "h5py"),
            ("plumbum", "plumbum"),
            ("torchvision", "torchvision"),
        ):
            ensure_package(requirement, import_name)

    def setupDDSegRequirements(self) -> None:
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
            ("numpy", "numpy"),
            ("scipy", "scipy"),
            ("nibabel>=5.0", "nibabel"),
            ("pynrrd", "nrrd"),
            ("torchvision", "torchvision"),
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
            preprocessing = importlib.import_module("ddsurferpipeline.preprocessing")
            prediction = importlib.import_module("ddsurferpipeline.prediction")
            postprocessing = importlib.import_module("ddsurferpipeline.postprocessing")
        except ImportError as exc:  # pragma: no cover - surfaced at runtime
            raise RuntimeError(
                "Failed to import SlicerDDSurfer pipeline code. Ensure ddsurferpipeline exists with preprocessing/prediction/postprocessing."
            ) from exc

        self._pipeline_modules = {
            "preprocessing": preprocessing,
            "prediction": prediction,
            "postprocessing": postprocessing,
        }
        return self._pipeline_modules

    def _ensure_ddseg_on_path(self) -> None:
        if self.ddseg_src.exists() and str(self.ddseg_src) not in sys.path:
            sys.path.insert(0, str(self.ddseg_src))

    def runDDSegPipeline(
        self,
        mask_path: Path,
        dwi_path: Path,
        bval_path: Path,
        bvec_path: Path,
        output_dir: Path,
        weights_dir: Path,
        slicer_base: Path,
        slicer_ext: Path,
        device: str = "cpu",
        apply_softmax: bool = False,
    ) -> None:
        self._ensure_ddseg_on_path()

        if not self.ddseg_src.exists():
            raise FileNotFoundError(f"DDSeg source not found at {self.ddseg_src}")

        from ddseg.config import DDSegConfig
        from ddseg.pipeline import run_ddseg

        cfg = DDSegConfig(
            input_mask_nii=mask_path,
            parameter_type="DTI",
            output_folder=output_dir,
            weights_dir=weights_dir,
            device=device,
            apply_softmax=apply_softmax,
            dwi_nii=dwi_path,
            bval=bval_path,
            bvec=bvec_path,
            slicer_base=slicer_base,
            slicer_ext=slicer_ext,
        )
        run_ddseg(cfg)

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
            raise RuntimeError("Dependency installation failed. Please check network or PyTorch extension.") from exc
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
            raise FileNotFoundError(f"Required input files missing:\n{missing_list}")

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
                "Preprocessing failed. Verify NIfTI/mask/template validity and that nibabel/SimpleITK/numpy are installed."
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
                    "Prediction failed. Ensure PyTorch/trimesh dependencies are installed and device parameters are valid."
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
                "Postprocessing failed. Ensure SimpleITK/trimesh dependencies exist and transform/predicted meshes are valid."
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

    def runDockerPostprocess(
        self,
        *,
        subject_id: str,
        native_dir: Path,
        mri_dir: Path,
        repo_path: Path,
        license_path: Path,
        mode: str,
        docker_image: Optional[str],
        force: bool,
        log_callback=None,
    ) -> None:
        if not subject_id:
            raise ValueError("Subject ID must be provided for Docker postprocess.")
        if not native_dir.is_dir():
            raise FileNotFoundError(f"Native output directory not found: {native_dir}")
        if not mri_dir.is_dir():
            raise FileNotFoundError(f"MRI directory not found: {mri_dir}")
        if not repo_path.is_dir():
            raise FileNotFoundError(f"postprocess-release directory not found: {repo_path}")
        if not license_path.is_file():
            raise FileNotFoundError(f"FreeSurfer license not found: {license_path}")

        try:
            import run_postprocess_docker as docker_helper
        except ImportError as exc:  # pragma: no cover - runtime environment guard
            raise RuntimeError(
                "Unable to import run_postprocess_docker.py. Ensure it is located in the SlicerDDSurfer module directory."
            ) from exc

        docker_helper.run_postprocess(
            subject_id=subject_id,
            native_dir=native_dir,
            mri_dir=mri_dir,
            postprocess_repo=repo_path,
            mode=mode,
            license_path=license_path,
            image_tag=docker_image,
            inputs_dir=None,
            outputs_dir=None,
            force=force,
            log_callback=log_callback,
        )

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
                self.module_dir / "ddsurferpipeline" / "template",
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
                self.module_dir / "ddsurferpipeline" / "ckpts",
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
