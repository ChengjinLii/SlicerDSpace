"""Collect actual local test outcomes and verify the tested install's core hashes."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(validation_root, output):
    log = validation_root / 'python_tests.log'
    text = log.read_text()
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK \(skipped=(\d+)\)', text)
    if not match:
        raise RuntimeError('Full Python suite has not passed')
    gui_root = validation_root / 'gui_frozen'
    gui = json.loads((gui_root / 'gui_acceptance.json').read_text())
    audit = json.loads((gui_root / 'package_resource_audit.json').read_text())
    if not gui['tests'] or any(row['status'] != 'PASS' for row in gui['tests']) or audit['status'] != 'pass':
        raise RuntimeError('Isolated Slicer/package acceptance has not passed')
    module = gui_root / 'install/SlicerDSpace/lib/Slicer-5.10/qt-scripted-modules'
    files = ['SlicerDSpace.py', 'shared/orchestrator.py', 'shared/validation.py', 'shared/pipeline.py',
             'shared/run_subject_pipeline_cli.py', 'shared/reporting.py', 'anatomy/segmentation/qc.py',
             'scripts/run_batch_pipeline.py', 'scripts/extension_runtime/runtime_resources.json']
    artifacts = {name: dict(source_sha256=digest(ROOT / name), installed_sha256=digest(module / name)) for name in files}
    if any(row['source_sha256'] != row['installed_sha256'] for row in artifacts.values()):
        raise RuntimeError('Tested core installation does not match the current source')
    payload = dict(status='passed', collected_at=datetime.now(timezone.utc).isoformat(),
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        working_tree='Uncommitted; core source/installed hashes below identify the tested state.',
        python_tests=dict(count=int(match[1]), seconds=float(match[2]), skipped=int(match[3]), log_sha256=digest(log)),
        slicer_tests=[{key: row[key] for key in ('name', 'status', 'exit_code', 'seconds', 'script_sha256')}
                      for row in gui['tests']],
        package=dict(status=audit['status'], files=audit['expected_file_count'], sha256=gui['archive_sha256'],
                     origin=gui['archive_origin']), core_artifacts=artifacts,
        scope='Code reliability, isolated staged Slicer UI/package and synthetic input checks. No new whole-brain performance or anatomical acceptance.',
        existing_live_sessions_updated=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(status=payload['status'], tests=payload['python_tests'],
                         slicer_tests=payload['slicer_tests'], package=payload['package']), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    collect(args.validation_root, args.output)
