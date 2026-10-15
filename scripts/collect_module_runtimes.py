#!/usr/bin/env python3
"""Create a scoped timing inventory without substituting estimates for records.

Historical task copies are deduplicated. Failed, reused, skipped and dry-run
records remain in the ledger, but cannot supply a successful compute timing.
"""

import argparse
from datetime import datetime, timezone
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.generate_protocol_benchmarks import _seconds, _report_generation_system


CATALOG = [
    ('input.nifti', 'NIfTI import', 'NIfTI 导入'),
    ('input.dicom', 'DICOM import', 'DICOM 导入'),
    ('input.nrrd', 'NRRD import', 'NRRD 导入'),
    ('validation', 'Input validation', '输入校验'),
    ('brainmask.pnl_cnn', 'PNL diffusion CNN mask', 'PNL CNN 掩膜'),
    ('brainmask.mrtrix', 'MRtrix dwi2mask', 'MRtrix 掩膜'),
    ('brainmask.synthstrip', 'SynthStrip mask', 'SynthStrip 掩膜'),
    ('preprocessing.dipy', 'DIPY preprocessing', 'DIPY 预处理'),
    ('preprocessing.mrtrix_fsl', 'MRtrix/FSL preprocessing', 'MRtrix/FSL 预处理'),
    ('microstructure.native_dti_fresh', 'Fresh native DTI fitting', '全新原生 DTI 拟合'),
    ('segmentation.ddseg', 'DDSeg', 'DDSeg'),
    ('segmentation.ddseg_world_qc', 'DDSeg world-coordinate QC', 'DDSeg 世界坐标 QC'),
    ('parcellation.ddparcel', 'DDParcel', 'DDParcel'),
    ('surface.ddsurfer', 'DDSurfer native surfaces', 'DDSurfer 原生表面'),
    ('surface.ddsurfer_postprocess', 'Surface postprocessing', '表面后处理'),
    ('microstructure.dti', 'DTI scalar export / ROI', 'DTI 参数导出 / ROI'),
    ('microstructure.freewater', 'Free-water', 'Free-water'),
    ('microstructure.noddi', 'AMICO NODDI', 'AMICO NODDI'),
    ('microstructure.dki', 'DIPY DKI WLS', 'DIPY DKI WLS'),
    ('microstructure.mkcurve', 'Python MK-Curve', 'Python MK-Curve'),
    ('tractography.dti_det', 'DTI deterministic tractography', 'DTI 确定性追踪'),
    ('tractography.csd_act', 'CSD / ACT / SIFT2 route', 'CSD / ACT / SIFT2 路线'),
    ('tractography.saf', 'SAF re-filtering', 'SAF 重新筛选'),
    ('bundles.wmql', 'WMQL', 'WMQL'),
    ('bundles.wma', 'WMA ORG atlas', 'WMA ORG atlas'),
    ('bundles.tractcloud', 'TractCloud', 'TractCloud'),
    ('connectome.streamline_count', 'Count connectome', '流线计数连接组'),
    ('connectome.sift2_weighted', 'SIFT2 connectome', 'SIFT2 加权连接组'),
    ('statistics.regional_microstructure', 'Six-map regional statistics', '六指标脑区统计'),
    ('slicer.load.wmql', 'Slicer WMQL result loading', 'Slicer 加载 WMQL'),
    ('slicer.load.tractcloud', 'Slicer TractCloud result loading', 'Slicer 加载 TractCloud'),
    ('slicer.load.wma', 'Slicer WMA result loading', 'Slicer 加载 WMA'),
]
SUCCESS = {'completed', 'passed', 'success', 'pass'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def bundle_timing_status(module, payload):
    from shared.bundle_qc import bundle_record_error

    if bundle_record_error(module, payload):
        return 'scientific_contract_failed'
    return payload.get('status', 'unknown')


def record(module, subject, seconds, source, field, scope, *, status='completed', priority=0, evidence='historical', **extra):
    return dict(module=module, subject_id=subject, runtime_seconds=_seconds(seconds), status=status,
                source_record=str(source.resolve()), source_field=field,
                source_record_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                scope=scope, priority=priority, evidence=evidence, **extra)


def collect_device_measurements(directory):
    """Keep paired/repeated/failed acceptances, not just the fastest GPU time."""
    records = []
    runs = [
        ('brainmask.pnl_cnn', '100307', 'cpu/pnl_cnn_acceptance.json', 'seconds', False,
         'CPU reference', '288-volume real HCP DWI'),
        ('brainmask.pnl_cnn', '100307', 'gpu/pnl_cnn_acceptance.json', 'seconds', True,
         'Default Auto GPU run', '288-volume real HCP DWI'),
        ('brainmask.pnl_cnn', '100307', 'gpu_warm/pnl_cnn_acceptance.json', 'seconds', False,
         'Explicit CUDA repeat', '288-volume real HCP DWI'),
        ('brainmask.synthstrip', 'sub-dicom', 'synthstrip_modern_cpu/synthstrip_acceptance.json', 'seconds', False,
         'Compatible-runtime CPU reference', '31-volume real DWI'),
        ('brainmask.synthstrip', 'sub-dicom', 'synthstrip_modern_gpu/synthstrip_acceptance.json', 'seconds', True,
         'Compatible-runtime Auto GPU run', '31-volume real DWI'),
        ('brainmask.synthstrip', 'sub-dicom', 'synthstrip_gpu/synthstrip_acceptance.json', 'seconds', False,
         'Stopped incompatible-runtime attempt; no mask', '31-volume real DWI'),
        ('brainmask.synthstrip', 'sub-dicom', 'synthstrip_old_guard/synthstrip_acceptance.json', 'seconds', False,
         'Incompatible-runtime rejection; no inference', '31-volume real DWI'),
        ('preprocessing.mrtrix_fsl', 'sub-dicom', 'eddy_cuda_real/acceptance.json', 'runtime_seconds', False,
         'Failed CUDA eddy thread-option attempt', '31-volume real DWI / reverse-PE b0'),
        ('preprocessing.mrtrix_fsl', 'sub-dicom', 'eddy_cuda_fixed/acceptance.json', 'runtime_seconds', True,
         'Corrected CUDA eddy full preprocessing', '31-volume real DWI / reverse-PE b0'),
        ('bundles.tractcloud', '100307', 'tractcloud/tractcloud_qc.json', 'elapsed_seconds', True,
         'Seeded CUDA inference and decoded QC', '50k CSD/ACT tracks / batch 2048 / seed 0'),
        ('brainmask.pnl_cnn', '100307', 'pnl_phase_gpu/pnl_cnn_acceptance.json', 'seconds', False,
         'Phase-instrumented Auto GPU repeat', '288-volume real HCP DWI'),
        ('brainmask.synthstrip', 'sub-dicom', 'synthstrip_phase_gpu/synthstrip_acceptance.json', 'seconds', False,
         'Phase-instrumented Auto GPU repeat', '31-volume real DWI'),
        ('preprocessing.mrtrix_fsl', 'sub-dicom', 'eddy_cuda_fresh/acceptance.json', 'runtime_seconds', True,
         'Latest current-policy CUDA preprocessing rerun', '31-volume real DWI / reverse-PE b0'),
    ]
    for module, subject, relative, field, representative, label, inputs in runs:
        path = directory / relative
        if not path.is_file():
            continue
        payload = read(path)
        result = payload.get('result', {})
        device = result.get('device_execution') or payload.get('device_execution') or {}
        device_path = path.parent / 'tractcloud_device.json'
        if module == 'bundles.tractcloud' and device_path.is_file():
            device = read(device_path)
        status = payload.get('status', 'unknown')
        qc = result.get('qc', {})
        integrity = None
        if module.startswith('brainmask.') and status.lower() in SUCCESS:
            integrity = (result.get('status') == 'completed'
                         and all(qc.get(key) is True for key in ('geometry_pass', 'binary', 'finite'))
                         and payload.get('supplied_mask_unchanged') is True)
        elif module == 'preprocessing.mrtrix_fsl' and status.lower() in SUCCESS:
            checks = payload.get('checks', {})
            integrity = bool(checks) and all(value is True for value in checks.values())
        elif module == 'bundles.tractcloud' and status.lower() in SUCCESS:
            products = payload.get('output_summary', {})
            count = products.get('bundle_count', 0)
            integrity = (payload.get('executed') is True and payload.get('return_code') == 0
                         and count > 0 and products.get('bundle_readable_count') == count
                         and products.get('bundle_nonempty_count') == count)
        if integrity is False:
            status = 'integrity_contract_failed'
        rounded_phases = {}
        if module == 'brainmask.pnl_cnn':
            for label_name, key in (('Pre-Processing', 'registration_and_preprocessing'),
                                    ('Masking', 'cnn_models'), ('Total', 'upstream_total')):
                match = re.search(re.escape(label_name) + r' Time Taken\s*:\s*([\d.]+)\s*min', result.get('stdout_tail', ''))
                if match:
                    rounded_phases[key] = float(match.group(1)) * 60
        scopes = {
            'brainmask.pnl_cnn': 'Fresh acceptance: hashing, b0 preparation, Python startup, ANTs registration, CNN, mask QC; excludes Docker startup/downloads',
            'brainmask.synthstrip': 'Fresh acceptance: hashing, b0 preparation, Python startup, SynthStrip and mask QC; excludes installation/GUI startup',
            'preprocessing.mrtrix_fsl': 'Whole preprocessing acceptance including CPU denoise/Gibbs/topup, CUDA eddy, final mask and integrity checks; not eddy-only time',
            'bundles.tractcloud': 'Fresh seeded CUDA wrapper/upstream inference and decoded QC; excludes tractography/model download; anatomical review pending',
        }
        records.append(record(
            module, subject, payload.get(field), path, field, scopes[module], status=status,
            priority=7 if relative == 'eddy_cuda_fresh/acceptance.json' else 6 if representative else 5, evidence='real_device_acceptance',
            input_scope=inputs, run_label=label, representative=representative,
            device=device.get('resolved'), requested_device=device.get('requested'),
            device_execution=device, input_records=result.get('signature', {}).get('inputs') or payload.get('source_sha256'),
            runtime_environment={key: device[key] for key in ('tensorflow_version', 'tensorflow_package_version', 'keras_package_version',
                                                          'torch_version', 'cuda_version') if key in device},
            device_source_record=str(device_path.resolve()) if device_path.is_file() else None,
            device_source_sha256=hashlib.sha256(device_path.read_bytes()).hexdigest() if device_path.is_file() else None,
            integrity_pass=integrity, original_status=payload.get('status'),
            phase_seconds=result.get('phase_seconds'), thread_environment=result.get('thread_environment'),
            rounded_upstream_phase_seconds=rounded_phases or None,
            anatomical_review=payload.get('anatomical_review') or payload.get('manual_scientific_review') or payload.get('human_review'),
            failure_reason=payload.get('error')))
    return records


def device_table(records, chinese=False):
    names = {module: zh if chinese else en for module, en, zh in CATALOG}
    selected_sources = {r['source_record'] for r in select(records) if r['source_record']}
    labels_zh = {
        'CPU reference': 'CPU 对照', 'Default Auto GPU run': '默认 Auto GPU 运行',
        'Explicit CUDA repeat': '显式 CUDA 重复',
        'Compatible-runtime CPU reference': '兼容环境 CPU 对照',
        'Compatible-runtime Auto GPU run': '兼容环境 Auto GPU 运行',
        'Stopped incompatible-runtime attempt; no mask': '不兼容环境中止；无掩膜',
        'Incompatible-runtime rejection; no inference': '不兼容环境提前拒绝；未推理',
        'Failed CUDA eddy thread-option attempt': 'CUDA eddy 线程参数失败',
        'Corrected CUDA eddy full preprocessing': '修正 CUDA eddy 后的完整预处理',
        'Seeded CUDA inference and decoded QC': '固定种子 CUDA 推理及解码 QC',
        'Phase-instrumented Auto GPU repeat': '含分阶段计时的 Auto GPU 重复',
        'Latest current-policy CUDA preprocessing rerun': '当前策略最新 CUDA 预处理重跑',
    }
    unrecorded = '未记录' if chinese else 'not recorded'
    lines = ['| 模块 | 运行 / 范围 | 请求 → 实际设备 | 秒 | 执行 / 完整性状态 |' if chinese else
             '| Module | Run / Scope | Requested / Actual Device | Seconds | Execution / Integrity Status |',
             '| --- | --- | --- | ---: | --- |']
    for r in records:
        if r.get('evidence') != 'real_device_acceptance':
            continue
        seconds = f"{r['runtime_seconds']:.3f}" if r['runtime_seconds'] is not None else 'MISSING'
        state = r['status']
        if r['source_record'] in selected_sources and state.lower() in SUCCESS:
            state += ' / ' + ('主表采用' if chinese else 'representative')
        label = labels_zh.get(r['run_label'], r['run_label']) if chinese else r['run_label']
        lines.append(f"| {names[r['module']]} | {label} | {r.get('requested_device') or unrecorded} / "
                     f"{r.get('device') or unrecorded} | {seconds} | {state} |")
    return '\n'.join(lines)


def collect(campaign, verification, device_verification=None):
    records, seen = [], set()
    for path in sorted(campaign.rglob('*_orchestration_manifest.json')):
        m = read(path)
        if m.get('kind') != 'slicerddsurfer_product_orchestration':
            continue
        for index, task in enumerate(m.get('tasks', [])):
            key = (m.get('subject_id'), task.get('name'), task.get('started_at'),
                   task.get('ended_at'), task.get('runtime_seconds'), task.get('status'))
            if key in seen:
                continue
            seen.add(key)
            name = task.get('name')
            if name == 'preprocessing.dwi':
                backend = read(Path(task['manifest_path'])).get('backend', {}).get('backend', 'unknown')
                name = 'preprocessing.' + backend
            scopes = {
                'microstructure.dti': 'Export scalar maps from an already fitted shared DTI bundle plus ROI statistics; not fresh tensor fitting',
                'surface.ddsurfer_postprocess': 'Historical full postprocessing before the October 13 synchronization; not a current-version performance claim',
                'tractography.csd_act': 'Combined response/FOD, ACT, tracking, conversion and SIFT2 stage; substeps not individually timed',
                'tractography.saf': 'Historical SAF route before the corrected Python port; use the separate current re-filter timing instead',
            }
            execution = task.get('status', 'unknown') if m.get('execute') else 'dry_run'
            if name in {'bundles.wmql', 'bundles.wma'} and execution in SUCCESS:
                qc = Path(task.get('qc_path') or '')
                execution = bundle_timing_status(name, read(qc) if qc.is_file() else {})
            records.append(record(name, m.get('subject_id'), task.get('runtime_seconds'), path,
                                  f'tasks[{index}].runtime_seconds', scopes.get(name, 'Recorded task wall time; shared prerequisite caches may already exist'),
                                  status=execution, started_at=task.get('started_at'), ended_at=task.get('ended_at'),
                                  input_scope='31-volume real DWI' if m.get('subject_id') == 'sub-dicom' else '100k UKF tracks' if name == 'bundles.wma' else 'HCP 100307 / task-specific real inputs'))
    measurements = verification / 'missing_times_slicer/measurements.json'
    if measurements.is_file():
        for index, r in enumerate(read(measurements)['records']):
            records.append(record(r['module'], r['subject_id'], r['runtime_seconds'], measurements,
                                  f'records[{index}].runtime_seconds', r['scope'], priority=3, evidence='new_real_measurement',
                                  input_scope=str(r.get('shape') or (str(r.get('roi_count')) + ' regions')), execution_record=r['source_record']))
    additional = [
        ('brainmask.pnl_cnn', '100307', ROOT / 'ignore/validation/brain_mask_backends_20261012/real-pnl/pnl_cnn_acceptance.json',
         'seconds', 'Historical CPU-only PNL mask generation and acceptance; includes hashing/b0/preprocessing/QC, excludes Docker startup and installation; full native HCP input', '288-volume real HCP DWI', False),
        ('brainmask.synthstrip', 'sub-dicom', verification / 'missing_times_slicer/mask_synthstrip.manifest.json',
         'runtime_seconds', 'Fresh SynthStrip mask, input hashing, b0 preparation and integrity checks', '31-volume real DWI', False),
        ('microstructure.dki', '100307', ROOT / 'ignore/validation/brain_mask_backends_20261012/dki/hcp100307_roi/outputs/02_microstructure/dki/dki_manifest.json',
         'runtime_seconds', 'Real 4x4x4x288 ROI only; full-brain DKI runtime remains unmeasured', '64 fit voxels / 288 volumes', True),
        ('microstructure.mkcurve', '100307', ROOT / 'ignore/validation/mkcurve_python_20261012/real_hcp100307_roi/python/mkcurve_record.json',
         'runtime_seconds', 'Real 2x2x2x288 ROI only; full-brain MK-Curve runtime remains unmeasured', '8 fit voxels / 288 volumes', True),
        ('tractography.saf', '100307', ROOT / 'ignore/validation/saf_python_20261013/refilter_100k/saf_qc.json',
         'elapsed_seconds', 'Corrected Python port re-filters 100k existing initial tracks; excludes new initial tractography', '100k tracks -> 13043 SAF candidates', False),
        ('bundles.wmql', '100307', verification / 'wmql_new/wmql_qc.json',
         'elapsed_seconds', 'Fresh current wrapper execution and decoded output QC; AF/CST rules, 27 output tracks; anatomical review pending', '50k CSD/ACT tracks', False),
        ('bundles.tractcloud', '100307', verification / 'tractcloud_seed0_run2/tractcloud_qc.json',
         'elapsed_seconds', 'Fresh seeded wrapper, upstream inference and decoded QC; excludes model download; seed 0; identical-hardware repeat verified', '50k CSD/ACT tracks / CUDA batch 2048 / seed 0', False),
        ('bundles.wma', '149741', campaign / '149741/outputs/04_tractography/bundles/wma_org_atlas/acceptance_science/wma_org_atlas_qc.json',
         'elapsed_seconds', 'Existing real official WMA run, rigid registration, 1 thread, 100k UKF tracks; not re-executed in this campaign', '100k UKF tracks / 74 nonempty bundles', False),
    ]
    for module, subject, path, field, scope, inputs, partial in additional:
        if path.is_file():
            m = read(path)
            records.append(record(module, subject, m.get(field), path, field, scope,
                                  status=bundle_timing_status(module, m) if module in {'bundles.wmql', 'bundles.wma'} else m.get('status', 'unknown'), priority=4, input_scope=inputs,
                                  evidence='new_real_measurement' if path.is_relative_to(verification) else 'historical_backend_record',
                                  partial=partial))
    native = verification / 'native_cli_fixed/bundle_products/bundle_products.json'
    if native.is_file() and read(native).get('status') == 'passed':
        for index, r in enumerate(read(native)['records']):
            records.append(record(r['module'], r['subject_id'], r['runtime_seconds'], native,
                                  f'records[{index}].runtime_seconds', r['scope'], priority=4, evidence='new_native_slicer_measurement',
                                  input_scope=str(r.get('shape') or (str(r.get('files')) + ' files / ' + str(r.get('streamlines')) + ' streamlines'))))
    latest = verification / 'native_seeded/bundle_products/bundle_products.json'
    if latest.is_file() and read(latest).get('status') == 'passed':
        for index, r in enumerate(read(latest)['records']):
            records.append(record(r['module'], r['subject_id'], r['runtime_seconds'], latest,
                                  f'records[{index}].runtime_seconds', r['scope'], priority=5, evidence='new_native_slicer_measurement',
                                  input_scope=f"{r['files']} files / {r['streamlines']} streamlines"))
    # Preserve known under-populated WMA evidence, but never promote its time
    # to the successful representative row just because an old status was green.
    for folder in ('qc_verified_20260916', 'linux_acceptance_20260813_full'):
        path = Path('/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/04_tractography/bundles/wma_org_atlas') / folder / 'wma_org_atlas_qc.json'
        if path.is_file():
            m = read(path)
            records.append(record('bundles.wma', '100307', m.get('elapsed_seconds'), path, 'elapsed_seconds',
                                  'Under-populated historical WMA output: excluded from successful timings, including a legacy completed status',
                                  status='scientific_contract_failed', original_status=m.get('status'), evidence='historical_failed_result'))
    if device_verification is not None:
        records.extend(collect_device_measurements(device_verification))
    return records


def collect_bundle_followup(directory):
    records = []
    for module, relative, scope in (
        ('bundles.wmql', 'wmql_dynamic1m/wmql_qc.json', 'Fresh 1M-track input; AF 80/53, CST 133/304; candidate integrity/sampling only, anatomy pending'),
        ('bundles.wma', 'wma_dynamic50k/wma_org_atlas_qc.json', 'Fresh official 50k dynamic CSD input; 64/74 nonempty but CST 1/0; FAILED, not a successful benchmark'),
    ):
        path = directory / relative
        if path.is_file():
            payload = read(path)
            records.append(record(module, payload.get('subject_id'), payload.get('elapsed_seconds'), path,
                                  'elapsed_seconds', scope, status=bundle_timing_status(module, payload), priority=10,
                                  evidence='real_bundle_followup', anatomical_review='pending', input_scope=scope))
    return records


def collect_cst_definition_followup(directory):
    source = directory / 'default_v4_paired/wmql_qc.json'
    audit_path = directory / 'default_v4_paired_audit.json'
    if not source.is_file() or not audit_path.is_file():
        return []
    from tractography.wmql import wmql_query_cache_current
    payload, independent = read(source), read(audit_path)
    manifest = read(source.with_name('wmql_manifest.json'))
    counts = {item['query_name']: item.get('streamline_count') for item in payload.get('output_summary', {}).get('bundles', [])}
    passed = (bundle_timing_status('bundles.wmql', payload) == 'completed'
              and wmql_query_cache_current(manifest)
              and bool(independent.get('checks')) and all(value is True for value in independent['checks'].values()))
    return [record('bundles.wmql', payload.get('subject_id'), payload.get('elapsed_seconds'), source,
                   'elapsed_seconds', 'QC v4; original paired DDParcel atlas; published/tutorial CST endpoint definition; anatomy pending',
                   status='completed' if passed else 'current_acceptance_failed', priority=30,
                   evidence='paired_published_cst_recheck', anatomical_review='pending',
                   input_scope=f"Existing {independent.get('input_streamlines')} CSD tracks; AF {counts.get('af.left')}/{counts.get('af.right')}, CST {counts.get('cst.left')}/{counts.get('cst.right')}; full query/import snapshots")]


def collect_completion_measurements(directory):
    """Promote new timings only after their independent acceptance completed."""
    records = []
    for module, relative in (
        ('microstructure.dki', 'dki_independent'),
        ('surface.ddsurfer_postprocess', 'postprocess'),
        ('bundles.wma', 'wma_dynamic1m'),
    ):
        source = directory / relative / 'acceptance.json'
        if not source.is_file():
            continue
        payload = read(source)
        passed = payload.get('status') == 'passed' and payload.get('automatic_qc_passed') is True
        passed &= bool(payload.get('checks') or payload.get('inputs_unchanged'))
        if payload.get('checks'):
            passed &= all(value is True for value in payload['checks'].values())
        if module == 'microstructure.dki':
            independent = payload.get('independent_checks') or []
            passed &= bool(independent) and all(check.get('passed') is True for check in independent)
            seconds = payload.get('full_fit_runtime_seconds')
            field = 'full_fit_runtime_seconds'
            scope = f"Full supplied brain mask: {payload.get('mask_voxels')} voxels; {payload.get('valid_voxels')} valid; read-only full-grid and direct-DIPY sample parity passed"
        else:
            seconds = payload.get('runtime_seconds')
            field = 'runtime_seconds'
            scope = ('Fresh full bilateral current-snapshot surface postprocessing; independent geometry/morphometry/annotation checks'
                     if module == 'surface.ddsurfer_postprocess' else
                     'Fresh official ORG atlas on existing 1M CSD input; decoded coverage and major-tract sampling checks')
            if module == 'bundles.wma':
                qc_path = Path(payload.get('qc') or '')
                passed &= qc_path.is_file() and not bundle_timing_status(module, read(qc_path)) == 'scientific_contract_failed'
            else:
                qc_path = Path(payload.get('qc') or '')
                qc = read(qc_path) if qc_path.is_file() else {}
                integrity = qc.get('integrity') or {}
                passed &= qc.get('automatic_qc_passed') is True and integrity.get('version') == 1
                passed &= bool(integrity.get('checks')) and all(value is True for value in integrity['checks'].values())
        records.append(record(module, payload.get('subject_id'), seconds, source, field, scope,
                              status='completed' if passed else payload.get('status', 'failed') if payload.get('status') != 'passed' else 'integrity_contract_failed',
                              priority=20, evidence='current_route_acceptance', anatomical_review=payload.get('human_review'),
                              input_scope=scope, device='cpu'))
    return records


def collect_scientific_closure(directory):
    """Full-brain timings and paired tracking comparisons, never anatomy approval."""
    records = []
    source = directory / 'mkcurve_fullbrain/acceptance.json'
    if source.is_file():
        payload = read(source)
        parity, checks = payload.get('reference_parity') or {}, payload.get('checks') or []
        passed = (payload.get('status') == 'passed' and payload.get('automatic_integrity_qc_passed') is True
                  and payload.get('inputs_unchanged') is True and bool(parity) and bool(checks)
                  and all(value.get('passed') is True for value in parity.values())
                  and all(check.get('passed') is True for check in checks)
                  and (payload.get('mask_voxels') or 0) > 0)
        records.append(record('microstructure.mkcurve', payload.get('subject_id', '100307'),
            payload.get('runtime_seconds'), source, 'runtime_seconds',
            'Complete supplied brain mask; batched WLLS with ill-conditioned QR fallback; full grid, source hashes and reference sample parity; no voxel filling',
            status='completed' if passed else 'current_acceptance_failed', priority=40,
            evidence='full_brain_mkcurve_acceptance', device='cpu', anatomical_review='pending',
            input_scope=f"{payload.get('mask_voxels')} mask voxels / {payload.get('corrected_valid_voxels')} corrected-valid; not all voxels valid",
            quantitative_domain_all_voxels_valid=payload.get('quantitative_domain_all_voxels_valid')))
    for module, relative, qc_name in (
        ('bundles.wmql', 'wmql_legacy_ukf', 'wmql_qc.json'),
        ('bundles.wma', 'wma_ukf_native', 'products/wma_org_atlas_qc.json'),
    ):
        source = directory / relative / qc_name
        independent = directory / (relative + '_independent') / 'acceptance.json'
        if not source.is_file():
            continue
        qc = read(source)
        audited = read(independent) if independent.is_file() else {}
        checks = audited.get('checks') or {}
        passed = (bundle_timing_status(module, qc) == 'completed'
                  and audited.get('status') == 'passed' and audited.get('automatic_qc_passed') is True
                  and bool(checks) and all(value is True for value in checks.values()))
        records.append(record(module, qc.get('subject_id'), qc.get('elapsed_seconds'), source,
            'elapsed_seconds', 'New same-subject UKF input; unchanged author classifier/rules and fixed major-tract gates; independent source membership; anatomy pending',
            status='completed' if passed else 'current_acceptance_failed', priority=40,
            evidence='paired_ukf_comparison', device='cpu', anatomical_review='pending',
            input_scope=f"{audited.get('input_streamlines')} UKF tracks; independent audit {'passed' if passed else 'required'}",
            independent_record=str(independent.resolve()) if independent.is_file() else None))
    return records


def select(records):
    rows = []
    for module, en, zh in CATALOG:
        eligible = [r for r in records if r['module'] == module and r['status'].lower() in SUCCESS
                    and r['runtime_seconds'] is not None]
        eligible.sort(key=lambda r: (r['priority'], r.get('started_at') or ''), reverse=True)
        selected = eligible[0] if eligible else {}
        value = selected.get('runtime_seconds')
        rows.append(dict(module=module, name=en, name_zh=zh,
                         measurement_status='PARTIAL' if selected.get('partial') else 'READY' if selected else 'MISSING',
                         seconds=value, minutes=value / 60. if value is not None else None,
                         subject_id=selected.get('subject_id'), input_scope=selected.get('input_scope'),
                         device=selected.get('device'), requested_device=selected.get('requested_device'),
                         anatomical_review=selected.get('anatomical_review'),
                         scope=selected.get('scope', 'No successful measured record in this scoped inventory'),
                         evidence=selected.get('evidence'), source_record=selected.get('source_record'),
                         source_field=selected.get('source_field'), source_record_sha256=selected.get('source_record_sha256')))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, default=ROOT / 'ignore/validation/slicer_acceptance_20261006/science/subjects')
    parser.add_argument('--verification', type=Path, default=ROOT / 'ignore/validation/bundles_runtime_20261013')
    parser.add_argument('--device-verification', type=Path, action='append', default=[ROOT / 'ignore/validation/pnl_gpu_20261013'])
    parser.add_argument('--report-date', default='2026-10-13', help='Dated documentation filename (YYYY-MM-DD); old inventories are preserved')
    parser.add_argument('--bundle-followup', type=Path, default=ROOT / 'ignore/validation/bundle_fix_20261015')
    parser.add_argument('--scalar-verification', type=Path)
    parser.add_argument('--completion-verification', type=Path, default=ROOT / 'ignore/validation/pipeline_completion_20261015')
    parser.add_argument('--cst-verification', type=Path, default=ROOT / 'ignore/validation/wmql_cst_20261015')
    parser.add_argument('--scientific-closure', type=Path, default=ROOT / 'ignore/validation/scientific_closure_20261015')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--documentation-dir', type=Path)
    args = parser.parse_args()
    try:
        date_id = datetime.strptime(args.report_date, '%Y-%m-%d').strftime('%Y%m%d')
    except ValueError:
        parser.error('--report-date must be a valid YYYY-MM-DD date')
    records = collect(args.campaign, args.verification)
    records.extend(collect_bundle_followup(args.bundle_followup))
    records.extend(collect_completion_measurements(args.completion_verification))
    records.extend(collect_cst_definition_followup(args.cst_verification))
    records.extend(collect_scientific_closure(args.scientific_closure))
    if args.scalar_verification:
        source = args.scalar_verification / 'acceptance.json'
        if source.is_file():
            payload = read(source)
            for index, stage in enumerate(payload.get('checks') or []):
                if stage.get('stage') == 'noddi_refit' and stage.get('status') == 'completed':
                    qc = read(Path(stage['qc']))
                    if qc.get('automatic_qc_passed') is True:
                        progress = read(Path(stage['qc']).with_name('noddi_progress.json'))
                        records.append(record('microstructure.noddi', payload['subject_id'], stage['seconds'], source,
                            f'checks[{index}].seconds', stage['scope'], priority=10, evidence='full_brain_isolated_refit',
                            input_scope=f"{qc.get('validity', {}).get('brain_mask_voxels')} mask voxels / {progress.get('nthreads')} CPU threads",
                            device='cpu', anatomical_review='pending'))
    for directory in dict.fromkeys(args.device_verification):
        records.extend(collect_device_measurements(directory))
    rows = select(records)
    preproc_seconds = next(r['seconds'] for r in rows if r['module'] == 'preprocessing.mrtrix_fsl')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / 'module_runtimes.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    result = dict(generated_at=datetime.now(timezone.utc).isoformat(), modules=rows, records=records,
                  report_host=_report_generation_system(),
                  notes=['READY means a scoped timing exists, not scientific accuracy certification.',
                         'Do not sum these rows: inputs, subjects, cached prerequisites and versions differ.',
                         'Historical hardware/thread/GPU configuration is not inferred from the current host.',
                         'Representative device acceptances are chosen by protocol, not minimum runtime; CPU references, repeats and failures remain in records.',
                         'PNL CPU/GPU times include registration/startup; do not claim speedup over a historical unpaired CPU record.',
                         'CUDA eddy acceptance measures the whole preprocessing route, not eddy alone.',
                         'DKI and MK-Curve use full-brain timings only after independent integrity/reference acceptance; historical ROI records remain, never extrapolated.',
                         'Resource downloads, optional UKF/WMA diffusion-measurement export, batch scheduling and final scene save are outside this catalog.'])
    (args.output_dir / 'module_runtimes.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    for chinese in (False, True):
        lines = ['| 模块 | 被试 | 设备 | 秒 | 分钟 | 状态 | 输入 / 范围 |' if chinese else '| Module | Subject | Device | Seconds | Minutes | Status | Input / Scope |',
                 '| --- | --- | --- | ---: | ---: | --- | --- |']
        for r in rows:
            seconds = f"{r['seconds']:.3f}" if r['seconds'] is not None else 'MISSING'
            minutes = f"{r['minutes']:.3f}" if r['minutes'] is not None else 'MISSING'
            name = r['name_zh'] if chinese else r['name']
            device = r['device'] or ('未记录' if chinese else 'not recorded')
            lines.append(f"| {name} | {r['subject_id'] or '-'} | {device} | {seconds} | {minutes} | {r['measurement_status']} | {r['input_scope'] or r['scope']} |")
        (args.output_dir / ('module_runtimes.zh-CN.md' if chinese else 'module_runtimes.md')).write_text('\n'.join(lines) + '\n', encoding='utf-8')
        if args.documentation_dir:
            docs = args.documentation_dir
            docs.mkdir(parents=True, exist_ok=True)
            suffix = '.zh-CN' if chinese else ''
            heading = '模块运行时间' if chinese else 'Module Runtime Inventory'
            alternate = f'MODULE_RUNTIMES_{date_id}.md' if chinese else f'MODULE_RUNTIMES_{date_id}.zh-CN.md'
            introduction = (
                f'汇总真实历史记录与本轮补测，共 {len(rows)} 项操作。READY 仅表示有明确范围的实测计时，不表示解剖准确性获认证。'
                '缺失不填 0，失败/跳过/缓存复用不充作成功计算。完整账本和来源哈希见下方 CSV/JSON。\n\n'
                '新增计时包括三种输入导入、MRtrix/SynthStrip 掩膜、全新全脑 DTI、六指标 ROI 统计和三类束的 Slicer 加载。'
                'WMQL/TractCloud 使用真实重跑；WMA 仅在新运行完成独立验收后替换原 149741 范围记录。'
                'PNL/SynthStrip 和 MRtrix/FSL 已纳入本轮真实 GPU 验收，CPU 对照、重复运行和失败记录在下方单独展示。\n'
                if chinese else
                f'Real historical records and new measurements cover {len(rows)} operations. READY means a scoped time exists, not anatomical certification. '
                'Missing values are not zero; failed/skipped/cache checks are not successful computation. CSV/JSON preserve the ledger and source hashes.\n\n'
                'New measurements include three imports, MRtrix/SynthStrip masks, fresh full-volume DTI, six-map ROI statistics and native bundle loading. '
                'WMQL/TractCloud use real reruns; WMA replaces the scoped 149741 record only after a new independent acceptance. '
                'PNL/SynthStrip and MRtrix/FSL now include real GPU acceptances; CPU references, repeats and failures are shown separately below.\n'
            )
            boundary = (
                '- DKI/MK-Curve 只有完整独立验收通过后才采用实测全脑时间；旧 64/8 体素记录保留且不外推。MK-Curve 计时不表示全部体素有效。\n'
                '- DTI 参数导出行复用已经拟合的张量；全新 DTI 行包含拟合与六指标转换，两者不混淆。\n'
                '- 表面后处理只有新版独立完整验收通过后才替换历史计时；范围和版本以 JSON 来源为准。\n'
                '- CSD/ACT/SIFT2 是组合阶段；没有伪造其中 FOD、ACT、SIFT2 的独立计时。\n'
                '- Slicer 加载时间包含独立坐标对照，排除启动和束提取。新全脑 DTI 测试进程总时间 165.7 秒，不冒充 136 秒拟合计时。\n'
                '- 不同被试、输入规模、缓存、线程、版本与当时负载不可直接横比或相加；历史硬件/线程缺记录时不从当前机器反推。\n'
                '- PNL 主表采用默认 Auto GPU 实测，而非最快一次；CPU 对照、显式 CUDA 重复和旧 CPU 346.7 秒记录均保留在 JSON。本轮 CPU 已约 79 秒，不能声称相对历史记录的四倍 GPU 加速。\n'
                '- MRtrix/FSL 的 GPU 行约 719 秒是完整路线，包含 CPU denoise/Gibbs/topup/最终掩膜，不是 eddy 单步耗时。\n'
                '- SynthStrip 旧环境 949 秒中止和 CUDA eddy 365 秒线程参数失败均不是成功计算；修正后的实测分别约 9 秒和 719 秒，解剖人工检查仍待完成。\n'
                '- PNL 历史慢记录主要在 CNN 阶段（日志约 284 秒），当前 CPU 日志约 15 秒；历史负载/完整线程环境缺失，根因未能唯一确定。新生成掩膜保留分阶段计时和线程环境，实际 GPU 重跑也独立记录。\n'
                '- 当前实测主机为 Xeon Platinum 8360Y、144 逻辑 CPU、约 503.5 GiB 内存、两张 H100；并非各记录都使用 GPU。\n'
                '- 模型下载、可选 UKF 追踪/WMA diffusion-measurement 导出、批调度和最终场景保存不在本表范围。\n'
                if chinese else
                '- DKI/MK-Curve use full-brain times only after independent acceptance; historical 64/8-voxel records remain, never extrapolated. MK-Curve timing does not imply every voxel is valid.\n'
                '- DTI scalar export reuses a fitted tensor; fresh DTI includes fitting and six scalar conversions.\n'
                '- A new surface-postprocessing time replaces the historical record only after independent full-route acceptance; JSON records identify the actual scope/version.\n'
                '- CSD/ACT/SIFT2 is a combined stage; no individual FOD/ACT/SIFT2 timings are invented.\n'
                '- Slicer loading includes independent coordinate comparison but excludes startup/extraction. The 165.7 s DTI acceptance process is not confused with the 136 s fitting measurement.\n'
                '- Different subjects, sizes, caches, threads, versions and concurrent load cannot be compared or summed directly. Missing historical hardware/thread metadata is not inferred.\n'
                '- The PNL representative is the default Auto GPU run, not the fastest repeat. CPU reference, explicit CUDA repeat and historical 346.7 s CPU time remain in JSON. The new CPU time is already about 79 s: no fourfold GPU speedup is claimed.\n'
                '- The approximately 719 s MRtrix/FSL GPU acceptance is the whole route, including CPU denoise/Gibbs/topup/final mask, not isolated eddy time.\n'
                '- The stopped 949 s old-runtime SynthStrip attempt and failed 365 s CUDA eddy thread-option attempt are not successful computation; corrected acceptances are about 9 s and 719 s, with anatomical review still pending.\n'
                '- The historical slow PNL record is dominated by its CNN phase (about 284 s in rounded logs versus about 15 s in the current CPU log). Historical load/full threading metadata is missing, so its cause is not uniquely established. Fresh masks now retain phase timings and thread environment; instrumented GPU repeats are recorded separately.\n'
                '- New-measurement host: Xeon Platinum 8360Y, 144 logical CPUs, about 503.5 GiB RAM and two H100 GPUs; not every operation used GPUs.\n'
                '- Downloads, optional UKF tracking/WMA diffusion-measurement export, batch scheduling and final scene saving are outside this catalog.\n'
            )
            if preproc_seconds is not None:
                boundary = boundary.replace('719', f'{preproc_seconds:.0f}')
            text = (f'<div align="center">\n\n# {heading}\n\n**2026-10-13 · Measured, scoped, traceable**\n\n'
                    f'[Project](../../README.md) | [QC](BUNDLE_BACKENDS_20261013{suffix}.md) | '
                    f'[GPU verification](GPU_POLICY_20261013.md) | '
                    f'[CSV](benchmarks/module_runtimes_{date_id}.csv) | [JSON](benchmarks/module_runtimes_{date_id}.json) | '
                    f'[Other language]({alternate})\n\n</div>\n\n' + introduction + '\n---\n\n' + '\n'.join(lines) +
                    '\n\n---\n\n' + ('## 计时边界\n\n' if chinese else '## Measurement Boundaries\n\n') + boundary +
                    '\n---\n\n' + ('## CPU / GPU 对照与失败记录\n\n' if chinese else '## CPU / GPU References And Failed Attempts\n\n') +
                    device_table(records, chinese) + '\n\n' +
                    ('设备缺少记录时不从日志推断；软件版本、输入哈希、来源文件和完整计时范围保留在 JSON。失败耗时仅供排障，不参与主表选取。\n'
                     if chinese else 'Unrecorded device choices are not inferred from logs. Software versions, input hashes, source files and full timing scopes remain in JSON. Failed durations are for troubleshooting, never representative compute timings.\n') +
                    '\n```bash\npython scripts/collect_module_runtimes.py --output-dir /path/to/report --documentation-dir docs/release\n```\n')
            text = text.replace('**2026-10-13 · Measured, scoped, traceable**', f'**{args.report_date} · Measured, scoped, traceable**')
            if date_id != '20261013':
                text += ('\n本表为更新后的汇总；多数模块仍使用限定范围的历史记录，不表示全部在该日期重跑。\n'
                         if chinese else '\nThis updated inventory includes scoped historical timings; not every module was rerun on this date.\n')
            (docs / f'MODULE_RUNTIMES_{date_id}{suffix}.md').write_text(text, encoding='utf-8')
    if args.documentation_dir:
        numerical = args.documentation_dir / 'benchmarks'
        numerical.mkdir(exist_ok=True)
        for suffix in ('csv', 'json'):
            shutil.copy2(args.output_dir / f'module_runtimes.{suffix}', numerical / f'module_runtimes_{date_id}.{suffix}')
    print(json.dumps({'rows': len(rows), 'records': len(records), 'missing': [r['module'] for r in rows if r['measurement_status'] == 'MISSING'],
                      'partial': [r['module'] for r in rows if r['measurement_status'] == 'PARTIAL']}, indent=2))


if __name__ == '__main__':
    main()
