#!/usr/bin/env python3
"""Independently audit the three regional cerebellar selections, never anatomy.

No Tract Querier evaluator is imported. Crossings reproduce its rounded/clipped
voxel lookup and >= per-label sample-point percentage (not arc-length fraction).
Only a report and optional path-free public receipt are written.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('cerebellar_bilateral', 'cerebellar_brainstem.left', 'cerebellar_brainstem.right')
ALIAS_SHA256 = '3fc2f3685af5061f5106f5f3c6c5644b926f0850211de0380082f274cb7be8a0'
OFFICIAL_SHA256 = '554a4eed4b99cdbe497cc5296d49ea8a65961e2b1920c1868e41d2f0dfc080ba'
SUPPORTED_BODY = '''
cb_region.side |= Cerebellum_White_Matter.side or Cerebellum_Cortex.side
cb_supratentorial |= (
    'ctx_*' or 'wm_*' or Cerebral_White_Matter.left or Cerebral_White_Matter.right or
    Cerebral_Cortex.left or Cerebral_Cortex.right or Thalamus_Proper.left or
    Thalamus_Proper.right or Caudate.left or Caudate.right or Putamen.left or
    Putamen.right or Pallidum.left or Pallidum.right or Thalamus.left or Thalamus.right or
    Accumbens_area.left or Accumbens_area.right or VentralDC.left or VentralDC.right or
    Hippocampus.left or Hippocampus.right or Amygdala.left or Amygdala.right
)
cerebellar_brainstem.side = (
    endpoints_in(cb_region.side) and
    both_endpoints_in(cb_region.side or Brain_Stem) and
    Cerebellum_White_Matter.side and Brain_Stem
) not in (cb_region.opposite or endpoints_in(cb_region.opposite)) not in (cb_supratentorial or endpoints_in(cb_supratentorial))
cerebellar_bilateral = (
    endpoints_in(cb_region.left) and endpoints_in(cb_region.right) and
    Cerebellum_White_Matter.left and Cerebellum_White_Matter.right and Brain_Stem
) not in (cb_supratentorial or endpoints_in(cb_supratentorial))
'''


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def _path(value, parent):
    path = Path(value).expanduser()
    return (path if path.is_absolute() else parent / path).resolve()


def inspect_definitions(manifest, parent):
    """Check frozen bytes/import order; AST inspection never evaluates queries."""
    root = _path(manifest.get('staged_query') or manifest['query_path'], parent)
    folders = [root.parent] + [_path(p, parent) for p in manifest.get('query_include_dirs', [])]
    expected = manifest.get('query_snapshot_dependencies') if manifest.get('staged_query') else manifest.get('query_dependencies')
    recorded = {_path(p, parent): value for p, value in (expected or {}).items()}
    files, events, active = {}, [], set()

    def visit(path):
        if path in active:
            raise ValueError('Cyclic query imports')
        active.add(path)
        files[path] = digest(path)
        for node in ast.parse(path.read_text(encoding='utf-8')).body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found = next((folder / alias.name for folder in folders if (folder / alias.name).is_file()), None)
                    if found is None:
                        raise ValueError('Missing frozen query import: ' + alias.name)
                    visit(found.resolve())
        events.append(path.name)
        active.remove(path)

    visit(root)
    if not recorded or files != recorded:
        raise ValueError('Query snapshot hashes do not match the manifest')
    aliases = [p for p in files if p.name == 'FreeSurfer.qry']
    bodies = [p for p in files if p.name == 'cerebellar_regions.qry']
    if len(aliases) != 1 or files[aliases[0]] != ALIAS_SHA256 or len(bodies) != 1:
        raise ValueError('Requires pinned FreeSurfer aliases and the import-free regional body')
    if ast.dump(ast.parse(bodies[0].read_text()), include_attributes=False) != ast.dump(ast.parse(SUPPORTED_BODY), include_attributes=False):
        raise ValueError('Unsupported regional predicate definition; update the independent audit explicitly')
    official = [p for p in files if p.name == 'freesurfer_queries.qry']
    if events.count('FreeSurfer.qry') != 1 or (official and (
            files[official[0]] != OFFICIAL_SHA256 or
            events.index('freesurfer_queries.qry') > events.index('cerebellar_regions.qry'))):
        raise ValueError('Unsafe alias re-import or regional/official import order')
    wrappers = {'cerebellar.qry': ['FreeSurfer.qry', 'cerebellar_regions.qry'],
                'official_cerebellar.qry': ['freesurfer_queries.qry', 'cerebellar_regions.qry']}
    tree = ast.parse(root.read_text())
    imports = [alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names]
    if root.name not in wrappers or imports != wrappers[root.name] or any(not isinstance(n, ast.Import) for n in tree.body):
        raise ValueError('Unsupported top-level cerebellar query wrapper')
    return files, aliases[0]


def supratentorial_labels(alias_path):
    """Resolve literal ctx_/wm_ aliases in declaration order, including overwrites."""
    aliases = {}
    for node in ast.parse(Path(alias_path).read_text()).body:
        if not isinstance(node, ast.AugAssign) or not isinstance(node.value, ast.Constant):
            continue
        target = node.target
        if isinstance(node.value.value, int) and isinstance(target, (ast.Name, ast.Attribute)):
            aliases[ast.unparse(target).lower()] = int(node.value.value)
    labels = {value for name, value in aliases.items() if name.startswith(('ctx_', 'wm_'))}
    labels.update((2, 41, 3, 42, 9, 48, 10, 49, 11, 50, 12, 51, 13, 52,
                   26, 58, 28, 60, 17, 53, 18, 54))
    return frozenset(labels)


def crossing_labels(point_labels, threshold):
    values = np.asarray(point_labels, dtype=np.int64)
    if values.ndim != 1 or len(values) < 2 or np.any(values < 0):
        raise ValueError('Expected at least two nonnegative point labels')
    if not np.isfinite(threshold) or not 0 <= threshold <= 100:
        raise ValueError('Crossing threshold must be finite and in [0,100]')
    counts = np.bincount(values)
    # At threshold zero even zero-count bins up to the maximum label qualify,
    # exactly as in the author indexer; do not replace this with unique labels.
    return set(np.flatnonzero(counts / float(len(values)) >= threshold / 100.0))


def regional_predicates(point_labels, threshold, supratentorial):
    values = np.asarray(point_labels)
    crossed = crossing_labels(values, threshold)
    endpoints = {int(values[0]), int(values[-1])}
    if 16 not in crossed or (crossed | endpoints) & supratentorial:
        return frozenset()
    left, right = {7, 8}, {46, 47}
    selected = set()
    for side, region, other, wm in (('left', left, right, 7), ('right', right, left, 46)):
        if (endpoints & region and endpoints <= region | {16} and wm in crossed
                and not (crossed | endpoints) & other):
            selected.add('cerebellar_brainstem.' + side)
    if endpoints & left and endpoints & right and {7, 46} <= crossed:
        selected.add('cerebellar_bilateral')
    return frozenset(selected)


def sample_labels(track, labels, inverse):
    voxels = np.round(np.dot(inverse[:3, :3], np.asarray(track).T).T + inverse[:3, 3]).astype(np.int64)
    outside = np.any((voxels < 0) | (voxels >= np.asarray(labels.shape)), axis=1)
    voxels = np.clip(voxels, 0, np.asarray(labels.shape) - 1)
    return labels[tuple(voxels.T)], int(outside.sum())


def tracks_from_file(path):
    """Read complete polylines in RAS mm; retain interiors and duplicate cells."""
    path = Path(path)
    if path.suffix.lower() == '.trk':
        import nibabel as nib
        tractogram = nib.streamlines.load(str(path), lazy_load=True).tractogram
        yield from tractogram.to_world(lazy=True).streamlines
        return
    if path.suffix.lower() not in ('.vtk', '.vtp'):
        raise ValueError('Unsupported streamline format')
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    reader = vtk.vtkXMLPolyDataReader() if path.suffix.lower() == '.vtp' else vtk.vtkPolyDataReader()
    errors = []
    reader.AddObserver('ErrorEvent', lambda *_: errors.append(True))
    reader.SetFileName(str(path))
    reader.Update()
    data = reader.GetOutput()
    if errors or reader.GetErrorCode() or data.GetNumberOfVerts() or data.GetNumberOfPolys() or data.GetNumberOfStrips():
        raise ValueError('Unreadable or non-streamline polydata')
    if not data.GetNumberOfLines():
        if data.GetNumberOfPoints():
            raise ValueError('Polydata points have no streamline cells')
        return
    points = vtk_to_numpy(data.GetPoints().GetData())
    cells = data.GetLines()
    offsets, connectivity = vtk_to_numpy(cells.GetOffsetsArray()), vtk_to_numpy(cells.GetConnectivityArray())
    if (len(offsets) != data.GetNumberOfLines() + 1 or offsets[0] != 0 or offsets[-1] != len(connectivity)
            or np.any(np.diff(offsets) < 2) or np.any(connectivity < 0) or np.any(connectivity >= len(points))):
        raise ValueError('Invalid streamline connectivity')
    for start, stop in zip(offsets[:-1], offsets[1:]):
        indices = connectivity[start:stop]
        yield points[indices]


def valid_track(track):
    values = np.asarray(track)
    return values.ndim == 2 and values.shape[1] == 3 and len(values) >= 2 and bool(np.isfinite(values).all())


def geometry_key(track):
    values = np.array(track, dtype='<f8', order='C', copy=True)
    values[values == 0] = 0  # Normalize signed zero without rounding geometry.
    return hashlib.sha256(len(values).to_bytes(8, 'little') + min(values.tobytes(), values[::-1].tobytes())).digest()


class GeometryIndex:
    """Counter equality first, then full-polyline one-to-one tolerant matching."""

    def __init__(self, tracks):
        self.tracks = list(tracks)
        self.valid = all(valid_track(t) for t in self.tracks)
        self.counter = Counter(geometry_key(t) for t in self.tracks if valid_track(t))
        self.tree = None

    def compare(self, candidates, tolerance=.001, subset=False):
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import maximum_bipartite_matching
        from scipy.spatial import cKDTree
        if not np.isfinite(tolerance) or tolerance < 0:
            raise ValueError('Geometry tolerance must be finite and nonnegative')
        candidates = list(candidates)
        finite = self.valid and all(valid_track(t) for t in candidates)
        observed = Counter(geometry_key(t) for t in candidates if valid_track(t))
        exact = finite and (not bool(observed - self.counter) if subset else observed == self.counter)
        result = dict(reference_count=len(self.tracks), candidate_count=len(candidates),
                      finite_geometry=finite, exact_multiset_equal=finite and observed == self.counter,
                      matched_count=0, missing_count=len(self.tracks), excess_count=len(candidates),
                      max_coordinate_delta_mm=None, passed=False)
        if exact or tolerance == 0 or not finite or not candidates or not self.tracks:
            matched = sum((observed & self.counter).values()) if finite else 0
            result.update(matched_count=matched, missing_count=len(self.tracks) - matched,
                          excess_count=len(candidates) - matched, passed=exact,
                          max_coordinate_delta_mm=0.0 if matched else None)
            return result
        if self.tree is None:
            endpoints = np.asarray([np.r_[t[0], t[-1]] for t in self.tracks])
            self.tree = cKDTree(np.vstack((endpoints, endpoints[:, [3, 4, 5, 0, 1, 2]])))
        rows, columns, errors = [], [], {}
        for i, track in enumerate(candidates):
            neighbors = self.tree.query_ball_point(np.r_[track[0], track[-1]], tolerance, p=np.inf)
            for j in {int(n) % len(self.tracks) for n in neighbors}:
                original = self.tracks[j]
                if original.shape != track.shape:
                    continue
                delta = min(float(np.max(np.abs(original.astype(float) - track))),
                            float(np.max(np.abs(original[::-1].astype(float) - track))))
                if delta <= tolerance:
                    rows.append(i)
                    columns.append(j)
                    errors[i, j] = delta
        graph = csr_matrix((np.ones(len(rows), dtype=np.int8), (rows, columns)), shape=(len(candidates), len(self.tracks)))
        matching = maximum_bipartite_matching(graph, perm_type='column')
        deltas = [errors[i, int(j)] for i, j in enumerate(matching) if j >= 0]
        matched = len(deltas)
        result.update(matched_count=matched, missing_count=len(self.tracks) - matched,
                      excess_count=len(candidates) - matched,
                      max_coordinate_delta_mm=max(deltas, default=None),
                      passed=matched == len(candidates) and (subset or matched == len(self.tracks)))
        return result


def length_mm(track):
    return float(np.linalg.norm(np.diff(np.asarray(track, dtype=float), axis=0), axis=1).sum())


def statistics(values):
    if not len(values):
        return None
    return dict(zip(('min', 'median', 'p95', 'max'), map(float, np.percentile(values, (0, 50, 95, 100)))))


def atlas_geometry(image):
    affine = np.asarray(image.affine)
    if len(image.shape) != 3 or affine.shape != (4, 4) or not np.isfinite(affine).all() or abs(np.linalg.det(affine[:3, :3])) < 1e-12:
        raise ValueError('Atlas needs finite nonsingular affine and three dimensions')
    qform, qcode = image.get_qform(coded=True)
    sform, scode = image.get_sform(coded=True)
    for form in (qform, sform):
        if form is not None and (not np.isfinite(form).all() or abs(np.linalg.det(form[:3, :3])) < 1e-12):
            raise ValueError('Invalid coded atlas qform/sform')
    return dict(shape=list(image.shape), affine=affine.tolist(),
                voxel_sizes_mm=np.linalg.norm(affine[:3, :3], axis=0).tolist(),
                determinant=float(np.linalg.det(affine[:3, :3])), qform_code=int(qcode), sform_code=int(scode),
                qform=None if qform is None else qform.tolist(), sform=None if sform is None else sform.tolist(),
                qform_sform_agree=None if qform is None or sform is None else bool(np.allclose(qform, sform, atol=1e-4, rtol=0)),
                coordinate_space='NIfTI affine maps voxel centres to RAS+ millimetres; VTK coordinates assumed RAS mm')


def audit(manifest_path, tolerance=.001, minimum=20, log=None):
    import nibabel as nib
    started = time.monotonic()
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('kind') != 'wmql_bundle_segmentation':
        raise ValueError('Requires a WMQL manifest')
    if not np.isfinite(tolerance) or tolerance < 0 or type(minimum) is not int or minimum < 1:
        raise ValueError('Invalid audit tolerance or minimum count')
    parent = manifest_path.parent
    definitions, alias_path = inspect_definitions(manifest, parent)
    supra = supratentorial_labels(alias_path)
    source_path, atlas_path = (_path(manifest[key], parent) for key in ('input_tractography', 'atlas_path'))
    threshold, length_threshold = float(manifest['threshold']), float(manifest['length_threshold'])
    if not np.isfinite(threshold) or not 0 <= threshold <= 100 or not np.isfinite(length_threshold) or length_threshold < 0:
        raise ValueError('Invalid recorded query thresholds')
    files = {}
    for item in manifest.get('outputs', {}).get('summary', {}).get('bundles', []):
        name = item['query_name'].lower()
        if name in NAMES:
            if name in files:
                raise ValueError('Duplicate output records for ' + name)
            files[name] = _path(item['path'], parent)
    # Include unrecorded on-disk regional outputs, but never old unrelated bundles.
    for file in parent.glob(str(manifest['subject_id']) + '_desc-wmql_*'):
        if file.suffix.lower() in ('.vtk', '.vtp', '.trk'):
            name = file.stem.split('_desc-wmql_', 1)[-1].lower()
            if name in NAMES:
                if name in files and files[name] != file.resolve():
                    raise ValueError('Ambiguous regional product paths')
                files[name] = file.resolve()
    observed_files = {str(manifest_path): digest(manifest_path), str(source_path): digest(source_path),
                      str(atlas_path): digest(atlas_path), **{str(p): value for p, value in definitions.items()},
                      **{str(p): digest(p) for p in files.values()}}
    image = nib.load(str(atlas_path))
    geometry = atlas_geometry(image)
    labels = np.asanyarray(image.dataobj)
    if not np.isfinite(labels).all() or np.any(labels < 0) or np.any(labels != np.floor(labels)):
        raise ValueError('Atlas must have finite nonnegative integer labels')
    labels = labels.astype(np.int64)
    inverse = np.linalg.inv(image.affine)
    source = list(tracks_from_file(source_path))
    if log:
        log(f'Independently evaluating {len(source)} source streamlines', flush=True)
    expected = {name: [] for name in NAMES}
    source_lengths, outside_points, outside_tracks, invalid, filtered = [], 0, 0, 0, 0
    for index, track in enumerate(source):
        if not valid_track(track):
            invalid += 1
            continue
        length = length_mm(track)
        source_lengths.append(length)
        point_labels, outside = sample_labels(track, labels, inverse)
        outside_points += outside
        outside_tracks += int(outside > 0)
        # Match the author's native-dtype length calculation for the optional filter.
        native_length = float(np.sqrt(((track[1:] - track[:-1]) ** 2).sum(axis=1)).sum())
        if native_length < length_threshold:
            filtered += 1
            continue
        for name in regional_predicates(point_labels, threshold, supra):
            expected[name].append(track)
        if log and (index + 1) % 100000 == 0:
            log(f'Evaluated {index + 1} source streamlines', flush=True)
    source_index = GeometryIndex(source)
    records = []
    for name in NAMES:
        tracks = list(tracks_from_file(files[name])) if name in files else []
        parity = GeometryIndex(expected[name]).compare(tracks, tolerance)
        membership = source_index.compare(tracks, tolerance, subset=True)
        pairs, lengths, violations, outside = Counter(), [], 0, 0
        for track in tracks:
            if not valid_track(track):
                violations += 1
                continue
            values, count = sample_labels(track, labels, inverse)
            outside += int(count > 0)
            pair = sorted((int(values[0]), int(values[-1])))
            pairs[f'{pair[0]},{pair[1]}'] += 1
            lengths.append(length_mm(track))
            violations += int(name not in regional_predicates(values, threshold, supra))
        records.append(dict(query_name=name, output_present=name in files,
                            expected_count=len(expected[name]), actual_count=len(tracks),
                            multiset_parity=parity, source_membership=membership,
                            all_points_finite=all(valid_track(t) for t in tracks),
                            all_lengths_positive=all(value > 0 for value in lengths) and len(lengths) == len(tracks),
                            length_mm=statistics(lengths), expected_length_mm=statistics([length_mm(t) for t in expected[name]]),
                            endpoint_label_pairs=dict(sorted(pairs.items())), regional_predicate_violations=violations,
                            outside_fov_tracks=outside, sampling_passed=len(tracks) >= minimum,
                            human_review='pending', quantification_eligible=False,
                            sha256=digest(files[name]) if name in files else None))
    requested = set(manifest.get('requested_queries') or manifest.get('query_selection') or NAMES)
    unchanged = all(digest(path) == value for path, value in observed_files.items())
    checks = dict(recorded_execution_completed=manifest.get('status') == 'completed' and manifest.get('executed') is True,
                  all_three_queries_requested=set(NAMES) <= requested,
                  query_snapshot_verified=True, atlas_labels_and_affine_valid=True,
                  source_nonempty_and_finite=bool(source) and invalid == 0,
                  source_positive_lengths=bool(source_lengths) and min(source_lengths) > 0,
                  full_expected_source_multisets_match=all(r['multiset_parity']['passed'] for r in records),
                  all_outputs_from_source=all(r['source_membership']['passed'] for r in records),
                  output_geometry_valid=all(r['all_points_finite'] and r['all_lengths_positive'] for r in records),
                  output_regional_predicates_pass=all(r['regional_predicate_violations'] == 0 for r in records),
                  all_minimum_streamlines=all(r['sampling_passed'] for r in records),
                  no_outside_fov_points=outside_points == 0 and all(r['outside_fov_tracks'] == 0 for r in records),
                  inputs_and_outputs_unchanged=unchanged)
    return dict(schema='wmql_cerebellar_independent_audit.v1',
                status='passed_anatomical_review_pending' if all(checks.values()) else 'needs_review',
                checks=checks, human_review='pending', quantification_eligible=False,
                manifest=str(manifest_path), source=str(source_path), atlas=str(atlas_path),
                parameters=dict(threshold_percent=threshold, length_threshold_mm=length_threshold,
                                geometry_tolerance_mm=tolerance, minimum_streamlines=minimum),
                source_summary=dict(streamlines=len(source), invalid_tracks=invalid, length_filtered_tracks=filtered,
                                    length_mm=statistics(source_lengths), outside_fov_tracks=outside_tracks,
                                    outside_fov_points=outside_points),
                atlas_geometry=geometry, supratentorial_label_ids=sorted(supra),
                hashes=dict(manifest=digest(manifest_path), source=digest(source_path), atlas=digest(atlas_path),
                            audit_script=digest(__file__), query_dependencies={p.name: value for p, value in definitions.items()}),
                file_hashes=observed_files, bundles=records, audit_seconds=time.monotonic() - started,
                semantics=dict(rounding='numpy.round, including ties-to-even; voxel centres; clip to atlas FOV',
                               crossing='Each numeric label independently occupies >= threshold percent of sampled points, not geometric length',
                               endpoints='First and last stored streamline points; no dilation or nearest-region search',
                               multiset='Direction-invariant float64 coordinate Counter; full-polyline one-to-one matching within tolerance if needed'),
                limitations=['Regional candidates only; no peduncle-specific identification or anatomical acceptance.',
                             'VTK has no spatial affine; native RAS-mm correspondence requires anatomical review.',
                             'Clipping matches the author but outside-FOV points are flagged, not silently accepted.',
                             'Brief interior exclusions below the per-label crossing threshold can remain.',
                             'Nonzero length filtering is checked against physical source tracks, not renumbered source indices.'])


def public_receipt(report):
    """Whitelist aggregate fields: never export paths, filenames, IDs or commands."""
    keys = ('schema', 'status', 'checks', 'human_review', 'quantification_eligible', 'parameters',
            'source_summary', 'hashes', 'bundles', 'semantics', 'limitations')
    return {key: report[key] for key in keys}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', '--report', dest='output', type=Path, required=True)
    parser.add_argument('--public-receipt', type=Path, help='Optional aggregate-only JSON without patient paths or IDs')
    parser.add_argument('--tolerance-mm', type=float, default=.001)
    parser.add_argument('--minimum-streamlines', type=int, default=20)
    args = parser.parse_args()
    report = audit(args.manifest, args.tolerance_mm, args.minimum_streamlines, log=print)
    outputs = [args.output] + ([args.public_receipt] if args.public_receipt else [])
    if len({p.resolve() for p in outputs}) != len(outputs) or any(str(p.resolve()) in report['file_hashes'] for p in outputs):
        raise ValueError('Report destinations must be distinct and cannot overwrite audited files')
    for path, value in [(args.output, report)] + ([(args.public_receipt, public_receipt(report))] if args.public_receipt else []):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=report['status'], checks=report['checks'],
                          bundles={r['query_name']: r['actual_count'] for r in report['bundles']})))
    return 0 if all(report['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
