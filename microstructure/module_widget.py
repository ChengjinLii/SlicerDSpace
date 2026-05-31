"""Microstructure workflow widget glue for SlicerDDSurfer."""

from __future__ import annotations

from pathlib import Path
from typing import List

import slicer


class MicrostructureWidgetMixin:
    """Widget handlers for the microstructure workflow."""

    def _connect_microstructure_ui(self) -> None:
        if hasattr(self.ui, "microstructureSubjectLineEdit"):
            self.ui.microstructureSubjectLineEdit.textChanged.connect(self._onMicrostructureSubjectChanged)
        if hasattr(self.ui, "microstructureInputRootPath"):
            self.ui.microstructureInputRootPath.currentPathChanged.connect(self._onMicrostructureInputRootChanged)
        if hasattr(self.ui, "microstructureOutputPath"):
            self.ui.microstructureOutputPath.currentPathChanged.connect(self._onMicrostructureOutputChanged)
        if hasattr(self.ui, "microstructureRoiPath"):
            self.ui.microstructureRoiPath.currentPathChanged.connect(self._onMicrostructureRoiChanged)
        if hasattr(self.ui, "microstructureFitComboBox"):
            self.ui.microstructureFitComboBox.currentTextChanged.connect(self._onMicrostructureFitChanged)
        if hasattr(self.ui, "microstructureRunFreeWaterCheckBox"):
            self.ui.microstructureRunFreeWaterCheckBox.toggled.connect(self._onMicrostructureRunFreeWaterChanged)
        if hasattr(self.ui, "microstructureRunNoddiCheckBox"):
            self.ui.microstructureRunNoddiCheckBox.toggled.connect(self._onMicrostructureRunNoddiChanged)
        if hasattr(self.ui, "microstructureForceRecomputeCheckBox"):
            self.ui.microstructureForceRecomputeCheckBox.toggled.connect(self._onMicrostructureForceRecomputeChanged)
        if hasattr(self.ui, "runMicrostructureButton"):
            self.ui.runMicrostructureButton.connect("clicked()", self._onRunMicrostructurePipeline)

    def _onMicrostructureSubjectChanged(self, newText: str) -> None:
        self._update_parameter_node("microstructureSubjectId", newText)

    def _onMicrostructureInputRootChanged(self, path: str) -> None:
        self._update_parameter_node("microstructureInputRoot", path)

    def _onMicrostructureOutputChanged(self, path: str) -> None:
        self._update_parameter_node("microstructureOutputDir", path)

    def _onMicrostructureRoiChanged(self, path: str) -> None:
        self._update_parameter_node("microstructureRoiPath", path)

    def _onMicrostructureFitChanged(self, value: str) -> None:
        self._update_parameter_node("microstructureFitMethod", value)

    def _onMicrostructureRunFreeWaterChanged(self, value: bool) -> None:
        self._update_parameter_node("microstructureRunFreeWater", bool(value))

    def _onMicrostructureRunNoddiChanged(self, value: bool) -> None:
        self._update_parameter_node("microstructureRunNoddi", bool(value))

    def _onMicrostructureForceRecomputeChanged(self, value: bool) -> None:
        self._update_parameter_node("microstructureForceRecompute", bool(value))

    def _onRunMicrostructurePipeline(self) -> None:
        if not self._parameterNode or not self.logic:
            return

        subject = (self._parameterNode.microstructureSubjectId or self._parameterNode.subjectId or "").strip()
        input_root = (self._parameterNode.microstructureInputRoot or "").strip()
        output_dir = (self._parameterNode.microstructureOutputDir or "").strip()
        roi_path = (self._parameterNode.microstructureRoiPath or "").strip()
        fit_method = (self._parameterNode.microstructureFitMethod or "wls").strip().lower() or "wls"
        run_free_water = bool(self._parameterNode.microstructureRunFreeWater)
        run_noddi = bool(self._parameterNode.microstructureRunNoddi)
        force_recompute = bool(self._parameterNode.microstructureForceRecompute)

        missing: List[str] = []
        if not subject:
            missing.append("Subject ID")
        if not input_root:
            missing.append("Microstructure subject directory")
        input_root_path = Path(input_root).expanduser() if input_root else None
        output_dir_path = Path(output_dir).expanduser() if output_dir else None
        roi_path_obj = Path(roi_path).expanduser() if roi_path else None
        if input_root_path and not input_root_path.is_dir():
            missing.append("Microstructure subject directory")
        if roi_path_obj and not roi_path_obj.is_file():
            missing.append("ROI label map")
        if fit_method not in {"wls", "ls"}:
            missing.append("Valid fit method (wls or ls)")

        if missing:
            slicer.util.errorDisplay(
                "Cannot run Microstructure. Please provide the following:\n- " + "\n- ".join(sorted(set(missing))),
                parent=self.parent,
            )
            return

        self.appendLog("Starting Microstructure pipeline...")
        self._setStatus("running", "Microstructure pipeline in progress")
        slicer.util.showStatusMessage("Microstructure pipeline running...", 0)

        with slicer.util.tryWithErrorDisplay("Microstructure pipeline failed.", waitCursor=True):
            self.logic.setupMicrostructureRequirements()
            self.logic.runMicrostructurePipeline(
                subject_id=subject,
                input_root=input_root_path,
                output_dir=output_dir_path,
                roi_label_map=roi_path_obj,
                fit_method=fit_method,
                run_free_water=run_free_water,
                run_noddi=run_noddi,
                force_recompute=force_recompute,
            )

        self.appendLog("Microstructure pipeline completed.")
        self._setStatus("ready", "Pipeline ready")
        slicer.util.showStatusMessage("Microstructure pipeline completed.", 5000)
