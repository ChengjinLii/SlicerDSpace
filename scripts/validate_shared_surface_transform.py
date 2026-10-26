#!/usr/bin/env python3
"""Separate stochastic registration from native-preparation reuse.

Retains the failed independent-registration pair. A controlled case uses the
same reference transform, but newly resamples the shared native scalars and
runs the real normalization and surface predictors. No production receipt is
fabricated or source result overwritten.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import nibabel as nib
import numpy as np
import nrrd
import SimpleITK as sitk
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from anatomy.surface import SurfaceConfig, run_surface
from shared.pipeline import build_cli_environment
from shared.external_process import merged_startup_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--slicer-home', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--subject', default='100307')
    args = parser.parse_args()
    root, stem = args.evidence_root.resolve(), args.subject
    controlled = root / 'controlled_reference_transform'
    controlled.mkdir(exist_ok=False)
    registered = controlled / 'registered'
    registered.mkdir()
    author = root / 'author/upstream' / stem / '.cache'
    native = root / 'subject/cache/native_dti/wls'
    atlas = args.assets.resolve() / 'surface/template/100HCP-population-mean-T2-1mm.nii.gz'
    reference_transform = author / 'dti' / stem / f'{stem}-b0ToAtlasT2.tfm'
    shutil.copy2(reference_transform, registered / reference_transform.name)
    resample = next(args.slicer_home.rglob('ResampleScalarVectorDWIVolume'))
    brainsfit = next(args.slicer_home.rglob('BRAINSFit'))
    def execute(binary, options):
        with (controlled / 'cli.log').open('ab') as stream:
            subprocess.run([str(args.slicer_home / 'Slicer'), '--launch', str(binary), *map(str, options)],
                check=True, stdout=stream, stderr=subprocess.STDOUT,
                env=merged_startup_environment(build_cli_environment(str(binary))))
    channels = dict(FractionalAnisotropy='FA', MinEigenvalue='MinEigenvalue', MidEigenvalue='MidEigenvalue',
                    MaxEigenvalue='MaxEigenvalue', MeanDiffusivity='MeanDiffusivity', Trace='Trace')
    native_checks = {}
    for channel, short in channels.items():
        reference = author / 'dti' / stem / f'{stem}-dti-{channel}.nhdr'
        source = native / f'DTI_{short}.nrrd'
        a, ah = nrrd.read(str(reference))
        b, bh = nrrd.read(str(source))
        native_checks[channel] = dict(exact_values=bool(np.array_equal(a, b, equal_nan=True)),
            geometry_exact=all(np.array_equal(ah[key], bh[key], equal_nan=True) for key in ('space origin', 'space directions')))
        execute(resample, ['-i', 'linear', source, '--Reference', atlas, '--transformationFile',
                          reference_transform, registered / f'{stem}-dti-{channel}-Reg.nii.gz'])
    execute(resample, ['-i', 'nn', root / 'subject/input/nodif_brain_mask.nii.gz', '--Reference', atlas,
                      '--transformationFile', reference_transform, registered / f'{stem}-mask-Reg.nii.gz'])
    # An additional unchanged author registration establishes its repeatability
    # boundary; this transform is diagnostic only and never used by predictors.
    repeated = controlled / 'author_repeat_transform.tfm'
    execute(brainsfit, ['--fixedVolume', atlas, '--movingVolume', author / 'dti' / stem / f'{stem}-b0.nhdr',
                       '--linearTransform', repeated, '--useRigid', '--useAffine'])
    first, second = sitk.ReadTransform(str(reference_transform)), sitk.ReadTransform(str(repeated))
    parameters = dict(exact=first.GetParameters() == second.GetParameters(),
        max_abs_difference=float(np.max(np.abs(np.asarray(first.GetParameters()) - np.asarray(second.GetParameters())))),
        fixed_parameters_exact=first.GetFixedParameters() == second.GetFixedParameters())
    started = time.perf_counter()
    result = run_surface(SurfaceConfig(stem, registered, controlled / 'surface', execute=True,
        model_assets_dir=args.assets.resolve(), device='auto'), log=lambda value: print(value, flush=True))
    elapsed = time.perf_counter() - started
    maps = {}
    for suffix in ('FA', 'MinEigenvalue', 'MidEigenvalue', 'MaxEigenvalue', 'MD', 'brainmask_resampled'):
        a = nib.load(author / 'volumes' / stem / f'{stem}-{suffix}.nii.gz')
        b = nib.load(controlled / 'surface/preprocessed' / stem / f'{stem}-{suffix}.nii.gz')
        aa, bb = np.asanyarray(a.dataobj), np.asanyarray(b.dataobj)
        maps[suffix] = dict(exact_values=bool(np.array_equal(aa, bb)), affine_exact=bool(np.array_equal(a.affine, b.affine)),
            max_abs_difference=float(np.max(np.abs(aa.astype(float) - bb))))
    surfaces = {}
    for hemi in ('lh', 'rh'):
        for kind in ('white', 'pial'):
            a = trimesh.load(root / 'author/pred_results_SlicerDDSurfer/native' / stem / f'{hemi}.{kind}.obj', process=False)
            b = trimesh.load(controlled / 'surface/pred_results_SlicerDDSurfer/native' / stem / f'{hemi}.{kind}.obj', process=False)
            surfaces[f'{hemi}.{kind}'] = dict(topology_exact=bool(np.array_equal(a.faces, b.faces)),
                vertices_exact=bool(np.array_equal(a.vertices, b.vertices)),
                max_vertex_distance_mm=float(np.max(np.linalg.norm(a.vertices - b.vertices, axis=1))))
    qc = json.loads(result.qc_path.read_text())
    record = dict(kind='shared_surface_fixed_transform_control', subject=stem, native_checks=native_checks,
        normalized_maps=maps, surfaces=surfaces, automatic_qc_passed=qc['automatic_qc_passed'],
        author_registration_repeat=parameters, controlled_surface_seconds=elapsed,
        reference_transform_sha256=hashlib.sha256(reference_transform.read_bytes()).hexdigest(),
        scope='Identical transform, newly resampled shared native features; not a timing comparison or independent registration equivalence',
        source_sha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in
            (Path(__file__), ROOT / 'shared/pipeline.py', ROOT / 'anatomy/surface/pipeline.py')})
    record['passed'] = (all(row['exact_values'] and row['geometry_exact'] for row in native_checks.values())
        and all(row['exact_values'] and row['affine_exact'] for row in maps.values())
        and all(row['topology_exact'] and row['vertices_exact'] for row in surfaces.values()) and qc['automatic_qc_passed'])
    (controlled / 'summary.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
