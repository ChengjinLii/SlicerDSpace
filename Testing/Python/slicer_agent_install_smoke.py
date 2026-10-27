"""Exercise the install skill's helper in isolated real Slicer settings."""

import json
import os
from pathlib import Path
import runpy
import traceback

import qt
import slicer


def run():
    root = Path(os.environ['SLICERDDSURFER_SMOKE_ROOT'])
    checks = []
    code = 0
    try:
        helper = runpy.run_path(os.environ['SLICERDDSURFER_AGENT_INSTALL_HELPER'])
        module = Path(os.environ['SLICERDDSURFER_EXTENSION_MODULE_DIR'])
        settings = slicer.app.userSettings()
        other = root / 'other-extension'
        other.mkdir(exist_ok=True)
        settings.setValue('Modules/AdditionalPaths', [str(other)])
        result = helper['activate'](module, persist=False)
        assert result['status'] == 'passed' and not result['persistent']
        assert list(settings.value('Modules/AdditionalPaths')) == [str(other)]
        checks.append('session_activation_does_not_change_settings')
        result = helper['activate'](module, persist=True)
        helper['activate'](module, persist=True)
        assert list(settings.value('Modules/AdditionalPaths')) == [str(other), str(module.resolve())]
        checks.append('persistent_activation_is_idempotent_and_preserves_other_extensions')
        assert result['dependency_readiness'] == result['scientific_qc'] == 'not_checked'
        checks.append('activation_does_not_claim_scientific_or_dependency_readiness')
        wrong = root / 'another-install'
        wrong.mkdir(exist_ok=True)
        (wrong / 'SlicerDDSurfer.py').write_text('# conflict fixture\n')
        settings.setValue('Modules/AdditionalPaths', [str(other), str(wrong)])
        try:
            helper['activate'](module, persist=True)
        except RuntimeError as exc:
            assert 'different SlicerDDSurfer installation' in str(exc)
        else:
            raise AssertionError('Conflicting installation was accepted')
        assert list(settings.value('Modules/AdditionalPaths')) == [str(other), str(wrong)]
        checks.append('conflicting_installation_is_rejected_before_settings_mutation')
        payload = dict(status='passed', checks=checks, activation=result)
    except Exception:
        payload = dict(status='failed', checks=checks, traceback=traceback.format_exc())
        print(payload['traceback'], flush=True)
        code = 1
    (root / 'agent_install.json').write_text(json.dumps(payload, indent=2) + '\n')
    slicer.app.exit(code)


qt.QTimer.singleShot(1000, run)
