"""Native Slicer Advanced control and CLI handoff, without fitting images."""

import qt
import slicer
import traceback


def run():
    try:
        slicer.util.selectModule('SlicerDSpace')
        widget=slicer.modules.slicerdspace.widgetRepresentation().self()
        node=widget._parameterNode
        control=widget.ui.parallelModelsSpinBox
        assert node.maxParallelModels==1
        assert control.minimum==1 and control.maximum==3
        node.targetMicrostructure=True
        widget._advancedSettingsPanel.collapsed=False
        widget.ui.advancedRunCollapsibleButton.collapsed=False
        widget._refresh_advanced_run_settings()
        slicer.app.processEvents()
        assert not control.isHidden()
        control.setValue(3)
        slicer.app.processEvents()
        assert node.maxParallelModels==3
        node.maxParallelModels=2
        slicer.app.processEvents()
        assert control.value==2
        from shared.ui_settings import COMMON_USER_SETTING_SPECS
        assert ('maxParallelModels',int) in COMMON_USER_SETTING_SPECS
        node.targetMicrostructure=False
        widget._refresh_advanced_run_settings()
        assert control.isHidden()
        print('PARALLEL_MODELS_GUI_PASS',flush=True)
        slicer.app.exit(0)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(1)


qt.QTimer.singleShot(4000,run)
