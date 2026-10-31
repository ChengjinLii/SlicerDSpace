"""Preparation recovery stores state, not permission to install or run analysis."""

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from shared.setup_resume import (complete_setup, pending_setup, refresh_setup_button, remember_setup,
                                 offer_pending_preparation, remember_functional_failure, functional_failure_matches)


class SetupResumeTests(unittest.TestCase):
    def test_functional_failure_survives_restart_and_matches_only_its_configuration(self):
        with tempfile.TemporaryDirectory() as tmp, patch('shared.setup_resume.pending_path', return_value=Path(tmp) / 'pending.json'):
            signature = [('targets', ('segmentation',)), ('model_assets_dir', Path(tmp) / 'models')]
            remember_functional_failure('failed-request', signature)
            self.assertTrue(functional_failure_matches(signature))
            self.assertFalse(functional_failure_matches([('targets', ('surface',))]))
            complete_setup('failed-request')
            self.assertFalse(functional_failure_matches(signature))
    def test_restart_offers_one_recheck_and_never_runs_scientific_analysis(self):
        from unittest.mock import Mock
        owner = SimpleNamespace(_pipelineActive=False, _selectedSetupActive=False)
        timer = Mock()
        timer.singleShot.side_effect = lambda delay, callback: callback()
        with patch('shared.setup_resume.pending_setup', return_value={'request': 'one'}), \
                patch.dict('sys.modules', {'qt': SimpleNamespace(QTimer=timer)}), \
                patch('shared.ui_environment_check.request_prepare_environment') as request:
            self.assertTrue(offer_pending_preparation(owner))
            self.assertFalse(offer_pending_preparation(owner))
            request.assert_called_once_with(owner)

    def test_cancelled_restart_request_does_not_start_preparation(self):
        owner = SimpleNamespace(_pipelineActive=False, _selectedSetupActive=False)
        callbacks = []
        timer = SimpleNamespace(singleShot=lambda delay, callback: callbacks.append(callback))
        with patch('shared.setup_resume.pending_setup', side_effect=[{'request': 'one'}, None]), \
                patch.dict('sys.modules', {'qt': SimpleNamespace(QTimer=timer)}), \
                patch('shared.ui_environment_check.request_prepare_environment') as request:
            self.assertTrue(offer_pending_preparation(owner))
            callbacks[0]()
            request.assert_not_called()

    def test_exiting_module_before_deferred_resume_does_not_touch_destroyed_ui(self):
        owner = SimpleNamespace(_pipelineActive=False, _selectedSetupActive=False, _setupResumeEnabled=True)
        callbacks = []
        timer = SimpleNamespace(singleShot=lambda delay, callback: callbacks.append(callback))
        with patch('shared.setup_resume.pending_setup', return_value={'request': 'one'}), \
                patch.dict('sys.modules', {'qt': SimpleNamespace(QTimer=timer)}), \
                patch('shared.ui_environment_check.request_prepare_environment') as request:
            offer_pending_preparation(owner)
            owner._setupResumeEnabled = False
            callbacks[0]()
            request.assert_not_called()
            self.assertIsNone(owner._setupResumeOffered)

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
