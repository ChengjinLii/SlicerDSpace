"""Actual GUI checks and setup cancellation with a source-built native runtime."""

import json
import os
from pathlib import Path
import time
import traceback

import qt
import slicer

ROOT = Path(os.environ['SLICERDSPACE_SMOKE_ROOT'])


def run():
    checks = []
    try:
        from shared.selected_setup import build_setup_plan
        slicer.util.selectModule('SlicerDSpace')
        owner = slicer.modules.slicerdspace.widgetRepresentation().self()
        owner._onboardingWidgets['language_combo'].setCurrentIndex(0)
        node = owner._parameterNode
        with slicer.util.NodeModify(node):
            for field in ('targetPreprocessing', 'targetSurface', 'targetSegmentation', 'targetParcellation',
                          'targetMicrostructure', 'targetTractography', 'targetBundles', 'targetConnectome'):
                setattr(node, field, False)
            node.targetSurfacePostprocess = True

        def set_path(name, value):
            owner._save_environment_path_setting(name, value)
            owner._environmentPathLineEdits[name].setText(value)

        def wait():
            deadline = time.monotonic() + 120
            while getattr(owner, '_setupJob', None) or getattr(owner, '_selectedSetupActive', False):
                assert time.monotonic() < deadline, 'Worker timeout'
                loop = qt.QEventLoop()
                qt.QTimer.singleShot(50, loop.quit)
                loop.exec_()

        set_path('postprocess_runtime', os.environ['SLICERDSPACE_TEST_SURFACE_RUNTIME'])
        set_path('postprocess_license_file', os.environ['SLICERDSPACE_TEST_SURFACE_LICENSE'])
        owner.ui.validateButton.click()
        wait()
        statuses = {item.key: item for item in owner._lastEnvironmentResult.statuses}
        assert statuses['surface_postprocess_runtime'].status == 'available', statuses
        assert statuses['surface_postprocess_license'].status == 'available'
        assert 'env:freesurfer_home' not in statuses
        checks.append('real_check_accepts_source_components_without_full_freesurfer')

        set_path('postprocess_license_file', str(ROOT / 'no-activation.txt'))
        owner.ui.validateButton.click()
        wait()
        statuses = {item.key: item for item in owner._lastEnvironmentResult.statuses}
        assert statuses['surface_postprocess_runtime'].status == 'available'
        assert statuses['surface_postprocess_license'].status == 'missing'
        assert not build_setup_plan(owner._lastEnvironmentResult)['surface_build_required']
        checks.append('missing_personal_activation_does_not_request_rebuild')

        prefix = ROOT / 'not-built'
        set_path('postprocess_runtime', str(prefix))
        owner.ui.validateButton.click()
        wait()
        plan = build_setup_plan(owner._lastEnvironmentResult)
        assert plan['surface_build_required'] and not prefix.exists()
        checks.append('check_reports_missing_components_without_building')

        confirmation = []
        timer = qt.QTimer()
        def reject():
            for dialog in qt.QApplication.topLevelWidgets():
                if dialog.objectName == 'selectedSetupConfirmationDialog' and dialog.visible:
                    labels = slicer.util.findChildren(dialog, className='QLabel')
                    text = '\n'.join(str(label.text) for label in labels)
                    confirmation.append('compile seven' in text and 'activation file' in text)
                    dialog.reject()
                    timer.stop()
        timer.connect('timeout()', reject)
        timer.start(50)
        owner._managedRuntimeSetupButton.click()
        wait()
        timer.stop()
        assert confirmation == [True], confirmation
        assert not prefix.exists()
        checks.append('prepare_requires_explicit_confirmation_and_cancel_creates_no_runtime')
        owner._onboardingWidgets['language_combo'].setCurrentIndex(1)
        assert '本机' in owner._environmentPathLineEdits['postprocess_runtime'].toolTip
        checks.append('new_environment_paths_are_localized')
        payload = dict(status='passed', checks=checks,
                       scope='Native GUI and actual read-only worker; no source compilation or anatomical accuracy test')
    except Exception:
        traceback.print_exc()
        payload = dict(status='failed', checks=checks, error=traceback.format_exc())
    (ROOT / 'surface_runtime.json').write_text(json.dumps(payload, indent=2) + '\n')
    print('SURFACE_RUNTIME=' + json.dumps(payload), flush=True)
    slicer.app.exit(0 if payload['status'] == 'passed' else 2)


qt.QTimer.singleShot(5000, run)
