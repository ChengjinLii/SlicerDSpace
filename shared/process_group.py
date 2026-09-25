"""Launch/kill helpers for a QProcess's whole process tree, not just one PID.

``QProcess.terminate()``/``.kill()`` only signal the direct child process.
When that child is a launcher (e.g. the Slicer executable running
``run_subject_pipeline_cli.py``) that spawns further subprocesses for each
pipeline task (MRtrix, FreeSurfer, dcm2niix, ...), cancelling just the top
process leaves those descendants running as orphans. Launch the child in its
own process group (POSIX, via ``setsid``) and kill the whole group/tree
instead of one PID. This mirrors the approach already used for setup jobs in
``shared/ui_setup_jobs.py``.
"""

from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess
from typing import Optional


def grouped_launch_command(program: str, args: list[str]) -> tuple[str, list[str], bool]:
    """Return ``(program, args, grouped)`` with a ``setsid`` prefix applied on POSIX.

    ``grouped`` is True only when the returned command will actually run the
    target program as the leader of its own process group (POSIX with
    ``setsid`` available on PATH). Windows needs no launch-time change:
    ``taskkill /T`` can kill a process's descendant tree from its PID alone.
    """

    if os.name == "posix":
        setsid = shutil.which("setsid")
        if setsid:
            return setsid, [program, *args], True
    return program, args, False


def kill_process_tree(
    pid: int,
    *,
    grouped: bool,
    force: bool,
    platform_name: Optional[str] = None,
) -> None:
    """Signal the whole process group/tree rooted at ``pid``.

    ``force`` requests an unconditional kill (``SIGKILL`` / ``taskkill /F``);
    when False, a milder terminate signal (``SIGTERM`` / ``taskkill``
    without ``/F``) is used instead, giving children a chance to shut down
    cleanly before a later, forced follow-up call.
    """

    if pid is None or pid <= 0:
        return
    system = platform_name or platform.system()
    if system == "Windows":
        command = ["taskkill", "/PID", str(pid), "/T"]
        if force:
            command.append("/F")
        subprocess.run(command, check=False, capture_output=True)
        return
    if grouped:
        try:
            if os.getpgid(pid) == pid:
                os.killpg(pid, signal.SIGKILL if force else signal.SIGTERM)
                return
        except ProcessLookupError:
            return
    try:
        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        pass
