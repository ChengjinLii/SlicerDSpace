"""Cancel a real setup QProcess whose child ignores SIGTERM (no installs)."""

import json
import os
from pathlib import Path
import signal
from types import SimpleNamespace
import traceback

import qt
import slicer

ROOT = Path(os.environ["SLICERDDSURFER_SMOKE_ROOT"])
STATE = {}


def running(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1][0] not in {"Z", "X"}
    except FileNotFoundError:
        return False


def completed(status, details, log_path):
    try:
        child = int((ROOT / "child.pid").read_text())
        record = {"status": status, "child_pid": child, "child_stopped": not running(child), "log": str(log_path)}
        (ROOT / "setup_tree.json").write_text(json.dumps(record, indent=2) + "\n")
        if not record["child_stopped"]:
            os.kill(child, signal.SIGKILL)
        assert status == "cancelled" and record["child_stopped"], record
        print("SETUP_TREE_CANCEL_PASS", flush=True)
        slicer.app.exit(0)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


def poll(count=0):
    if (ROOT / "child.pid").is_file():
        STATE["owner"]._setupJob.cancel()
    elif count < 40:
        qt.QTimer.singleShot(100, lambda: poll(count + 1))
    else:
        STATE["owner"]._setupJob.shutdown()
        slicer.app.exit(3)


def start():
    from shared.ui_setup_jobs import start_setup_job
    slicer.util.selectModule("SlicerDDSurfer")
    widget = slicer.modules.slicerddsurfer.widgetRepresentation().self()
    owner = SimpleNamespace(parent=slicer.util.mainWindow(), _latestEnvironmentReportDir=ROOT,
                            _pipelineActive=False, appendLog=print)
    owner._setPipelineActive = lambda active: setattr(owner, "_pipelineActive", active)
    STATE["owner"] = owner
    code = ("import subprocess,sys,time; from pathlib import Path; "
            "p=subprocess.Popen([sys.executable,'-c',"
            "'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)']); "
            "time.sleep(0.5); "
            f"Path({str(ROOT / 'child.pid')!r}).write_text(str(p.pid)); time.sleep(60)")
    assert start_setup_job(owner, "Synthetic child cancellation", [(
        widget._slicer_launcher_program(), ["--launch", "PythonSlicer", "-u", "-c", code], {})], completed)
    poll()


qt.QTimer.singleShot(5000, start)
qt.QTimer.singleShot(60000, lambda: slicer.app.exit(3))
