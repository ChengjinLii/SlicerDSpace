#!/usr/bin/env python3
"""Export explicitly selected, verified measurements without private runtime paths."""

import argparse
import hashlib
from html import escape
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / 'docs/release/benchmarks'
SITE = ROOT / 'docs/site'
BEGIN, END = '<!-- measured-evidence:start -->', '<!-- measured-evidence:end -->'


def build_evidence():
    sources = []

    def load(name):
        path = BENCHMARKS / name
        sources.append({'file': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        return json.loads(path.read_text())

    full = load('freewater_tensor_helpers_full_20261022.json')
    if not all(full.get(key) is True for key in ('inputs_unchanged', 'snapshot_unchanged', 'harness_unchanged', 'qc_equal')) or full['status'] != 'passed':
        raise ValueError('Full Free-water evidence has not passed its independent verification')
    previous = load('complete_models_20261020.json')
    rows = []

    def add(identifier, title, category, scope, reference, optimized, method, baseline, unchanged, limitation, sample, evidence_date='2026-10-20'):
        if not all(math.isfinite(value) and value > 0 for value in (reference, optimized)):
            raise ValueError('Invalid measured duration')
        rows.append(dict(id=identifier, title=title, category=category, scope=scope, evidence_date=evidence_date,
                         reference_seconds=reference, optimized_seconds=optimized,
                         speed_ratio=reference / optimized, seconds_saved=reference - optimized,
                         reduction_percent=100 * (1 - optimized / reference), method=method,
                         baseline=baseline, unchanged=unchanged, limitation=limitation, sample=sample))

    case = full['records'][0]
    if not case['exact_raw_parameters'] or not case['exact_exported_maps_and_qc'] or not case['automatic_qc_passed']:
        raise ValueError('Free-water numerical equivalence is incomplete')
    add('freewater', 'Free-water WLS', 'implementation', 'Full brain',
        case['reference_seconds'], case['optimized_seconds'],
        'Diagonal-free weight multiplication and source-qualified direct tensor-helper calls remove repeated allocation and compatibility checks.',
        'Original installed DIPY WLS, not an earlier plugin. One numerical thread in both paths.',
        f"All 13 raw fit parameters, four maps/masks, affines, dtypes and automatic QC match. The same {case['validity']['excluded_tissue_voxels']} voxels remain excluded.",
        'One subject, one pair on a shared Linux host; optimized first. OS caches were not flushed. Both calls include raw-parameter evidence export.',
        f"{case['mask_voxels']} mask voxels; {case['measurements']} measurements; automatic QC passes, anatomical review pending.", evidence_date='2026-10-22')

    pairs = {row['stage']: row for row in previous['complete_model_pairs']}
    for key in ('wma', 'noddi', 'mkcurve'):
        pair = pairs[key]
        if pair['status'] != 'passed' or not pair['products'] or not all(item['exact'] for item in pair['products']):
            raise ValueError('Incomplete output-equivalence evidence: ' + key)
    pair = pairs['wma']
    add('wma', 'WMA registration & classification', 'implementation', 'Complete module',
        pair['reference_seconds'], pair['optimized_seconds'],
        'Bulk geometry copying and verified registration-input reuse reduce repeated Python/VTK traversal and preparation.',
        'Original-author processing versus equivalent bulk/cache implementation, with identical UKF input and atlas.',
        'All 74 anatomical-tract output files are byte-identical; source inputs and author code are unchanged.',
        'One full-module pair on a shared Linux host. Matching files do not certify small-bundle sampling or anatomical validity. Later transform optimizations are not measured by this pair.',
        'Full registration and 74-tract output; no streamline downsampling introduced for timing.')
    pair = pairs['noddi']
    add('noddi', 'NODDI / AMICO', 'parallel', 'Full brain',
        pair['reference_seconds'], pair['optimized_seconds'],
        'Use AMICO\'s existing native multithreading: one thread versus eight.',
        'The same author implementation and model settings. This is a thread-configuration comparison, not a new algorithm.',
        'NDI, ODI, IsoVF, RMSE, NRMSE and the tissue-validity mask match voxelwise, including affines.',
        'One shared-host pair. Hardware-specific multithreading benefit; not a universal speed or whole-workflow guarantee.',
        'Original 740916-voxel brain mask; fresh output directories.')
    pair = pairs['mkcurve']
    add('mkcurve', 'MK-Curve Python port', 'port', 'Full brain',
        pair['reference_seconds'], pair['optimized_seconds'],
        'Reuse fixed tensor bases and integration terms instead of reconstructing them for each block.',
        'Earlier Python-port computation versus fixed-basis reuse. NOT original MATLAB versus Python.',
        'All 55 compared maps, curves, coefficients and masks match. Invalid voxels remain excluded.',
        'One shared-host pair, batched solver, one worker, 256-voxel chunks, maximum shell 2500 s/mm2. It does not measure the later default-QR optimization or certify fit validity.',
        'Full-brain port comparison; not a MATLAB runtime benchmark.')

    roi = previous['roi_evidence']
    if roi['status'] != 'passed' or not all(item['all_output_arrays_exact'] and item['source_unchanged'] for item in roi['cases']):
        raise ValueError('DKI ROI equivalence did not pass')
    case = roi['cases'][0]
    add('dki', 'DKI WLS metrics', 'implementation', 'Native 24-cubed ROI',
        case['median_seconds']['reference'], case['median_seconds']['optimized'],
        'Evaluate the author\'s existing array-capable kurtosis metrics once per block, avoiding repeated per-voxel result wrappers.',
        'Unchanged DIPY WLS fit and metrics; only result evaluation is reorganized.',
        'All exported voxel arrays and affines match in three subjects, with three alternating repeats each.',
        'Table shows subject 100307 medians. Across all three subjects the ratio is 3.20-3.24x. No completed full-brain DKI pair is available; do not apply this ratio to historical whole-brain timings.',
        'Three subjects; three repeats per path; native-grid ROI, no resampling.')
    rows[-1]['subject_results'] = [dict(subject=item['subject'], reference_seconds=item['median_seconds']['reference'],
                                       optimized_seconds=item['median_seconds']['optimized'], speed_ratio=item['speed_ratio'])
                                  for item in roi['cases']]
    schedule = previous['concurrency_evidence']
    if schedule['status'] != 'passed' or not all(item['all_arrays_exact'] for item in schedule['measurements']):
        raise ValueError('Concurrent output equivalence did not pass')
    times = {item['mode']: item['elapsed_seconds'] for item in schedule['measurements']}
    add('scheduling', 'Independent FW + DKI jobs', 'workflow', 'Native 24-cubed ROI',
        times['sequential'], times['concurrent'],
        'Overlap independent model subprocesses after their shared inputs are ready; preserve downstream dependencies.',
        'The same model computations, serial scheduling versus two concurrent workers.',
        'All exported scalar and mask arrays match. Process startup is included.',
        'One ROI pair. This reduces schedule wall time, not the cost of an individual scientific model. Default model concurrency remains one; memory/CPU budgets may prevent overlap.',
        'Two independent models; CPU/memory-constrained scheduling; not full-brain timing.')

    filtering = load('author_wma_optimizations_20261020.json')
    sample = filtering['full_inputs']['cases'][0]
    if filtering['status'] != 'passed' or filtering['full_inputs']['status'] != 'passed':
        raise ValueError('Author WMA filtering comparison did not pass')
    add('wma-filter', 'WMA atlas length filtering', 'implementation', 'Single substage',
        sample['author_median_seconds'], sample['optimized_median_seconds'],
        'Replace per-point Python geometry copying with equivalent bulk coordinate/topology operations.',
        'Unmodified author filter on the full 1989106-streamline registration atlas.',
        'Output coordinates/topology and fixed-seed samples match exactly.',
        'One full-atlas substage pair, not complete WMA. The large local ratio must not be multiplied by or added to the full WMA result.',
        'Full registration-atlas length-filter substage only.')
    return dict(kind='slicerddsurfer_public_performance_evidence', version=1, reviewed_on='2026-10-22',
                sources=sources, records=rows,
                policy='Output equivalence is not anatomical or clinical validation. No whole-workflow speedup has been established.',
                pending=['Repeated multi-subject full-module pairs', 'Completed full-brain DKI comparison',
                         'Full-brain validation for later default-QR MK-Curve changes',
                         'Matched CSD/ACT/SIFT2 complete-module baseline', 'Native Windows/macOS scientific timing',
                         'Optional persistent-model worker: proposed, not implemented or benchmarked'])


LABELS = dict(implementation='Same-method implementation', parallel='Native threads',
              port='Python-port computation', workflow='Workflow scheduling')


def duration(seconds):
    return f'{seconds / 60:.2f} min' if seconds >= 180 else f'{seconds:.2f} s'


def render(evidence):
    rows, methods = [], []
    for row in evidence['records']:
        identifier, category = escape(row['id']), escape(row['category'])
        rows.append(f'''<tr data-category="{category}"><th scope="row"><a href="#method-{identifier}">{escape(row['title'])}</a><small>{escape(row['scope'])} / record {row['evidence_date']}</small></th><td><span class="perf-kind {category}">{LABELS[row['category']]}</span></td><td>{duration(row['reference_seconds'])}</td><td>{duration(row['optimized_seconds'])}</td><td>{row['speed_ratio']:.2f}x<small>{row['reduction_percent']:.2f}% less time</small></td></tr>''')
        methods.append(f'''<details class="perf-method" data-category="{category}" id="method-{identifier}"><summary><span>{escape(row['title'])}</span><span class="perf-scope">{escape(row['scope'])}</span></summary><div class="perf-method-body"><dl><dt>What changed</dt><dd>{escape(row['method'])}</dd><dt>Reference</dt><dd>{escape(row['baseline'])}</dd><dt>Equivalence</dt><dd>{escape(row['unchanged'])}</dd><dt>Measured scope</dt><dd>{escape(row['sample'])}</dd><dt>Limits</dt><dd>{escape(row['limitation'])}</dd></dl></div></details>''')
    cards = []
    for row in evidence['records'][:2]:
        cards.append(f'''<figure class="perf-chart" data-category="implementation"><figcaption><span class="perf-kind implementation">{escape(row['scope'])} / implementation</span><h3>{escape(row['title'])}</h3></figcaption><div class="perf-bar-row"><span>Reference</span><div class="perf-track"><span class="perf-bar reference" style="--extent:100%"></span></div><strong>{duration(row['reference_seconds'])}</strong></div><div class="perf-bar-row"><span>Optimized</span><div class="perf-track"><span class="perf-bar" style="--extent:{100 * row['optimized_seconds'] / row['reference_seconds']:.4f}%"></span></div><strong>{duration(row['optimized_seconds'])}</strong></div><p class="perf-chart-note">{row['reduction_percent']:.2f}% less time in this measured call. Output equivalence checked; one shared-host pair.</p></figure>''')
    return '\n'.join([
        '<div class="perf-chart-grid">' + ''.join(cards) + '</div>',
        '<div class="perf-table-wrap" tabindex="0" role="region" aria-label="Measured performance comparisons, scroll horizontally on small screens"><table class="perf-table"><caption>Different models and scopes are not ranked against each other. Ratios are reference time divided by optimized time.</caption><thead><tr><th scope="col">Computation / scope</th><th scope="col">Type of change</th><th scope="col">Reference</th><th scope="col">Optimized</th><th scope="col">Measured ratio</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>',
        '<p class="note">Only Free-water and WMA are highlighted above; NODDI multithreading, Python-port comparisons and ROI measurements are deliberately labeled separately. No timing here establishes higher anatomical validity.</p>',
        '<div class="perf-methods"><h3>Methods &amp; verification</h3><p class="muted">Open a record for the reference implementation, changes, checks and limits.</p>' + ''.join(methods) + '</div>'
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if checked-in website evidence is stale')
    args = parser.parse_args()
    evidence = build_evidence()
    payload = json.dumps(evidence, indent=2) + '\n'
    page = SITE / 'performance.html'
    original = page.read_text()
    if original.count(BEGIN) != 1 or original.count(END) != 1:
        raise ValueError('Expected one performance evidence region')
    before, middle = original.split(BEGIN)
    _, after = middle.split(END)
    expected = before + BEGIN + '\n' + render(evidence) + '\n' + END + after
    data = SITE / 'assets/data/performance.json'
    if args.check:
        if not data.is_file() or data.read_text() != payload or original != expected:
            raise SystemExit('Website performance evidence is stale; run scripts/build_performance_site.py')
        print('PASS public performance data, source hashes and rendered measurements')
    else:
        data.parent.mkdir(parents=True, exist_ok=True)
        data.write_text(payload)
        page.write_text(expected)
        print('Exported seven scoped measurements; private paths and runtime snapshots excluded')


if __name__ == '__main__':
    main()
