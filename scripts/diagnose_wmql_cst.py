#!/usr/bin/env python3
"""Trace unmodified author AF/CST predicates on the exact original tractogram."""

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def track_multiset_parity(reference, candidate, tolerance=.001):
    """Check one-to-one geometry identity, allowing the recorded ASCII precision."""
    from collections import Counter
    import numpy as np
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import maximum_bipartite_matching
    from scipy.spatial import cKDTree
    from scripts.audit_bundle_products import line_hash

    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Geometry tolerance must be finite and positive')
    reference, candidate = list(reference), list(candidate)
    geometry_ok = all(np.asarray(t).ndim == 2 and np.asarray(t).shape[1] == 3
                      and len(t) >= 2 and np.isfinite(t).all() for t in reference + candidate)
    result = dict(reference_count=len(reference), candidate_count=len(candidate),
                  tolerance_mm=tolerance, finite_geometry=geometry_ok,
                  exact_byte_multiset=False, matched_count=0,
                  max_coordinate_delta_mm=None, passed=False)
    if not geometry_ok:
        return result
    result['exact_byte_multiset'] = Counter(map(line_hash, reference)) == Counter(map(line_hash, candidate))
    if not reference or not candidate:
        result['passed'] = not reference and not candidate
        return result
    endpoints = np.asarray([np.r_[t[0], t[-1]] for t in reference])
    tree = cKDTree(np.vstack([endpoints, endpoints[:, [3, 4, 5, 0, 1, 2]]]))
    rows, columns, errors = [], [], {}
    for i, track in enumerate(candidate):
        track = np.asarray(track, dtype=float)
        for j in {int(j) % len(reference) for j in tree.query_ball_point(
                np.r_[track[0], track[-1]], tolerance, p=np.inf)}:
            original = np.asarray(reference[j], dtype=float)
            if original.shape != track.shape:
                continue
            delta = min(float(np.max(np.abs(original - track))),
                        float(np.max(np.abs(original[::-1] - track))))
            if delta <= tolerance:
                rows.append(i)
                columns.append(j)
                errors[i, j] = delta
    # Membership alone would allow duplicate output tracks to replace a missing
    # source track. A bipartite match preserves the selected multiset instead.
    graph = csr_matrix((np.ones(len(rows), dtype=np.int8), (rows, columns)),
                       shape=(len(candidate), len(reference)))
    matching = maximum_bipartite_matching(graph, perm_type='column')
    deltas = [errors[i, int(j)] for i, j in enumerate(matching) if j >= 0]
    result.update(matched_count=len(deltas), max_coordinate_delta_mm=max(deltas, default=None),
                  passed=len(deltas) == len(reference) == len(candidate))
    return result


def compare_cst_results(reference_manifest, candidate_manifest, output):
    from collections import Counter
    from scripts.audit_bundle_products import line_hash, tracks_from_file
    from tractography.wmql import bundled_wmql_query_path

    manifests = [json.loads(path.read_text()) for path in (reference_manifest, candidate_manifest)]
    queries = [Path(record['staged_query']) for record in manifests]
    def cst_assignment(path):
        tree = ast.parse(path.read_text())
        return [ast.dump(node, include_attributes=False) for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                        and target.value.id.lower() == 'cst' and target.attr.lower() == 'side' for target in node.targets)]
    expected = cst_assignment(bundled_wmql_query_path().with_name('CST_WMQL2016.qry'))
    checks = {'published_assignment_identical': bool(expected) and all(cst_assignment(path) == expected for path in queries)}
    products = []
    for record in manifests:
        qc = json.loads(Path(record['outputs']['qc']).read_text())
        products.append({item['query_name']: Path(item['path']) for item in qc['output_summary']['bundles']})
    bundles = {}
    for name in ('cst.left', 'cst.right'):
        paths = [mapping[name] for mapping in products]
        counters = [Counter(map(line_hash, tracks_from_file(path))) for path in paths]
        checks[name] = counters[0] == counters[1] and bool(counters[0])
        bundles[name] = dict(reference_count=sum(counters[0].values()), candidate_count=sum(counters[1].values()),
                             identical_track_multiset=counters[0] == counters[1],
                             files=[dict(path=str(path.resolve()), sha256=sha256(path)) for path in paths])
    result = dict(status='passed' if all(checks.values()) else 'failed', checks=checks, bundles=bundles,
                  manifests=list(map(lambda path: str(path.resolve()), (reference_manifest, candidate_manifest))),
                  scope='Published CST assignment AST and output-streamline multiset identity; not anatomical ground truth')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'definition_parity.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
    return result


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def trace_predicates(queries, side, structure):
    opposite = 'right' if side == 'left' else 'left'
    base = queries[f'{structure}.{side}'].tracts & queries['brain_stem'].tracts
    remaining, stages = set(base), []
    for name in (f'superiorfrontal.{side}', f'cerebellum_white_matter.{side}',
                 f'thalamus_proper.{side}', f'hemisphere.{opposite}'):
        excluded = queries[name].tracts
        stages.append(dict(predicate=name, input=len(remaining), excluded_alone=len(base & excluded),
                           removed=len(remaining & excluded), remaining=len(remaining - excluded)))
        remaining -= excluded
    expected = queries[f'cst_{"pre" if structure == "precentral" else "post"}.{side}'].tracts
    return dict(base_streamlines=len(base), stages=stages, final_count=len(remaining),
                original_query_count=len(expected), exact_author_set_match=remaining == expected), base, remaining


def trace_af_predicates(queries, side):
    frontal = set().union(*(queries[f'{name}.{side}'].tracts for name in
                          ('inferior_frontal_gyrus', 'middle_frontal_gyrus', 'precentral')))
    temporal = set().union(*(queries[f'{name}.{side}'].tracts for name in ('superiortemporal', 'middletemporal')))
    base = frontal & temporal
    remaining, stages = set(base), []
    for name in ('slf_ii', 'slf_iii', 'mdlf', 'ioff', 'ilf', 'extreme_capsule',
                 'insula', 'centrum_semiovale', 'occipital', 'temporalpole',
                 'medialorbitofrontal', 'lateralorbitofrontal'):
        excluded = queries[f'{name}.{side}'].tracts
        stages.append(dict(predicate=f'{name}.{side}', input=len(remaining),
                           excluded_alone=len(base & excluded), removed=len(remaining & excluded),
                           remaining=len(remaining - excluded)))
        remaining -= excluded
    expected = queries[f'af.{side}'].tracts
    return dict(frontal_candidates=len(frontal), temporal_candidates=len(temporal),
                base_streamlines=len(base), stages=stages, final_count=len(remaining),
                original_query_count=len(expected), exact_author_set_match=remaining == expected), remaining


def author_trace_query(manifest):
    """Do not apply the author's AF exclusions to an adapted endpoint query."""
    from tractography.wmql import wmql_query_dependencies, wmql_query_provenance

    query = Path(manifest.get('staged_query') or manifest['query_path'])
    folders = [query.parent]
    if not manifest.get('staged_query'):
        folders.append(Path(manifest['backend']['root']) / 'tract_querier/data')
    dependencies = wmql_query_dependencies(query, folders)
    recorded = manifest.get('query_snapshot_dependencies')
    if manifest.get('staged_query') and recorded and dependencies != recorded:
        raise ValueError('WMQL query snapshot no longer matches its recorded dependencies')
    provenance = wmql_query_provenance(query, dependencies)
    if provenance['preset'] != 'author_repository_crossing_exclusion':
        raise ValueError('Author AF/CST trace requires the unmodified author preset and aliases; '
                         'use endpoint_rule_check for DDParcel AF candidates or endpoint protocols')
    return query, folders, dependencies


def diagnose(manifest_path, output):
    from scripts.audit_bundle_products import tracks_from_file
    import nibabel as nib
    import numpy as np

    manifest = json.loads(manifest_path.read_text())
    query_path, includes, dependencies = author_trace_query(manifest)
    backend_root = Path(manifest['backend']['root'])
    sys.path.insert(0, str(backend_root))
    import tract_querier as tq

    tract_path, atlas_path = map(Path, (manifest['input_tractography'], manifest['atlas_path']))
    before = {**dependencies, **{str(path.resolve()): sha256(path) for path in (tract_path, atlas_path)}}
    original = tq.tractography.tractography_from_file(str(tract_path))
    tracks = original.tracts()
    atlas = nib.load(atlas_path)
    labels = np.asarray(atlas.dataobj)
    print(f'Indexing original {len(tracks)} streamlines at author threshold {manifest["threshold"]}', flush=True)
    index = tq.TractographySpatialIndexing(tracks, labels, atlas.affine, manifest['length_threshold'], manifest['threshold'])
    evaluator = tq.EvaluateQueries(index)
    body = tq.queries_preprocess(query_path.read_text(), filename=str(query_path), include_folders=list(map(str, includes)))
    evaluator.visit(ast.Module(body=body, type_ignores=[]))
    queries = evaluator.evaluated_queries_info
    report = dict(kind='unmodified_author_cst_predicate_trace', source_hashes=before,
                  manifest=str(manifest_path.resolve()), input_streamlines=len(tracks), threshold_percent=manifest['threshold'],
                  coordinate_space='native scanner RAS mm', atlas_shape=list(atlas.shape), atlas_affine=atlas.affine.tolist(), hemispheres={})
    csv_rows = []
    saved = {item['query_name']: Path(item['path']) for item in manifest['outputs']['summary']['bundles']}
    for side in ('left', 'right'):
        hemisphere = {}
        bases, finals = [], []
        for structure in ('precentral', 'postcentral'):
            trace, base, final = trace_predicates(queries, side, structure)
            hemisphere[structure] = trace
            bases.append(base)
            finals.append(final)
            for row in trace['stages']:
                csv_rows.append(dict(hemisphere=side, branch=structure, **row))
        cortex = queries[f'precentral.{side}'].labels | queries[f'postcentral.{side}'].labels
        brainstem = queries['brain_stem'].labels
        def endings(region):
            return set().union(*(index.ending_labels_tracts[end].get(label, set()) for label in region for end in (0, 1)))
        published = endings(cortex) & endings(brainstem)
        base, final = set.union(*bases), set.union(*finals)
        saved_parity = track_multiset_parity(
            (tracks[number] for number in sorted(final)), tracks_from_file(saved[f'cst.{side}']))
        missing_crossing = dict(cortical_crossing_below_threshold=0, brainstem_crossing_below_threshold=0)
        selected = []
        inverse = np.linalg.inv(atlas.affine)
        for number in sorted(published):
            points = np.asarray(tracks[number])
            voxels = np.rint(nib.affines.apply_affine(inverse, points)).astype(int)
            inside = np.all((voxels >= 0) & (voxels < labels.shape), axis=1)
            point_labels = np.zeros(len(points), dtype=int)
            point_labels[inside] = labels[tuple(voxels[inside].T)]
            fractions = {str(int(label)): float(np.count_nonzero(point_labels == label) / len(points))
                         for label in np.unique(point_labels)}
            if number not in base:
                crossings = index.crossing_tracts_labels[number]
                missing_crossing['cortical_crossing_below_threshold'] += int(not bool(crossings & cortex))
                missing_crossing['brainstem_crossing_below_threshold'] += int(not bool(crossings & brainstem))
            selected.append(dict(source_index=number, length_mm=float(np.linalg.norm(np.diff(points.astype(float), axis=0), axis=1).sum()),
                                 satisfies_legacy_base=number in base, survives_legacy_exclusions=number in final,
                                 endpoint_labels=list(map(int, point_labels[[0, -1]])), point_label_fractions=fractions))
        hemisphere.update(legacy_cst=len(queries[f'cst.{side}'].tracts),
                          traced_legacy_union_match=final == queries[f'cst.{side}'].tracts,
                          saved_cst_matches_author_set=saved_parity['passed'],
                          saved_cst_geometry_parity=saved_parity,
                          published_endpoint_cst=len(published), published_also_legacy_base=len(published & base),
                          published_also_legacy_final=len(published & final),
                          endpoint_candidates_missing_crossings=missing_crossing,
                          relevant_label_voxels={str(label): int(np.count_nonzero(labels == label)) for label in sorted(cortex | brainstem)},
                          published_endpoint_source_indices=sorted(published), endpoint_predicate_details=selected)
        if f'af.{side}' in saved:
            af, af_final = trace_af_predicates(queries, side)
            af['saved_geometry_parity'] = track_multiset_parity(
                (tracks[number] for number in sorted(af_final)), tracks_from_file(saved[f'af.{side}']))
            involved = ('inferior_frontal_gyrus', 'middle_frontal_gyrus', 'precentral',
                        'superiortemporal', 'middletemporal')
            involved_labels = set().union(*(queries[f'{name}.{side}'].labels for name in involved))
            af['relevant_label_voxels'] = {str(label): int(np.count_nonzero(labels == label))
                                           for label in sorted(involved_labels)}
            from tractography.wmql import MIN_BUNDLE_STREAMLINES
            af['sampling_passed'] = af['final_count'] >= MIN_BUNDLE_STREAMLINES
            af['sampling_minimum'] = MIN_BUNDLE_STREAMLINES
            hemisphere['af'] = af
            csv_rows.extend(dict(hemisphere=side, branch='af', **row) for row in af['stages'])
        report['hemispheres'][side] = hemisphere
    unique = np.unique(labels)
    report['regional_wm_labels'] = [int(value) for value in unique if 3001 <= value <= 3035 or 4001 <= value <= 4035]
    report['inputs_unchanged'] = all(sha256(Path(path)) == value for path, value in before.items())
    report['automatic_predicate_parity_passed'] = report['inputs_unchanged'] and all(
        h['traced_legacy_union_match'] and h['saved_cst_matches_author_set']
        and all(h[s]['exact_author_set_match'] for s in ('precentral', 'postcentral'))
        and ('af' not in h or (h['af']['exact_author_set_match'] and h['af']['saved_geometry_parity']['passed']))
        for h in report['hemispheres'].values())
    report['scope'] = 'Author predicate and saved geometry parity only; diagnostic success does not certify sampling or anatomy'
    report['status'] = 'passed' if report['automatic_predicate_parity_passed'] else 'failed'
    report['limitations'] = ['Predicate tracing is not anatomical ground truth.',
                             'Legacy repository crossing/exclusion queries differ from the published/tutorial endpoint CST definition.',
                             'No thresholds, labels, endpoints, or tracts were changed.']
    output.mkdir(parents=True, exist_ok=False)
    (output / 'predicate_trace.json').write_text(json.dumps(report, indent=2) + '\n')
    with (output / 'predicate_trace.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    print(json.dumps({side: {key: value for key, value in result.items()
                            if key not in {'endpoint_predicate_details', 'published_endpoint_source_indices'}}
                      for side, result in report['hemispheres'].items()}, indent=2), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--manifest', type=Path)
    group.add_argument('--reference-manifest', type=Path)
    parser.add_argument('--candidate-manifest', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    if args.reference_manifest:
        if not args.candidate_manifest:
            parser.error('--reference-manifest requires --candidate-manifest')
        result = compare_cst_results(args.reference_manifest, args.candidate_manifest, args.output)
    else:
        result = diagnose(args.manifest, args.output)
    print(f'Diagnostic seconds: {time.monotonic() - started:.3f}', flush=True)
    if result['status'] != 'passed':
        raise SystemExit(1)
