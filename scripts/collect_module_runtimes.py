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
    ('surface.ddsurfer_postprocess', 'Surface postprocessing (historical)', '表面后处理（历史版）'),
    ('microstructure.dti', 'DTI scalar export / ROI', 'DTI 参数导出 / ROI'),
    ('microstructure.freewater', 'Free-water', 'Free-water'),
    ('microstructure.noddi', 'AMICO NODDI', 'AMICO NODDI'),
    ('microstructure.dki', 'DIPY DKI WLS (64 voxels)', 'DIPY DKI WLS（64 体素）'),
    ('microstructure.mkcurve', 'Python MK-Curve (8 voxels)', 'Python MK-Curve（8 体素）'),
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


def record(module, subject, seconds, source, field, scope, *, status='completed', priority=0, evidence='historical', **extra):
    return dict(module=module, subject_id=subject, runtime_seconds=_seconds(seconds), status=status,
                source_record=str(source.resolve()), source_field=field,
                source_record_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                scope=scope, priority=priority, evidence=evidence, **extra)


def collect(campaign, verification):
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
         'seconds', 'External PNL CNN acceptance including container/launcher overhead; full native HCP input', '288-volume real HCP DWI', False),
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
                                  status=m.get('status', 'unknown'), priority=4, input_scope=inputs,
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
                         scope=selected.get('scope', 'No successful measured record in this scoped inventory'),
                         evidence=selected.get('evidence'), source_record=selected.get('source_record'),
                         source_field=selected.get('source_field'), source_record_sha256=selected.get('source_record_sha256')))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, default=ROOT / 'ignore/validation/slicer_acceptance_20261006/science/subjects')
    parser.add_argument('--verification', type=Path, default=ROOT / 'ignore/validation/bundles_runtime_20261013')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--documentation-dir', type=Path)
    args = parser.parse_args()
    records = collect(args.campaign, args.verification)
    rows = select(records)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / 'module_runtimes.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = dict(generated_at=datetime.now(timezone.utc).isoformat(), modules=rows, records=records,
                  report_host=_report_generation_system(),
                  notes=['READY means a scoped timing exists, not scientific accuracy certification.',
                         'Do not sum these rows: inputs, subjects, cached prerequisites and versions differ.',
                         'Historical hardware/thread/GPU configuration is not inferred from the current host.',
                         'Full-brain DKI and MK-Curve times are not extrapolated from their ROI measurements.',
                         'Resource downloads, optional UKF/WMA diffusion-measurement export, batch scheduling and final scene save are outside this catalog.'])
    (args.output_dir / 'module_runtimes.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    for chinese in (False, True):
        lines = ['| 模块 | 被试 | 秒 | 分钟 | 状态 | 输入 / 范围 |' if chinese else '| Module | Subject | Seconds | Minutes | Status | Input / Scope |',
                 '| --- | --- | ---: | ---: | --- | --- |']
        for r in rows:
            seconds = f"{r['seconds']:.3f}" if r['seconds'] is not None else 'MISSING'
            minutes = f"{r['minutes']:.3f}" if r['minutes'] is not None else 'MISSING'
            name = r['name_zh'] if chinese else r['name']
            lines.append(f"| {name} | {r['subject_id'] or '-'} | {seconds} | {minutes} | {r['measurement_status']} | {r['input_scope'] or r['scope']} |")
        (args.output_dir / ('module_runtimes.zh-CN.md' if chinese else 'module_runtimes.md')).write_text('\n'.join(lines) + '\n', encoding='utf-8')
        if args.documentation_dir:
            docs = args.documentation_dir
            docs.mkdir(parents=True, exist_ok=True)
            suffix = '.zh-CN' if chinese else ''
            heading = '模块运行时间' if chinese else 'Module Runtime Inventory'
            alternate = 'MODULE_RUNTIMES_20261013.md' if chinese else 'MODULE_RUNTIMES_20261013.zh-CN.md'
            introduction = (
                '汇总真实历史记录与本轮补测，共 32 项操作。READY 仅表示有明确范围的实测计时，不表示解剖准确性获认证。'
                '缺失不填 0，失败/跳过/缓存复用不充作成功计算。完整账本和来源哈希见下方 CSV/JSON。\n\n'
                '新增计时包括三种输入导入、MRtrix/SynthStrip 掩膜、全新全脑 DTI、六指标 ROI 统计和三类束的 Slicer 加载。'
                'WMQL/TractCloud 用当前修正封装真实重跑；WMA 使用已有通过范围契约的 149741 记录。\n'
                if chinese else
                'Real historical records and new measurements cover 32 operations. READY means a scoped time exists, not anatomical certification. '
                'Missing values are not zero; failed/skipped/cache checks are not successful computation. CSV/JSON preserve the ledger and source hashes.\n\n'
                'New measurements include three imports, MRtrix/SynthStrip masks, fresh full-volume DTI, six-map ROI statistics and native bundle loading. '
                'WMQL/TractCloud use corrected reruns; WMA uses the existing scoped-pass 149741 run.\n'
            )
            boundary = (
                '- **DKI 和 MK-Curve 是真实小 ROI 的 PARTIAL 记录**：分别 64 / 8 体素，不能当作全脑耗时，不能外推。\n'
                '- DTI 参数导出行复用已经拟合的张量；全新 DTI 行包含拟合与六指标转换，两者不混淆。\n'
                '- 表面后处理为 10 月 6 日历史全流程，不能作为 10 月 13 日优化版的速度保证。\n'
                '- CSD/ACT/SIFT2 是组合阶段；没有伪造其中 FOD、ACT、SIFT2 的独立计时。\n'
                '- Slicer 加载时间包含独立坐标对照，排除启动和束提取。新全脑 DTI 测试进程总时间 165.7 秒，不冒充 136 秒拟合计时。\n'
                '- 不同被试、输入规模、缓存、线程、版本与当时负载不可直接横比或相加；历史硬件/线程缺记录时不从当前机器反推。\n'
                '- 当前实测主机为 Xeon Platinum 8360Y、144 逻辑 CPU、约 503.5 GiB 内存、两张 H100；并非各记录都使用 GPU。\n'
                '- 模型下载、可选 UKF 追踪/WMA diffusion-measurement 导出、批调度和最终场景保存不在本表范围。\n'
                if chinese else
                '- **DKI / MK-Curve are PARTIAL real-ROI measurements**, 64 / 8 voxels respectively. Full-brain times are unmeasured and not extrapolated.\n'
                '- DTI scalar export reuses a fitted tensor; fresh DTI includes fitting and six scalar conversions.\n'
                '- Surface postprocessing is the October 6 historical full route, not an October 13 optimized-version speed claim.\n'
                '- CSD/ACT/SIFT2 is a combined stage; no individual FOD/ACT/SIFT2 timings are invented.\n'
                '- Slicer loading includes independent coordinate comparison but excludes startup/extraction. The 165.7 s DTI acceptance process is not confused with the 136 s fitting measurement.\n'
                '- Different subjects, sizes, caches, threads, versions and concurrent load cannot be compared or summed directly. Missing historical hardware/thread metadata is not inferred.\n'
                '- New-measurement host: Xeon Platinum 8360Y, 144 logical CPUs, about 503.5 GiB RAM and two H100 GPUs; not every operation used GPUs.\n'
                '- Downloads, optional UKF tracking/WMA diffusion-measurement export, batch scheduling and final scene saving are outside this catalog.\n'
            )
            text = (f'<div align="center">\n\n# {heading}\n\n**2026-10-13 · Measured, scoped, traceable**\n\n'
                    f'[Project](../../README.md) | [QC](BUNDLE_BACKENDS_20261013{suffix}.md) | '
                    f'[CSV](benchmarks/module_runtimes_20261013.csv) | [JSON](benchmarks/module_runtimes_20261013.json) | '
                    f'[Other language]({alternate})\n\n</div>\n\n' + introduction + '\n---\n\n' + '\n'.join(lines) +
                    '\n\n---\n\n' + ('## 计时边界\n\n' if chinese else '## Measurement Boundaries\n\n') + boundary +
                    '\n```bash\npython scripts/collect_module_runtimes.py --output-dir /path/to/report\n```\n')
            (docs / f'MODULE_RUNTIMES_20261013{suffix}.md').write_text(text, encoding='utf-8')
    if args.documentation_dir:
        numerical = args.documentation_dir / 'benchmarks'
        numerical.mkdir(exist_ok=True)
        for suffix in ('csv', 'json'):
            shutil.copy2(args.output_dir / f'module_runtimes.{suffix}', numerical / f'module_runtimes_20261013.{suffix}')
    print(json.dumps({'rows': len(rows), 'records': len(records), 'missing': [r['module'] for r in rows if r['measurement_status'] == 'MISSING'],
                      'partial': [r['module'] for r in rows if r['measurement_status'] == 'PARTIAL']}, indent=2))


if __name__ == '__main__':
    main()
