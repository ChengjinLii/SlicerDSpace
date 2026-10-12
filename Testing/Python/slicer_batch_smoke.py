"""Run two actual subjects through the Slicer batch button and verify DTI QC."""

import json
import os
from pathlib import Path
import time
import traceback

import numpy as np
import nibabel as nib
import qt
import slicer

ROOT = Path(os.environ["SLICERDDSURFER_SMOKE_ROOT"])
CONFIG = json.loads(Path(os.environ["SLICERDDSURFER_TASKS_CONFIG"]).read_text())
STATE = {"errors": [], "beats": 0}


def finish():
    try:
        widget = STATE["widget"]
        path = Path(widget._backgroundManifestPath)
        batch = json.loads(path.read_text())
        assert {r["subject_id"] for r in batch["results"]} == {"100307", "149741"}
        assert all(r["returncode"] == 0 for r in batch["results"]), batch["results"]
        assert not STATE["errors"], STATE["errors"]
        assert STATE["beats"] > 20, "GUI heartbeat did not run during batch"
        records = []
        for item in batch["results"]:
            manifest_path = ROOT / "outputs" / item["subject_id"] / "00_run_metadata/batch_dti_orchestration_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            assert manifest["status"] == "completed"
            task = next(t for t in manifest["tasks"] if t["name"] == "microstructure.dti")
            assert task["status"] == "completed", task
            fa_path = Path(task["outputs"]["fa"])
            fa = nib.load(fa_path).get_fdata()
            assert np.isfinite(fa).all() and fa.min() >= 0 and fa.max() <= 1.00001
            records.append({"subject_id": item["subject_id"], "manifest": str(manifest_path),
                            "fa": str(fa_path), "shape": list(fa.shape), "fa_range": [float(fa.min()), float(fa.max())]})
        (ROOT / "batch.json").write_text(json.dumps({"status": "PASS", "batch_manifest": str(path),
             "subjects": records, "gui_heartbeats": STATE["beats"], "human_anatomical_review": "pending"}, indent=2) + "\n")
        slicer.util.mainWindow().grab().save(str(ROOT / "batch.png"))
        print("SLICER_BATCH_PASS", flush=True)
        slicer.app.exit(0)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


def poll():
    if time.monotonic() - STATE["started"] > 3600:
        STATE["widget"].cleanup()
        slicer.app.exit(3)
        return
    process = STATE["widget"]._backgroundProcess
    if process is None or process.state() == qt.QProcess.NotRunning:
        finish()
    else:
        qt.QTimer.singleShot(1000, poll)


def start():
    try:
        slicer.util.selectModule("SlicerDDSurfer")
        widget = slicer.modules.slicerddsurfer.widgetRepresentation().self()
        STATE["widget"] = widget
        original_log = widget.appendLog
        def log(message):
            print(str(message), flush=True)
            original_log(message)
        widget.appendLog = log
        batch_root = ROOT / "subjects"
        for subject in ("100307", "149741"):
            case = next(c for c in CONFIG["cases"] if c["subject_id"] == subject)
            dest = batch_root / subject / "input"
            dest.mkdir(parents=True)
            for path in (Path(case["subject_root"]) / "input").iterdir():
                if path.is_file():
                    (dest / path.name).symlink_to(path)
        node = widget._parameterNode
        with slicer.util.NodeModify(node):
            node.subjectId = "batch"
            node.inputDirectory = str(batch_root)
            node.outputDirectory = str(ROOT / "outputs")
            node.batchMode = True
            node.batchRoot = str(batch_root)
            node.batchSize = 2
            node.batchArrangeInputs = "none"
            node.orchestrationRunName = "batch_dti"
            for field in ("targetPreprocessing", "targetSegmentation", "targetParcellation", "targetSurface",
                          "targetSurfacePostprocess", "targetTractography", "targetBundles", "targetConnectome"):
                setattr(node, field, False)
            node.targetMicrostructure = True
            node.orchestrationMicrostructureStages = "dti"
            node.autoInstallPythonDependencies = False
        slicer.util.errorDisplay = lambda message, *args, **kwargs: STATE["errors"].append(str(message))
        widget._show_actionable_error = lambda **kwargs: STATE["errors"].append(str(kwargs))
        timer = qt.QTimer()
        timer.setInterval(100)
        timer.connect("timeout()", lambda: STATE.update(beats=STATE["beats"] + 1))
        timer.start()
        STATE["timer"] = timer
        STATE["started"] = time.monotonic()
        widget._checkCanApply()
        assert widget.ui.runSelectedButton.enabled
        widget.ui.runSelectedButton.click()
        assert widget._backgroundProcess is not None
        qt.QTimer.singleShot(1000, poll)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


qt.QTimer.singleShot(5000, start)
