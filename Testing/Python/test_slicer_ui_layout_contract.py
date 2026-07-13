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
    def test_main_workflow_is_three_step(self) -> None:
        root = _load_ui()
        self.assertEqual(_property_text(_widget(root, "configurationCollapsibleButton"), "text"), "Run workflow")
        self.assertEqual(_property_text(_widget(root, "configurationSectionLabel"), "text"), "<b>1. Choose input</b>")
        self.assertEqual(_property_text(_widget(root, "targetsSectionLabel"), "text"), "<b>2. Choose products</b>")
        self.assertEqual(_property_text(_widget(root, "runStepSectionLabel"), "text"), "<b>3. Run</b>")
        self.assertEqual(_property_text(_widget(root, "runSelectedButton"), "text"), "Preflight and run")

    def test_advanced_sections_are_collapsed_by_default(self) -> None:
        root = _load_ui()
        environment = _widget(root, "environmentCollapsibleButton")
        advanced = _widget(root, "advancedRunCollapsibleButton")
        self.assertEqual(_property_text(environment, "text"), "Advanced: Dependency profile")
        self.assertEqual(_property_text(environment, "collapsed"), "true")
        self.assertEqual(
            _property_text(advanced, "text"),
            "Advanced settings: backends, batch, streamlines",
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
