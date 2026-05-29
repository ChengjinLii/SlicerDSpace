"""Surface workflow widget glue for SlicerDDSurfer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import slicer

from shared import inspect_subject_directory

LOGGER = logging.getLogger(__name__)


class SurfaceWidgetMixin:
    """Widget handlers for the surface workflow and its post-processing tools."""

    def _connect_surface_ui(self) -> None:
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

    def _onOutputDirectoryChanged(self, newPath: str) -> None:
        if not self._update_parameter_node("outputDirectory", newPath or ""):
            return
        self._checkCanApply()

    def _onInputDirectoryChanged(self, newPath: str) -> None:
        if not self._update_parameter_node("inputDirectory", newPath or ""):
            return
        self._checkCanApply()

    def _onPredictModeChanged(self, newText: str) -> None:
        if not self._update_parameter_node("predictMode", newText or "all"):
            return
        self._checkCanApply()

    def _onDeviceChanged(self, newText: str) -> None:
        if not self._update_parameter_node("device", newText or "cpu"):
            return
        self._checkCanApply()

    def _onPostprocessSubjectChanged(self, newText: str) -> None:
        self._update_parameter_node("postprocessSubjectId", newText or "")

    def _onPostprocessNativeDirChanged(self, path: str) -> None:
        self._update_parameter_node("postprocessNativeDir", path or "")

    def _onPostprocessMriDirChanged(self, path: str) -> None:
        self._update_parameter_node("postprocessMriDir", path or "")

    def _onPostprocessRepoChanged(self, path: str) -> None:
        self._update_parameter_node("postprocessRepoDir", path or "")

    def _onPostprocessLicenseChanged(self, path: str) -> None:
        self._update_parameter_node("postprocessLicensePath", path or "")

    def _onPostprocessModeChanged(self, text: str) -> None:
        self._update_parameter_node("postprocessMode", text or "whole")

    def _onPostprocessImageChanged(self, text: str) -> None:
        self._update_parameter_node("postprocessDockerImage", text or "")

    def _onPostprocessForceToggled(self, state: bool) -> None:
        self._update_parameter_node("postprocessForce", bool(state))

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

        if not input_dir_str:
            missing.append("Subject directory")
            return False, missing

        candidate = Path(input_dir_str).expanduser()
        if not candidate.is_dir():
            missing.append("Subject directory")
            return False, missing

        inspected = inspect_subject_directory(candidate, subject_id) if subject_id else {"mode": "missing"}
        mode = inspected.get("mode")
        if mode == "missing":
            missing.append("Subject input layout")
        elif mode == "legacy_registered":
            if not output_dir_str:
                missing.append("Output directory")
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
            subject_dir = Path(inspected["subject_dir"])
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
            file_errors = any(
                entry.startswith(prefix)
                for entry in missing
                if entry.endswith(".nii.gz") or entry.endswith(".tfm")
            )
        self._setWidgetError(
            getattr(self.ui, "inputDirectoryPath", None),
            any(token in missing for token in ("Subject directory", "Subject input layout", subject_token))
            or file_errors,
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
