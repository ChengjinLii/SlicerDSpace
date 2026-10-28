#!/usr/bin/env python3
"""Own a Linux process group while the Windows bridge supplies a heartbeat."""

import argparse
import math
import os
from pathlib import Path
import signal
import subprocess
import time


def stop_group(pgid, grace_seconds=3.0):
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def supervise(command, heartbeat, timeout_seconds=15.0, grace_seconds=3.0):
    if os.name != 'posix':
        raise RuntimeError('The command supervisor must execute inside WSL, not Windows.')
    if not command or not math.isfinite(timeout_seconds) or timeout_seconds <= 0 or not math.isfinite(grace_seconds) or grace_seconds < 0:
        raise ValueError('Command and positive heartbeat timeout are required.')
    heartbeat = Path(heartbeat)
    # Refuse a cancelled/never-started bridge before launching expensive tools.
    if not heartbeat.is_file() or time.time() - heartbeat.stat().st_mtime > timeout_seconds:
        raise RuntimeError('Windows bridge heartbeat is missing or expired.')
    previous_stamp = heartbeat.stat().st_mtime_ns
    last_update = time.monotonic()
    interrupted = []
    old_handlers = {}
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        old_handlers[signum] = signal.signal(signum, lambda value, _: interrupted.append(value))
    process = None
    try:
        process = subprocess.Popen(command, start_new_session=True)
        while process.poll() is None:
            if interrupted:
                return 128 + interrupted[0]
            try:
                stamp = heartbeat.stat().st_mtime_ns
                if stamp != previous_stamp:
                    previous_stamp = stamp
                    last_update = time.monotonic()
                # Clock skew between Windows/WSL must not keep a dead bridge alive.
                expired = time.monotonic() - last_update > timeout_seconds
            except OSError:
                expired = True
            if expired:
                print('SlicerDSpace: Windows bridge stopped; cancelling owned WSL task.', flush=True)
                return 130
            time.sleep(0.1)
        return process.returncode if process.returncode >= 0 else 128 - process.returncode
    finally:
        if process is not None:
            # Include descendants when the immediate launcher has already exited.
            stop_group(process.pid, grace_seconds)
            process.wait()
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--heartbeat', required=True, type=Path)
    parser.add_argument('--timeout-seconds', type=float, default=15.0)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    return supervise(command, args.heartbeat, args.timeout_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
