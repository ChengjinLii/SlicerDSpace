"""Preparation recovery stores state, not permission to install or run analysis."""

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from shared.setup_resume import complete_setup, pending_setup, refresh_setup_button, remember_setup


class SetupResumeTests(unittest.TestCase):
    def test_restart_recovery_and_clear_are_request_scoped(self):
        with tempfile.TemporaryDirectory() as tmp, patch('shared.setup_resume.pending_path', return_value=Path(tmp) / 'pending.json'):
            self.assertIsNone(pending_setup())
            remember_setup('request-one')
            self.assertEqual(pending_setup()['request'], 'request-one')
            remember_setup('request-two')
            complete_setup('request-one')
            self.assertEqual(pending_setup()['request'], 'request-two')
            complete_setup('request-two')
            self.assertIsNone(pending_setup())

    def test_invalid_marker_does_not_offer_execution(self):
        with tempfile.TemporaryDirectory() as tmp, patch('shared.setup_resume.pending_path', return_value=Path(tmp) / 'pending.json'):
            for payload in ('broken', '[]', json.dumps({'kind': 'slicerddsurfer_pending_setup', 'request': '../outside'})):
                (Path(tmp) / 'pending.json').write_text(payload)
                self.assertIsNone(pending_setup())
            with self.assertRaises(ValueError):
                remember_setup('../outside')

    def test_resume_caption_reuses_existing_button_and_translation_binding(self):
        button = SimpleNamespace(setText=lambda text: setattr(button, 'text', text))
        owner = SimpleNamespace(_managedRuntimeSetupButton=button, _onboardingLanguage='en',
                                _uiLanguageBindings=[(button, 'text', 'managed_runtime_setup')])
        with patch('shared.setup_resume.pending_setup', return_value={'request': 'one'}):
            refresh_setup_button(owner)
        self.assertIn('Continue', button.text)
        self.assertEqual(owner._uiLanguageBindings[0][2], 'managed_runtime_resume')
        self.assertEqual(len(owner._uiLanguageBindings), 1)
        with patch('shared.setup_resume.pending_setup', return_value=None):
            refresh_setup_button(owner)
        self.assertEqual(owner._uiLanguageBindings[0][2], 'managed_runtime_setup')


if __name__ == '__main__':
    unittest.main()
