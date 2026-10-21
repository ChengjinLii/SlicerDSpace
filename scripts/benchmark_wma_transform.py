"""Paired author point transforms and complete bounded optimizer fixtures.

Neither phase is a complete WMA/74-tract workflow timing. Author code is pinned
and both routes use one VTK/BLAS thread, identical samples and optimizer budgets.
"""

import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tractography.wma_transform import AuthorCompatibleFiberTransform, registration_transform_support


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wma-root', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True, action='append')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.report.exists():
        parser.error('Refusing to overwrite evidence')
    args.output.mkdir(parents=True)
    sys.path.insert(0, str(args.wma_root.resolve()))
    import numpy as np
    import vtk
    import whitematteranalysis as wma
    reg = wma.register_two_subjects
    vtk.vtkSMPTools.Initialize(1)
    vtk.vtkMultiThreader.SetGlobalMaximumNumberOfThreads(1)
    compatibility = registration_transform_support(Path(reg.__file__).parent)
    assert compatibility['supported'], compatibility
    original = reg.transform_fiber_array_numpy
    fast = AuthorCompatibleFiberTransform(original, reg.convert_transform_to_vtk)
    sources = [Path(__file__), ROOT/'tractography/wma_transform.py', Path(reg.__file__),
               Path(wma.congeal_multisubject.__file__), *args.input]
    hashes = {str(path.resolve()): sha(path) for path in sources}
    records = []
    for number, source in enumerate(args.input):
        subject = source.name.split('_')[0]
        work = args.output/subject
        work.mkdir()
        polydata = wma.io.read_polydata(str(source.resolve()))
        source_lines = polydata.GetNumberOfLines()
        sampled = wma.filter.downsample(polydata, 1000, random_seed=2026, verbose=False, preserve_cell_data=False)
        fibers = wma.fibers.FiberArray()
        fibers.convert_from_polydata(sampled, 15)
        array = np.array([getattr(fibers, 'fiber_array_'+axis) for axis in ('r', 'a', 's')])
        del sampled, polydata
        before = hashlib.sha256(array.tobytes()).hexdigest()
        rng = np.random.default_rng(2026)
        vectors = [np.r_[rng.normal(size=6)*5, np.ones(3)*200+rng.normal(size=3), rng.normal(size=6)]
                   for _ in range(8)]
        for vector in vectors:
            for mode in ([1, 1, 0, 0], [1, 1, 1, 1]):
                np.testing.assert_array_equal(original(array, vector, mode), fast(array, vector, mode))
        vector = vectors[-1]
        original(array, vector)
        fast(array, vector)
        transform_times = {'author': [], 'optimized': []}
        for repeat in range(5):
            methods = [('author', original), ('optimized', fast)]
            if repeat % 2:
                methods.reverse()
            for name, method in methods:
                start = time.perf_counter()
                method(array, vector)
                transform_times[name].append(time.perf_counter()-start)
        fixed = array[:, :128].copy()
        moving = array[:, 128:192].copy()
        moving[0] += 20.

        def optimizer(name, iteration):
            folder = work/(name+str(iteration))
            folder.mkdir()
            initial = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0], dtype=float)
            context = patch.object(reg, 'transform_fiber_array_numpy', fast) if name == 'optimized' else nullcontext()
            with context:
                start = time.perf_counter()
                output = wma.congeal_multisubject.congeal_multisubject_inner_loop(
                    fixed.copy(), moving.copy(), initial, 'Affine', 20, 1, 1, str(folder),
                    np.array([10., 5.]), 300, False, 6)
                return time.perf_counter()-start, output

        def equal(left, right):
            for first, second in zip(left, right):
                np.testing.assert_array_equal(first, second)

        equal(optimizer('author', 'warm')[1], optimizer('optimized', 'warm')[1])
        optimizer_times = {'author': [], 'optimized': []}
        outputs = {}
        for repeat in range(3):
            methods = list(optimizer_times)
            if repeat % 2:
                methods.reverse()
            for name in methods:
                elapsed, outputs[name] = optimizer(name, repeat)
                optimizer_times[name].append(elapsed)
            equal(outputs['author'], outputs['optimized'])
        assert before == hashlib.sha256(array.tobytes()).hexdigest()
        assert reg.transform_fiber_array_numpy is original
        old, new = (statistics.median(transform_times[key]) for key in ('author', 'optimized'))
        old_opt, new_opt = (statistics.median(optimizer_times[key]) for key in ('author', 'optimized'))
        records.append(dict(subject_id=subject, source_lines=source_lines, sampled_fibers=1000, points_per_fiber=15,
            transform_author_seconds=old, transform_optimized_seconds=new, transform_speed_ratio=old/new,
            transform_times=transform_times, transform_repeats=5,
            optimizer_author_seconds=old_opt, optimizer_optimized_seconds=new_opt,
            optimizer_speed_ratio=old_opt/new_opt, optimizer_times=optimizer_times, optimizer_repeats=3,
            fixed_fibers=128, moving_fibers=64, maxfun=300, sigma=20, controlled_offset_ras_mm=[20, 0, 0],
            exact_all_points=True, exact_objective_history=True, exact_transform=True,
            objective_history=np.asarray(outputs['author'][1]).tolist(),
            objective_change=float(outputs['author'][2]),
            optimizer_improved=bool(outputs['author'][2] < 0), input_array_unchanged=True))
        print(json.dumps(records[-1]), flush=True)
    assert all(sha(path) == digest for path, digest in hashes.items()), 'Inputs or implementation changed'
    report = dict(status='passed', reviewed_on='2026-10-21', records=records, compatibility=compatibility,
                  implementation=fast.summary(), source_sha256=hashes, source_inputs_unchanged=True,
                  environment=dict(python=sys.version, numpy=np.__version__, vtk=vtk.vtkVersion.GetVTKVersion(),
                                   vtk_threads=vtk.vtkSMPTools.GetEstimatedNumberOfThreads(),
                                   platform=platform.platform(), thread_env={k:os.environ.get(k) for k in
                                   ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')}),
                  scope='Author point-transform substep and complete small author optimizer on three real-subject fixtures with explicit synthetic offsets; not complete WMA',
                  limitations=['Shared host; warm-process/page-cache timings',
                               'No reduced optimizer budget or objective change between methods',
                               'Neither transform ratios nor small-optimizer ratios imply full-WMA acceleration or anatomical accuracy'])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
