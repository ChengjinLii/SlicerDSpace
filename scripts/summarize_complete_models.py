#!/usr/bin/env python3
"""Publish measured pairs and explicit pending states, optionally while running."""

import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time


def read(path):
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def wma_input_audit(campaign, current):
    """Independently fingerprint the actual WMA inputs before its first fit."""
    settings=(current or {}).get('settings',{})
    if 'wma' not in settings.get('stages','').split(','):
        return None
    path=campaign.parent/'wma_input_audit.json'
    record=read(path)
    def signatures():
        files=[Path(settings['wma_input'])]
        files.extend(p for p in Path(settings['wma_atlas']).rglob('*') if p.is_file())
        files.extend(Path(settings['wma_root']).rglob('*.py'))
        result={}
        for file in sorted(set(files)):
            digest=hashlib.sha256()
            with file.open('rb') as stream:
                for block in iter(lambda:stream.read(8*1024*1024),b''):
                    digest.update(block)
            result[str(file.resolve())]=digest.hexdigest()
        return result
    try:
        if record is None:
            before_stage=not (campaign.parent/'wma').exists()
            before=signatures()
            before_stage=before_stage and not (campaign.parent/'wma').exists()
            record=dict(status='pending',captured_before_wma=before_stage,
                captured_at=datetime.now(timezone.utc).isoformat(),before=before,
                scope='WMA tractogram, complete ORG atlas files and author Python sources; outside timed calls')
        if (campaign.parent/'wma/comparison.json').is_file() and record['status']=='pending':
            record['after']=signatures()
            record['inputs_unchanged']=record['before']==record['after']
            record['status']='passed' if record['captured_before_wma'] and record['inputs_unchanged'] else 'failed'
            record['checked_at']=datetime.now(timezone.utc).isoformat()
    except (OSError,KeyError) as exc:
        record=dict(status='failed',error=str(exc))
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)
    return dict(status=record['status'],captured_before_wma=record.get('captured_before_wma'),
                inputs_unchanged=record.get('inputs_unchanged'),path=str(path.resolve()),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def summarize(campaign, roi, concurrency, output):
    current,regions,overlap=(read(path) for path in (campaign,roi,concurrency))
    wma_sources=wma_input_audit(campaign,current)
    pairs=[]
    for item in (current or {}).get('pairs',[]):
        item=item.copy()
        if item['stage']=='wma' and item['status']=='passed' and (wma_sources or {}).get('status')!='passed':
            item.update(status='source_audit_not_passed',speed_ratio=None,seconds_saved=None)
        pairs.append(item)
    rows=[]
    for row in pairs:
        rows.append(dict(stage=row['stage'],scope='complete_model',status=row['status'],
            reference_seconds=row.get('reference_seconds'),optimized_seconds=row.get('optimized_seconds'),
            speed_ratio=row.get('speed_ratio'),seconds_saved=row.get('seconds_saved')))
    for row in (regions or {}).get('cases',[]):
        rows.append(dict(stage='DKI '+row['subject'],scope=f"real_{regions['roi_side']}^3_ROI_complete_stage",
            status='passed' if row['all_output_arrays_exact'] else 'failed',
            reference_seconds=row['median_seconds']['reference'],optimized_seconds=row['median_seconds']['optimized'],
            speed_ratio=row['speed_ratio'],seconds_saved=row['seconds_saved']))
    if overlap and overlap.get('status')=='passed':
        rows.append(dict(stage='FW + DKI',scope='real_24^3_ROI_model_scheduling',status='passed',
            reference_seconds=overlap['measurements'][0]['elapsed_seconds'],
            optimized_seconds=overlap['measurements'][1]['elapsed_seconds'],
            speed_ratio=overlap['speed_ratio'],seconds_saved=overlap['seconds_saved']))
    evidence={}
    for name,path in (('campaign',campaign),('roi',roi),('concurrency',concurrency)):
        if path is not None and path.is_file():
            evidence[name]=dict(path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    record=dict(kind='complete_models_and_concurrency_evidence',updated_at=datetime.now(timezone.utc).isoformat(),
        campaign_status=(current or {}).get('status','not_started'),
        current_pair=(current or {}).get('current'),measurements=rows,
        complete_model_pairs=pairs,wma_input_audit=wma_sources,
        completed_variants=[],roi_evidence=regions,concurrency_evidence=overlap,evidence=evidence,
        limitations=['ROI measurements are never extrapolated to full brain',
                     'Concurrent scheduling is not an original-algorithm speedup',
                     'No whole SlicerDDSurfer matched end-to-end pair completed by this summary',
                     'Shared Linux host; single complete-model pair, no confidence interval',
                     'Scientific validity/excluded voxels and human anatomical review remain separate'])
    if current:
        for stage in current['settings']['stages'].split(','):
            for variant in ('reference','optimized'):
                measurement=campaign.parent/stage/variant/'measurement.json'
                if measurement.is_file():
                    item=read(measurement)
                    record['completed_variants'].append(dict(stage=stage,variant=variant,
                        seconds=item['runtime_seconds'],inputs_unchanged=item['inputs_unchanged'],
                        evidence=str(measurement.resolve()),sha256=hashlib.sha256(measurement.read_bytes()).hexdigest()))
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.tmp')
    temporary.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    temporary.replace(output)
    columns=['stage','scope','status','reference_seconds','optimized_seconds','speed_ratio','seconds_saved']
    csv_path=output.with_suffix('.csv')
    temporary=csv_path.with_suffix('.csv.tmp')
    with temporary.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(csv_path)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--roi',type=Path)
    parser.add_argument('--concurrency',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--watch',action='store_true')
    args=parser.parse_args()
    while True:
        result=summarize(args.campaign,args.roi,args.concurrency,args.output)
        print(json.dumps(dict(updated_at=result['updated_at'],campaign_status=result['campaign_status'],
            completed_pairs=len(result['complete_model_pairs']),rows=len(result['measurements']))),flush=True)
        if not args.watch or (result['campaign_status'] in ('passed','failed')
                             and (result['roi_evidence'] or {}).get('status') in ('passed','failed')):
            break
        time.sleep(60)
