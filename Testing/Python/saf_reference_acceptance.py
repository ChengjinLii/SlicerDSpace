#!/usr/bin/env python3
"""Compare SAF kernels against unmodified .m code executed by GNU Octave.

No MATLAB runtime or imaging outputs are simulated. Synthetic fixtures exercise
index layout and general-position intersections, not biological correctness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy.io import loadmat, savemat

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def fixture() -> dict:
    rng = np.random.default_rng(20261013)
    triangles = rng.normal(size=(1200, 3, 3))
    tetra = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])
    faces = np.array([[1, 2, 3], [0, 1, 3], [0, 2, 1], [0, 3, 2]])
    vertices = np.vstack([tetra, tetra + [2., 0., 0.]])
    faces = np.vstack([faces, faces + 4])
    # Different y/z values force distinct nearest vertices at both ends.
    x = np.array([-.5, -.1, .1, .25, .4, .55, .7, .9, 1.2, 1.8, 1.9, 2.1, 2.25, 2.4, 2.55, 2.7, 2.9, 3.2])
    tracks = np.empty((1, 3), dtype=object)
    tracks[0, 0] = np.column_stack([x, np.full_like(x, .1), np.full_like(x, .1)])
    tracks[0, 1] = np.column_stack([x, np.full_like(x, .1), np.full_like(x, .6)])
    tracks[0, 2] = np.column_stack([x, np.full_like(x, .6), np.full_like(x, .1)])
    return {
        'P1': triangles[:, 0], 'P2': triangles[:, 1], 'P3': triangles[:, 2],
        'Q1': rng.normal(size=(1200, 3)), 'Q2': rng.normal(size=(1200, 3)),
        'triangle_vertices': np.arange(3600).reshape(1200, 3) + 1,
        'face_ids': np.arange(1200)[:, None] + 1,
        'segment_ids': (2 * np.arange(1200))[:, None] + 1,
        'vertices': vertices, 'faces': faces + 1, 'tracks': tracks,
        'inside': False, 'outer_intersection': False,
    }


def compare(data: dict, reference: dict, *, analytic_fixture=True) -> dict:
    from tractography.saf_backend.Filters.streamlineXmesh.crop_streamlines_outside_mesh_fast import crop_streamlines_outside_mesh_fast
    from tractography.saf_backend.Filters.streamlineXmesh.crop_streamlines_outside_mesh_complete import crop_streamlines_outside_mesh_complete
    from tractography.saf_backend.Filters.streamlineXmesh.trintersect_fast import trintersect_fast
    from tractography.saf_backend.Filters.streamlineXmesh.trintersect_complete import trintersect_complete

    args = [data[k] for k in ('P1', 'P2', 'P3', 'Q1', 'Q2')]
    checks = {}
    checks['fast_general_position_1200'] = bool(np.array_equal(trintersect_fast(*args), reference['fast_intersections'].ravel()))
    checks['complete_general_position_1200'] = bool(np.array_equal(
        trintersect_complete(*args, data['triangle_vertices'], data['face_ids'].ravel(), data['segment_ids'].ravel()),
        reference['complete_intersections'].ravel(),
    ))
    tracks = list(data['tracks'].flat)
    for name, crop in [('fast', crop_streamlines_outside_mesh_fast), ('complete', crop_streamlines_outside_mesh_complete)]:
        actual = crop(data['vertices'], data['faces'] - 1, tracks, False, False)
        expected_tracks = list(reference[f'{name}_tracks'].flat)
        checks[f'{name}_trimmed_coordinates'] = len(actual[0]) == len(expected_tracks) and all(
            np.array_equal(a, b) for a, b in zip(actual[0], expected_tracks)
        )
        for key, value, expected in [
            ('source_indices', actual[1], reference[f'{name}_original'].ravel() - 1),
            ('point_indices', actual[3], reference[f'{name}_points'] - 1),
        ]:
            checks[f'{name}_{key}'] = bool(np.array_equal(value, expected))
        # The author kernel mixes endpoint layouts in its final vertex lookup.
        # Use analytically determined tetrahedron vertices, not its faulty
        # lookup, as the oracle for this explicitly documented correction.
        if analytic_fixture:
            gold = np.array([[1, 5, 4, 8, 3, 7], [2, 6, 4, 8, 3, 7]])
            checks[f'{name}_endpoint_vertices_geometric_gold'] = bool(np.array_equal(actual[2], gold))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--octave', default='octave')
    parser.add_argument('--docker-image')
    parser.add_argument('--real-state', type=Path)
    parser.add_argument('--real-initial', type=Path)
    parser.add_argument('--sample-count', type=int, default=128)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    data = fixture()
    real_source = None
    if args.real_state or args.real_initial:
        if not (args.real_state and args.real_initial) or args.sample_count < 1:
            parser.error('Real comparisons require --real-state, --real-initial and positive --sample-count')
        import nibabel as nib
        dwi = loadmat(args.real_state, simplify_cells=True)['SD']['DWI']
        candidates = np.flatnonzero(np.all(dwi['saf']['t'] > 0, axis=0) & ~dwi['saf']['h'][0].astype(bool))
        chosen = candidates[np.unique(np.linspace(0, len(candidates) - 1, min(len(candidates), args.sample_count), dtype=int))]
        initial = nib.streamlines.load(str(args.real_initial)).streamlines
        real_tracks = np.empty((1, len(chosen)), dtype=object)
        for i, index in enumerate(chosen):
            real_tracks[0, i] = np.asarray(initial[int(index)], dtype=float)
        mesh = dwi['rh']
        faces = mesh['faces'].astype(int)
        faces = faces[np.all(mesh['usedv'][faces], axis=1)]
        data.update(vertices=mesh['white'].astype(float), faces=faces + 1, tracks=real_tracks)
        np.savetxt(out / 'original_track_indices.csv', chosen, fmt='%d', header='zero_based_original_track_index', comments='')
        real_source = {'state': str(args.real_state.resolve()), 'initial': str(args.real_initial.resolve()),
                       'initial_sha256': hashlib.sha256(args.real_initial.read_bytes()).hexdigest(),
                       'sample_count': int(len(chosen)), 'hemisphere': 'right', 'selection': 'Uniform among retained right-hemisphere source indices; not random whole-tractogram validation.'}
    savemat(out / 'fixture.mat', data)
    def quote(path):
        return "'" + str(path).replace("'", "''") + "'"
    expr = f"addpath({quote(Path(__file__).parent)}); saf_matlab_reference({quote(args.upstream.resolve())}, {quote(out / 'fixture.mat')}, {quote(out / 'reference.mat')});"
    command = [args.octave, '--quiet', '--no-gui', '--eval', expr]
    if args.docker_image:
        import os
        command = ['docker', 'run', '--rm', '--cpus=2', '--user', f'{os.getuid()}:{os.getgid()}',
                   '-e', 'OPENBLAS_NUM_THREADS=1', '-v', f'{ROOT}:{ROOT}:ro', '-v', f'{out}:{out}',
                   args.docker_image] + command
    completed = subprocess.run(command, text=True, capture_output=True, timeout=300)
    (out / 'octave.log').write_text(completed.stdout + completed.stderr, encoding='utf-8')
    completed.check_returncode()
    checks = compare(data, loadmat(out / 'reference.mat'), analytic_fixture=real_source is None)
    source_hashes = {str(p.relative_to(args.upstream)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((args.upstream / 'Filters/streamlineXmesh').glob('*.m'))}
    result = {'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
              'scope': 'Synthetic numeric/index fixtures; unmodified MATLAB-source kernels executed in GNU Octave, not MATLAB itself.',
              'source_sha256': source_hashes, 'command': command}
    result['real_source'] = real_source
    if real_source:
        result['scope'] = 'Unmodified author .m kernels in GNU Octave: synthetic general-position intersection fixtures plus the recorded right-hemisphere real-tractogram crop sample. Endpoint-vertex parity is excluded for the documented upstream defect.'
    result['documented_deviations'] = {
        'endpoint_vertex_lookup': 'Original MATLAB mixes interleaved endpoint coordinates with column-major faces. Corrected Python is tested against analytic geometry, not that faulty lookup.',
        'complete_boundary_intersections': 'Original trintersect_complete resets edge/vertex flags to false. Python retains them and de-duplicates shared streamline points; separate gold-case unit tests cover this deviation.',
        'clustering': 'scikit-learn and MATLAB k-means do not guarantee identical clusters. This fixture does not test clustering or a full MRtrix pipeline.'}
    (out / 'parity.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
