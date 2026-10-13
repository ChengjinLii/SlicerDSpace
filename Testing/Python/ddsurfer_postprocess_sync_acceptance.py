"""Real FreeSurfer parity checks on existing results; never change source data."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'anatomy/surface/ddsurfer_backend'
sys.path.insert(0, str(BACKEND))

from postprocessing.labels import read_regions, write_labels
from postprocessing.overlays import FIELDS, copy_frames, write_stack
from postprocessing.stats import read_measurements, write_stats
from utils.files import sha256_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Existing complete FreeSurfer-style subject directory')
    parser.add_argument('--freesurfer-home', type=Path, required=True)
    parser.add_argument('--previous-backend', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True, help='New, unused output directory')
    args = parser.parse_args()
    source, home, output = args.source.resolve(), args.freesurfer_home.resolve(), args.report.resolve()
    if output == source or output in source.parents or source in output.parents:
        raise ValueError('Use an independent evidence directory, not the source tree')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'subjects').mkdir()
    subject = source.name
    (output / 'subjects' / subject).symlink_to(source, target_is_directory=True)
    (output / 'subjects/fsaverage').symlink_to(home / 'subjects/fsaverage', target_is_directory=True)
    env = dict(os.environ, SUBJECTS_DIR=str(output / 'subjects'), FREESURFER_HOME=str(home),
               FS_LICENSE=os.environ.get('FS_LICENSE', str(home / 'license.txt')),
               OMP_NUM_THREADS='2', ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS='2')
    hemi = 'lh'
    atlases = ('aparc', 'aparc.a2009s')
    paths = [source / 'surf' / f'{hemi}.{name}' for name in
             ('white', 'sphere.reg', 'area', 'area.pial', 'thickness', 'curv', 'sulc', 'white.K')]
    paths += [source / 'label' / f'{hemi}.{name}' for name in ('cortex.label', 'aparc.annot', 'aparc.a2009s.annot')]
    paths += [home / 'subjects/fsaverage/surf/lh.sphere.reg']
    before = {str(path): sha256_file(path) for path in paths}
    checks, commands = [], []

    def run(name, arguments):
        command = [str(home / 'bin' / arguments[0]), *map(str, arguments[1:])]
        start = perf_counter()
        with (output / f'{name}.log').open('w') as log:
            subprocess.run(command, env=env, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        commands.append(dict(name=name, command=command, seconds=perf_counter() - start))

    def require(name, passed, **details):
        checks.append(dict(name=name, passed=bool(passed), **details))
        if not passed:
            raise AssertionError(name)

    spec = importlib.util.spec_from_file_location('previous_surface_stats', args.previous_backend / 'postprocessing/stats.py')
    old_stats = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old_stats)
    old_subject = output / 'previous_stats' / subject
    old_subject.mkdir(parents=True)
    for folder in ('surf', 'label'):
        (old_subject / folder).symlink_to(source / folder, target_is_directory=True)
    measurements = read_measurements(source, hemi)
    for atlas in atlases:
        old_labels, new_labels = output / f'command_labels_{atlas}', output / f'python_labels_{atlas}'
        old_labels.mkdir()
        run(f'labels_{atlas}', ['mri_annotation2label', '--subject', subject, '--hemi', hemi,
                              '--annotation', atlas, '--outdir', old_labels])
        count, regions = read_regions(source / 'label' / f'{hemi}.{atlas}.annot')
        outputs = [new_labels / f'{hemi}.{name}.label' for name, _ in regions]
        write_labels(source / 'surf' / f'{hemi}.white', subject, count, regions, outputs)
        old_files, new_files = set(path.name for path in old_labels.glob('*.label')), set(path.name for path in outputs)
        require(f'{atlas}.label_file_set', old_files == new_files, count=len(new_files))
        require(f'{atlas}.label_bytes', all((old_labels / name).read_bytes() == (new_labels / name).read_bytes()
                                         for name in old_files), count=len(new_files))
        old_stats.write_stats(old_subject, hemi, atlas)
        old_path = old_subject / 'stats' / f'{hemi}.{atlas}.stats'
        new_path = output / f'{atlas}.stats'
        write_stats(source, hemi, atlas, output=new_path, measurements=measurements)
        require(f'{atlas}.stats_bytes', old_path.read_bytes() == new_path.read_bytes())

    # The new shared transfer retains the same FreeSurfer registration/defaults.
    write_stack(source / 'surf', hemi, output / 'source.mgh', len(measurements[1]['thickness']), fields=measurements[1])
    run('shared_mapping', ['mri_surf2surf', '--srcsubject', subject, '--trgsubject', 'fsaverage', '--hemi', hemi,
                          '--sval', output / 'source.mgh', '--tval', output / 'mapped.mgh', '--split'])
    new_frames = [output / f'new_{field}.mgh' for field in FIELDS]
    copy_frames(output / 'mapped.mgh', new_frames)
    for field, actual in zip(FIELDS, new_frames):
        reference = output / f'old_{field}.mgh'
        run('single_mapping_' + field, ['mri_surf2surf', '--srcsubject', subject, '--trgsubject', 'fsaverage',
                                       '--hemi', hemi, '--sval', source / 'surf' / f'{hemi}.{field}', '--tval', reference])
        left, right = nib.load(actual), nib.load(reference)
        require(field + '.frame_bytes', actual.read_bytes() == reference.read_bytes(), vertices=int(left.shape[0]),
                max_abs_difference=float(np.max(np.abs(left.get_fdata() - right.get_fdata()))),
                affine_equal=bool(np.array_equal(left.affine, right.affine)))
    require('source_files_unchanged', before == {str(path): sha256_file(path) for path in paths})
    report = dict(status='PASS', scope='Existing subject, left hemisphere, two atlases and four fsaverage overlays; not full inference/postprocess validation',
                  subject=subject, source=str(source), checks=checks, commands=commands, input_sha256=before,
                  upstream_commit=json.loads((BACKEND / 'UPSTREAM.json').read_text())['commit'])
    (output / 'parity.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status='PASS', checks=len(checks), output=str(output)), indent=2))


if __name__ == '__main__':
    main()
