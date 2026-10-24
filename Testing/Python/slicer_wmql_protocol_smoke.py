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
        assert node.orchestrationWmqlPreset == 'official'
        assert combo.currentText == 'official'
        assert combo.count == 1
        node.targetBundles = True
        node.orchestrationBundleBackend = 'wmql'
        widget._advancedSettingsPanel.collapsed = False
        widget.ui.parametersCollapsibleButton.collapsed = False
        slicer.app.processEvents()
        widget._refresh_advanced_run_settings()
        print('WMQL_PRESET_STATE', node.targetBundles, node.orchestrationBundleBackend,
              combo.currentText, combo.isHidden(), flush=True)
        assert not combo.isHidden(), 'WMQL preset row must not be dropped/hidden in its form layout'
        selection = widget.ui.wmqlQuerySelectionLineEdit
        selection.setText('AF,CST,UF')
        slicer.app.processEvents()
        assert node.orchestrationWmqlSelection == 'AF,CST,UF'
        node.orchestrationWmqlSelection = 'cc_4'
        slicer.app.processEvents()
        assert selection.text == 'cc_4'
        from tractography.wmql_protocol import canonical_wmql_selection
        assert canonical_wmql_selection('AF,CST,UF') == ('af.left', 'af.right', 'cst.left', 'cst.right', 'uf.left', 'uf.right')
        node.orchestrationBundleBackend = 'wma'
        widget._refresh_advanced_run_settings()
        assert combo.isHidden()
        assert selection.isHidden()
        raw = node.parameterNode
        widget.setParameterNode(None)
        raw.SetParameter('orchestrationWmqlPreset', 'ddparcel_act')
        migrated = widget.logic.getParameterNode()
        assert migrated.orchestrationWmqlPreset == 'official'
        assert migrated.parameterNode.GetAttribute('SlicerDDSurfer.LegacyWMQLPreset') == 'ddparcel_act'
        widget.setParameterNode(migrated)
        print('WMQL_PROTOCOL_GUI_PASS', flush=True)
        slicer.app.exit(0)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(1)


qt.QTimer.singleShot(4000, run)
