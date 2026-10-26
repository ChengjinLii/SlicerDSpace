"""Check the current single-subject GUI without launching scientific tasks."""
import json
import os
from pathlib import Path
import traceback

import qt
import slicer

ROOT = Path(os.environ["SLICERDDSURFER_SMOKE_ROOT"])


def run():
    try:
        slicer.util.selectModule("SlicerDDSurfer")
        owner = slicer.modules.slicerddsurfer.widgetRepresentation().self()
        from shared.ui_advanced_layout import BATCH_CONTROLS, CATEGORIES
        from shared.ui_algorithm_picker import selected_algorithms
        combo = owner._onboardingWidgets["language_combo"]
        combo.setCurrentIndex(combo.findData("en"))
        node = owner._parameterNode
        with slicer.util.NodeModify(node):
            node.batchMode = True
            node.batchSize = 4
            node.subjectId = ""
            node.inputDirectory = ""
        owner.setParameterNode(node)
        assert node.batchMode is False and node.batchSize == 1
        assert len(owner._algorithmButtons) == 3
        assert all(button.text == "..." for button in owner._algorithmButtons.values())
        assert owner._advancedCategorySelector.count == len(CATEGORIES)
        for index in range(len(CATEGORIES)):
            owner._advancedCategorySelector.setCurrentIndex(index)
            slicer.app.processEvents()
            assert all(getattr(owner.ui, name).isHidden() for name in BATCH_CONTROLS)
        with slicer.util.NodeModify(node):
            node.batchMode = True
        owner._onRunSelectedClicked()
        assert node.batchMode is False
        assert owner._backgroundProcess is None
        report = dict(status="PASS", slicer_version=slicer.app.applicationVersion,
                      gui_subject_count=1, legacy_batch_state_migrated=True,
                      cohort_controls_hidden=list(BATCH_CONTROLS),
                      advanced_categories=[item[1] for item in CATEGORIES],
                      algorithms={family: list(selected_algorithms(node, family))
                                  for family in owner._algorithmButtons},
                      invalid_input_starts_no_process=True, scientific_tasks_executed=False)
        (ROOT / "single_subject_gui.json").write_text(json.dumps(report, indent=2) + "\n")
        print("SLICER_SINGLE_SUBJECT_GUI_PASS", flush=True)
        slicer.app.exit(0)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


qt.QTimer.singleShot(5000, run)
