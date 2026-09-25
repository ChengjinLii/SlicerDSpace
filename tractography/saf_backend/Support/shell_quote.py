"""Shared helper for safely embedding values in shell=True command strings.

Several SAF pipeline modules build a single command string (an MRtrix
prefix, a command name, and one or more filesystem paths) and hand it to
:func:`sys_exec`, which runs it with ``shell=True``. Any interpolated path
that is not quoted can be misinterpreted by the shell if it contains
whitespace or shell metacharacters (for example ``;``). Wrap every
interpolated path with :func:`shell_quote` before building such a command.
"""

import shlex


def shell_quote(value) -> str:
    """Return a POSIX-shell-safe quoted form of ``value``."""

    return shlex.quote(str(value))
