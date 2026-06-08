"""SlicerDDSurfer scripted module for multi-workflow diffusion MRI analysis."""

from __future__ import annotations

from typing import Annotated, Optional

import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleWidget,
)
from slicer.parameterNodeWrapper import Choice, parameterNodeWrapper
from slicer.util import VTKObservationMixin

from connectome.module_logic import ConnectomeLogicMixin
from microstructure.module_logic import MicrostructureLogicMixin
from microstructure.module_widget import MicrostructureWidgetMixin
from parcellation.module_logic import ParcellationLogicMixin
from parcellation.module_widget import ParcellationWidgetMixin
from preprocessing.module_logic import PreprocessingLogicMixin
from segmentation.module_logic import SegmentationLogicMixin
from segmentation.module_widget import SegmentationWidgetMixin
from shared.module_logic import SharedLogicMixin
from shared.module_widget import SharedWidgetMixin
from surface.module_logic import PipelineResult, SurfaceLogicMixin
from surface.module_widget import SurfaceWidgetMixin
from tractography.module_logic import TractographyLogicMixin


class SlicerDDSurfer(ScriptedLoadableModule):
    """Main module metadata presented inside Slicer."""

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "SlicerDDSurfer"
        self.parent.categories = ["Diffusion"]
        # Do not set Slicer module-level dependencies here. Missing optional
        # extensions must not prevent the UI from loading; the dependency doctor
        # reports runnable and blocked targets after the module opens. Release
        # packaging declares recommended extension dependencies in CMake/.s4ext.
        self.parent.dependencies = []
        self.parent.contributors = ["SlicerDDSurfer Team"]
        self.parent.helpText = (
            "Run multiple diffusion-MRI workflows inside one Slicer extension, including cortical "
            "surface reconstruction, parcellation, segmentation, and microstructure analysis. "
            "The module reuses shared subject-root diffusion caches so related workflows can be "
            "combined without repeating the same DTI and registration preparation steps."
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
    predictMode: Annotated[str, Choice(["all", "wm"])] = "all"
    device: Annotated[str, Choice(["auto", "cpu", "cuda:0"])] = "auto"
    cleanupIntermediates: bool = False
    postprocessSubjectId: str = ""
    postprocessNativeDir: str = ""
    postprocessMriDir: str = ""
    postprocessRepoDir: str = ""
    postprocessLicensePath: str = ""
    postprocessMode: Annotated[str, Choice(["whole", "left", "right"])] = "whole"
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
    ddsegDevice: Annotated[str, Choice(["auto", "cpu", "cuda:0"])] = "auto"
    ddsegApplySoftmax: bool = False
    microstructureSubjectId: str = ""
    microstructureInputRoot: str = ""
    microstructureOutputDir: str = ""
    microstructureRoiPath: str = ""
    microstructureFitMethod: Annotated[str, Choice(["wls", "ls"])] = "wls"
    microstructureRunFreeWater: bool = False
    microstructureRunNoddi: bool = False
    microstructureForceRecompute: bool = False
    targetPreprocessing: bool = True
    preprocessingBackend: Annotated[str, Choice(["dipy", "mrtrix_fsl"])] = "dipy"
    orchestrationRunName: str = "csd_act_ui"
    orchestrationTractographyBackend: Annotated[str, Choice(["csd_act", "dti_det", "saf"])] = "csd_act"
    orchestrationBundleBackend: Annotated[str, Choice(["wmql", "wma", "tractcloud", "all"])] = "wmql"
    orchestrationSelectStreamlines: int = 100000
    orchestrationMicrostructureStages: Annotated[str, Choice(["dti", "dti,freewater", "dti,freewater,noddi"])] = "dti"
    orchestrationRunFreeWater: bool = False
    orchestrationRunNoddi: bool = False
    connectomeBackend: Annotated[str, Choice(["python", "mrtrix"])] = "python"
    connectomeCompressMrtrixDense: bool = False
    autoInstallPythonDependencies: bool = True
    targetSurface: bool = True
    targetParcellation: bool = True
    targetSegmentation: bool = True
    targetMicrostructure: bool = True
    targetTractography: bool = True
    targetBundles: bool = True
    targetConnectome: bool = True


class SlicerDDSurferWidget(
    SharedWidgetMixin,
    SurfaceWidgetMixin,
    ParcellationWidgetMixin,
    MicrostructureWidgetMixin,
    SegmentationWidgetMixin,
    ScriptedLoadableModuleWidget,
    VTKObservationMixin,
):
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
        self._uiWidget = uiWidget
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        uiWidget.setMRMLScene(slicer.mrmlScene)

        self.logic = SlicerDDSurferLogic()
        self.logic.logCallback = self.appendLog

        self._connect_surface_ui()
        self._connect_parcellation_ui()
        self._connect_microstructure_ui()
        self._connect_segmentation_ui()
        self._connect_common_ui()
        self._initialize_common_ui_state()


class SlicerDDSurferLogic(
    SharedLogicMixin,
    PreprocessingLogicMixin,
    SurfaceLogicMixin,
    ParcellationLogicMixin,
    MicrostructureLogicMixin,
    SegmentationLogicMixin,
    TractographyLogicMixin,
    ConnectomeLogicMixin,
    ScriptedLoadableModuleLogic,
):
    """Drive the product-specific workflows exposed by the module."""

    def __init__(self) -> None:
        ScriptedLoadableModuleLogic.__init__(self)
        self._initialize_shared_logic_state()

    def getParameterNode(self) -> SlicerDDSurferParameterNode:
        return SlicerDDSurferParameterNode(super().getParameterNode())
