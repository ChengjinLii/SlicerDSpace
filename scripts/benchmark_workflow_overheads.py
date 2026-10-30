#!/usr/bin/env python3
"""Measure validation/report overhead on isolated synthetic inputs, without MRI fitting."""

from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(output: Path, repeats: int):
    import nibabel as nib
    import numpy as np
    from shared import ProductOrchestratorConfig, run_subject_products

    records = []
    with tempfile.TemporaryDirectory(prefix='slicerdspace-overheads-') as temporary:
        for repeat in range(repeats):
            subject = Path(temporary) / f'fixture-{repeat}'
            directory = subject / 'input'
            directory.mkdir(parents=True)
            shape = (5 + repeat, 5, 5)
            nib.save(nib.Nifti1Image(np.ones((*shape, 4), dtype=np.float32), np.eye(4)), directory / 'data.nii.gz')
            mask = np.zeros(shape, dtype=np.uint8)
            mask[1:-1, 1:-1, 1:-1] = 1
            nib.save(nib.Nifti1Image(mask, np.eye(4)), directory / 'nodif_brain_mask.nii.gz')
            (directory / 'bvals').write_text('0 1000 1000 1000')
            (directory / 'bvecs').write_text('0 1 0 0\n0 0 1 0\n0 0 0 1\n')
            (directory / 'data.json').write_text(json.dumps(dict(PhaseEncodingDirection='j-', TotalReadoutTime=.065)))
            for scenario in ('fresh_output_directory', 'same_settings_repeat', 'gradient_modified'):
                if scenario == 'gradient_modified':
                    (directory / 'bvals').write_text('0 1000 1000 1200')
                started = time.monotonic()
                with contextlib.redirect_stdout(io.StringIO()):
                    result = run_subject_products(ProductOrchestratorConfig(
                        subject.name, subject, targets=('validation',), execute=True, resume=True,
                        brain_mask_backend='provided', run_name='overhead_pilot'))
                external_wall = time.monotonic() - started
                manifest = json.loads(result.run_manifest_path.read_text())
                if manifest['status'] != 'completed' or manifest.get('report_error') or manifest.get('output_tree_report_error'):
                    raise RuntimeError(f'Pilot failed: {manifest.get("report_error", manifest["status"])}')
                if external_wall < manifest['wall_time_seconds'] or manifest['wall_time_seconds'] < manifest['elapsed_seconds']:
                    raise RuntimeError('Timing boundaries are inconsistent')
                profile = manifest['performance_profile']
                records.append(dict(scenario=scenario, repeat=repeat, spatial_shape=list(shape),
                    external_api_wall_seconds=external_wall, legacy_pre_report_seconds=manifest['elapsed_seconds'],
                    orchestrator_wall_seconds=manifest['wall_time_seconds'], phases_seconds=manifest['phase_timings_seconds'],
                    directory_scan_seconds=profile['directory_statistics']['total_scan_seconds'],
                    declared_path_queries=len(profile['directory_statistics']['declared_output_queries']),
                    status=manifest['status']))
    sources = ['shared/orchestrator.py', 'shared/validation.py', 'shared/pipeline.py',
               'shared/reporting.py', 'shared/run_subject_pipeline_cli.py', 'scripts/benchmark_workflow_overheads.py']
    payload = dict(status='passed', measured_at=datetime.now(timezone.utc).isoformat(),
        scope='Synthetic validation and reporting only; no MRI model fitting, model-cache timing, or speedup comparison.',
        python=platform.python_version(), platform=platform.platform(),
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
        cpu_affinity_count=len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count(),
        load_average=list(os.getloadavg()) if hasattr(os, 'getloadavg') else None,
        threads={key: os.environ.get(key) for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')},
        cache_policy='Fresh output directories share the host OS cache; no cache flush or model computation.',
        records=records, medians={scenario: {key: statistics.median(row[key] for row in records if row['scenario'] == scenario)
            for key in ('external_api_wall_seconds', 'legacy_pre_report_seconds', 'orchestrator_wall_seconds', 'directory_scan_seconds')}
            for scenario in sorted({row['scenario'] for row in records})})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    print(json.dumps(payload['medians'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    run(args.output, args.repeats)
