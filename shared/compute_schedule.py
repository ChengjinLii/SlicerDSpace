"""Resource-bounded independent subprocesses; no MRML/Qt work in workers."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time


@dataclass(frozen=True)
class ComputeJob:
    name: str
    command: tuple[str, ...]
    threads: int = 1
    memory_bytes: int = 0
    environment: dict | None = None


def available_resources():
    try:
        cpus = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        cpus = os.cpu_count() or 1
    try:
        import psutil
        memory = int(psutil.virtual_memory().available * .7)
    except ImportError:
        memory = 0
    return cpus, memory


def _save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def _stop(process):
    try:
        import psutil
        children = psutil.Process(process.pid).children(recursive=True)
    except (ImportError, OSError):
        children = []
    except Exception:
        children = []
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        for child in reversed(children):
            try:
                child.terminate()
            except Exception:
                pass
        try:
            process.terminate()
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    for child in children:
        try:
            if child.is_running():
                child.kill()
        except Exception:
            pass


def run_independent_jobs(jobs, *, directory, max_workers=1, cpu_budget=None,
                         memory_budget=None, log=None):
    """Jobs must have disjoint outputs and all dependencies already satisfied.

    Children inherit the workflow's process group, so Slicer's normal whole-tree
    cancellation still applies. Failures stop remaining children, never publish
    a successful aggregate. Per-job logs retain failures and incomplete work.
    """
    jobs = list(jobs)
    if (max_workers < 1 or len({job.name for job in jobs}) != len(jobs)
            or any(not re.fullmatch(r'[A-Za-z0-9_-]+', job.name) for job in jobs)):
        raise ValueError('Positive worker count and unique job names are required')
    cpus, memory = available_resources()
    cpus = cpus if cpu_budget is None else cpu_budget
    memory = memory if memory_budget is None else memory_budget
    if cpus < 1 or memory < 0 or any(job.threads < 1 or job.memory_bytes < 0 for job in jobs):
        raise ValueError('Invalid CPU or memory budget')
    if any(job.threads > cpus or (memory and job.memory_bytes > memory) for job in jobs):
        raise ValueError('A compute job exceeds the available resource budget')
    requested_workers = max_workers
    if not memory:
        max_workers = 1
        if requested_workers > 1 and log:
            log('[Compute] Available memory is unknown; using sequential model execution')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    report = directory / 'schedule.json'
    start = time.monotonic()
    rows = {job.name: dict(name=job.name, status='queued', threads=job.threads,
                           memory_bytes=job.memory_bytes, command=list(job.command)) for job in jobs}
    record = dict(kind='independent_model_schedule', status='running', max_workers=max_workers,
                  requested_workers=requested_workers,
                  cpu_budget=cpus, memory_budget=memory, jobs=list(rows.values()),
                  scope='Independent model subprocess wall time, not an algorithmic speedup')
    active, waiting, handles = {}, jobs.copy(), []
    previous_signal = None
    def cancel(_signum, _frame):
        raise InterruptedError('Workflow cancelled')
    if threading.current_thread() is threading.main_thread():
        previous_signal = signal.signal(signal.SIGTERM, cancel)
    _save(report, record)
    try:
        while waiting or active:
            for job in waiting.copy():
                if len(active) >= max_workers:
                    break
                used_cpu = sum(item[0].threads for item in active.values())
                used_mem = sum(item[0].memory_bytes for item in active.values())
                if used_cpu + job.threads > cpus or (memory and used_mem + job.memory_bytes > memory):
                    continue
                stream = (directory / (job.name + '.log')).open('wb')
                handles.append(stream)
                environment = os.environ.copy()
                environment.update(job.environment or {})
                process = subprocess.Popen(job.command, env=environment, stdout=stream, stderr=subprocess.STDOUT)
                active[job.name] = job, process, time.monotonic()
                waiting.remove(job)
                rows[job.name].update(status='running', started_at=datetime.now(timezone.utc).isoformat(),
                                     start_offset_seconds=time.monotonic()-start, pid=process.pid,
                                     log=str(stream.name))
                if log:
                    log(f'[Compute] Running {job.name} ({job.threads} CPU threads reserved)')
                _save(report, record)
            for name, (job, process, began) in list(active.items()):
                code = process.poll()
                if code is None:
                    continue
                rows[name].update(status='completed' if code == 0 else 'failed', exit_code=code,
                                  ended_at=datetime.now(timezone.utc).isoformat(),
                                  runtime_seconds=time.monotonic()-began)
                del active[name]
                _save(report, record)
                if code:
                    raise RuntimeError(f'{name} failed with exit code {code}; see {rows[name]["log"]}')
                if log:
                    log(f'[Compute] Completed {name}: {rows[name]["runtime_seconds"]:.3f} s')
            if waiting or active:
                time.sleep(.1)
        record['status'] = 'completed'
        return record
    except BaseException as exc:
        record.update(status='cancelled' if isinstance(exc, (InterruptedError, KeyboardInterrupt)) else 'failed',
                      error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        for name, (_, process, began) in active.items():
            if process.poll() is None:
                _stop(process)
            rows[name].update(status='cancelled', runtime_seconds=time.monotonic()-began)
        for job in waiting:
            rows[job.name]['status'] = 'not_run'
        for stream in handles:
            stream.close()
        if previous_signal is not None:
            signal.signal(signal.SIGTERM, previous_signal)
        record['elapsed_seconds'] = time.monotonic()-start
        record['job_seconds_sum'] = sum(row.get('runtime_seconds', 0) for row in rows.values())
        _save(report, record)
