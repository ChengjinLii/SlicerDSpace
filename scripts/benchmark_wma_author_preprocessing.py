#!/usr/bin/env python3
"""Paired unmodified-author versus bulk WMA filtering; no fitted product reuse."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tractography.wma_preprocessing import AuthorCompatibleLengthFilter
from tractography.wma_registration import registration_cache_support


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wma-root', type=Path, required=True)
    parser.add_argument('--input', type=Path, action='append', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--sample-size', type=int, default=50000, help='Zero uses full input')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--warmups', type=int, default=1)
    args = parser.parse_args()
    if args.report.exists() or args.repeats < 1 or args.warmups < 0 or args.sample_size < 0:
        parser.error('Use a new report path and valid sample/repetition counts')
    sys.path.insert(0, str(args.wma_root.resolve()))
    import numpy as np
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    import whitematteranalysis as wma

    compatibility = registration_cache_support(Path(wma.__file__).resolve().parent)
    if not compatibility['supported']:
        raise ValueError('Refusing a comparison against unverified author source')
    record = dict(kind='original_author_wma_vs_bulk_filter', status='running',
        author_repository='SlicerDMRI/whitematteranalysis', author_commit='4532b911386d2d1bc7ebba63fdd13e65b1660623',
        compatibility=compatibility, sample_size=args.sample_size, repeats=args.repeats, warmups=args.warmups,
        length_minimum_mm=40, length_maximum_mm=260, output_reuse=False,
        implementation_sha256={str(path.relative_to(ROOT)): digest(path) for path in
            (Path(__file__), ROOT/'tractography/wma_preprocessing.py')}, cases=[],
        environment=dict(python=sys.version, platform=platform.platform(), numpy=np.__version__, vtk=vtk.vtkVersion.GetVTKVersion(),
            thread_env={key: os.environ.get(key) for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}),
        scope='Fresh author preprocess() calls vs fresh bulk calls, never the old plugin or completed-fit cache; filtering only',
        limitations=['Shared Linux host, not exclusive hardware', 'No whole registration/classification or anatomical accuracy claim',
                     'One full-atlas repetition is a scoped observation, not a confidence interval', 'Native Windows/macOS not benchmarked'])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    def save():
        temporary = args.report.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, indent=2)+'\n')
        temporary.replace(args.report)
    def array_digest(array):
        array = np.asarray(array)
        value = hashlib.sha256()
        for start in range(0, len(array), 262144):
            value.update(np.ascontiguousarray(array[start:start+262144]).tobytes())
        return value.hexdigest()
    def signature(polydata):
        return dict(lines=polydata.GetNumberOfLines(), points=polydata.GetNumberOfPoints(),
            points_sha256=array_digest(vtk_to_numpy(polydata.GetPoints().GetData())),
            lines_sha256=array_digest(vtk_to_numpy(polydata.GetLines().GetData())),
            point_dtype=polydata.GetPoints().GetDataType(),
            point_arrays=polydata.GetPointData().GetNumberOfArrays(), cell_arrays=polydata.GetCellData().GetNumberOfArrays())
    def sampled_signature(polydata):
        signatures = []
        for seed in (124, 125, 126):
            sample, indices = wma.filter.downsample(polydata, 200, return_indices=True, verbose=False,
                                                   preserve_cell_data=False, random_seed=seed)
            fibers = wma.fibers.FiberArray()
            fibers.convert_from_polydata(sample, 10)
            signatures.append(dict(seed=seed, geometry=signature(sample), indices=array_digest(indices),
                fibers=[array_digest(getattr(fibers, 'fiber_array_'+axis)) for axis in ('r','a','s')],
                random_state=array_digest(np.random.get_state()[1])))
        return signatures
    save()
    try:
        for path in args.input:
            source_hash = digest(path)
            polydata = wma.io.read_polydata(str(path.resolve()))
            source_lines = polydata.GetNumberOfLines()
            if args.sample_size and source_lines > args.sample_size:
                polydata = wma.filter.downsample(polydata, args.sample_size, preserve_cell_data=False,
                                                  random_seed=2026, verbose=False)
            input_signature = signature(polydata)
            fast = AuthorCompatibleLengthFilter(wma.filter.preprocess)
            actions = {'author': wma.filter.preprocess, 'optimized': fast}
            for _ in range(args.warmups):
                for action in actions.values():
                    output = action(polydata, 40, max_length_mm=260, preserve_cell_data=False, verbose=False)
                    del output
            timings = {key: [] for key in actions}
            reference = sampling_reference = None
            for repeat in range(args.repeats):
                order = list(actions) if repeat % 2 == 0 else list(reversed(actions))
                for key in order:
                    started = time.perf_counter()
                    output = actions[key](polydata, 40, max_length_mm=260, preserve_cell_data=False, verbose=False)
                    elapsed = time.perf_counter() - started
                    timings[key].append(elapsed)
                    current = signature(output)
                    sampled = sampled_signature(output)
                    if reference is None:
                        reference, sampling_reference = current, sampled
                    if current != reference or sampled != sampling_reference:
                        raise ValueError('Author/bulk points, cells, fixed-seed arrays or random state differ')
                    print(path.name, repeat, key, elapsed, flush=True)
                    del output
            before, after = (statistics.median(timings[key]) for key in ('author','optimized'))
            unchanged = digest(path) == source_hash and signature(polydata) == input_signature
            if not unchanged or fast.bypassed or fast.calls != args.warmups + args.repeats:
                raise ValueError('Source changed or bulk path was not actually executed')
            case = dict(input=str(path.resolve()), input_sha256=source_hash, source_lines=source_lines,
                measured_input=input_signature, full_input_measured=polydata.GetNumberOfLines()==source_lines,
                author_median_seconds=before, optimized_median_seconds=after, speed_ratio=before/after,
                time_reduction_percent=100*(1-after/before), raw_seconds=timings,
                output_signature=reference, sampling_signatures=sampling_reference,
                all_output_bytes_equal=True, source_unchanged=unchanged, bulk=fast.summary())
            record['cases'].append(case)
            print(json.dumps(case), flush=True)
            save()
            del polydata
        record['status']='passed'
    except BaseException as error:
        record.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        save()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
