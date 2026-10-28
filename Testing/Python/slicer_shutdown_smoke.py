"""Close real Slicer while an owned background process and child are active."""

import json
import os
import signal
from pathlib import Path
import traceback

import qt
import slicer

ROOT = Path(os.environ["SLICERDSPACE_SMOKE_ROOT"])
STATE = {}


def running(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1][0] not in {"Z", "X"}
    except FileNotFoundError:
        return False


def inspect_shutdown():
    try:
        child = int((ROOT / "child.pid").read_text())
        widget = STATE["widget"]
        manifest = ROOT / "outputs/00_run_metadata/quit_test_cancelled_orchestration_manifest.json"
        status = json.loads(manifest.read_text())["status"]
        record = {"process_stopped": not running(STATE["process_pid"]),
                  "child_stopped": not running(child), "child_pid": child,
                  "manifest_status": status, "cleanup_ran": widget._cleanedUp}
        record["passed"] = all(record[key] for key in ("process_stopped", "child_stopped", "cleanup_ran")) and status == "cancelled"
        (ROOT / "shutdown.json").write_text(json.dumps(record, indent=2) + "\n")
        print("SLICER_SHUTDOWN=" + json.dumps(record), flush=True)
        if not record["child_stopped"]:
            os.kill(child, signal.SIGKILL)
    except Exception:
        traceback.print_exc()


def poll(count=0):
    if (ROOT / "child.pid").is_file():
        STATE["process_pid"] = int(STATE["widget"]._backgroundProcess.processId())
        # Also exercise Cancel followed by Quit after the launcher has exited,
        # before the GUI's delayed child force-kill timer can run.
        slicer.app.connect("aboutToQuit()", inspect_shutdown)
        if os.environ.get("SLICERDSPACE_CANCEL_BEFORE_QUIT") == "1":
            STATE["widget"]._onCancelRunClicked()
            qt.QTimer.singleShot(500, quit_after_cancel)
        else:
            slicer.app.exit(0)
    elif count < 20:
        qt.QTimer.singleShot(250, lambda: poll(count + 1))
    else:
        slicer.app.exit(2)


def quit_after_cancel(count=0):
    if STATE["widget"]._backgroundProcess is None:
        slicer.app.exit(0)
    elif count < 20:
        qt.QTimer.singleShot(250, lambda: quit_after_cancel(count + 1))
    else:
        slicer.app.exit(2)


def run():
    try:
        slicer.util.selectModule("SlicerDSpace")
        widget = slicer.modules.slicerdspace.widgetRepresentation().self()
        STATE["widget"] = widget
        code = ("import subprocess,sys,time; from pathlib import Path; "
                "p=subprocess.Popen([sys.executable,'-c',"
                "'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)']); "
                "time.sleep(0.5); "
                f"Path({str(ROOT / 'child.pid')!r}).write_text(str(p.pid)); "
                "print('OWNED_CHILD_READY',flush=True); time.sleep(60)")
        widget._build_background_cli_args = lambda *args: ["--launch", "PythonSlicer", "-u", "-c", code]
        common = dict(subject_id="quit-test", subject_root=ROOT, output_root=ROOT / "outputs",
                      targets=("validation",), run_name="quit_test", tractography_backend="dti_det",
                      bundle_backend="wmql", connectome_backend="python", select_streamlines=100,
                      ddseg_device="cpu", surface_device="cpu")
        widget._startBackgroundPipeline(common, {}, ["validation"])
        poll()
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


qt.QTimer.singleShot(5000, run)
qt.QTimer.singleShot(60000, lambda: slicer.app.exit(3))
