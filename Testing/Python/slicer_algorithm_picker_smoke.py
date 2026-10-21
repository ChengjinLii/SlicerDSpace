"""Actual multi-select dialogs, MRML persistence and independent setup panel."""

import json
import os
from pathlib import Path
import traceback

import qt
import slicer

ROOT = Path(os.environ['SLICERDDSURFER_SMOKE_ROOT'])


def run():
    checks = []
    try:
        slicer.util.selectModule('SlicerDDSurfer')
        owner = slicer.modules.slicerddsurfer.widgetRepresentation().self()
        from shared.ui_algorithm_picker import choose_algorithms, selected_algorithms
        combo = owner._onboardingWidgets['language_combo']
        combo.setCurrentIndex(combo.findData('en'))
        assert len(owner._algorithmButtons) == 3
        assert not owner._advancedSettingsPanel.isAncestorOf(owner.ui.environmentCollapsibleButton)
        assert not owner._advancedSettingsPanel.isAncestorOf(owner.ui.resultsCollapsibleButton)
        assert owner._advancedCategorySelector.count == 4
        checks.append('three_pickers_and_independent_environment')
        def choose(family, values=None, cancel=False):
            def interact():
                for dialog in qt.QApplication.topLevelWidgets():
                    if dialog.objectName != 'algorithmPicker_' + family or not dialog.visible:
                        continue
                    if cancel:
                        dialog.reject()
                        return
                    boxes = slicer.util.findChildren(dialog, className='QCheckBox')
                    buttons = slicer.util.findChildren(dialog, className='QDialogButtonBox')[0]
                    for box in boxes:
                        if box.enabled:
                            box.checked = False
                    if family != 'microstructure':
                        assert not buttons.button(qt.QDialogButtonBox.Apply).enabled
                    for box in boxes:
                        box.checked = box.objectName.removeprefix('algorithm_') in values
                    assert buttons.button(qt.QDialogButtonBox.Apply).enabled
                    buttons.button(qt.QDialogButtonBox.Apply).click()
                    return
            qt.QTimer.singleShot(200, interact)
            return choose_algorithms(owner, family)
        assert choose('microstructure', ['dti', 'freewater', 'noddi', 'dki'])
        assert selected_algorithms(owner._parameterNode, 'microstructure') == ('dti', 'freewater', 'noddi', 'dki')
        assert choose('tractography', ['csd_act', 'ukf'])
        assert owner._parameterNode.orchestrationTractographyBackend == 'csd_act,ukf'
        assert choose('bundles', ['wmql', 'tractcloud'])
        assert owner._parameterNode.orchestrationBundleBackend == 'wmql,tractcloud'
        checks.append('all_three_real_multiselect_dialogs')
        before = owner._parameterNode.orchestrationBundleBackend
        assert not choose('bundles', cancel=True)
        assert owner._parameterNode.orchestrationBundleBackend == before
        checks.append('empty_selection_disabled_and_cancel_preserved')
        owner._save_common_user_settings()
        from shared.user_config import load_user_config
        defaults = load_user_config()['run_defaults']
        assert defaults['tractography_backend'] == 'csd_act,ukf'
        assert defaults['bundle_backend'] == 'wmql,tractcloud'
        checks.append('selections_persist_in_shared_config')
        owner._advancedSettingsPanel.collapsed = True
        slicer.util.mainWindow().resize(1280, 900)
        dock = slicer.util.findChild(slicer.util.mainWindow(), 'PanelDockWidget')
        dock.setFixedWidth(480)
        slicer.util.findChild(slicer.util.mainWindow(), 'DataProbeCollapsibleWidget').collapsed = True
        slicer.app.processEvents()
        geometry = {}
        for family, name in (('microstructure', 'targetMicrostructureCheckBox'),
                             ('tractography', 'targetTractographyCheckBox'), ('bundles', 'targetBundlesCheckBox')):
            checkbox = getattr(owner.ui, name)
            label = owner._algorithmSummaryLabels[name]
            geometry[family] = {key: [widget.x, widget.y, widget.width, widget.height, widget.text]
                                for key, widget in (('check', checkbox), ('label', label), ('button', owner._algorithmButtons[family]))}
            assert label.x >= checkbox.x + checkbox.width + 4, geometry[family]
        (ROOT / 'selection_geometry.json').write_text(json.dumps(geometry, indent=2))
        slicer.util.mainWindow().grab().save(str(ROOT / 'main_multiselect.png'))
        owner._advancedSettingsPanel.collapsed = False
        for index in range(4):
            owner._advancedCategorySelector.setCurrentIndex(index)
            slicer.app.processEvents()
            owner._fitAdvancedPage()
            owner._advancedSettingsPanel.grab().save(str(ROOT / f'advanced_{index}.png'))
            assert owner._uiWidget.width <= 480, (index, owner._uiWidget.width)
            if index == 1:
                slicer.util.mainWindow().grab().save(str(ROOT / 'advanced_models_window.png'))
                label = owner._advancedCategoryForms['models'].labelForField(owner.ui.orchestrationDkiFitMethodComboBox)
                assert label.visible and label.text
                group = owner._ukfGroup
                group.collapsed = False
                slicer.app.processEvents()
                slicer.app.processEvents()
                assert owner._ukfControls['Rs'].visible
                assert owner._advancedCategoryStack.height > 250
                group.collapsed = True
        checks.append('four_compact_parameter_categories')
        combo.setCurrentIndex(combo.findData('zh'))
        assert all(button.text == '选择…' for button in owner._algorithmButtons.values())
        assert owner.ui.environmentCollapsibleButton.text == '环境与安装'
        checks.append('chinese_picker_and_setup_labels')
        record = {'status': 'passed', 'checks': checks}
        code = 0
    except Exception:
        record = {'status': 'failed', 'checks': checks, 'error': traceback.format_exc()}
        traceback.print_exc()
        code = 1
    (ROOT / 'algorithm_picker.json').write_text(json.dumps(record, indent=2))
    slicer.app.exit(code)


qt.QTimer.singleShot(4000, run)
