"""Non-blocking, cancellable setup jobs. Qt callbacks always run on the UI thread."""

import os
import signal
import shutil
from pathlib import Path
from datetime import datetime

from shared.ui_output_loading import qbytearray_to_text


class SetupJob:
    def __init__(self, owner, title, commands, on_done):
        import qt
        import slicer

        self.owner, self.commands, self.on_done = owner, commands, on_done
        self.index = 0
        self.cancelled = self.finished = False
        self.tail = ""
        report_dir = getattr(owner, "_latestEnvironmentReportDir", None)
        if not report_dir:
            from shared.user_config import default_user_config_path
            report_dir = default_user_config_path().parent / "setup-logs"
        folder = Path(report_dir)
        folder.mkdir(parents=True, exist_ok=True)
        owner._latestEnvironmentReportDir = folder
        self.log_path = folder / ("setup-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".log")
        self.log = self.log_path.open("w", encoding="utf-8")
        self.dialog = qt.QProgressDialog(title, "Cancel", 0, 0, slicer.util.mainWindow())
        self.dialog.setWindowTitle(title)
        self.dialog.setWindowModality(qt.Qt.NonModal)
        self.dialog.setAutoClose(False)
        self.dialog.setMinimumDuration(0)
        self.dialog.connect("canceled()", self.cancel)
        self.process = qt.QProcess(owner.parent)
        self.process.setProcessChannelMode(qt.QProcess.MergedChannels)
        self.process.connect("readyReadStandardOutput()", self.read)
        self.process.connect("finished(int,QProcess::ExitStatus)", self.step_finished)
        self.process.connect("errorOccurred(QProcess::ProcessError)", self.error)
        self.process.connect("started()", lambda: self.signal_process(False) if self.cancelled else None)
        self.dialog.show()

    def start_next(self):
        import qt
        if self.cancelled:
            self.finish("cancelled")
            return
        if self.index >= len(self.commands):
            self.finish("completed")
            return
        program, args, environment = self.commands[self.index]
        env = qt.QProcessEnvironment.systemEnvironment()
        for key, value in environment.items():
            env.insert(key, str(value))
        env.insert("PYTHONUNBUFFERED", "1")
        self.process.setProcessEnvironment(env)
        self.grouped = os.name == "posix" and bool(shutil.which("setsid"))
        if self.grouped:
            args = [program, *args]
            program = shutil.which("setsid")
        command_text = repr([program, *args])
        self.log.write(command_text + "\n")
        self.log.flush()
        self.owner.appendLog("[Setup] " + command_text)
        self.dialog.setLabelText(f"Step {self.index + 1}/{len(self.commands)}\nStarting...\nLog: {self.log_path}")
        self.process.start(program, args)

    def read(self):
        text = qbytearray_to_text(self.process.readAllStandardOutput())
        if not text or self.finished:
            return
        self.log.write(text)
        self.log.flush()
        self.tail = (self.tail + text)[-6000:]
        lines = text.strip().splitlines()
        if lines and not self.cancelled:
            self.dialog.setLabelText(f"Step {self.index + 1}/{len(self.commands)}\n{lines[-1][-220:]}\nLog: {self.log_path}")

    def cancel(self):
        import qt
        if self.finished or self.cancelled:
            return
        self.cancelled = True
        self.dialog.setLabelText("Cancelling... waiting for the process to stop.")
        self.signal_process(False)
        qt.QTimer.singleShot(2000, lambda: self.signal_process(True) if not self.finished else None)

    def signal_process(self, force):
        pid = int(self.process.processId())
        if pid <= 0:
            return
        if self.grouped:
            try:
                if os.getpgid(pid) == pid:
                    os.killpg(pid, signal.SIGKILL if force else signal.SIGTERM)
                    return
            except ProcessLookupError:
                return
        self.process.kill() if force else self.process.terminate()

    def step_finished(self, code, exit_status):
        if self.finished:
            return
        self.read()
        if self.cancelled:
            self.finish("cancelled")
        elif code != 0 or int(exit_status) != 0:
            self.finish("failed")
        else:
            self.index += 1
            self.start_next()

    def error(self, error):
        import qt
        if error == qt.QProcess.FailedToStart:
            self.tail += "\n" + self.process.errorString()
            self.finish("cancelled" if self.cancelled else "failed")

    def finish(self, status):
        if self.finished:
            return
        self.finished = True
        self.log.write(f"\nSTATUS: {status}\n")
        self.log.close()
        self.dialog.close()
        self.owner._setupJob = None
        self.owner._setPipelineActive(False)
        self.owner.appendLog(f"[Setup] {status}. Log: {self.log_path}")
        try:
            self.on_done(status, self.tail, self.log_path)
        finally:
            self.process.deleteLater()
            self.dialog.deleteLater()


def start_setup_job(owner, title, commands, on_done):
    import slicer
    if getattr(owner, "_setupJob", None) or getattr(owner, "_pipelineActive", False):
        slicer.util.infoDisplay("Wait for the current job to finish or cancel it first.", parent=owner.parent)
        return False
    owner._setPipelineActive(True)
    if hasattr(owner, "_setStatus"):
        owner._setStatus("running", title + " (background)")
    try:
        owner._setupJob = SetupJob(owner, title, commands, on_done)
        owner._setupJob.start_next()
    except Exception:
        owner._setupJob = None
        owner._setPipelineActive(False)
        raise
    return True
