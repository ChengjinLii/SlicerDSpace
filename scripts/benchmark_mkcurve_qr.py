"""Paired complete numeric chunks, using a frozen pre-optimization tensor file.

Inputs are NPZ files with signals, design and grid; no sampling is done here.
Fix BLAS thread counts before launching both interpreters for comparable runs.
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from unittest.mock import patch

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from microstructure import mkcurve, mkcurve_tensor


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(left, right):
    for index in (0, 1, 2):
        np.testing.assert_array_equal(left[index], right[index])
    assert left[3].keys() == right[3].keys()
    for key in left[3]:
        np.testing.assert_array_equal(left[3][key], right[3][key])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--input', required=True, action='append', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error('At least three alternating repetitions are required')
    if args.output.exists() or args.output.with_suffix('.csv').exists():
        parser.error('Refusing to overwrite an existing benchmark report')
    spec = importlib.util.spec_from_file_location('_mkcurve_qr_baseline', args.reference)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    # The frozen code and current code read the same unchanged author resource.
    reference.integration_directions = mkcurve_tensor.integration_directions
    sources = [args.reference, Path(mkcurve_tensor.__file__), Path(mkcurve.__file__),
               Path(__file__), Path(mkcurve_tensor.__file__).with_name('mkcurve_directions.json'), *args.input]
    hashes = {str(path.resolve()): sha(path) for path in sources}
    records = []
    for path in args.input:
        with np.load(path) as fixture:
            signals, design, grid = (fixture[key].copy() for key in ('signals', 'design', 'grid'))
        for solver in ('reference', 'batched'):
            def run(implementation):
                with patch.dict(sys.modules, {'microstructure.mkcurve_tensor': implementation}):
                    return mkcurve._fit_chunk((signals.copy(), design, grid, .5, solver))
            compare(run(reference), run(mkcurve_tensor))
            times = {'reference': [], 'optimized': []}
            for repetition in range(args.repeats):
                outputs = {}
                methods = [('reference', reference), ('optimized', mkcurve_tensor)]
                if repetition % 2:
                    methods.reverse()
                for name, implementation in methods:
                    start = time.perf_counter()
                    outputs[name] = run(implementation)
                    times[name].append(time.perf_counter() - start)
                compare(outputs['reference'], outputs['optimized'])
            old, new = (statistics.median(times[name]) for name in ('reference', 'optimized'))
            record = dict(subject_id=path.name.split('_')[0], solver=solver,
                          reference_median_seconds=old, optimized_median_seconds=new,
                          speed_ratio=old/new, time_reduction_percent=100*(1-new/old),
                          times_seconds=times, repeats=args.repeats, warmups_per_method=1,
                          voxels=len(signals), measurements=len(design), grid_samples=len(grid),
                          exact_output_parity=True, comparison_keys=list(outputs['optimized'][3]))
            records.append(record)
            print(json.dumps(record), flush=True)
    assert all(sha(path) == digest for path, digest in hashes.items()), 'Source/input changed during measurement'
    report = dict(status='passed', reviewed_on=datetime.now(timezone.utc).date().isoformat(), records=records, source_sha256=hashes,
                  source_inputs_unchanged=True,
                  scope='All WLLS, full synthetic-b0 grid, correction, raw coefficients, maps, masks and residuals for saved real-signal chunks; excludes file preparation/export',
                  comparison='Same preceding Python solver implementation; not original MATLAB runtime or a new scientific model',
                  environment=dict(python=sys.version, executable=sys.executable, scipy=scipy.__version__,
                                   numpy=np.__version__, platform=platform.platform(),
                                   thread_env={key: os.environ.get(key) for key in
                                               ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')}),
                  limitations=['Shared host; warm process; three subjects, not full-brain or whole workflow',
                               'No changed solver choice, voxel selection, thresholds, grid or thread counts',
                               'Speed ratios must not be extrapolated or multiplied by previous full-stage ratios'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    with args.output.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['subject_id', 'solver', 'reference_median_seconds',
            'optimized_median_seconds', 'speed_ratio', 'time_reduction_percent', 'voxels',
            'measurements', 'grid_samples', 'repeats', 'exact_output_parity'], extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)


if __name__ == '__main__':
    main()
