"""Exercise real Qt/MRML advanced WMQL preset binding in an isolated Slicer."""

import traceback
import qt
import slicer


def run():
    try:
        slicer.util.selectModule('SlicerDDSurfer')
        widget = slicer.modules.slicerddsurfer.widgetRepresentation().self()
        node = widget._parameterNode
        combo = widget.ui.wmqlQueryPresetComboBox
        assert node.orchestrationWmqlPreset == 'ddparcel_act'
        assert combo.currentText == 'ddparcel_act'
        node.targetBundles = True
        node.orchestrationBundleBackend = 'wmql'
        widget._advancedSettingsPanel.collapsed = False
        widget.ui.parametersCollapsibleButton.collapsed = False
        slicer.app.processEvents()
        widget._refresh_advanced_run_settings()
        print('WMQL_PRESET_STATE', node.targetBundles, node.orchestrationBundleBackend,
              combo.currentText, combo.isHidden(), flush=True)
        assert not combo.isHidden(), 'WMQL preset row must not be dropped/hidden in its form layout'
        combo.setCurrentText('published_endpoints')
        slicer.app.processEvents()
        assert node.orchestrationWmqlPreset == 'published_endpoints'
        node.orchestrationWmqlPreset = 'author'
        slicer.app.processEvents()
        assert combo.currentText == 'author'
        node.orchestrationBundleBackend = 'wma'
        widget._refresh_advanced_run_settings()
        assert combo.isHidden()
        print('WMQL_PROTOCOL_GUI_PASS', flush=True)
        slicer.app.exit(0)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(1)


qt.QTimer.singleShot(4000, run)
