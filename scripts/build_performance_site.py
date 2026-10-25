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

    full = load('freewater_latest_stable_full_20261022.json')
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
    for key in ('wma', 'noddi'):
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
    qr = load('mkcurve_qr_scipy1181_20261022.json')
    if qr['status'] != 'passed' or qr['environment']['scipy'] != '1.18.1' or not all(row['exact_output_parity'] for row in qr['records']):
        raise ValueError('Current SciPy QR verification did not pass')
    current_qr = [row for row in qr['records'] if row['solver'] == 'reference']
    case = current_qr[0]
    add('mkcurve', 'MK-Curve QR / Python port', 'port', '64-voxel numeric chunk',
        case['reference_median_seconds'], case['optimized_median_seconds'],
        'Reuse protocol/design checks and LAPACK workspace sizes while keeping the same pivoted QR and full b0 grid.',
        'Current SciPy 1.18.1 public gelsy solver versus qualified direct-driver/cache use in the same Python port. NOT original MATLAB versus Python.',
        'Raw coefficients, full curves, every map and validity decision match in all three subjects; both reference and batched solvers checked.',
        'Table shows subject 100206 default-QR medians, three alternating repeats after warmup. Numeric chunks exclude input preparation and file export; not whole ROI or full brain. SciPy already supplies native batching.',
        'Three real 64-voxel chunks; 181 measurements; complete 200-201 point b0 grids; one numerical thread.', evidence_date='2026-10-22')
    rows[-1]['solver_results'] = [dict(subject=item['subject_id'], solver=item['solver'],
        reference_seconds=item['reference_median_seconds'], optimized_seconds=item['optimized_median_seconds'],
        speed_ratio=item['speed_ratio']) for item in qr['records']]

    roi = load('dki_latest_stable_integration_20261022.json')
    if roi['status'] != 'passed' or not all(item['all_output_arrays_exact'] and item['source_unchanged'] for item in roi['cases']):
        raise ValueError('DKI ROI equivalence did not pass')
    case = roi['cases'][0]
    add('dki', 'DKI WLS metrics', 'integration', 'Native 24-cubed ROI',
        case['median_seconds']['reference'], case['median_seconds']['optimized'],
        'Evaluate the author\'s existing array-capable kurtosis metrics once per block, avoiding repeated per-voxel result wrappers.',
        'Previous plugin per-voxel integration versus existing DIPY array usage. No improvement over the author\'s native vectorized API is claimed.',
        'All exported voxel arrays and affines match in three subjects, with three alternating repeats each.',
        'Table shows subject 100307 medians. This adopts existing native DIPY functionality, not a new upstream algorithm improvement. No completed full-brain DKI pair; do not scale ROI times to whole brain.',
        'Three subjects; three repeats per path; native-grid ROI, no resampling; DIPY 1.12.1 with SciPy 1.18.1.', evidence_date='2026-10-22')
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

    nls = load('freewater_dispatch_slicer_20261021.json')
    if (nls['status'] != 'passed' or not nls['source_inputs_unchanged'] or
            not all(item['exact_raw_parameters'] and item['exact_exported_maps_and_qc'] and
                    item['automatic_qc_passed'] for item in nls['records'])):
        raise ValueError('Free-water NLS equivalence did not pass')
    case = nls['records'][0]
    add('freewater-nls', 'Free-water NLS dispatch', 'implementation', '1728-voxel ROI',
        case['reference_median_seconds'], case['optimized_median_seconds'],
        'Call source-qualified author NLS, residual and Jacobian bodies directly, removing repeated keyword-compatibility dispatch.',
        'Installed original DIPY 1.12.1 serial NLS versus the same function bodies; one numerical thread in both paths.',
        'All 13 raw parameters, exported maps, affine and QC decisions match in all three subjects.',
        'Subject 100307 medians, three alternating repeats after warmup. ROI, not full brain. These timings precede later WLS-initialization/helper changes and cannot be added to them.',
        'Three native 12-cubed ROIs; 288 measurements; complete ROI stage including fresh export.', evidence_date='2026-10-21')

    transform = load('wma_transform_20261021.json')
    if (transform['status'] != 'passed' or not transform['source_inputs_unchanged'] or
            not transform['compatibility']['supported'] or
            not all(item['exact_all_points'] and item['exact_objective_history'] and item['exact_transform']
                    for item in transform['records'])):
        raise ValueError('WMA transform equivalence did not pass')
    case = transform['records'][0]
    add('wma-transform', 'WMA point transformation', 'implementation', '1000 fibers x 15 points',
        case['transform_author_seconds'], case['transform_optimized_seconds'],
        'Use the same author vtkTransform with a bounded bulk point call, instead of one Python/VTK call per point.',
        'Unmodified author point-transform loop versus bulk calls with the same float64 point order and transform.',
        'All transformed points, complete small-optimizer trajectories and final transforms match in three subjects.',
        'Subject 100206 median of five point-transform repeats, not full registration. Small-optimizer gains were only about 1.27-1.28x; the point-kernel ratio cannot be applied to whole WMA.',
        'Three real-subject fixtures; explicit synthetic offset for the separate optimizer check.', evidence_date='2026-10-21')

    fibers = load('wma_fibers_bounded_20261021.json')
    if (fibers['status'] != 'passed' or not fibers['sources_unchanged'] or
            not fibers['compatibility']['supported'] or
            not all(item['exact_all_arrays_and_hemispheres'] and item['exact_entire_optimizer_trajectory'] and
                    item['exact_final_transform'] for item in fibers['records'])):
        raise ValueError('WMA array-conversion equivalence did not pass')
    case = fibers['records'][0]
    add('wma-fibers', 'WMA fiber-array conversion', 'implementation', '20000 fibers x 15 points',
        case['author_seconds'], case['optimized_seconds'],
        'Gather the same author nearest-neighbor fiber samples from VTK connectivity in bounded NumPy blocks.',
        'Unmodified author FiberArray conversion versus equivalent bulk conversion; no interpolation or streamline reduction added.',
        'All arrays, hemisphere flags and separate small-optimizer trajectories/transforms match in three subjects.',
        'Subject 100206 median of five conversion repeats. Not whole WMA; small-optimizer gains were only about 1.02-1.05x. Historical source sampling failures remain failed.',
        '20000 identical sampled fibers per subject; original nearest-neighbor rule and ordering.', evidence_date='2026-10-21')

    historical = load('performance_optimizations_20261020.json')
    comparisons = {row['id']: row for row in historical['comparisons']}
    selected = (
        ('wma_registration_preprocessing', 'wma-cache', 'WMA registration-input reuse', 'implementation', 'Three preparation calls',
         'Reuse verified deterministic atlas/subject length-filter results across seeds; keep fresh author random sampling.',
         'Three original author preparation calls versus first cache fill plus reuse, with the same input and fixed seeds.',
         'One subject, one pair; includes initial cache construction. This overlaps WMA filtering and the full-module pair; savings cannot be added.'),
        ('surface_four_overlay_mapping', 'surface-mapping', 'DDSurfer surface-map reuse', 'inherited', 'Four left-hemisphere overlays',
         'Pack four overlays into one multi-frame mri_surf2surf call, sharing the same surface registration.',
         'Four separate FreeSurfer commands versus one multi-frame command. Inherited from DDSurfer upstream c3b2d40, not plugin-original work.',
         'One subject, command timing only; extra packing/validation excluded. Not surface reconstruction or a new FreeSurfer algorithm.'),
        ('diffusion_three_slab_io', 'dwi-io', 'Compressed DWI block reading', 'io', 'Three slabs',
         'Decode gzip once to temporary disk, then memory-map the same requested blocks; leave the source file unchanged.',
         'Repeated compressed-array reads versus one sequential decode and disk-backed block reads; no indexed_gzip in this measurement.',
         'One subject, one pair, uncontrolled OS page cache; needs temporary disk. I/O only, not model fitting; no universal storage-performance guarantee.'),
    )
    for key, identifier, title, category, scope, method, baseline, limitation in selected:
        case = comparisons[key]
        if (case['category'] not in ('same_input_stage_comparison', 'same_input_io_comparison') or
                not case['output_check'] or not case['evidence'] or
                not all(len(historical['evidence_records'][name]['sha256']) == 64 for name in case['evidence'])):
            raise ValueError('Incomplete preserved paired evidence: ' + key)
        add(identifier, title, category, scope, case['reference_seconds'], case['optimized_seconds'],
            method, baseline, case['output_check'], limitation, case['scope'])

    audit = load('upstream_freshness_verified_20261022.json')
    upstream = audit['repositories']
    references = {
        'freewater': f"Measured DIPY {full['environment']['dipy']}; latest stable at review: {upstream['dipy/dipy']['pypi']['version']}. " +
            ('Current stable-release full-brain pair.' if full['environment']['dipy'] == upstream['dipy/dipy']['pypi']['version'] else 'Historical full-brain timing, not latest-release timing; new stable ROI pairs verified separately.'),
        'wma': 'Author commit ' + upstream['SlicerDMRI/whitematteranalysis']['measured_reference_sha'][:12] +
            (': matches current HEAD and measured source bytes.' if upstream['SlicerDMRI/whitematteranalysis']['measured_reference_is_current_head'] else ': historical commit, no longer current HEAD.'),
        'wma-filter': 'Same immutable current WMA source audit as the full-module record.',
        'noddi': 'AMICO ' + upstream['daducci/AMICO']['pypi']['version'] +
            (' verified in both timed configurations; latest stable at review. Threads are already upstream functionality.' if upstream['daducci/AMICO']['measured_versions_match_latest_stable'] else '; timed configuration versions are not verified against current stable.'),
        'dki': 'DIPY 1.12.1 is current stable at review. Array metrics already exist upstream; this is plugin integration, not an author-algorithm speedup.',
        'mkcurve': 'Current MATLAB reference ' + upstream['zhangfanmark/MK-Curve']['head_sha'][:12] +
            '; measured on current stable SciPy 1.18.1. This port-only comparison does not claim to outperform MATLAB or invent upstream native batching.',
        'scheduling': 'Historical plugin scheduler comparison, not a latest-upstream algorithm performance claim.',
        'freewater-nls': 'Measured DIPY 1.12.1 in Slicer; author NLS/residual/Jacobian source hashes match the dated stable-source audit.',
        'wma-transform': 'Author register_two_subjects.py SHA256 matches the 22 October WMA source audit; measured bulk vtkTransform path.',
        'wma-fibers': 'Author fibers.py at 4532b911386d independently verified; native VTK array sampling, not a new registration algorithm.',
        'wma-cache': 'Preserved same-author preparation pair. Source-qualified reuse, not a fresh latest-version benchmark.',
        'surface-mapping': 'Optimization inherited from DDSurfer c3b2d40; no plugin-original credit or latest-FreeSurfer speed claim.',
        'dwi-io': 'Generic compression/I/O control, not an improvement to a scientific estimator or an upstream-freshness claim.',
    }
    measurement_sources = {
        'freewater': 'freewater_latest_stable_full_20261022.json',
        'wma': 'complete_models_20261020.json', 'noddi': 'complete_models_20261020.json',
        'mkcurve': 'mkcurve_qr_scipy1181_20261022.json', 'dki': 'dki_latest_stable_integration_20261022.json',
        'scheduling': 'complete_models_20261020.json', 'wma-filter': 'author_wma_optimizations_20261020.json',
        'freewater-nls': 'freewater_dispatch_slicer_20261021.json', 'wma-transform': 'wma_transform_20261021.json',
        'wma-fibers': 'wma_fibers_bounded_20261021.json',
        **{identifier: 'performance_optimizations_20261020.json' for _, identifier, *_ in selected},
    }
    for row in rows:
        row['upstream_reference'] = references[row['id']]
        row['measurement_source'] = next(source for source in sources if source['file'] == measurement_sources[row['id']])
    return dict(kind='slicerddsurfer_public_performance_evidence', version=3, reviewed_on='2026-10-25',
                sources=sources, records=rows,
                upstream_review=dict(checked_at_utc=audit['checked_at_utc'],
                    stable_versions={key: upstream[repo]['pypi']['version'] for key, repo in (
                        ('dipy', 'dipy/dipy'), ('scipy', 'scipy/scipy'), ('amico', 'daducci/AMICO'))},
                    policy='Latest release and default-branch source identity are checked separately; source review is not a development-branch benchmark.'),
                policy='Output equivalence is not anatomical or clinical validation. No whole-workflow speedup has been established.',
                pending=['Repeated multi-subject full-module pairs', 'Completed full-brain DKI comparison',
                         'Full-brain validation for later default-QR MK-Curve changes',
                         'Matched CSD/ACT/SIFT2 complete-module baseline', 'Native Windows/macOS scientific timing',
                         'Optional persistent-model worker: proposed, not implemented or benchmarked'])


LABELS = dict(implementation='Same-method implementation', integration='Existing upstream capability', parallel='Native threads',
              port='Python-port computation', workflow='Workflow scheduling', inherited='Inherited upstream optimization', io='Compressed data I/O')


def duration(seconds):
    if seconds < .1:
        return f'{seconds * 1000:.3g} ms'
    return f'{seconds / 60:.2f} min' if seconds >= 180 else f'{seconds:.2f} s'


def render(evidence):
    rows, methods = [], []
    for row in evidence['records']:
        identifier, category = escape(row['id']), escape(row['category'])
        rows.append(f'''<tr data-category="{category}"><th scope="row"><a href="#method-{identifier}">{escape(row['title'])}</a><small>{escape(row['scope'])} / record {row['evidence_date']}</small></th><td><span class="perf-kind {category}">{LABELS[row['category']]}</span></td><td>{duration(row['reference_seconds'])}</td><td>{duration(row['optimized_seconds'])}</td><td>{row['speed_ratio']:.2f}x<small>{row['reduction_percent']:.2f}% less time</small></td></tr>''')
        methods.append(f'''<details class="perf-method" data-category="{category}" id="method-{identifier}"><summary><span>{escape(row['title'])}</span><span class="perf-scope">{escape(row['scope'])}</span></summary><div class="perf-method-body"><dl><dt>Upstream check</dt><dd>{escape(row['upstream_reference'])}</dd><dt>What changed</dt><dd>{escape(row['method'])}</dd><dt>Reference</dt><dd>{escape(row['baseline'])}</dd><dt>Equivalence</dt><dd>{escape(row['unchanged'])}</dd><dt>Measured scope</dt><dd>{escape(row['sample'])}</dd><dt>Limits</dt><dd>{escape(row['limitation'])}</dd></dl></div></details>''')
    cards = []
    for row in evidence['records'][:2]:
        cards.append(f'''<figure class="perf-chart" data-category="implementation"><figcaption><span class="perf-kind implementation">{escape(row['scope'])} / implementation</span><h3>{escape(row['title'])}</h3></figcaption><div class="perf-bar-row"><span>Reference</span><div class="perf-track"><span class="perf-bar reference" style="--extent:100%"></span></div><strong>{duration(row['reference_seconds'])}</strong></div><div class="perf-bar-row"><span>Optimized</span><div class="perf-track"><span class="perf-bar" style="--extent:{100 * row['optimized_seconds'] / row['reference_seconds']:.4f}%"></span></div><strong>{duration(row['optimized_seconds'])}</strong></div><p class="perf-chart-note">{row['reduction_percent']:.2f}% less time in this measured call. Output equivalence checked; one shared-host pair.</p></figure>''')
    return '\n'.join([
        '<div class="perf-chart-grid">' + ''.join(cards) + '</div>',
        '<div class="perf-table-wrap" tabindex="0" role="region" aria-label="Measured performance comparisons, scroll horizontally on small screens"><table class="perf-table"><caption>Different models and scopes are not ranked against each other. Ratios are reference time divided by optimized time.</caption><thead><tr><th scope="col">Computation / scope</th><th scope="col">Type of change</th><th scope="col">Reference</th><th scope="col">Optimized</th><th scope="col">Measured ratio</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>',
        '<p class="note">Only Free-water and WMA are highlighted above; NODDI multithreading, Python-port comparisons and integration of existing DIPY array metrics are deliberately labeled separately. No timing here establishes higher anatomical validity.</p>',
        '<div class="perf-methods"><h3>Methods &amp; verification</h3><p class="muted">Open a record for the reference implementation, changes, checks and limits.</p>' + ''.join(methods) + '</div>'
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if checked-in website evidence is stale')
    args = parser.parse_args()
    evidence = build_evidence()
    payload = json.dumps(evidence, indent=2) + '\n'
    page = SITE / 'index.html'
    original = page.read_text()
    if original.count(BEGIN) != 1 or original.count(END) != 1:
        raise ValueError('Expected one performance evidence region in docs/site/index.html')
    before, middle = original.split(BEGIN)
    _, after = middle.split(END)
    expected = before + BEGIN + '\n' + render(evidence) + '\n' + END + after
    data = SITE / 'assets/data/performance.json'
    if args.check:
        if not data.is_file() or data.read_text() != payload or original != expected:
            raise SystemExit('Website performance evidence in index.html is stale; run scripts/build_performance_site.py')
        print('PASS public performance data, source hashes and rendered measurements')
    else:
        data.parent.mkdir(parents=True, exist_ok=True)
        data.write_text(payload)
        page.write_text(expected)
        print(f"Exported {len(evidence['records'])} scoped measurements; private paths and runtime snapshots excluded")


if __name__ == '__main__':
    main()
