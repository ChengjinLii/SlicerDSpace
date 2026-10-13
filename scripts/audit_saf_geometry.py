#!/usr/bin/env python3
"""Read-only audit of actual SAF products and saved native-space surfaces.

All tractogram coordinates/lengths are checked. Triangle distances use a
deterministic capped sample, reported separately from whole-file checks.
No curvature threshold is presented as a biological SAF classifier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.io import loadmat


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'path': str(path.resolve()), 'size': path.stat().st_size, 'sha256': digest.hexdigest()}


def quantiles(values):
    values = np.asarray(values)
    return dict(zip(('min', 'p05', 'median', 'p95', 'max'),
                    map(float, np.percentile(values, (0, 5, 50, 95, 100)))))


def triangle_distances(vertices, faces, points):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray

    polydata = vtk.vtkPolyData()
    vtk_points = vtk.vtkPoints()
    vtk_points.SetData(numpy_to_vtk(np.ascontiguousarray(vertices), deep=True))
    polydata.SetPoints(vtk_points)
    cells = vtk.vtkCellArray()
    packed = np.column_stack([np.full(len(faces), 3), faces]).astype(np.int64).ravel()
    cells.SetCells(len(faces), numpy_to_vtkIdTypeArray(packed, deep=True))
    polydata.SetPolys(cells)
    locator = vtk.vtkStaticCellLocator()
    locator.SetDataSet(polydata)
    locator.BuildLocator()
    distances = []
    for point in points:
        closest = [0., 0., 0.]
        cell, sub, distance = vtk.reference(0), vtk.reference(0), vtk.reference(0.)
        locator.FindClosestPoint(point, closest, cell, sub, distance)
        distances.append(float(distance) ** .5)
    return np.asarray(distances)


def audit(directory, sample_limit=20000):
    tck = directory / 'SAF.tck'
    manifest_path = directory / 'saf_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    sd_path = directory / 'SD.mat'
    if not sd_path.is_file():
        sd_path = directory / 'cache/SD.mat'
    dwi = loadmat(sd_path, simplify_cells=True)['SD']['DWI']
    saf = dwi['saf']
    selected = np.all(saf['t'] > 0, axis=0)
    hemispheres = saf['h'][:, selected].astype(bool)
    tracks = nib.streamlines.load(str(tck)).streamlines
    if not len(tracks):
        raise ValueError('SAF tractogram is empty; no geometry pass can be reported')
    lengths, ratios, point_counts = [], [], []
    finite = True
    for track in tracks:
        finite &= bool(np.isfinite(track).all())
        points = np.asarray(track, dtype=float)
        length = float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())
        lengths.append(length)
        ratios.append(float(np.linalg.norm(points[-1] - points[0]) / length) if length > 0 else 1.)
        point_counts.append(len(points))
    length_array = np.asarray(lengths)
    paired_indices = saf['t'][:, selected].astype(int)
    mapped_distances, valid_vertices = [], True
    proximity = {}
    for hemi, is_left in [('rh', False), ('lh', True)]:
        track_indices = np.flatnonzero(hemispheres[0] == is_left)
        if not len(track_indices):
            proximity[hemi] = {'streamlines': 0, 'sampled_streamlines': 0, 'surfaces': {}}
            continue
        mesh = dwi[hemi]
        vertex_indices = paired_indices[:, track_indices] - 1
        valid_vertices &= bool(np.all((vertex_indices >= 0) & (vertex_indices < len(mesh['white']))))
        if valid_vertices:
            valid_vertices &= bool(np.all(mesh['usedv'][vertex_indices]))
        all_endpoints = np.stack([np.asarray(tracks[int(i)])[[0, -1]] for i in track_indices])
        assigned = mesh['white'][vertex_indices.T]
        mapped_distances.extend(np.linalg.norm(assigned - all_endpoints, axis=2).ravel())
        sampled = track_indices[np.unique(np.linspace(0, len(track_indices) - 1, min(len(track_indices), sample_limit // 2), dtype=int))]
        sample_points = np.stack([np.asarray(tracks[int(i)])[[0, len(tracks[int(i)]) // 2, -1]] for i in sampled])
        surfaces = {}
        for surface in ('white', 'pial'):
            distances = triangle_distances(mesh[surface], mesh['faces'].astype(int), sample_points.reshape(-1, 3)).reshape(-1, 3)
            surfaces[surface] = {'start_mm': quantiles(distances[:, 0]), 'middle_mm': quantiles(distances[:, 1]),
                                 'end_mm': quantiles(distances[:, 2]),
                                 'endpoints_over_1mm_fraction': float(np.mean(distances[:, [0, 2]] > 1.))}
        proximity[hemi] = {'streamlines': int(len(track_indices)), 'sampled_streamlines': int(len(sampled)), 'surfaces': surfaces}
    vtk_file = directory / 'SAF.vtk'
    vtk_result = {'status': 'missing'}
    if vtk_file.is_file():
        import vtk
        from vtk.util.numpy_support import vtk_to_numpy
        reader = vtk.vtkPolyDataReader()
        reader.SetFileName(str(vtk_file))
        reader.Update()
        polydata = reader.GetOutput()
        vtk_points = vtk_to_numpy(polydata.GetPoints().GetData())
        offsets = vtk_to_numpy(polydata.GetLines().GetOffsetsArray())
        connectivity = vtk_to_numpy(polydata.GetLines().GetConnectivityArray())
        indices = np.unique(np.linspace(0, len(tracks) - 1, min(201, len(tracks)), dtype=int))
        delta = 0.
        for index in indices:
            a = vtk_points[connectivity[offsets[index]:offsets[index + 1]]]
            b = np.asarray(tracks[int(index)])
            delta = max(delta, float(np.max(np.abs(a - b))) if a.shape == b.shape else float('inf'))
        vtk_result = {'line_count': polydata.GetNumberOfLines(), 'sampled_lines': int(len(indices)), 'max_coordinate_delta_mm': delta}
    maximum = (manifest.get('parameters') or {}).get('maxlen')
    checks = {
        'manifest_output_resolves_to_source': Path(manifest['outputs']['saf_tractogram']).resolve() == tck.resolve(),
        'finite_coordinates': finite,
        'positive_lengths': bool(np.all(length_array > 0)),
        'count_matches_saved_selection': int(selected.sum()) == len(tracks),
        'same_hemisphere_flags': bool(np.all(hemispheres[0] == hemispheres[1])),
        'mapped_vertices_in_cortex': valid_vertices,
        'within_configured_maximum_length': maximum is None or float(length_array.max()) <= float(maximum) + .001,
        'vtk_counts_match': vtk_result.get('line_count') == len(tracks),
        'vtk_sampled_coordinates_match': vtk_result.get('max_coordinate_delta_mm', float('inf')) <= .001,
        'sampled_white_endpoints_within_1mm': all(v['surfaces']['white']['endpoints_over_1mm_fraction'] == 0. for v in proximity.values() if v['streamlines']),
    }
    return {'status': 'geometry_pass_manual_review_pending' if all(checks.values()) else 'needs_review',
            'subject_id': manifest.get('subject_id'), 'source': fingerprint(tck), 'saved_state': fingerprint(sd_path),
            'parameters': manifest.get('parameters'), 'implementation': manifest.get('implementation'),
            'checks': checks, 'streamline_count': len(tracks), 'length_mm': quantiles(lengths),
            'chord_to_arc_ratio': quantiles(ratios), 'fraction_chord_to_arc_le_0_7': float(np.mean(np.asarray(ratios) <= .7)),
            'point_counts': quantiles(point_counts), 'assigned_white_vertex_distance_mm': quantiles(mapped_distances),
            'surface_proximity': proximity, 'vtk': vtk_result,
            'limitations': ['Triangle proximity is sampled, not a whole-file pass for depth or pial containment.',
                            'These checks do not prove adjacent-gyri connectivity, U shape, absence of false positives or biological validity.',
                            'Older surface projections need recomputation with corrected endpoint indexing; a geometry pass does not validate them.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saf-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sample-limit', type=int, default=20000)
    args = parser.parse_args()
    if args.sample_limit < 2:
        parser.error('--sample-limit must be at least 2')
    result = audit(args.saf_dir.resolve(), args.sample_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'streamline_count', 'length_mm', 'checks')}, indent=2))
    return 0 if all(result['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
