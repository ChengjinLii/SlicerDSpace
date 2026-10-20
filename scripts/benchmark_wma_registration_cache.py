#!/usr/bin/env python3
"""Compare original and cached WMA preprocessing on real, unchanged polydata.

This checks each seed's sampled geometry and registration arrays, not full WMA
classification or anatomical accuracy. Run in the configured WMA interpreter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tractography.wma_registration import RegistrationPreprocessCache, registration_cache_support


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def main():
    import numpy as np
    from vtk.util.numpy_support import vtk_to_numpy
    import whitematteranalysis as wma

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subject', type=Path, required=True)
    parser.add_argument('--atlas', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--iterations', type=int, default=3)
    parser.add_argument('--reference-report', type=Path,
                        help='Validate current cached inputs against a preserved same-source author benchmark')
    args = parser.parse_args()
    if args.iterations < 2:
        parser.error('At least two iterations are required to test reuse')
    if args.report.exists():
        parser.error('Refusing to overwrite an earlier benchmark')
    record = {'kind': 'wma_registration_cache_parity', 'status': 'running', 'iterations': args.iterations,
              'scope': 'Full native input preprocessing and fixed-seed registration input arrays; not full registration/classification',
              'compatibility': registration_cache_support(Path(wma.__file__).resolve().parent),
              'source': {name: {'path': str(path.resolve()), 'sha256': digest(path)}
                         for name, path in (('subject', args.subject), ('atlas', args.atlas))}, 'runs': [],
              'implementation_sha256': {name: digest(path) for name, path in (
                  ('benchmark', Path(__file__)), ('cache', Path(__file__).resolve().parents[1] / 'tractography/wma_registration.py'))}}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    def save():
        temporary = args.report.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
        temporary.replace(args.report)
    save()
    try:
        if not record['compatibility']['supported']:
            raise ValueError('Unverified author implementation; benchmark not claimed')
        if args.reference_report:
            reference = json.loads(args.reference_report.read_text())
            if (reference['status'] != 'passed' or reference['iterations'] != args.iterations
                    or reference['compatibility'] != record['compatibility']
                    or any(reference['source'][key]['sha256'] != value['sha256'] for key, value in record['source'].items())):
                raise ValueError('Reference must be a passed, same-source, same-protocol original-author benchmark')
            record['reference_report'] = {'path': str(args.reference_report.resolve()), 'sha256': digest(args.reference_report)}
            record['runs'] = reference['runs'][:args.iterations]
        inputs = (wma.io.read_polydata(str(args.atlas)), wma.io.read_polydata(str(args.subject)))
        record['input_lines'] = [item.GetNumberOfLines() for item in inputs]
        cache = RegistrationPreprocessCache(wma.filter.preprocess)
        implementations = [('cached', cache)] if args.reference_report else [('author', wma.filter.preprocess), ('cached', cache)]
        for label, preprocess in implementations:
            for iteration in range(args.iterations):
                started = time.monotonic()
                signatures = []
                for polydata, size in zip(inputs, (1000, 200)):
                    filtered = preprocess(polydata, 40, max_length_mm=260, return_indices=False,
                                          preserve_point_data=False, preserve_cell_data=False, verbose=False)
                    sampled, indices = wma.filter.downsample(filtered, size, return_indices=True,
                                                            verbose=False, random_seed=124 + iteration)
                    fibers = wma.fibers.FiberArray()
                    fibers.convert_from_polydata(sampled, 10)
                    signature = hashlib.sha256()
                    for array in (indices, vtk_to_numpy(sampled.GetPoints().GetData()),
                                  vtk_to_numpy(sampled.GetLines().GetData()),
                                  fibers.fiber_array_r, fibers.fiber_array_a, fibers.fiber_array_s,
                                  np.random.get_state()[1]):
                        signature.update(np.ascontiguousarray(array).tobytes())
                    signatures.append({'filtered_lines': filtered.GetNumberOfLines(),
                                       'sampled_lines': sampled.GetNumberOfLines(), 'sha256': signature.hexdigest()})
                record['runs'].append({'implementation': label, 'iteration': iteration,
                                       'elapsed_seconds': time.monotonic() - started, 'signatures': signatures})
                print(label, iteration, record['runs'][-1]['elapsed_seconds'], flush=True)
                save()
        baseline = record['runs'][:args.iterations]
        optimized = record['runs'][args.iterations:]
        parity = all(a['signatures'] == b['signatures'] for a, b in zip(baseline, optimized))
        original_seconds = sum(item['elapsed_seconds'] for item in baseline)
        cached_seconds = sum(item['elapsed_seconds'] for item in optimized)
        record.update(status='passed' if parity else 'failed', bitwise_registration_inputs_equal=parity,
                      author_seconds=original_seconds, cached_seconds=cached_seconds,
                      cache=cache.summary(),
                      source_inputs_unchanged=all(digest(Path(item['path'])) == item['sha256'] for item in record['source'].values()))
        if not args.reference_report:
            record['measured_preprocessing_speedup'] = original_seconds / cached_seconds
        if not record['source_inputs_unchanged']:
            record['status'] = 'failed'
    except Exception as exc:
        record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        save()
    return 0 if record['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
