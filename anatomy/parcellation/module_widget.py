"""Parcellation workflow widget glue for SlicerDSpace."""

from __future__ import annotations

from pathlib import Path
from typing import List

import slicer


class ParcellationWidgetMixin:
    """Widget handlers for the DDParcel workflow."""

    def _connect_parcellation_ui(self) -> None:
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

    def _onDDParcelSubjectChanged(self, newText: str) -> None:
        self._update_parameter_node("ddparcelSubjectId", newText or "")

    def _onDDParcelInputRootChanged(self, path: str) -> None:
        self._update_parameter_node("ddparcelInputRoot", path or "")

    def _onDDParcelOutputRootChanged(self, path: str) -> None:
        self._update_parameter_node("ddparcelOutputRoot", path or "")

    def _onDDParcelAtlasChanged(self, path: str) -> None:
        self._update_parameter_node("ddparcelAtlasPath", path or "")

    def _onDDParcelFlipChanged(self, value: int) -> None:
        self._update_parameter_node("ddparcelFlip", int(value))

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
            missing.append("DDParcel subject directory")
        if not atlas_path:
            missing.append("Atlas T2")

        input_root_path = Path(input_root).expanduser() if input_root else None
        output_root_path = Path(output_root).expanduser() if output_root else None
        atlas_path_obj = Path(atlas_path).expanduser() if atlas_path else None
        if input_root_path and not input_root_path.is_dir():
            missing.append("DDParcel subject directory")
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

        with slicer.util.tryWithErrorDisplay("DDParcel pipeline failed.", waitCursor=True):
            self.logic.setupDDParcelRequirements()
            self.logic.runDDParcelPipeline(
                subject_id=subject,
                input_root=input_root_path,
                output_root=output_root_path,
                atlas_t2=atlas_path_obj,
                flip=flip,
                device=getattr(self._parameterNode, "ddsegDevice", "auto") or "auto",
            )

        self.appendLog("DDParcel pipeline completed.")
        self._setStatus("ready", "Pipeline ready")
        slicer.util.showStatusMessage("DDParcel pipeline completed.", 5000)
