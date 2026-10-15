#!/usr/bin/env python3
"""Read-only, reproducible length and atlas-compatibility diagnostics."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def diagnose(path, atlas_path=None, sample_size=20000):
    started = time.monotonic()
    path = Path(path).resolve()
    if sample_size <= 0:
        raise ValueError('sample_size must be positive')
    if path.suffix.lower() in {'.trk', '.tck'}:
        data = nib.streamlines.load(str(path))
        tracks = data.streamlines
    else:
        from scripts.audit_bundle_products import tracks_from_file
        tracks = tracks_from_file(path)
    count = len(tracks)
    indices = np.unique(np.linspace(0, count - 1, min(count, sample_size), dtype=int)) if count else []
    sampled = [np.asarray(tracks[i], dtype=float) for i in indices]
    if not sampled or any(len(track) < 2 or not np.isfinite(track).all() for track in sampled):
        raise ValueError('Empty input or invalid sampled streamline geometry')
    lengths = np.asarray([np.linalg.norm(np.diff(track, axis=0), axis=1).sum() for track in sampled])
    endpoints = np.asarray([track[[0, -1]] for track in sampled])
    result = {
        'input': str(path), 'input_sha256': file_hash(path), 'input_streamlines': count,
        'sampled_streamlines': len(sampled), 'sampling': 'deterministic uniform source indices; no filtering or editing',
        'length_mm': dict(zip(('min', 'p25', 'median', 'p75', 'p95', 'max'),
                            map(float, np.percentile(lengths, (0, 25, 50, 75, 95, 100))))),
        'sample_fraction_below_40mm': float(np.mean(lengths < 40)),
        'sample_fraction_at_least_80mm': float(np.mean(lengths >= 80)),
        'endpoint_bounds_ras_mm': [endpoints.reshape(-1, 3).min(0).tolist(), endpoints.reshape(-1, 3).max(0).tolist()],
        'limitations': ['Sampled geometry is not a full input QC or anatomical accuracy assessment.',
                        '40 mm is the pinned WMA CLI preprocessing default, not a disease/accuracy threshold.',
                        'Length bias, atlas compatibility and registration must be reviewed independently.'],
    }
    if atlas_path is not None:
        atlas_path = Path(atlas_path).resolve()
        image = nib.load(str(atlas_path))
        labels = np.asarray(image.dataobj)
        if labels.ndim != 3 or not np.isfinite(labels).all() or not np.equal(labels, np.rint(labels)).all():
            raise ValueError('Atlas must be a finite 3D integer label image')
        unique, counts = np.unique(labels, return_counts=True)
        vox = np.rint(nib.affines.apply_affine(np.linalg.inv(image.affine), endpoints)).astype(int)
        in_fov = np.all((vox >= 0) & (vox < labels.shape), axis=-1)
        endpoint_labels = np.full(in_fov.shape, -1, dtype=int)
        endpoint_labels[in_fov] = labels[tuple(vox[in_fov].T)]
        result['atlas'] = {
            'path': str(atlas_path), 'sha256': file_hash(atlas_path), 'shape': list(labels.shape),
            'affine_ras_mm': image.affine.tolist(),
            'label_voxels': {str(int(label)): int(count) for label, count in zip(unique, counts)},
            'regional_white_matter_labels_left': [int(x) for x in unique if 3001 <= x <= 3035],
            'regional_white_matter_labels_right': [int(x) for x in unique if 4001 <= x <= 4035],
            'sample_endpoint_outside_fov_fraction': float(np.mean(~in_fov)),
            'sample_endpoint_label_counts': {str(label): count for label, count in Counter(endpoint_labels.ravel().tolist()).items()},
            'warning': ('No regional WM labels: FreeSurfer WMQL queries that require wm_* or regional bounding '
                        'boxes are not equivalent to DDParcel cortical endpoint candidates.'
                        if not any(3001 <= x <= 4035 for x in unique) else None),
        }
    result['diagnostic_seconds'] = time.monotonic() - started
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--atlas', type=Path)
    parser.add_argument('--sample-size', type=int, default=20000)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = diagnose(args.input, args.atlas, args.sample_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: result[key] for key in ('input_streamlines', 'sampled_streamlines', 'length_mm', 'sample_fraction_below_40mm')}, indent=2))


if __name__ == '__main__':
    main()
