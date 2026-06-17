from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_PATH = REPO_ROOT / "Resources" / "UI" / "SlicerDDSurfer.ui"


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


if __name__ == "__main__":
    unittest.main()
