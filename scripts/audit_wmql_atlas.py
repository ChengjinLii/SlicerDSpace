#!/usr/bin/env python3
"""Compare native/derived WMQL runs and independently sample atlas assignments."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def audit_pair(native_path, derived_path):
    import nibabel as nib
    import numpy as np
    from scipy.spatial.distance import cdist
    from tractography.wmql_atlas import digest, prepared_atlas_current, RADIUS_MM

    native, derived = (json.loads(path.read_text(encoding='utf-8')) for path in (native_path, derived_path))
    raw, prepared = nib.load(native['atlas_path']), nib.load(derived['atlas_path'])
    original, result = np.asarray(raw.dataobj), np.asarray(prepared.dataobj)
    receipt = derived['atlas_preparation']
    checks = dict(
        same_subject=native['subject_id'] == derived['subject_id'],
        same_tractogram=digest(native['input_tractography']) == digest(derived['input_tractography']),
        same_native_atlas=digest(native['atlas_path']) == receipt['source_sha256'],
        same_query_definitions={Path(k).name: v for k, v in native['query_dependencies'].items()}
                               == {Path(k).name: v for k, v in derived['query_dependencies'].items()},
        same_selection=native['requested_queries'] == derived['requested_queries'],
        same_threshold=native['threshold'] == derived['threshold'] == 2.0,
        same_length_threshold=native['length_threshold'] == derived['length_threshold'],
        source_and_cache_current=prepared_atlas_current(receipt, native['atlas_path']),
        same_grid=raw.shape == prepared.shape and np.array_equal(raw.affine, prepared.affine),
        protected_labels_unchanged=np.array_equal(original[~np.isin(original, (2, 41, 192))],
                                                result[~np.isin(original, (2, 41, 192))]),
    )
    rng = np.random.default_rng(20261030)
    samples = []
    for hemi, wm, base, deep in (('left', 2, 1000, 5001), ('right', 41, 2000, 5002)):
        seed_voxels = np.argwhere((original > base) & (original <= base + 35) & (original != base + 4))
        seeds = nib.affines.apply_affine(raw.affine, seed_voxels)
        labels = original[tuple(seed_voxels.T)].astype(np.int16)
        voxels = np.argwhere(original == wm)
        ids = rng.choice(len(voxels), min(256, len(voxels)), replace=False)
        mismatches = 0
        for index in ids:
            world = nib.affines.apply_affine(raw.affine, voxels[index:index + 1])
            squared = cdist(world, seeds, metric='sqeuclidean')[0]
            minimum = squared.min()
            expected = (int(labels[np.isclose(squared, minimum, atol=1e-9, rtol=0)].min()) + 2000
                        if np.sqrt(minimum) <= RADIUS_MM else deep)
            mismatches += int(result[tuple(voxels[index])] != expected)
        allowed = {deep} | {int(label) + 2000 for label in np.unique(labels)}
        checks[hemi + '_wm_stays_in_hemisphere'] = set(map(int, np.unique(result[original == wm]))) <= allowed
        checks[hemi + '_independent_assignment_sample'] = mismatches == 0
        samples.append(dict(hemisphere=hemi, sampled_voxels=len(ids), mismatches=mismatches))
    checks['callosal_support_preserved'] = set(map(int, np.unique(result[original == 192]))) <= {192, 3004, 4004}
    counts = {}
    qc_reports = []
    for name, manifest in (('native', native), ('derived', derived)):
        qc = json.loads(Path(manifest['outputs']['qc']).read_text())
        qc_reports.append(qc)
        assessment = qc['bundle_assessment']
        counts[name] = dict(nonempty=assessment['extracted_count'], requested=assessment['requested_count'],
                            sampling_passed=sum(item['sampling_passed'] for item in assessment['bundles']),
                            empty_or_missing=sum(item['streamline_count'] == 0 for item in assessment['bundles']),
                            sparse=sum(0 < item['streamline_count'] < 20 for item in assessment['bundles']),
                            execution_seconds=qc['elapsed_seconds'], automatic_qc_passed=qc['automatic_qc_passed'])
        checks[name + '_execution_integrity'] = bool(qc['execution_passed'] and qc['output_integrity_passed'])
        checks[name + '_minimum_unchanged'] = assessment['minimum_streamlines'] == 20
    checks['experimental_not_automatically_accepted'] = not qc_reports[1]['automatic_qc_passed']
    before = {item['query_name']: item for item in qc_reports[0]['bundle_assessment']['bundles']}
    after = {item['query_name']: item for item in qc_reports[1]['bundle_assessment']['bundles']}
    return dict(subject=native['subject_id'], checks={key: bool(value) for key, value in checks.items()},
                assignment_validation=dict(method='Independent brute-force squared Euclidean distances to all cortical seed centres',
                                           random_seed=20261030, scope='512 sampled cerebral WM voxels, all protected voxels and all hemisphere-label memberships',
                                           samples=samples),
                input_hashes=dict(tractogram=digest(native['input_tractography']), native_atlas=digest(native['atlas_path'])),
                atlas_preparation_seconds=receipt['preparation_seconds'], counts=counts,
                query_comparison=[dict(query=name, native_count=before[name]['streamline_count'],
                                       derived_count=after[name]['streamline_count'],
                                       derived_sampling_passed=after[name]['sampling_passed']) for name in sorted(after)],
                anatomical_review='pending', default_route_changed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-manifest', type=Path, action='append', required=True)
    parser.add_argument('--derived-manifest', type=Path, action='append', required=True)
    parser.add_argument('--author-parity', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if len(args.native_manifest) != len(args.derived_manifest):
        parser.error('Provide one native manifest per derived manifest, in matching order')
    cases = [audit_pair(native, derived) for native, derived in zip(args.native_manifest, args.derived_manifest)]
    parity = None
    if args.author_parity:
        source = json.loads(args.author_parity.read_text())
        parity = dict(status=source['status'], checks=source['checks'], queries=len(source['comparisons']),
                      reference_runtime_seconds=source['reference_runtime_seconds'])
    passed = all(all(case['checks'].values()) for case in cases) and (parity is None or parity['status'] == 'passed')
    report = dict(schema='wmql_experimental_atlas_comparison.v1', implementation_checks='passed' if passed else 'failed',
                  scientific_acceptance='pending', radius_mm=5, minimum_streamlines=20, cases=cases,
                  author_engine_parity=parity, scope='Label preparation and extraction implementation; not expert anatomical validation',
                  default_route_changed=False, publication_figure_changed=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(implementation_checks=report['implementation_checks'],
                         cases=[dict(subject=case['subject'], counts=case['counts']) for case in cases]), indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
