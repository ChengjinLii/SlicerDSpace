"""Original-author array conversion and complete small optimizer, not full WMA."""
import argparse
from contextlib import nullcontext
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from unittest.mock import patch
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tractography.wma_fibers import AuthorCompatibleFiberArrayConverter, fiber_conversion_support


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wma-root', type=Path, required=True)
    parser.add_argument('--input', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.report.exists() or args.report.with_suffix('.csv').exists():
        parser.error('Refusing to overwrite evidence')
    args.output.mkdir(parents=True)
    sys.path.insert(0, str(args.wma_root.resolve()))
    import numpy as np
    import vtk
    import whitematteranalysis as wma
    vtk.vtkSMPTools.Initialize(1)
    vtk.vtkMultiThreader.SetGlobalMaximumNumberOfThreads(1)
    original = wma.fibers.FiberArray.convert_from_polydata
    fast = AuthorCompatibleFiberArrayConverter(wma.fibers.FiberArray)
    support = fiber_conversion_support(Path(wma.fibers.__file__).parent)
    assert support['supported'], support
    url = ('https://raw.githubusercontent.com/SlicerDMRI/whitematteranalysis/'
           '4532b911386d2d1bc7ebba63fdd13e65b1660623/whitematteranalysis/fibers.py')
    with urlopen(url, timeout=60) as response:
        author_sha = hashlib.sha256(response.read()).hexdigest()
    assert author_sha == support['source_sha256']
    sources = [Path(__file__), ROOT/'tractography/wma_fibers.py', ROOT/'scripts/run_wma_registration.py',
               Path(wma.fibers.__file__), Path(wma.register_two_subjects.__file__), *args.input]
    hashes = {str(path.resolve()): sha(path) for path in sources}
    records = []
    for source in args.input:
        subject = source.name.split('_')[0]
        work = args.output/subject
        work.mkdir()
        pd = wma.io.read_polydata(str(source.resolve()))
        source_count = pd.GetNumberOfLines()
        sample = wma.filter.downsample(pd, 20000, random_seed=2026, verbose=False,
                                       preserve_cell_data=False, preserve_point_data=False)
        del pd
        def convert(name, count=15, polydata=sample):
            fibers = wma.fibers.FiberArray()
            fibers.hemispheres = True
            fibers.hemisphere_percent_threshold = .95
            (original if name == 'author' else fast)(fibers, polydata, count)
            return fibers
        def equal(left, right):
            for key in vars(left):
                np.testing.assert_equal(vars(left)[key], vars(right)[key], err_msg=key)
        for count in (2, 3, 10, 15, 30):
            equal(convert('author', count), convert('bulk', count))
        times = {'author': [], 'bulk': []}
        for repeat in range(5):
            names = list(times)
            if repeat%2:
                names.reverse()
            outputs = {}
            for name in names:
                started = time.perf_counter()
                outputs[name] = convert(name)
                times[name].append(time.perf_counter()-started)
            equal(outputs['author'], outputs['bulk'])
        bounded = wma.filter.downsample(sample, 192, random_seed=2026, verbose=False,
                                        preserve_cell_data=False, preserve_point_data=False)
        optimizer_times = {'author': [], 'bulk': []}
        def optimizer(name, iteration):
            context = patch.object(wma.fibers.FiberArray, 'convert_from_polydata', fast.method) if name == 'bulk' else nullcontext()
            folder = work/(name+str(iteration))
            folder.mkdir()
            with context:
                started = time.perf_counter()
                fibers = wma.fibers.FiberArray()
                fibers.convert_from_polydata(bounded, 15)
                array = np.array([getattr(fibers, 'fiber_array_'+axis) for axis in 'ras'])
                fixed, moving = array[:, :128].copy(), array[:, 128:].copy()
                moving[0] += 20.
                initial = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0], dtype=float)
                output = wma.congeal_multisubject.congeal_multisubject_inner_loop(
                    fixed, moving, initial, 'Affine', 20, 1, 1, str(folder),
                    np.array([10., 5.]), 300, False, 6)
                return time.perf_counter()-started, output
        def equal_optimizer(left, right):
            for a, b in zip(left, right):
                np.testing.assert_array_equal(a, b)
        equal_optimizer(optimizer('author', 'warm')[1], optimizer('bulk', 'warm')[1])
        for repeat in range(3):
            names = list(optimizer_times)
            if repeat%2:
                names.reverse()
            outputs = {}
            for name in names:
                elapsed, outputs[name] = optimizer(name, repeat)
                optimizer_times[name].append(elapsed)
            equal_optimizer(outputs['author'], outputs['bulk'])
        assert wma.fibers.FiberArray.convert_from_polydata is original
        old, new = (statistics.median(times[key]) for key in times)
        old_opt, new_opt = (statistics.median(optimizer_times[key]) for key in optimizer_times)
        record = dict(subject_id=subject, source_lines=source_count, sampled_fibers=20000,
                      points_per_fiber=15, author_seconds=old, optimized_seconds=new,
                      speed_ratio=old/new, saved_seconds=old-new, times=times,
                      exact_all_arrays_and_hemispheres=True, exact_point_counts=[2,3,10,15,30],
                      optimizer_author_seconds=old_opt, optimizer_bulk_seconds=new_opt,
                      optimizer_ratio=old_opt/new_opt, optimizer_times=optimizer_times,
                      optimizer_fixed=128, optimizer_moving=64, maxfun=300,
                      synthetic_translation_mm=[20,0,0],
                      exact_entire_optimizer_trajectory=True, exact_final_transform=True,
                      objective_history=np.asarray(outputs['author'][1]).tolist(),
                      objective_change=float(outputs['author'][2]))
        records.append(record)
        print(json.dumps(record), flush=True)
    assert all(sha(path) == value for path, value in hashes.items())
    payload = dict(status='passed', reviewed_on='2026-10-21', records=records,
                   author_verification=dict(url=url, sha256=author_sha), compatibility=support,
                   source_sha256=hashes, sources_unchanged=True, hook=fast.summary(),
                   environment=dict(python=sys.version, numpy=np.__version__, vtk=vtk.vtkVersion.GetVTKVersion(),
                                    platform=platform.platform(), thread_env={key:os.environ.get(key) for key in
                                    ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}),
                   scope='Complete array-conversion substage and complete small author optimizer; not full WMA',
                   limitations=['20,000 sampled lines per subject, no full-tractogram timing',
                                'Only registration process hook enabled, not 74-tract clustering',
                                'Shared host, warm cache; no full-WMA or anatomical-accuracy claim',
                                'Historical source tractograms with sampling QC failures remain failed'])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2)+'\n')
    fields = ('subject_id','sampled_fibers','points_per_fiber','author_seconds','optimized_seconds',
              'speed_ratio','saved_seconds','optimizer_author_seconds','optimizer_bulk_seconds','optimizer_ratio')
    with args.report.with_suffix('.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows({key:record[key] for key in fields} for record in records)


if __name__ == '__main__':
    main()
