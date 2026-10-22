"""Scene parameters, readiness and log reading in an isolated real Slicer GUI."""

import json
import os
from pathlib import Path
import traceback
from types import SimpleNamespace

import qt
import slicer


ROOT = Path(os.environ['SLICERDDSURFER_SMOKE_ROOT'])


def run():
    checks = {}
    try:
        from shared.user_config import update_user_config
        slicer.util.selectModule('SlicerDDSurfer')
        owner = slicer.modules.slicerddsurfer.widgetRepresentation().self()
        owner._onboardingWidgets['language_combo'].setCurrentIndex(0)
        with slicer.util.NodeModify(owner._parameterNode):
            owner._parameterNode.subjectId = 'scene-subject'
            owner._parameterNode.orchestrationTractographyBackend = 'ukf'
            owner._parameterNode.maxParallelModels = 2
        owner._commonUserSettingsSaveTimer.stop()
        update_user_config({'recent': {'subject_id': 'different-recent-subject'},
                            'run_defaults': {'tractography_backend': 'csd_act'}})
        settings = slicer.app.userSettings()
        settings.setValue(owner._user_settings_key('subjectId'), 'different-recent-subject')
        settings.setValue(owner._user_settings_key('maxParallelModels'), 1)
        slicer.util.selectModule('Welcome')
        slicer.util.selectModule('SlicerDDSurfer')
        checks['module_return_preserves_unsaved_scene_parameters'] = (
            owner._parameterNode.subjectId == 'scene-subject'
            and owner._parameterNode.orchestrationTractographyBackend == 'ukf'
            and owner._parameterNode.maxParallelModels == 2)

        with slicer.util.NodeModify(owner._parameterNode):
            owner._parameterNode.subjectId = 'saved-scene-subject'
            owner._parameterNode.orchestrationTractographyBackend = 'ukf'
            owner._parameterNode.maxParallelModels = 2
        scene_file = ROOT / 'parameters.mrml'
        assert slicer.util.saveScene(str(scene_file))
        owner._commonUserSettingsSaveTimer.stop()
        update_user_config({'recent': {'subject_id': 'different-recent-subject'},
                            'run_defaults': {'tractography_backend': 'csd_act'}})
        slicer.mrmlScene.Clear(0)
        slicer.util.loadScene(str(scene_file))
        assert slicer.mrmlScene.GetSingletonNode('SlicerDDSurfer', 'vtkMRMLScriptedModuleNode') is not None
        slicer.util.selectModule('Welcome')
        slicer.util.selectModule('SlicerDDSurfer')
        checks['loaded_scene_wins_over_global_recent_settings'] = (
            owner._parameterNode.subjectId == 'saved-scene-subject'
            and owner._parameterNode.orchestrationTractographyBackend == 'ukf'
            and owner._parameterNode.maxParallelModels == 2)

        owner.ui.logPlainTextEdit.clear()
        owner.appendLog('\n'.join('background line ' + str(index) for index in range(500)))
        slicer.app.processEvents()
        bar = owner.ui.logPlainTextEdit.verticalScrollBar()
        assert bar.maximum > 100, bar.maximum
        bar.setValue(0)
        owner.appendLog('new background line')
        checks['incoming_logs_preserve_reader_scroll_position'] = bar.value == 0
        bar.setValue(bar.maximum)
        owner.appendLog('follow this background line')
        checks['live_tail_still_follows_when_already_at_bottom'] = bar.value == bar.maximum

        owner._parameterNode.inputDirectory = ''
        owner._parameterNode.subjectId = ''
        owner._update_environment_status(SimpleNamespace(blocker_count=0, runnable_targets=(),
                                                        blocked_targets=(), statuses=()))
        checks['ready_environment_does_not_claim_inputs_are_ready'] = 'Waiting:' in owner.ui.statusLabel.text
        payload = {'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
                   'scope': 'Real Slicer GUI and synthetic scene; no scientific accuracy claim'}
    except Exception:
        traceback.print_exc()
        payload = {'status': 'failed', 'checks': checks, 'error': traceback.format_exc()}
    (ROOT / 'gui_state.json').write_text(json.dumps(payload, indent=2) + '\n')
    print('GUI_STATE=' + json.dumps(payload), flush=True)
    slicer.app.exit(0 if payload['status'] == 'passed' else 2)


qt.QTimer.singleShot(5000, run)
