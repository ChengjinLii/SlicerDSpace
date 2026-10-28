#!/usr/bin/env python3
"""Run an explicit GUI/CLI experiment request with isolated outputs and live records."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.experiments import compile_plan
from shared.external_process import text_subprocess_kwargs


def write_record(path, record):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def run_plan(plan, *, cancel_event=None):
    cancel = cancel_event if cancel_event is not None else threading.Event()
    output = Path(plan['output_root'])
    output.mkdir(parents=True, exist_ok=False)
    manifest = Path(plan['manifest_path'])
    manifest.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    started = time.monotonic()
    plan.update(status='running', started_at=datetime.now(timezone.utc).isoformat())
    write_record(manifest, plan)
    print('[Batch] manifest: ' + str(manifest), flush=True)
    groups = {}
    for job in plan['subjects']:
        job['status'] = 'pending'
        groups.setdefault(job['subject_root'], []).append(job)

    def run_subject(jobs):
        for job in jobs:
            if cancel.is_set():
                break
            with lock:
                job['status'] = 'running'
                write_record(manifest, plan)
            logs = output / '00_batch_metadata' / 'logs'
            logs.mkdir(exist_ok=True)
            stdout_log, stderr_log = (logs / (job['job_id'] + suffix) for suffix in ('.stdout.log', '.stderr.log'))
            before = time.monotonic()
            print(f'[Experiments] Running {job["subject_id"]} / {job["variant"]}', flush=True)
            code, reason = 127, ''
            try:
                with stdout_log.open('w', encoding='utf-8') as stdout, stderr_log.open('w', encoding='utf-8') as stderr:
                    process = subprocess.Popen(job['command'], stdout=stdout, stderr=stderr, **text_subprocess_kwargs())
                    terminated_at = None
                    while process.poll() is None:
                        if cancel.is_set():
                            if terminated_at is None:
                                process.terminate()
                                terminated_at = time.monotonic()
                            elif time.monotonic() - terminated_at > 10:
                                process.kill()
                        time.sleep(0.1)
                    code = process.wait()
                if code == 0:
                    record = json.loads(Path(job['run_manifest_path']).read_text(encoding='utf-8'))
                    if (record.get('execute') is not True or record.get('subject_id') != job['subject_id']
                            or not isinstance(record.get('tasks'), list) or not record['tasks']):
                        raise ValueError('Child run record does not match this experiment')
                    problems = [task.get('name') for task in record.get('tasks', [])
                                if task.get('status') in {'failed', 'partial_failed', 'blocked', 'cancelled'}]
                    if problems or record.get('status') in {'failed', 'blocked', 'cancelled'}:
                        code, reason = 2, 'Incomplete child tasks: ' + ', '.join(str(v) for v in problems)
            except (OSError, ValueError) as exc:
                code, reason = 1, str(exc)
            status = 'cancelled' if cancel.is_set() else 'failed' if code else 'completed'
            result = {**job, 'status': status, 'returncode': code, 'elapsed_seconds': time.monotonic() - before,
                      'stdout_log': str(stdout_log), 'stderr_log': str(stderr_log), 'reason': reason}
            if code and stderr_log.is_file():
                with stderr_log.open('rb') as stream:
                    stream.seek(0, 2)
                    stream.seek(max(0, stream.tell() - 4000))
                    tail = stream.read().decode('utf-8', errors='replace').strip()
                if tail:
                    print(f'[Experiments] {job["job_id"]}: {tail}', flush=True)
            with lock:
                job['status'] = status
                plan['results'].append(result)
                plan['updated_at'] = datetime.now(timezone.utc).isoformat()
                write_record(manifest, plan)
            print(f'[Experiments] Finished {job["job_id"]}: exit {code}', flush=True)

    try:
        with ThreadPoolExecutor(max_workers=plan['jobs']) as executor:
            futures = [executor.submit(run_subject, jobs) for jobs in groups.values()]
            for future in futures:
                future.result()
        failed = sum(result['returncode'] != 0 for result in plan['results'])
        plan['status'] = 'cancelled' if cancel.is_set() else 'failed' if failed else 'completed'
    except Exception as exc:
        plan.update(status='failed', error=str(exc))
    finally:
        done = {result['job_id'] for result in plan['results']}
        plan.update(not_launched=[job['job_id'] for job in plan['subjects'] if job['job_id'] not in done],
                    elapsed_seconds=time.monotonic() - started, ended_at=datetime.now(timezone.utc).isoformat())
        write_record(manifest, plan)
        print('[Batch] manifest: ' + str(manifest), flush=True)
    return 130 if plan['status'] == 'cancelled' else 2 if plan['status'] == 'failed' else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--execute', action='store_true', help='Omit to validate and print a plan without writing outputs')
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding='utf-8'))
        plan = compile_plan(request, python_executable=sys.executable,
                            pipeline_script=ROOT / 'shared/run_subject_pipeline_cli.py')
        if not args.execute:
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            return 0
        cancel = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: cancel.set())
        signal.signal(signal.SIGINT, lambda *_: cancel.set())
        return run_plan(plan, cancel_event=cancel)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
