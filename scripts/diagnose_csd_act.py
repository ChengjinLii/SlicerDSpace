#!/usr/bin/env python3
"""Controlled CSD/ACT diagnostics on saved FODs; never overwrite original data."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import nibabel as nib
import numpy as np
from scipy.ndimage import binary_erosion

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.prepare_scientific_review import fingerprint
from shared.external_process import external_python_environment
from shared.world_space import resample_nearest_to_grid
from tractography.act_prep import ACTPrepConfig, run_act_prep


def run_command(command, directory, name, env):
    import subprocess

    start = time.monotonic()
    print(f'Start {name}', flush=True)
    with (directory / f'{name}.log').open('w') as stream:
        done = subprocess.run(list(map(str, command)), stdout=stream, stderr=stream, env=env)
    record = dict(command=list(map(str, command)), returncode=done.returncode,
                  seconds=time.monotonic() - start, log=str(directory / f'{name}.log'))
    (directory / f'{name}_command.json').write_text(json.dumps(record, indent=2) + '\n')
    if done.returncode:
        raise RuntimeError(f'{name} failed: see {record["log"]}')
    print(f'Completed {name}: {record["seconds"]:.1f}s', flush=True)
    return record


def tissue_region_summary(five_tt, parcellation):
    result = {}
    for label in (7, 16, 28, 46, 60):
        values = five_tt[parcellation == label]
        result[str(label)] = dict(voxels=len(values),
            mean_5tt=values.mean(axis=0).tolist() if len(values) else None,
            dominant_tissue_counts=np.bincount(values.argmax(axis=1), minlength=5).tolist() if len(values) else [0] * 5)
    return result


def track_coverage(path, atlas, affine):
    """Read all tracks; anatomical label hits are proxies, not CST certification."""
    from collections import Counter
    from scipy.ndimage import map_coordinates

    inverse = np.linalg.inv(affine)
    counts = Counter()
    lengths = []
    selected = []
    source = nib.streamlines.load(str(path), lazy_load=True)
    for index, track in enumerate(source.streamlines):
        points = np.asarray(track, dtype=float)
        if len(points) < 2 or not np.isfinite(points).all():
            raise ValueError(f'Invalid generated streamline {index}')
        length = float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())
        lengths.append(length)
        voxels = nib.affines.apply_affine(inverse, points)
        labels = map_coordinates(atlas, voxels.T, order=0, mode='constant', cval=0, prefilter=False)
        unique = set(labels.tolist())
        counts['brainstem_crossing'] += int(16 in unique)
        for side, motor in (('left', {1022, 1024}), ('right', {2022, 2024})):
            candidate = 16 in unique and bool(unique & motor)
            counts[f'brainstem_motor_crossing_{side}'] += int(candidate)
            counts[f'brainstem_motor_opposite_endpoints_{side}'] += int(
                (labels[0] == 16 and labels[-1] in motor) or (labels[-1] == 16 and labels[0] in motor))
            if candidate:
                selected.append(dict(index=index, side=side, length_mm=length,
                                     endpoint_labels=list(map(int, labels[[0, -1]]))))
        for label in (16, 28, 60):
            counts[f'endpoint_label_{label}'] += int(labels[0] == label) + int(labels[-1] == label)
    count = len(lengths)
    return dict(streamlines=count, counts=dict(counts),
                length_mm=dict(zip(('min', 'median', 'p95', 'max'), map(float, np.percentile(lengths, [0, 50, 95, 100])))) if count else {},
                motor_crossing_candidates=selected,
                scope='Native point-label crossing and opposite-endpoint proxies; NOT anatomical ground truth or a WMA result.')


def render_diagnosis(report_path):
    """Native RAS projections for review, not a screenshot or anatomical approval."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    report_path = Path(report_path)
    report = json.loads(report_path.read_text())
    colors = ('#667f99', '#bc855b', '#4f907f', '#8e829b')
    fig, axes = plt.subplots(2, len(report['arms']), figsize=(14, 7), sharex=True, sharey=True)
    details = {}
    for column, ((name, arm), color) in enumerate(zip(report['arms'].items(), colors)):
        path = report_path.parent / f'{name}.tck'
        tracks = nib.streamlines.load(str(path)).streamlines
        selected = sorted({item['index'] for item in arm['motor_crossing_candidates']})
        preview = np.unique(np.linspace(0, len(tracks) - 1, min(500, len(tracks)), dtype=int)) if len(tracks) else []
        for row, indices in enumerate((preview, selected)):
            ax = axes[row, column]
            ax.add_collection(LineCollection([np.asarray(tracks[i])[:, (0, 2)] for i in indices],
                colors=color, linewidths=.3 if row == 0 else .6, alpha=.25 if row == 0 else .65))
            ax.set(xlim=(-85, 85), ylim=(-70, 100), aspect='equal', xlabel='R (mm)', ylabel='S (mm)')
            ax.spines[['right', 'top']].set_visible(False)
            counts = arm['counts']
            title = f'{name.replace("_", " ")}\n{len(tracks):,} accepted tracks' if row == 0 else (
                'Motor-crossing proxies\n'
                f'L {counts.get("brainstem_motor_crossing_left", 0)} / R {counts.get("brainstem_motor_crossing_right", 0)}')
            ax.set_title(title, fontsize=10)
        details[name] = dict(preview_count=len(preview), displayed_motor_candidates=len(selected), source=fingerprint(path))
    fig.suptitle(f'Same saved CSD FOD | {report["attempted_seeds_per_arm"]:,} attempted brainstem seeds per arm\n'
                 'Coronal projections, NOT slices or anatomically certified CST', fontsize=12, y=.99)
    fig.tight_layout(rect=(0, 0, 1, .93))
    for suffix in ('png', 'svg'):
        fig.savefig(report_path.parent / f'tracking_comparison.{suffix}', dpi=180, facecolor='white')
    plt.close(fig)
    (report_path.parent / 'projection_sources.json').write_text(json.dumps(details, indent=2) + '\n')


def diagnose(args):
    args.output.mkdir(parents=True, exist_ok=False)
    csd = json.loads(args.manifest.read_text())
    act_manifest = Path(csd['dependencies']['five_tt']['path']).parent / 'act_prep_manifest.json'
    act = json.loads(act_manifest.read_text())
    inputs = act['inputs']
    atlas_path = Path(inputs['parcellation']['path'])
    old_path = Path(csd['dependencies']['five_tt']['path'])
    fod_path = Path(csd['outputs']['wm_fod_norm'])
    source_paths = [args.manifest, act_manifest, old_path, fod_path, atlas_path,
                    *[Path(csd['dependencies'][key]['path']) for key in ('bval', 'bvec', 'mask')]]
    before = {str(path.resolve()): fingerprint(path) for path in source_paths}
    env = external_python_environment(extra_env={'MRTRIX_RNG_SEED': str(args.seed)}, path_prepend=[args.bin])
    report = dict(kind='controlled_csd_act_diagnosis', timestamp=datetime.now(timezone.utc).isoformat(),
                  mode=args.mode, source_manifest=str(args.manifest.resolve()), source_files=before,
                  commands=[], anatomical_review='pending')
    if args.mode == 'gradients':
        dwi = Path(csd['commands'][0][2])
        command = [args.bin / 'dwigradcheck', dwi, '-mask', csd['dependencies']['mask']['path'],
                   '-number', args.gradient_tracks, '-nthreads', args.threads,
                   '-export_grad_mrtrix', args.output / 'screened_gradients.b',
                   '-scratch', args.output, '-force']
        report['commands'].append(run_command(command, args.output, 'dwigradcheck', env))
        original = args.output / 'original_gradients.b'
        report['commands'].append(run_command([args.bin / 'mrinfo', dwi, '-export_grad_mrtrix', original],
                                              args.output, 'gradient_export', env))
        one, two = np.loadtxt(original), np.loadtxt(args.output / 'screened_gradients.b')
        observed = one[:, 3] > 50
        dots = np.abs(np.sum(one[observed, :3] * two[observed, :3], axis=1))
        report.update(gradient_tracks_per_hypothesis=args.gradient_tracks, hypotheses=48,
                      antipodal_direction_max_error=float(np.max(np.abs(1 - dots))),
                      bvalue_max_error=float(np.max(np.abs(one[:, 3] - two[:, 3]))),
                      originals_modified=False,
                      limitation='Screening heuristic, not ground truth. No gradient changes are applied.')
    else:
        image = nib.load(old_path)
        old = np.asarray(image.dataobj)
        parc_img = nib.load(atlas_path)
        atlas = resample_nearest_to_grid(np.asarray(parc_img.dataobj), parc_img.affine, image.shape[:3], image.affine).astype(np.int32)
        corrected = run_act_prep(ACTPrepConfig(subject_id=csd['subject_id'],
            segmentation_path=Path(inputs['segmentation']['path']),
            probability_paths={key: Path(value['path']) for key, value in inputs['probabilities'].items()},
            parcellation_path=atlas_path, output_dir=args.output / 'corrected_act',
            mrtrix_bin_dir=args.bin, anatomy_source=act.get('anatomy_source', {}), execute=True), log=print)
        fixed = np.asarray(nib.load(corrected.five_tt_path).dataobj)
        # A predeclared ablation changes only the mistaken ventral-DC tissue identity.
        vdc_only = old.copy()
        vdc = np.isin(atlas, (28, 60))
        vdc_only[vdc] = fixed[vdc]
        vdc_path = args.output / 'ventral_dc_only_5tt.nii.gz'
        nib.save(nib.Nifti1Image(vdc_only, image.affine), vdc_path)
        seed = binary_erosion(atlas == 16, iterations=1)
        if not seed.any():
            raise ValueError('No interior brainstem seed voxels')
        seed_path = args.output / 'brainstem_seed.nii.gz'
        nib.save(nib.Nifti1Image(seed.astype(np.uint8), image.affine), seed_path)
        report.update(seed=args.seed, attempted_seeds_per_arm=args.attempts,
                      seed_voxels=int(seed.sum()), seeding='Uniform random within one-voxel-eroded DDParcel brainstem; same RNG seed',
                      five_tt_regions={'original': tissue_region_summary(old, atlas), 'corrected': tissue_region_summary(fixed, atlas)}, arms={})
        for name, five_tt in (('original_act', old_path), ('ventral_dc_only', vdc_path),
                              ('corrected_act', corrected.five_tt_path), ('without_act', None)):
            output = args.output / f'{name}.tck'
            command = [args.bin / 'tckgen', fod_path, output, '-algorithm', 'iFOD2',
                       '-seed_image', seed_path, '-seeds', args.attempts, '-select', 0,
                       '-minlength', 10, '-maxlength', 250, '-cutoff', 0.05, '-nthreads', 0, '-force']
            if five_tt is None:
                command += ['-mask', csd['dependencies']['mask']['path']]
            else:
                command += ['-act', five_tt, '-backtrack', '-crop_at_gmwmi']
            report['commands'].append(run_command(command, args.output, name, env))
            report['arms'][name] = track_coverage(output, atlas, image.affine)
            (args.output / 'diagnosis_progress.json').write_text(json.dumps(report, indent=2) + '\n')
        report['limitation'] = ('Targeted brainstem experiment with fixed attempted seed count, NOT whole-brain density or WMA acceptance. '
                               'Without-ACT arm necessarily changes termination rules. No original FOD, DWI, atlas, tractogram or QC is replaced.')
    report['inputs_unchanged'] = all(fingerprint(Path(path))['sha256'] == record['sha256'] for path, record in before.items())
    (args.output / 'diagnosis.json').write_text(json.dumps(report, indent=2) + '\n')
    if args.mode == 'tracking':
        render_diagnosis(args.output / 'diagnosis.json')
    print(json.dumps({key: value for key, value in report.items() if key not in ('source_files', 'arms', 'five_tt_regions')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--bin', required=True, type=Path)
    parser.add_argument('--mode', choices=('tracking', 'gradients'), default='tracking')
    parser.add_argument('--attempts', type=int, default=10000)
    parser.add_argument('--gradient-tracks', type=int, default=2000)
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--seed', type=int, default=20261015)
    arguments = parser.parse_args()
    if min(arguments.attempts, arguments.gradient_tracks, arguments.threads) <= 0 or arguments.seed < 0:
        parser.error('Counts and threads must be positive; seed must be nonnegative')
    diagnose(arguments)
