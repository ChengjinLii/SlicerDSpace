#!/usr/bin/env python3
"""Fresh, immutable-snapshot complete-model pairs with incremental evidence.

Run under a configured scientific Python. This never reuses fitted products or
changes an existing subject's outputs. A running pair is not a speedup result.
"""

import argparse
import hashlib
from importlib.metadata import PackageNotFoundError, version
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def save(path, record):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def numerical_environment():
    packages = {}
    for name in ('dipy', 'scipy', 'numpy', 'nibabel', 'dmri-amico'):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return dict(python=sys.version, packages=packages,
                scope='Python benchmark worker; not a version probe of external Slicer/WSL children')


def export_freewater_campaign(campaign_path, output):
    """Recheck a completed immutable pair before exporting publication evidence."""
    if output.exists():
        raise FileExistsError('Refusing to replace measured evidence')
    campaign = json.loads(campaign_path.read_text())
    settings = campaign['settings']
    if campaign['status'] != 'passed' or not campaign['snapshot_unchanged'] or not campaign['harness_unchanged']:
        raise ValueError('Campaign is incomplete or changed')
    snapshot = Path(settings['snapshot'])
    if any(digest(snapshot / name) != value for name, value in settings['snapshot_hashes'].items()):
        raise ValueError('Frozen source changed after measurement')
    if digest(settings['benchmark_harness']) != settings['benchmark_harness_sha256']:
        raise ValueError('Frozen harness changed after measurement')
    root = campaign_path.parent / 'freewater'
    measurements = {name: json.loads((root / name / 'measurement.json').read_text())
                    for name in ('reference', 'optimized')}
    for measurement in measurements.values():
        if not measurement['inputs_unchanged']:
            raise ValueError('Inputs changed during measurement')
        for name, value in measurement['inputs_sha256'].items():
            path = Path(settings['source']) / {'dwi_path': 'data.nii.gz', 'bval_path': 'bvals',
                'bvec_path': 'bvecs', 'mask_path': 'nodif_brain_mask.nii.gz'}[name]
            if digest(path) != value:
                raise ValueError('Source input changed after measurement')
    reference, optimized = (measurements[name] for name in ('reference', 'optimized'))
    if reference['environment'] != optimized['environment']:
        raise ValueError('Backend environments differ')
    paired = compare(reference, optimized, 'freewater')
    if paired['status'] != 'passed' or not paired['qc_equal']:
        raise ValueError('Raw parameters/maps/QC did not match')
    raw = [row for row in paired['products'] if row['product'].startswith('raw_parameters_')]
    if not raw or not all(row['exact'] for row in raw):
        raise ValueError('Raw parameter evidence missing')
    qc = optimized['qc']
    before, after = reference['runtime_seconds'], optimized['runtime_seconds']
    import numpy as np
    record = dict(subject_id=settings['subject_id'], fit_method='WLS', engine='serial',
        mask_voxels=qc['validity']['brain_mask_voxels'],
        measurements=int(np.loadtxt(Path(settings['source']) / 'bvals').size),
        reference_seconds=before, optimized_seconds=after, seconds_saved=before-after,
        speed_ratio=before/after, time_reduction_percent=100*(1-after/before),
        pairs=1, threads_per_variant=1, order=['optimized', 'reference'],
        exact_raw_parameters=True, exact_exported_maps_and_qc=True,
        automatic_qc_passed=qc['automatic_qc_passed'], validity=qc['validity'])
    result = dict(status='passed', reviewed_on=datetime.now(timezone.utc).date().isoformat(),
        records=[record], products=paired['products'], inputs_unchanged=True,
        snapshot_unchanged=True, harness_unchanged=True, qc_equal=True,
        qc={key: qc[key] for key in ('status', 'automatic_qc_passed', 'checks', 'validity', 'parameters', 'summary', 'warnings')},
        environment={**optimized['environment']['packages'], 'python': optimized['environment']['python']},
        campaign_sha256=digest(campaign_path), harness_sha256=digest(settings['benchmark_harness']),
        source_inputs_sha256=optimized['inputs_sha256'],
        runtime_snapshot_sha256=settings['snapshot_hashes'],
        scope='Complete native full-brain FW pair, not the whole workflow',
        limitations=['One shared-host pair; optimized first; caches not flushed',
                     'Each timed call includes the same raw parameter export',
                     'Within-environment equivalence, not cross-release equivalence or anatomical review'])
    output.parent.mkdir(parents=True, exist_ok=True)
    save(output, result)
    return result


def stage_benchmark_harness(output):
    """Keep developer tooling outside the installable runtime snapshot."""
    harness = output/'harness'
    harness.mkdir()
    target = harness/Path(__file__).name
    shutil.copy2(Path(__file__), target)
    return target


def worker(args):
    settings = json.loads(args.settings.read_text())
    source = Path(settings['source'])
    root = args.settings.parent
    output = root / args.variant
    output.mkdir(exist_ok=False)
    sys.path.insert(0, settings['snapshot'])
    from shared.pipeline import RawInputBundle
    raw = RawInputBundle(root, settings['subject_id'], source,
        source/'data.nii.gz',source/'bvals',source/'bvecs',source/'nodif_brain_mask.nii.gz')
    input_files={key:getattr(raw,key) for key in ('dwi_path','bval_path','bvec_path','mask_path')}
    if args.stage=='wma':
        input_files['wma_input']=Path(settings['wma_input'])
        for kind,folder,pattern in (('atlas',settings['wma_atlas'],'*'),('author',settings['wma_root'],'*.py')):
            for path in Path(folder).rglob(pattern):
                if path.is_file():
                    input_files[kind+':'+str(path.relative_to(folder))]=path
    before = {key:digest(path) for key,path in input_files.items()}
    start = time.monotonic()
    if args.stage == 'noddi':
        from microstructure import pipeline as p
        # No native DTI is consumed by this independent NODDI model fit.
        config = p.MicrostructureConfig(raw.subject_id,raw,None,output,run_noddi=True,
                                        noddi_nthreads=1 if args.variant=='reference' else 8)
        paths=p._output_paths(raw.subject_id,output)
        p._compute_noddi_maps(config=config,paths=paths,log=print)
        files={key:str(paths[key]) for key in p.NODDI_KEYS}
        qc=p._read_json(paths['noddi_qc'])
    elif args.stage == 'mkcurve':
        from microstructure.mkcurve import run_mkcurve
        if args.variant == 'reference':
            import microstructure.mkcurve_tensor as tensor
            from itertools import combinations_with_replacement
            from math import factorial
            import numpy as np
            def basis(directions,order):
                directions=np.asarray(directions,dtype=np.float64)
                indices=list(combinations_with_replacement(range(3),order))
                counts=[factorial(order)/np.prod([factorial(index.count(j)) for j in range(3)]) for index in indices]
                return np.stack([np.prod(directions[...,index],axis=-1)*count for index,count in zip(indices,counts)],axis=-1)
            def mean(coefficients):
                directions=tensor.integration_directions()
                adc=coefficients[:,1:7]@basis(directions,2).T
                fourth=coefficients[:,7:22]@basis(directions,4).T
                with np.errstate(all='ignore'):
                    result=np.mean(fourth/adc**2,axis=1)
                    squared=np.mean(coefficients[:,[1,4,6]],axis=1)**2
                    result[(squared==0)|~np.isfinite(squared)]=np.nan
                return result
            tensor.tensor_basis,tensor.mean_kurtosis=basis,mean
        qc=run_mkcurve(raw.dwi_path,raw.bval_path,raw.bvec_path,raw.mask_path,output/'fit',
            max_bvalue=2500.,voxels_per_chunk=256,num_workers=1,solver='batched',log=print)
        files={**qc['maps'],**qc['auxiliary_files']}
    elif args.stage == 'dki':
        from microstructure.dki import DkiConfig, run_dki
        config=DkiConfig(raw.subject_id,raw,output/'fit',force_recompute=True,
                         dense_metrics=args.variant=='optimized')
        result=run_dki(config,log=print)
        files={key:str(path) for key,path in result.outputs.items() if key not in ('manifest','qc','progress')}
        qc=json.loads(result.qc_path.read_text())
    elif args.stage == 'freewater':
        from contextlib import nullcontext
        from functools import wraps
        from unittest.mock import patch
        import numpy as np
        from dipy.reconst import fwdti
        from microstructure import freewater_dispatch, pipeline as p
        config=p.MicrostructureConfig(raw.subject_id,raw,None,output,run_free_water=True,
                                      free_water_fit_method='WLS',free_water_engine='serial')
        paths=p._output_paths(raw.subject_id,output)
        paths['fwf'].parent.mkdir(parents=True,exist_ok=True)
        original_fit=fwdti.FreeWaterTensorModel.fit
        raw_parameters={}
        @wraps(original_fit)
        def recorded_fit(model,*fit_args,**fit_kwargs):
            fitted=original_fit(model,*fit_args,**fit_kwargs)
            key=f'raw_parameters_{len(raw_parameters):04d}'
            path=output/(key+'.npy')
            np.save(path,fitted.model_params)
            raw_parameters[key]=str(path)
            return fitted
        dispatch=patch.object(freewater_dispatch,'configure_freewater_dispatch',return_value={
            'enabled':False,'implementation':'dipy_original_dispatch'}) if args.variant=='reference' else nullcontext()
        with dispatch, patch.object(fwdti.FreeWaterTensorModel,'fit',recorded_fit):
            p._compute_free_water_maps(config=config,paths=paths,log=print)
        files={**{key:str(paths[key]) for key in p.FREE_WATER_KEYS},**raw_parameters}
        qc=json.loads(paths['free_water_qc'].read_text())
    elif args.stage == 'wma':
        from tractography.wma import WMAOrgAtlasConfig,run_wma_org_atlas
        result=run_wma_org_atlas(WMAOrgAtlasConfig(raw.subject_id,Path(settings['wma_input']),
            Path(settings['wma_atlas']),output/'fit',Path(settings['slicer']),
            wma_root=Path(settings['wma_root']),num_threads=8,use_virtual_x=True,execute=True,
            registration_preprocess_cache=args.variant=='optimized'),log=print)
        qc=json.loads(result.qc_path.read_text())
        files={path.name:str(path) for path in (output/'fit').rglob('T_*.vtp')}
        if result.status != 'completed':
            raise RuntimeError('WMA did not complete; retain failed QC, do not compare timing as success')
    else:
        raise ValueError(args.stage)
    elapsed=time.monotonic()-start
    unchanged=before=={key:digest(path) for key,path in input_files.items()}
    if not unchanged:
        raise RuntimeError('Benchmark inputs changed')
    save(output/'measurement.json',dict(status='completed',stage=args.stage,variant=args.variant,
        runtime_seconds=elapsed,inputs_sha256=before,inputs_unchanged=unchanged,files=files,
        qc=qc,threads=os.environ.get('OMP_NUM_THREADS'), environment=numerical_environment(),
        scope='Complete model call including preparation, fitting, QC and output; not whole SlicerDDSurfer'))


def compare(left,right,stage):
    import nibabel as nib
    import numpy as np
    records=[]
    if left['files'].keys()!=right['files'].keys():
        raise ValueError('Product sets differ')
    for key in left['files']:
        paths=[Path(row['files'][key]) for row in (left,right)]
        if paths[0].name.endswith('.nii.gz'):
            images=[nib.load(path) for path in paths]
            arrays=[np.asanyarray(image.dataobj) for image in images]
            exact=bool(np.array_equal(images[0].affine,images[1].affine)
                       and images[0].header.get_data_dtype()==images[1].header.get_data_dtype()
                       and np.array_equal(*arrays,equal_nan=True))
        elif paths[0].suffix=='.npy':
            arrays=[np.load(path,mmap_mode='r') for path in paths]
            exact=arrays[0].dtype==arrays[1].dtype and arrays[0].shape==arrays[1].shape and all(np.array_equal(arrays[0][start:start+1024],arrays[1][start:start+1024],equal_nan=True) for start in range(0,len(arrays[0]),1024))
        else:
            exact=digest(paths[0])==digest(paths[1])
        records.append(dict(product=key,exact=exact))
    passed=bool(records) and all(row['exact'] for row in records)
    qc_equal=None
    if stage=='freewater':
        keys=('status','automatic_qc_passed','checks','validity','parameters','summary','warnings')
        qc_equal=all(left['qc'].get(key)==right['qc'].get(key) for key in keys)
        passed=passed and qc_equal
    return dict(status='passed' if passed else 'failed',products=records,
        reference_seconds=left['runtime_seconds'],optimized_seconds=right['runtime_seconds'],
        speed_ratio=left['runtime_seconds']/right['runtime_seconds'] if passed else None,
        seconds_saved=left['runtime_seconds']-right['runtime_seconds'] if passed else None,
        qc_equal=qc_equal,
        interpretation=('AMICO original thread capability, not a new algorithm' if stage=='noddi' else
                        'Original WMA versus verified-source bulk/cache' if stage=='wma' else
                        'Implementation comparison, not original MATLAB' if stage=='mkcurve' else
                        'Original DIPY WLS versus verified diagonal-free WLS, same serial threads' if stage=='freewater' else
                        'Unchanged DIPY WLS with array-level metric evaluation'),
        limitations=['One pair on a shared Linux host; no confidence interval',
                     'Not whole-workflow or anatomical-accuracy acceptance'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--subject-id',default='100307')
    parser.add_argument('--stages',default='noddi,wma,mkcurve,dki')
    parser.add_argument('--wma-input',type=Path)
    parser.add_argument('--wma-atlas',type=Path)
    parser.add_argument('--wma-root',type=Path)
    parser.add_argument('--slicer',type=Path)
    parser.add_argument('--settings',type=Path)
    parser.add_argument('--stage')
    parser.add_argument('--variant')
    parser.add_argument('--export-freewater', type=Path, help='Recheck a completed campaign and write --output JSON')
    args=parser.parse_args()
    if args.export_freewater:
        return export_freewater_campaign(args.export_freewater, args.output)
    if args.settings:
        return worker(args)
    from scripts.stage_slicer_extension import stage_extension
    for name in ('output','source','wma_input','wma_atlas','wma_root','slicer'):
        if getattr(args,name) is not None:
            setattr(args,name,getattr(args,name).resolve())
    args.output.mkdir(parents=True,exist_ok=False)
    install=stage_extension(args.output/'install',slicer_version='Slicer-5.10',clean=False,link_mode='copy')
    snapshot=Path(install['module_dir'])
    harness=stage_benchmark_harness(args.output)
    stages=args.stages.split(',')
    if any(stage not in ('noddi','wma','mkcurve','dki','freewater') for stage in stages):
        raise ValueError('Unknown benchmark stage')
    settings={key:str(value) for key,value in vars(args).items() if value is not None}
    settings['snapshot']=str(snapshot)
    settings['benchmark_harness']=str(harness)
    settings['benchmark_harness_sha256']=digest(harness)
    settings['snapshot_hashes']={str(p.relative_to(snapshot)):digest(p) for p in snapshot.rglob('*') if p.is_file()}
    record=dict(kind='complete_model_paired_campaign',status='running',settings=settings,pairs=[],
                scope='Fresh complete model calls, not an end-to-end workflow comparison')
    evidence=args.output/'campaign.json'
    save(evidence,record)
    for stage in stages:
        folder=args.output/stage
        folder.mkdir()
        configuration=folder/'settings.json'
        save(configuration,settings)
        try:
            for variant in ('optimized','reference'):
                record['current']=dict(stage=stage,variant=variant,status='running')
                save(evidence,record)
                with (folder/(variant+'.log')).open('wb') as stream:
                    process=subprocess.run([sys.executable,str(harness),
                        '--settings',str(configuration),'--stage',stage,'--variant',variant],
                        stdout=stream,stderr=subprocess.STDOUT,env=os.environ.copy())
                if process.returncode:
                    raise RuntimeError(f'{stage}/{variant} failed, see retained log')
            measurements=[json.loads((folder/variant/'measurement.json').read_text()) for variant in ('reference','optimized')]
            result=compare(*measurements,stage)
            result['stage']=stage
            save(folder/'comparison.json',result)
            record['pairs'].append(result)
        except Exception as exc:
            record['pairs'].append(dict(stage=stage,status='failed',error=str(exc)))
        save(evidence,record)
    snapshot_unchanged=all(digest(snapshot/name)==value for name,value in settings['snapshot_hashes'].items())
    harness_unchanged=digest(harness)==settings['benchmark_harness_sha256']
    record.update(status='passed' if all(p['status']=='passed' for p in record['pairs']) and snapshot_unchanged and harness_unchanged else 'failed',
                  current=None,snapshot_unchanged=snapshot_unchanged,harness_unchanged=harness_unchanged)
    save(evidence,record)


if __name__=='__main__':
    main()
