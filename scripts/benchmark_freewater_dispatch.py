"""Complete-stage original DIPY versus verified NLS-dispatch measurements.

Crop native real input grids without resampling, retain every mask voxel, then
alternate fresh output directories. This is ROI evidence, not full-brain timing.
"""

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys
import time
from unittest.mock import patch

import dipy
from dipy.core.gradients import gradient_table
from dipy.reconst import fwdti
import nibabel as nib
import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from microstructure import freewater_dispatch, pipeline
from shared.pipeline import RawInputBundle


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(left, right):
    paths, qc = left
    other_paths, other_qc = right
    for key in pipeline.FREE_WATER_KEYS:
        first, second = nib.load(paths[key]), nib.load(other_paths[key])
        np.testing.assert_array_equal(first.get_fdata(), second.get_fdata())
        np.testing.assert_array_equal(first.affine, second.affine)
        assert first.header.get_data_dtype() == second.header.get_data_dtype()
    for key in ('status', 'automatic_qc_passed', 'checks', 'validity', 'parameters', 'summary', 'warnings'):
        assert qc[key] == other_qc[key], key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append', required=True, type=Path, help='Canonical input directory')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--crop-size', type=int, default=12)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--fit-method', choices=('WLS', 'NLS'), default='NLS')
    args = parser.parse_args()
    if args.repeats < 3 or args.crop_size < 1:
        parser.error('At least three repeats and a positive crop size are required')
    if args.report.exists() or args.report.with_suffix('.csv').exists() or args.output.exists():
        parser.error('Refusing to overwrite existing evidence')
    args.output.mkdir(parents=True)
    from microstructure import freewater_wls
    code_paths = [Path(pipeline.__file__), Path(freewater_dispatch.__file__), Path(freewater_wls.__file__), Path(__file__),
                  Path(fwdti.__file__)]
    hashes = {str(path.resolve()): sha(path) for path in code_paths}
    records = []
    for source in args.source:
        source = source.resolve()
        subject = source.parent.name
        work = args.output / subject
        inputs = work / 'input'
        inputs.mkdir(parents=True)
        original = [source / name for name in ('data.nii.gz', 'bvals', 'bvecs', 'nodif_brain_mask.nii.gz')]
        hashes.update({str(path): sha(path) for path in original})
        image = nib.load(original[0])
        if any(size < args.crop_size for size in image.shape[:3]):
            raise ValueError('Crop must fit in every native input dimension')
        crop = tuple(slice((size-args.crop_size)//2, (size-args.crop_size)//2+args.crop_size)
                     for size in image.shape[:3])
        nib.save(image.slicer[crop], inputs / original[0].name)
        nib.save(nib.load(original[3]).slicer[crop], inputs / original[3].name)
        for path in original[1:3]:
            shutil.copy2(path, inputs / path.name)
        hashes.update({str(path): sha(path) for path in inputs.iterdir()})
        raw = RawInputBundle(work, subject, inputs, inputs/'data.nii.gz', inputs/'bvals',
                             inputs/'bvecs', inputs/'nodif_brain_mask.nii.gz')
        mask = nib.load(raw.mask_path).get_fdata() > 0
        signals = nib.load(raw.dwi_path).get_fdata(dtype=np.float32)[mask]
        bvals, bvecs = pipeline._load_bvals_bvecs(raw)
        gtab = gradient_table(bvals, bvecs=bvecs, b0_threshold=50)
        author = fwdti.FreeWaterTensorModel(gtab, fit_method=args.fit_method)
        optimized = fwdti.FreeWaterTensorModel(gtab, fit_method=args.fit_method)
        dispatch = freewater_dispatch.configure_freewater_dispatch(optimized, args.fit_method, 'serial')
        assert dispatch['enabled'], dispatch
        np.testing.assert_array_equal(author.fit(signals).model_params, optimized.fit(signals).model_params)

        def run(name, iteration):
            config = pipeline.MicrostructureConfig(subject, raw, None, work/(name+str(iteration)),
                         run_free_water=True, free_water_fit_method=args.fit_method, free_water_engine='serial')
            paths = pipeline._output_paths(subject, config.output_dir)
            paths['fwf'].parent.mkdir(parents=True)
            with patch.object(freewater_dispatch, 'configure_freewater_dispatch', return_value={
                    'enabled': False, 'implementation': 'dipy_original_dispatch'}) if name == 'reference' else nullcontext():
                start = time.perf_counter()
                pipeline._compute_free_water_maps(config=config, paths=paths)
                elapsed = time.perf_counter() - start
            qc = json.loads(paths['free_water_qc'].read_text())
            return elapsed, (paths, qc)

        compare(run('reference', 'warm')[1], run('optimized', 'warm')[1])
        times = {'reference': [], 'optimized': []}
        for repeat in range(args.repeats):
            outputs = {}
            methods = list(times)
            if repeat % 2:
                methods.reverse()
            for name in methods:
                elapsed, outputs[name] = run(name, repeat)
                times[name].append(elapsed)
            compare(outputs['reference'], outputs['optimized'])
        old, new = (statistics.median(times[name]) for name in ('reference', 'optimized'))
        record = dict(subject_id=subject, fit_method=args.fit_method, engine='serial',
                      shape=list(mask.shape), mask_voxels=int(mask.sum()), measurements=len(bvals),
                      reference_median_seconds=old, optimized_median_seconds=new, speed_ratio=old/new,
                      time_reduction_percent=100*(1-new/old), times_seconds=times,
                      repeats=args.repeats, warmups_per_method=1, exact_raw_parameters=True,
                      exact_exported_maps_and_qc=True, dispatch=dispatch,
                      automatic_qc_passed=outputs['optimized'][1]['automatic_qc_passed'],
                      validity=outputs['optimized'][1]['validity'])
        records.append(record)
        print(json.dumps(record), flush=True)
    assert all(sha(path) == digest for path, digest in hashes.items()), 'Source/input changed during benchmark'
    report = dict(status='passed', reviewed_on=datetime.now(timezone.utc).date().isoformat(), records=records,
                  source_sha256=hashes, source_inputs_unchanged=True,
                  comparison='Installed original DIPY '+args.fit_method+' versus source-qualified diagonal-free WLS and dispatch optimization',
                  scope='Complete real native-grid ROI stage: input validation/reading, same estimator, all mask voxels, maps, QC and fresh exports; no resampling',
                  environment=dict(python=sys.version, executable=sys.executable, dipy=dipy.__version__,
                                   numpy=np.__version__, scipy=scipy.__version__, platform=platform.platform(),
                                   thread_env={key: os.environ.get(key) for key in
                                               ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')}),
                  limitations=['Shared host, warm process; ROI timings are not full-brain or whole-workflow speedups',
                               'Nonserial engines remain unchanged; WLS/NLS are reported separately',
                               'No solver, initialization, convergence, weighting, precision, voxel or QC-threshold changes'])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    with args.report.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['subject_id', 'fit_method', 'engine', 'mask_voxels',
            'measurements', 'reference_median_seconds', 'optimized_median_seconds', 'speed_ratio',
            'time_reduction_percent', 'repeats', 'exact_raw_parameters', 'exact_exported_maps_and_qc',
            'automatic_qc_passed'], extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)


if __name__ == '__main__':
    main()
