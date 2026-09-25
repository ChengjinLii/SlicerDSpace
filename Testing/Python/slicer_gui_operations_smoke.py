"""Exercise real scene ownership and asynchronous cancellation without downloads."""

import json
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import qt
import slicer

TEMP = tempfile.TemporaryDirectory()
ROOT = Path(TEMP.name)
STATE = {}


def fail():
    traceback.print_exc()
    slicer.app.exit(2)


def run():
    try:
        from shared.module_logic import SharedLogicMixin
        from shared.result_scene import owned_nodes
        from shared.ui_setup_jobs import start_setup_job

        slicer.util.selectModule("SlicerDDSurfer")
        widget = slicer.modules.slicerddsurfer.widgetRepresentation().self()
        widget._latestResultManifestPath = "previous-run.json"
        for button in widget._resultSceneButtons:
            button.enabled = True
        widget._reset_result_scene_actions()
        assert widget._latestResultManifestPath is None
        assert not any(button.enabled for button in widget._resultSceneButtons)
        print("GUI_RESULT_ACTION_RESET=True", flush=True)
        STATE["widget"] = widget
        node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "synthetic")
        slicer.util.updateVolumeFromArray(node, np.ones((4, 5, 6), dtype=np.float32))
        image = ROOT / "fa.nii.gz"
        assert slicer.util.saveNode(node, str(image))
        slicer.mrmlScene.RemoveNode(node)
        manifest = ROOT / "run.json"
        manifest.write_text(json.dumps({"subject_id": "gui-test", "run_name": "Test1", "tasks": [
            {"name": "microstructure.dti", "status": "completed", "outputs": {"fa": str(image)}},
            {"name": "microstructure.noddi", "status": "failed", "outputs": {"ndi": str(image)}}]}))
        logic = SharedLogicMixin()
        logic.log = print
        first = logic.loadKeyResultsFromManifest(manifest)
        assert len(first["loaded"]) == 1 and len(first["skipped"]) == 1
        assert len(logic.loadKeyResultsFromManifest(manifest)["reused"]) == 1
        assert len(owned_nodes(slicer, str(manifest))) == 1
        logic.loadKeyResultsFromManifest(manifest, mode="append")
        assert len(owned_nodes(slicer, str(manifest))) == 2
        logic.loadKeyResultsFromManifest(manifest, mode="replace")
        assert len(owned_nodes(slicer, str(manifest))) == 1
        # Ownership persists through scene serialization.
        scene_file = ROOT / "scene.mrb"
        assert slicer.util.saveScene(str(scene_file))
        slicer.mrmlScene.Clear(0)
        assert slicer.util.loadScene(str(scene_file))
        assert len(logic.loadKeyResultsFromManifest(manifest)["reused"]) == 1
        assert logic.clearResultsFromManifest(manifest) == 1
        print("GUI_SCENE_OWNERSHIP=True", flush=True)
        STATE["beats"] = 0
        timer = qt.QTimer()
        timer.connect("timeout()", lambda: STATE.update(beats=STATE["beats"] + 1))
        timer.start(50)
        STATE["timer"] = timer
        owner = SimpleNamespace(parent=slicer.util.mainWindow(), _latestEnvironmentReportDir=ROOT,
                                _pipelineActive=False, appendLog=print)
        owner._setPipelineActive = lambda active: setattr(owner, "_pipelineActive", active)
        STATE["owner"] = owner
        program = widget._slicer_launcher_program()
        command = (program, ["--launch", "PythonSlicer", "-u", "-c", "import time; print('working',flush=True); time.sleep(30)"], {})

        def done(status, details, log_path):
            try:
                assert status == "cancelled", status
                assert STATE["beats"] >= 5, STATE["beats"]
                assert "cancelled" in log_path.read_text()
                assert owner._setupJob is None and not owner._pipelineActive
                STATE["timer"].stop()
                print("GUI_SETUP_CANCEL_AND_RESPONSIVENESS=True", flush=True)
                slicer.util.mainWindow().resize(1500, 1050)
                widget.ui.environmentCollapsibleButton.collapsed = True
                widget.ui.configurationCollapsibleButton.collapsed = False
                widget.ui.advancedRunCollapsibleButton.collapsed = True
                slicer.app.processEvents()
                slicer.util.mainWindow().grab().save("/tmp/slicerdsurfer-gui-20260920.png")
                widget._runStatusPanel.grab().save("/tmp/slicerdsurfer-result-panel-20260920.png")
                slicer.app.exit(0)
            except Exception:
                fail()
        def failed_done(status, details, log_path):
            try:
                assert status == "failed" and "intentional failure" in details
                print("GUI_SETUP_FAILURE=True", flush=True)
                assert start_setup_job(owner, "Synthetic cancellation test", [command], done)
                qt.QTimer.singleShot(1500, owner._setupJob.cancel)
            except Exception:
                fail()

        def success_done(status, details, log_path):
            try:
                assert status == "completed" and "step two" in details
                print("GUI_SETUP_SEQUENCE=True", flush=True)
                failure = (program, ["--launch", "PythonSlicer", "-u", "-c", "print('intentional failure'); raise SystemExit(7)"], {})
                assert start_setup_job(owner, "Synthetic failure test", [failure], failed_done)
            except Exception:
                fail()
        success_commands = [(program, ["--launch", "PythonSlicer", "-u", "-c", f"print('{message}')"], {})
                            for message in ("step one", "step two")]
        assert start_setup_job(owner, "Synthetic success test", success_commands, success_done)
    except Exception:
        fail()


qt.QTimer.singleShot(5000, run)
qt.QTimer.singleShot(90000, lambda: slicer.app.exit(3))
