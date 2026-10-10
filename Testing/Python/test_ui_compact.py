"""Pure contracts for concise labels and pending-input presentation."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from shared.ui_compact import apply_compact_language
from shared.ui_onboarding import translated_ui_message


class Text:
    def setText(self, value):
        self.text = value

    def setToolTip(self, value):
        self.tooltip = value


class CompactUiTest(unittest.TestCase):
    def test_language_changes_presentation_not_analysis_state(self):
        names = ("headlineLabel", "configurationCollapsibleButton", "targetsCollapsibleButton",
                 "parametersCollapsibleButton", "environmentCollapsibleButton", "resultsCollapsibleButton",
                 "runSelectedButton", "logHintLabel", "targetPreprocessingCheckBox", "targetSurfaceCheckBox",
                 "targetSurfacePostprocessCheckBox", "targetParcellationCheckBox", "targetSegmentationCheckBox",
                 "targetMicrostructureCheckBox", "targetTractographyCheckBox", "targetBundlesCheckBox",
                 "targetConnectomeCheckBox")
        ui = SimpleNamespace(**{name: Text() for name in names})
        ui.targetSurfaceCheckBox.checked = True
        node = SimpleNamespace(orchestrationSelectStreamlines=1000000)
        owner = SimpleNamespace(ui=ui, _advancedSettingsPanel=Text(), _parameterNode=node,
                                _onboardingWidgets={"language_combo": Text()},
                                _prepareInputWidgets={"panel": Text()})
        for language, advanced, run, log in (("en", "Advanced settings", "Run SlicerDDSurfer", "Log"),
                                           ("zh", "高级设置", "运行 SlicerDDSurfer", "日志")):
            apply_compact_language(owner, language)
            self.assertEqual(owner._advancedSettingsPanel.text, advanced)
            self.assertEqual(ui.runSelectedButton.text, run)
            self.assertEqual(ui.logHintLabel.text, log)
            self.assertEqual(ui.headlineLabel.text, "SlicerDDSurfer")
            self.assertIn("import" if language == "en" else "导入", owner._prepareInputWidgets["panel"].text)
            self.assertTrue(ui.targetSurfaceCheckBox.checked)
            self.assertEqual(node.orchestrationSelectStreamlines, 1000000)

    def test_pending_input_status_switches_both_directions(self):
        english = "Waiting: Subject ID; Subject directory"
        chinese = "待填写：受试者 ID; 受试者目录"
        self.assertEqual(translated_ui_message("zh", english), chinese)
        self.assertEqual(translated_ui_message("en", chinese), english)

    def test_empty_inputs_are_neutral_until_manual_validation(self):
        path = Path(__file__).resolve().parents[2] / "anatomy/surface/module_widget.py"
        method = next(node for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if
                      isinstance(node, ast.FunctionDef) and node.name == "validateInputs")
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
        updates = []
        statuses = []
        owner = SimpleNamespace(_evaluateInputs=lambda: (False, ["Subject ID", "Subject directory"]),
            _pipelineActive=False, _parameterNode=None, _lastStatusMessage="pending",
            ui=SimpleNamespace(subjectIdLineEdit="id", inputDirectoryPath="input", outputDirectoryPath="output"),
            _setStatus=lambda *args: statuses.append(args), appendLog=lambda *args: None,
            _summarise_missing=lambda *args: "pending", _setWidgetError=lambda *args: updates.append(args))
        validate = namespace["validateInputs"]
        self.assertFalse(validate(owner))
        self.assertFalse(any(error for widget, error in updates))
        self.assertEqual(statuses[-1][0], "waiting")
        updates.clear()
        self.assertFalse(validate(owner, manual=True))
        self.assertIn(("id", True), updates)
        self.assertIn(("input", True), updates)
        self.assertEqual(statuses[-1][0], "error")
        self.assertFalse(validate(owner))
        self.assertEqual(statuses[-1][0], "error")
        owner._evaluateInputs = lambda: (True, [])
        self.assertTrue(validate(owner))
        self.assertEqual(statuses[-1][0], "ready")
        self.assertFalse(owner._inputValidationAttempted)

    def test_invalid_run_click_returns_before_setup_or_launch(self):
        path = Path(__file__).resolve().parents[2] / "shared/module_widget.py"
        method = next(node for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if
                      isinstance(node, ast.FunctionDef) and node.name == "_onRunSelectedClicked")
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
        statuses = []
        validations = []
        owner = SimpleNamespace(_pipelineActive=False, logic=object(),
            _parameterNode=SimpleNamespace(batchMode=False, inputDirectory=""),
            validateInputs=lambda **kwargs: validations.append(kwargs) or False,
            _setStatus=lambda *args: statuses.append(args),
            _summarise_missing=lambda entries: "Waiting: " + "; ".join(entries))
        click = namespace["_onRunSelectedClicked"]
        click(owner)
        self.assertEqual(validations, [{"manual": True}])
        owner._parameterNode.batchMode = True
        click(owner)
        self.assertEqual(statuses[-1], ("error", "Waiting: Batch root"))
        owner._parameterNode.batchMode = False
        owner.validateInputs = lambda **kwargs: True
        owner._selected_workflows = lambda: []
        click(owner)
        self.assertEqual(statuses[-1], ("error", "Waiting: Target products"))
        owner._pipelineActive = True
        owner.validateInputs = lambda **kwargs: self.fail("Active run must not revalidate or start")
        click(owner)


if __name__ == "__main__":
    unittest.main()
