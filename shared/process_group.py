"""Launch/kill helpers for a QProcess's whole process tree, not just one PID.

``QProcess.terminate()``/``.kill()`` only signal the direct child process.
When that child is a launcher (e.g. the Slicer executable running
``run_subject_pipeline_cli.py``) that spawns further subprocesses for each
pipeline task (MRtrix, FreeSurfer, dcm2niix, ...), cancelling just the top
process leaves those descendants running as orphans. Launch the child in its
own process group (POSIX, via ``setsid`` or a ``setpgrp`` fallback) and kill
the whole group/tree instead of one PID. This mirrors the approach already
used for setup jobs in ``shared/ui_setup_jobs.py``.
"""

from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess
from typing import Optional

_PERL_SETPGRP_PATH = "/usr/bin/perl"
_PERL_SETPGRP_SCRIPT = "setpgrp(0, 0); exec @ARGV"


def _perl_setpgrp_launcher() -> Optional[str]:
    """Return a perl interpreter usable for the ``setpgrp`` launch trick, if any.

    Prefers the canonical ``/usr/bin/perl`` -- present on macOS and
    virtually every Linux distribution, including ones that ship no
    system-wide ``perl`` on PATH by default -- and falls back to whatever
    ``perl`` is on PATH for the rare system where it lives elsewhere.
    """

    if os.path.exists(_PERL_SETPGRP_PATH):
        return _PERL_SETPGRP_PATH
    return shutil.which("perl")


def grouped_launch_command(program: str, args: list[str]) -> tuple[str, list[str], bool]:
    """Return ``(program, args, grouped)`` so the target runs as its own process-group leader.

    ``grouped`` is True only when the returned command will actually run the
    target program as the leader of its own process group. Windows needs no
    launch-time change: ``taskkill /T`` can kill a process's descendant tree
    from its PID alone.

    On POSIX, ``setsid(1)`` (from util-linux) is preferred when present. It
    is absent on macOS and other BSD-derived systems -- ``shutil.which
    ("setsid")`` always returns ``None`` there -- which used to mean grouping
    silently fell back to "ungrouped" on exactly the platform where this
    extension is primarily developed and used. The fallback is a one-line
    perl script that calls the ``setpgrp(0, 0)`` syscall directly (making
    the not-yet-``exec``'d process the leader of a new process group of its
    own -- the same property ``setsid(1)`` provides for this purpose) and
    then ``exec``s the real target in its place, preserving its pid. Both
    paths leave the launched process as its own process-group leader, i.e.
    with ``pgid == pid`` -- see :func:`capture_process_group_id`.
    """

    if os.name == "posix":
        setsid = shutil.which("setsid")
        if setsid:
            return setsid, [program, *args], True
        perl = _perl_setpgrp_launcher()
        if perl:
            return perl, ["-e", _PERL_SETPGRP_SCRIPT, "--", program, *args], True
    return program, args, False


def capture_process_group_id(pid: int) -> Optional[int]:
    """Return ``pid``'s process-group id, or ``None`` if it cannot be determined.

    Call this once, right after a grouped launch, while the launched process
    is known to still be alive (e.g. immediately after
    ``QProcess.waitForStarted()`` succeeds) and store the result. Passing
    that stored value to :func:`kill_process_tree` later -- rather than
    re-deriving the pgid from the pid at kill time -- matters because
    ``os.getpgid(pid)`` raises ``ProcessLookupError`` once the group's
    leader process has already exited, which happens routinely: launchers
    often exit quickly while the descendants they spawned (MRtrix,
    FreeSurfer, dcm2niix, ...) keep running well past that point, and those
    descendants are the whole reason a group kill is needed.
    """

    if os.name != "posix" or pid is None or pid <= 0:
        return None
    try:
        return os.getpgid(pid)
    except ProcessLookupError:
        return None


def kill_process_tree(
    pid: int,
    *,
    grouped: bool,
    force: bool,
    pgid: Optional[int] = None,
    platform_name: Optional[str] = None,
) -> None:
    """Signal the whole process group/tree rooted at ``pid``.

    ``force`` requests an unconditional kill (``SIGKILL`` / ``taskkill /F``);
    when False, a milder terminate signal (``SIGTERM`` / ``taskkill``
    without ``/F``) is used instead, giving children a chance to shut down
    cleanly before a later, forced follow-up call.

    ``pgid`` should be the value :func:`capture_process_group_id` returned at
    launch time. When it is available, ``killpg`` is called unconditionally
    against it, ignoring ``ProcessLookupError`` (ESRCH): by the time a forced
    follow-up call fires, the group leader may already be gone even though
    its descendants are not, and re-deriving the pgid from ``pid`` at this
    point (via ``os.getpgid``) would itself raise in exactly that case. When
    ``pgid`` is omitted, ``pid`` is used in its place: by construction,
    :func:`grouped_launch_command` only reports ``grouped=True`` when the
    launched process was made the leader of its own new process group, so
    its own pid equals its pgid at launch time.
    """

    system = platform_name or platform.system()
    if system == "Windows":
        if pid is None or pid <= 0:
            return
        command = ["taskkill", "/PID", str(pid), "/T"]
        if force:
            command.append("/F")
        subprocess.run(command, check=False, capture_output=True)
        return
    if grouped:
        target_pgid = pgid if pgid is not None else pid
        if target_pgid and target_pgid > 0:
            try:
                os.killpg(target_pgid, signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                pass
            return
    if pid is None or pid <= 0:
        return
    try:
        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        pass
