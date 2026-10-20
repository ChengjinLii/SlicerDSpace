#!/usr/bin/env python3
"""Fresh, immutable-snapshot complete-model pairs with incremental evidence.

Run under a configured scientific Python. This never reuses fitted products or
changes an existing subject's outputs. A running pair is not a speedup result.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
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
        qc=qc,threads=os.environ.get('OMP_NUM_THREADS'),
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
                       and np.array_equal(*arrays,equal_nan=True))
        elif paths[0].suffix=='.npy':
            arrays=[np.load(path,mmap_mode='r') for path in paths]
            exact=arrays[0].shape==arrays[1].shape and all(np.array_equal(arrays[0][start:start+1024],arrays[1][start:start+1024],equal_nan=True) for start in range(0,len(arrays[0]),1024))
        else:
            exact=digest(paths[0])==digest(paths[1])
        records.append(dict(product=key,exact=exact))
    passed=bool(records) and all(row['exact'] for row in records)
    return dict(status='passed' if passed else 'failed',products=records,
        reference_seconds=left['runtime_seconds'],optimized_seconds=right['runtime_seconds'],
        speed_ratio=left['runtime_seconds']/right['runtime_seconds'] if passed else None,
        seconds_saved=left['runtime_seconds']-right['runtime_seconds'] if passed else None,
        interpretation=('AMICO original thread capability, not a new algorithm' if stage=='noddi' else
                        'Original WMA versus verified-source bulk/cache' if stage=='wma' else
                        'Implementation comparison, not original MATLAB' if stage=='mkcurve' else
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
    args=parser.parse_args()
    if args.settings:
        return worker(args)
    from scripts.stage_slicer_extension import stage_extension
    for name in ('output','source','wma_input','wma_atlas','wma_root','slicer'):
        if getattr(args,name) is not None:
            setattr(args,name,getattr(args,name).resolve())
    args.output.mkdir(parents=True,exist_ok=False)
    install=stage_extension(args.output/'install',slicer_version='Slicer-5.10',clean=False,link_mode='copy')
    snapshot=Path(install['module_dir'])
    stages=args.stages.split(',')
    if any(stage not in ('noddi','wma','mkcurve','dki') for stage in stages):
        raise ValueError('Unknown benchmark stage')
    settings={key:str(value) for key,value in vars(args).items() if value is not None}
    settings['snapshot']=str(snapshot)
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
                    process=subprocess.run([sys.executable,str(snapshot/'scripts/benchmark_complete_models.py'),
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
    record.update(status='passed' if all(p['status']=='passed' for p in record['pairs']) else 'failed',
                  current=None,snapshot_unchanged=all(digest(snapshot/name)==value for name,value in settings['snapshot_hashes'].items()))
    save(evidence,record)


if __name__=='__main__':
    main()
