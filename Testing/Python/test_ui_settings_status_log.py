#!/usr/bin/env python3
"""Tests for widget settings/status helper modules."""

from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from shared.ui_settings import (coerce_user_setting_value, common_user_setting_specs,
                                mark_new_parameter_node, consume_user_defaults_request, SETTINGS_STATE_ATTRIBUTE)
from shared.ui_status_log import set_existing_report_path, append_log


class ParameterNode:
    def __init__(self, parameters=()):
        self.parameters = parameters
        self.attributes = {}

    def GetParameterNames(self):
        return self.parameters

    def GetAttribute(self, name):
        return self.attributes.get(name)

    def SetAttribute(self, name, value):
        self.attributes[name] = value


class LogWidget:
    def __init__(self, position=100):
        self.bar = SimpleNamespace(value=position, maximum=100)
        self.bar.setValue = lambda value: setattr(self.bar, 'value', value)
        self.insertions = []
        self.followed = False

    def verticalScrollBar(self):
        return self.bar

    def appendHtml(self, text):
        self.insertions.append(text)
        self.bar.maximum += 1
        self.bar.value = self.bar.maximum

    def ensureCursorVisible(self):
        self.followed = True


class UISettingsStatusLogTest(unittest.TestCase):
    def test_user_defaults_only_apply_once_to_new_nodes(self):
        raw = ParameterNode()
        mark_new_parameter_node(raw)
        self.assertEqual(raw.GetAttribute(SETTINGS_STATE_ATTRIBUTE), 'pending')
        wrapped = SimpleNamespace(parameterNode=raw)
        self.assertTrue(consume_user_defaults_request(wrapped))
        raw.parameters = ('subjectId',)
        mark_new_parameter_node(raw)
        self.assertFalse(consume_user_defaults_request(wrapped))
        pending = ParameterNode()
        mark_new_parameter_node(pending)
        configured = SimpleNamespace(parameterNode=pending, allParameters=('subjectId',),
                                     getValue=lambda name: 'configured-before-gui',
                                     default=lambda name: SimpleNamespace(value=''))
        self.assertFalse(consume_user_defaults_request(configured))

    def test_existing_legacy_scene_keeps_parameters_without_new_marker(self):
        raw = ParameterNode(('subjectId', 'orchestrationTractographyBackend'))
        mark_new_parameter_node(raw)
        self.assertFalse(consume_user_defaults_request(SimpleNamespace(parameterNode=raw)))
        self.assertEqual(raw.attributes, {})

    def test_log_chunk_is_one_escaped_insertion_and_preserves_reading_position(self):
        for position in (0, 40, 100):
            log = LogWidget(position)
            owner = SimpleNamespace(ui=SimpleNamespace(logPlainTextEdit=log),
                                    _lastProcessEventsAt=0, _trim_log_widget=lambda widget: None)
            with patch.dict(sys.modules, {'slicer': SimpleNamespace(app=SimpleNamespace(processEvents=lambda: None))}):
                append_log(owner, 'first <line>\nWARNING: second line\nlast line')
            self.assertEqual(len(log.insertions), 1)
            self.assertEqual(log.insertions[0].count('<p '), 3)
            self.assertIn('&lt;line&gt;', log.insertions[0])
            self.assertEqual(log.followed, position == 100)
            if position < 100:
                self.assertEqual(log.bar.value, position)

    def test_blank_lines_keep_the_original_insertion_path(self):
        log = LogWidget()
        owner = SimpleNamespace(ui=SimpleNamespace(logPlainTextEdit=log),
                                _lastProcessEventsAt=0, _trim_log_widget=lambda widget: None)
        with patch.dict(sys.modules, {'slicer': SimpleNamespace(app=SimpleNamespace(processEvents=lambda: None))}):
            append_log(owner, 'first\n\nlast')
        self.assertEqual(len(log.insertions), 3)
        self.assertNotIn('<p ', ''.join(log.insertions))

    def test_common_user_setting_specs_include_run_and_target_state(self) -> None:
        names = [name for name, _value_type in common_user_setting_specs()]

        self.assertIn("orchestrationRunName", names)
        self.assertIn("batchMode", names)
        self.assertIn("targetTractography", names)

    def test_coerce_user_setting_values(self) -> None:
        self.assertTrue(coerce_user_setting_value("true", bool))
        self.assertFalse(coerce_user_setting_value("0", bool))
        self.assertEqual(coerce_user_setting_value("7", int), 7)
        self.assertEqual(coerce_user_setting_value(None, str), "")

    def test_set_existing_report_path_updates_button_state(self) -> None:
        owner = SimpleNamespace(_button=SimpleNamespace(enabled=False))
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.html"
            report.write_text("report", encoding="utf-8")

            set_existing_report_path(owner, "_report", "_button", report)

        self.assertEqual(owner._report, report)
        self.assertTrue(owner._button.enabled)

    def test_set_existing_report_path_clears_missing_path(self) -> None:
        owner = SimpleNamespace(_button=SimpleNamespace(enabled=True))

        set_existing_report_path(owner, "_report", "_button", "/missing/report.html")

        self.assertIsNone(owner._report)
        self.assertFalse(owner._button.enabled)


if __name__ == "__main__":
    unittest.main()
