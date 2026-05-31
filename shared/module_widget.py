"""Common scripted-module widget glue for SlicerDDSurfer."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

import slicer
import vtk
from qt import QFrame, QHBoxLayout, QLabel, QPixmap, QPushButton, QSignalBlocker

from workflow_catalog import NAVIGATION_WORKFLOW_AREAS


class SharedWidgetMixin:
    """Shared UI helpers used across the unified SlicerDDSurfer widget."""

    def _connect_common_ui(self) -> None:
        if hasattr(self.ui, "runSelectedButton"):
            self.ui.runSelectedButton.connect("clicked()", self._onRunSelectedClicked)
        if hasattr(self.ui, "validateButton"):
            self.ui.validateButton.connect("clicked()", self._onValidateClicked)
        if hasattr(self.ui, "clearLogButton"):
            self.ui.clearLogButton.connect("clicked()", self._onClearLogClicked)

    def _initialize_common_ui_state(self) -> None:
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
        label = QLabel("Choose product workflow:")
        label.setStyleSheet("font-weight: 600; color: #263238;")
        layout.addWidget(label)

        buttons = [(area.navigation_label, area.navigation_target) for area in NAVIGATION_WORKFLOW_AREAS]
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
        if not self._parameterNode:
            return

        if not (self._parameterNode.ddparcelAtlasPath or "").strip():
            atlas_path = self.resourcePath("Data/100HCP-population-mean-T2.nii.gz")
            if atlas_path and os.path.exists(atlas_path):
                self._parameterNode.ddparcelAtlasPath = atlas_path

        ddseg_weights_dir = self.logic.segmentation_dir / "weights"
        if not (self._parameterNode.ddsegWeightsDir or "").strip() and ddseg_weights_dir.is_dir():
            self._parameterNode.ddsegWeightsDir = ddseg_weights_dir.as_posix()

        slicer_base = self._default_slicer_base_dir()
        if not (self._parameterNode.ddsegSlicerBase or "").strip() and slicer_base is not None:
            self._parameterNode.ddsegSlicerBase = slicer_base.as_posix()

        slicer_dmri = self._default_slicerdmri_dir()
        if not (self._parameterNode.ddsegSlicerExt or "").strip() and slicer_dmri is not None:
            self._parameterNode.ddsegSlicerExt = slicer_dmri.as_posix()

    def _default_slicer_base_dir(self) -> Optional[Path]:
        app = getattr(slicer, "app", None)
        if app is None:
            return None
        try:
            return Path(str(app.slicerHome)).resolve()
        except Exception:
            return None

    def _default_slicerdmri_dir(self) -> Optional[Path]:
        slicer_base = self._default_slicer_base_dir()
        if slicer_base is None:
            return None
        extensions_root = slicer_base / "slicer.org"
        if not extensions_root.is_dir():
            return None
        for candidate in sorted(extensions_root.glob("Extensions-*/*")):
            if candidate.is_dir() and candidate.name == "SlicerDMRI":
                return candidate.resolve()
        return None

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
        if target == "LOCAL_DDSURFER":
            try:
                slicer.util.selectModule("SlicerDDSurfer")
                if hasattr(self, "ui") and getattr(self.ui, "configurationCollapsibleButton", None):
                    self.ui.configurationCollapsibleButton.collapsed = False
            except Exception:
                pass
            slicer.util.showStatusMessage("Jumped to DDSurfer configuration", 3000)
            return

        if target == "LOCAL_MICROSTRUCTURE":
            try:
                slicer.util.selectModule("SlicerDDSurfer")
                panel = getattr(self.ui, "microstructureCollapsibleButton", None)
                if panel:
                    panel.collapsed = False
                    panel.raise_()
            except Exception:
                pass
            slicer.util.showStatusMessage("Jumped to microstructure workflow", 3000)
            return

        try:
            slicer.util.selectModule(target)
            slicer.util.showStatusMessage(f"Jumped to {target}", 3000)
        except Exception:
            slicer.util.infoDisplay(f"Module {target} not installed or not yet implemented. Coming soon.")

    def setParameterNode(self, inputParameterNode) -> None:
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._checkCanApply()

    def _sync_path_widget(self, widget, desired: str) -> None:
        if not widget or widget.currentPath == desired:
            return
        blocker = QSignalBlocker(widget)
        widget.setCurrentPath(desired)
        del blocker

    def _sync_line_edit(self, widget, desired: str) -> None:
        if not widget:
            return
        current_text = widget.text() if callable(getattr(widget, "text", None)) else widget.text
        if current_text == desired:
            return
        blocker = QSignalBlocker(widget)
        widget.setText(desired)
        del blocker

    def _sync_combo_text(self, widget, desired: str, *, via_index: bool = True) -> None:
        if not widget or widget.currentText == desired:
            return
        blocker = QSignalBlocker(widget)
        if via_index:
            index = widget.findText(desired)
            if index >= 0:
                widget.setCurrentIndex(index)
        else:
            widget.setCurrentText(desired)
        del blocker

    def _sync_checkbox(self, widget, desired: bool) -> None:
        if not widget or widget.isChecked() == desired:
            return
        blocker = QSignalBlocker(widget)
        widget.setChecked(desired)
        del blocker

    def _sync_spinbox(self, widget, desired: int) -> None:
        if not widget or widget.value == desired:
            return
        blocker = QSignalBlocker(widget)
        widget.value = desired
        del blocker

    def _checkCanApply(self, caller=None, event=None) -> None:
        node = self._parameterNode
        if node:
            self._sync_path_widget(getattr(self.ui, "inputDirectoryPath", None), node.inputDirectory or "")
            self._sync_path_widget(getattr(self.ui, "outputDirectoryPath", None), node.outputDirectory or "")
            self._sync_combo_text(getattr(self.ui, "predictModeComboBox", None), node.predictMode or "all")
            self._sync_combo_text(getattr(self.ui, "deviceComboBox", None), node.device or "cpu")

            self._sync_line_edit(getattr(self.ui, "postprocessSubjectLineEdit", None), node.postprocessSubjectId or "")
            self._sync_path_widget(getattr(self.ui, "postprocessNativePath", None), node.postprocessNativeDir or "")
            self._sync_path_widget(getattr(self.ui, "postprocessMriPath", None), node.postprocessMriDir or "")
            self._sync_path_widget(getattr(self.ui, "postprocessRepoPath", None), node.postprocessRepoDir or "")
            self._sync_path_widget(getattr(self.ui, "postprocessLicensePath", None), node.postprocessLicensePath or "")
            self._sync_combo_text(
                getattr(self.ui, "postprocessModeComboBox", None),
                node.postprocessMode or "whole",
            )
            self._sync_line_edit(getattr(self.ui, "postprocessImageLineEdit", None), node.postprocessDockerImage or "")
            self._sync_checkbox(getattr(self.ui, "postprocessForceCheckBox", None), bool(node.postprocessForce))

            self._sync_line_edit(getattr(self.ui, "ddparcelSubjectLineEdit", None), node.ddparcelSubjectId or "")
            self._sync_path_widget(getattr(self.ui, "ddparcelInputRootPath", None), node.ddparcelInputRoot or "")
            self._sync_path_widget(getattr(self.ui, "ddparcelOutputRootPath", None), node.ddparcelOutputRoot or "")
            self._sync_path_widget(getattr(self.ui, "ddparcelAtlasPath", None), node.ddparcelAtlasPath or "")
            self._sync_spinbox(getattr(self.ui, "ddparcelFlipSpinBox", None), int(node.ddparcelFlip))

            self._sync_line_edit(
                getattr(self.ui, "microstructureSubjectLineEdit", None),
                node.microstructureSubjectId or "",
            )
            self._sync_path_widget(
                getattr(self.ui, "microstructureInputRootPath", None),
                node.microstructureInputRoot or "",
            )
            self._sync_path_widget(
                getattr(self.ui, "microstructureOutputPath", None),
                node.microstructureOutputDir or "",
            )
            self._sync_path_widget(getattr(self.ui, "microstructureRoiPath", None), node.microstructureRoiPath or "")
            self._sync_combo_text(
                getattr(self.ui, "microstructureFitComboBox", None),
                (node.microstructureFitMethod or "wls").lower(),
            )
            self._sync_checkbox(
                getattr(self.ui, "microstructureRunFreeWaterCheckBox", None),
                bool(node.microstructureRunFreeWater),
            )
            self._sync_checkbox(
                getattr(self.ui, "microstructureRunNoddiCheckBox", None),
                bool(node.microstructureRunNoddi),
            )
            self._sync_checkbox(
                getattr(self.ui, "microstructureForceRecomputeCheckBox", None),
                bool(node.microstructureForceRecompute),
            )

            self._sync_path_widget(getattr(self.ui, "ddsegMaskPath", None), node.ddsegMaskPath or "")
            self._sync_path_widget(getattr(self.ui, "ddsegDwiPath", None), node.ddsegDwiPath or "")
            self._sync_path_widget(getattr(self.ui, "ddsegBvalPath", None), node.ddsegBvalPath or "")
            self._sync_path_widget(getattr(self.ui, "ddsegBvecPath", None), node.ddsegBvecPath or "")
            self._sync_path_widget(getattr(self.ui, "ddsegOutputPath", None), node.ddsegOutputDir or "")
            self._sync_path_widget(getattr(self.ui, "ddsegWeightsPath", None), node.ddsegWeightsDir or "")
            self._sync_path_widget(getattr(self.ui, "ddsegSlicerBasePath", None), node.ddsegSlicerBase or "")
            self._sync_path_widget(getattr(self.ui, "ddsegSlicerExtPath", None), node.ddsegSlicerExt or "")
            self._sync_combo_text(
                getattr(self.ui, "ddsegDeviceComboBox", None),
                node.ddsegDevice or "cpu",
                via_index=False,
            )
            self._sync_checkbox(getattr(self.ui, "ddsegSoftmaxCheckBox", None), bool(node.ddsegApplySoftmax))
            self._sync_checkbox(getattr(self.ui, "targetPreprocessingCheckBox", None), bool(node.targetPreprocessing))
            self._sync_combo_text(
                getattr(self.ui, "preprocessingBackendComboBox", None),
                node.preprocessingBackend or "dipy",
                via_index=False,
            )
            self._sync_line_edit(getattr(self.ui, "orchestrationRunNameLineEdit", None), node.orchestrationRunName or "")
            self._sync_spinbox(
                getattr(self.ui, "orchestrationSelectStreamlinesSpinBox", None),
                int(node.orchestrationSelectStreamlines),
            )
            self._sync_combo_text(
                getattr(self.ui, "connectomeBackendComboBox", None),
                node.connectomeBackend or "python",
                via_index=False,
            )
            self._sync_checkbox(
                getattr(self.ui, "connectomeCompressMrtrixDenseCheckBox", None),
                bool(node.connectomeCompressMrtrixDense),
            )
            self._sync_checkbox(getattr(self.ui, "targetSurfaceCheckBox", None), bool(node.targetSurface))
            self._sync_checkbox(getattr(self.ui, "targetParcellationCheckBox", None), bool(node.targetParcellation))
            self._sync_checkbox(getattr(self.ui, "targetSegmentationCheckBox", None), bool(node.targetSegmentation))
            self._sync_checkbox(getattr(self.ui, "targetMicrostructureCheckBox", None), bool(node.targetMicrostructure))
            self._sync_checkbox(getattr(self.ui, "targetTractographyCheckBox", None), bool(node.targetTractography))
            self._sync_checkbox(getattr(self.ui, "targetBundlesCheckBox", None), bool(node.targetBundles))
            self._sync_checkbox(getattr(self.ui, "targetConnectomeCheckBox", None), bool(node.targetConnectome))

        self.validateInputs(manual=False)

    def _update_parameter_node(self, attribute: str, value: Any) -> bool:
        if not self._parameterNode:
            return False
        with slicer.util.NodeModify(self._parameterNode):
            setattr(self._parameterNode, attribute, value)
        return True

    def appendLog(self, text: str) -> None:
        if hasattr(self.ui, "logPlainTextEdit"):
            self.ui.logPlainTextEdit.appendPlainText(text)
            self.ui.logPlainTextEdit.ensureCursorVisible()

    def _onClearLogClicked(self) -> None:
        if hasattr(self.ui, "logPlainTextEdit"):
            self.ui.logPlainTextEdit.clear()

    def _selected_workflows(self) -> list[str]:
        node = self._parameterNode
        if not node:
            return []
        selected: list[str] = []
        if bool(node.targetPreprocessing):
            selected.append("DWI Preprocessing")
        if bool(node.targetSurface):
            selected.append("Surface / DDSurfer")
        if bool(node.targetParcellation):
            selected.append("Parcellation / DDParcel")
        if bool(node.targetSegmentation):
            selected.append("Segmentation / DDSeg")
        if bool(node.targetMicrostructure):
            selected.append("Microstructure")
        if bool(node.targetTractography):
            selected.append("Tractography")
        if bool(node.targetBundles):
            selected.append("Bundles")
        if bool(node.targetConnectome):
            selected.append("Connectome")
        return selected

    def _selected_orchestrator_targets(self) -> tuple[str, ...]:
        node = self._parameterNode
        if not node:
            return ()
        targets = ["validation"]
        if bool(node.targetSegmentation):
            targets.append("segmentation")
        if bool(node.targetParcellation):
            targets.append("parcellation")
        if bool(node.targetMicrostructure):
            targets.append("microstructure")
        if bool(node.targetTractography):
            targets.append("tractography")
        if bool(node.targetBundles):
            targets.append("bundles")
        if bool(node.targetConnectome):
            targets.append("connectome")
        return tuple(targets)

    def _apply_shared_inputs_to_workflow_fields(self) -> None:
        """Populate empty product-specific fields from the shared subject setup."""
        node = self._parameterNode
        if not node:
            return
        subject_id = (node.subjectId or "").strip()
        subject_root = (node.inputDirectory or "").strip()
        with slicer.util.NodeModify(node):
            if subject_id:
                if not (node.ddparcelSubjectId or "").strip():
                    node.ddparcelSubjectId = subject_id
                if not (node.microstructureSubjectId or "").strip():
                    node.microstructureSubjectId = subject_id
            if subject_root:
                if not (node.ddparcelInputRoot or "").strip():
                    node.ddparcelInputRoot = subject_root
                if not (node.microstructureInputRoot or "").strip():
                    node.microstructureInputRoot = subject_root
                if not (node.ddsegDwiPath or "").strip():
                    node.ddsegDwiPath = subject_root

    def _onRunSelectedClicked(self) -> None:
        if not self._parameterNode or not self.logic:
            return
        selected = self._selected_workflows()
        if not selected:
            slicer.util.errorDisplay("Select at least one target product to run.", parent=self.parent)
            return

        self._apply_shared_inputs_to_workflow_fields()
        self.appendLog("Running selected products: " + ", ".join(selected))
        self._setPipelineActive(True)
        try:
            if bool(self._parameterNode.targetPreprocessing):
                output_dir_text = (self._parameterNode.outputDirectory or "").strip()
                self.logic.runDwiPreprocessingPipeline(
                    subject_id=(self._parameterNode.subjectId or "").strip(),
                    input_root=Path((self._parameterNode.inputDirectory or "").strip()).expanduser(),
                    output_dir=Path(output_dir_text).expanduser() if output_dir_text else None,
                    backend=(self._parameterNode.preprocessingBackend or "dipy").strip(),
                    execute=True,
                    skip=False,
                )
            if bool(self._parameterNode.targetSurface):
                self.onApplyButton()
            orchestrator_targets = self._selected_orchestrator_targets()
            if any(target != "validation" for target in orchestrator_targets):
                subject_root = Path((self._parameterNode.inputDirectory or "").strip()).expanduser()
                output_root_text = (self._parameterNode.outputDirectory or "").strip()
                subject_id = (self._parameterNode.subjectId or "").strip()
                run_name = (self._parameterNode.orchestrationRunName or "csd_act_ui").strip() or "csd_act_ui"
                self.logic.runSelectedProductOrchestration(
                    subject_id=subject_id,
                    subject_root=subject_root,
                    output_root=Path(output_root_text).expanduser() if output_root_text else None,
                    targets=orchestrator_targets,
                    run_name=run_name,
                    execute=True,
                    resume=True,
                    select_streamlines=max(1, int(self._parameterNode.orchestrationSelectStreamlines)),
                    connectome_backend=(self._parameterNode.connectomeBackend or "python").strip(),
                    connectome_compress_mrtrix_dense=bool(self._parameterNode.connectomeCompressMrtrixDense),
                )
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
        ui_ready = self.validateInputs(manual=False)
        node = self._parameterNode
        if not node or not self.logic:
            self.appendLog("Validation failed. Parameter node or logic is unavailable.")
            self._setStatus("error", "Validation failed")
            return

        subject_id = (node.subjectId or "").strip()
        input_root = (node.inputDirectory or "").strip()
        output_dir = (node.outputDirectory or "").strip()
        if not subject_id or not input_root:
            self.appendLog("Validation failed. Subject ID and subject directory are required.")
            self._setStatus("error", "Validation failed")
            return

        try:
            inspected = self.logic._resolve_subject_input(Path(input_root).expanduser(), subject_id)
        except Exception as exc:
            self.appendLog(f"Validation failed. Unable to resolve input layout: {exc}")
            self._setStatus("error", "Validation failed")
            return

        if inspected.get("mode") != "subject_root":
            if ui_ready:
                self.appendLog(
                    "Validation succeeded for legacy registered input. "
                    "Shared DWI import QC is only available for subject-root/input layouts."
                )
                self._setStatus("ready", "Validation passed")
            else:
                self.appendLog("Validation failed. Legacy registered input is incomplete.")
                self._setStatus("error", "Validation failed")
            return

        self.appendLog("Starting shared input validation / QC...")
        try:
            result = self.logic.runInputValidation(
                subject_id=subject_id,
                input_root=Path(input_root).expanduser(),
                output_dir=Path(output_dir).expanduser() if output_dir else None,
                dependency_groups=("core", "microstructure", "tractography"),
                require_phase_encoding=False,
            )
        except Exception as exc:
            self.appendLog(f"Validation failed: {exc}")
            self._setStatus("error", "Validation failed")
            return

        report = result.report_path.as_posix() if result.report_path else "not written"
        self.appendLog(
            f"Validation {result.status}: {result.error_count} error(s), "
            f"{result.warning_count} warning(s)."
        )
        self.appendLog(f"Validation report: {report}")
        for issue in result.messages:
            detail = f" {issue.details}" if issue.details else ""
            self.appendLog(f"[{issue.level.upper()}] {issue.category}: {issue.message}{detail}")

        if result.passed and ui_ready:
            self._setStatus("ready", "Validation passed")
        elif result.passed:
            self._setStatus("error", "Validation passed with legacy input warning")
        else:
            self._setStatus("error", "Validation failed")

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
