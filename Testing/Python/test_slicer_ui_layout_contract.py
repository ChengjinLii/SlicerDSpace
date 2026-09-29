from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_PATH = REPO_ROOT / "Resources" / "UI" / "SlicerDDSurfer.ui"
MODULE_WIDGET_PATH = REPO_ROOT / "shared" / "module_widget.py"


def _load_ui() -> ET.Element:
    return ET.parse(UI_PATH).getroot()


def _widget(root: ET.Element, name: str) -> ET.Element:
    for element in root.iter("widget"):
        if element.attrib.get("name") == name:
            return element
    raise AssertionError(f"UI widget not found: {name}")


def _layout(root: ET.Element, name: str) -> ET.Element:
    for element in root.iter("layout"):
        if element.attrib.get("name") == name:
            return element
    raise AssertionError(f"UI layout not found: {name}")


def _property_text(element: ET.Element, property_name: str) -> str:
    for prop in element.findall("property"):
        if prop.attrib.get("name") != property_name:
            continue
        string = prop.find("string")
        if string is not None and string.text is not None:
            return string.text
        boolean = prop.find("bool")
        if boolean is not None and boolean.text is not None:
            return boolean.text
    return ""


class SlicerUiLayoutContractTest(unittest.TestCase):
    def test_main_workflow_sections_follow_workflow_order(self) -> None:
        root = _load_ui()
        expected = [
            ("gettingStartedCollapsibleButton", "Getting started"),
            ("configurationCollapsibleButton", "1. Inputs"),
            ("targetsCollapsibleButton", "2. Targets"),
            ("parametersCollapsibleButton", "3. Route and parameters"),
            ("runCollapsibleButton", "4. Run"),
            ("resultsCollapsibleButton", "5. Results"),
            ("environmentCollapsibleButton", "Advanced: Dependency profile"),
        ]
        top_level = [
            element.attrib.get("name")
            for element in _layout(root, "verticalLayout").findall("item/widget")
            if element.attrib.get("class") == "ctkCollapsibleButton"
        ]
        ordered = [name for name in top_level if name in {name for name, _ in expected}]
        self.assertEqual(ordered, [name for name, _ in expected])
        for name, text in expected:
            self.assertEqual(_property_text(_widget(root, name), "text"), text)
        self.assertEqual(_property_text(_widget(root, "runSelectedButton"), "text"), "Preflight and run")
        self.assertEqual(_property_text(_widget(root, "runSelectedButton"), "styleSheet"), "")

    def test_route_section_holds_backends_and_topup_group(self) -> None:
        root = _load_ui()
        parameters = _widget(root, "parametersCollapsibleButton")
        names = {element.attrib.get("name") for element in parameters.iter("widget")}
        for name in (
            "preprocessingBackendComboBox",
            "topupCollapsibleGroupBox",
            "preprocessingPhaseEncodingDirectionComboBox",
            "preprocessingReadoutTimeSpinBox",
            "preprocessingReversePhaseB0Path",
            "orchestrationTractographyBackendComboBox",
            "orchestrationBundleBackendComboBox",
            "orchestrationMicrostructureStagesComboBox",
            "advancedRunCollapsibleButton",
        ):
            self.assertIn(name, names)
        self.assertEqual(_property_text(_widget(root, "topupCollapsibleGroupBox"), "title"), "Distortion correction (topup)")
        self.assertEqual(_property_text(_widget(root, "preprocessingReadoutTimeLabel"), "text"), "Total readout time (s)")
        self.assertEqual(_property_text(_widget(root, "preprocessingPhaseEncodingDirectionLabel"), "text"), "Phase-encoding direction")
        self.assertEqual(_property_text(_widget(root, "preprocessingReversePhaseB0Label"), "text"), "Reverse-PE b=0 image")
        spin = _widget(root, "preprocessingReadoutTimeSpinBox")
        self.assertEqual(_property_text(spin, "specialValueText"), "Not set")
        # ctkPathLineEdit stops emitting currentPathChanged for .nii.gz when nameFilters are set,
        # which would silently drop the reverse-PE path; suffixes are validated in Python instead.
        reverse = _widget(root, "preprocessingReversePhaseB0Path")
        self.assertNotIn("nameFilters", {prop.attrib.get("name") for prop in reverse.findall("property")})
        # The topup widgets are bound by hand (combo data != label), not via SlicerParameterName.
        for name in ("preprocessingPhaseEncodingDirectionComboBox", "preprocessingReadoutTimeSpinBox", "preprocessingReversePhaseB0Path"):
            self.assertEqual(_property_text(_widget(root, name), "SlicerParameterName"), "")

    def test_tab_order_covers_the_main_workflow(self) -> None:
        root = _load_ui()
        stops = [element.text for element in root.findall("tabstops/tabstop")]
        for earlier, later in (
            ("subjectIdLineEdit", "inputDirectoryPath"),
            ("inputDirectoryPath", "targetPreprocessingCheckBox"),
            ("targetConnectomeCheckBox", "preprocessingBackendComboBox"),
            ("preprocessingBackendComboBox", "preprocessingPhaseEncodingDirectionComboBox"),
            ("preprocessingReversePhaseB0Path", "runSelectedButton"),
        ):
            self.assertLess(stops.index(earlier), stops.index(later))
        widget_names = {element.attrib.get("name") for element in root.iter("widget")}
        self.assertTrue(set(stops) <= widget_names)

    def test_forms_wrap_long_rows_for_narrow_panels(self) -> None:
        root = _load_ui()
        for name in ("configurationFormLayout", "targetProductsFormLayout", "parametersFormLayout", "topupFormLayout", "advancedRunFormLayout"):
            layout = _layout(root, name)
            policies = {prop.attrib.get("name"): prop.findtext("enum") for prop in layout.findall("property")}
            self.assertEqual(policies.get("rowWrapPolicy"), "QFormLayout::WrapLongRows", name)

    def test_advanced_sections_are_collapsed_by_default(self) -> None:
        root = _load_ui()
        environment = _widget(root, "environmentCollapsibleButton")
        advanced = _widget(root, "advancedRunCollapsibleButton")
        self.assertEqual(_property_text(environment, "text"), "Advanced: Dependency profile")
        self.assertEqual(_property_text(environment, "collapsed"), "true")
        self.assertEqual(
            _property_text(advanced, "text"),
            "Analysis settings",
        )
        self.assertEqual(_property_text(advanced, "collapsed"), "true")
        self.assertIsNotNone(_layout(root, "advancedRunFormLayout"))

    def test_native_surface_and_freesurfer_postprocess_are_distinct_targets(self) -> None:
        root = _load_ui()
        native_surface = _widget(root, "targetSurfaceCheckBox")
        postprocess = _widget(root, "targetSurfacePostprocessCheckBox")

        self.assertIn("native", _property_text(native_surface, "text").lower())
        self.assertIn("does not create a complete FreeSurfer subject", _property_text(native_surface, "toolTip"))
        self.assertEqual(_property_text(postprocess, "checked"), "false")
        self.assertEqual(_property_text(postprocess, "SlicerParameterName"), "targetSurfacePostprocess")
        self.assertIn("complete FreeSurfer installation", _property_text(postprocess, "toolTip"))
        self.assertIn("Surface and Parcellation", _property_text(postprocess, "toolTip"))

    def test_surface_postprocess_target_is_restored_from_json_defaults(self) -> None:
        source = MODULE_WIDGET_PATH.read_text(encoding="utf-8")
        self.assertIn('targets_configured = "targets" in defaults', source)
        self.assertIn("if targets_configured:", source)
        self.assertIn(
            'node.targetSurfacePostprocess = "surface_postprocess" in targets',
            source,
        )


if __name__ == "__main__":
    unittest.main()
