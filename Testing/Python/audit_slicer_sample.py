"""Independently audit the upstream DWIVolume import and its recorded DTI run."""

import argparse
import hashlib
import json
from pathlib import Path

import nibabel as nib
import nrrd
import numpy as np


SOURCE_HASHES = {
    'dwi.nhdr': '7666d83bc205382e418444ea60ab7df6dba6a0bd684933df8809da6b476b0fed',
    'dwi.raw.gz': 'cf03fd53583dc05120d3314d0a82bdf5946799b1f72f2a7f08963f3fd24ca692',
}


def audit(source, subject):
    hashes = {}
    for name, expected in SOURCE_HASHES.items():
        digest = hashlib.sha256()
        with (source / name).open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        hashes[name] = digest.hexdigest()
        if hashes[name] != expected:
            raise ValueError('Upstream sample hash mismatch: ' + name)
    data, header = nrrd.read(str(source / 'dwi.nhdr'))
    if header['space'] != 'right-anterior-superior' or header['kinds'][0] != 'list':
        raise ValueError('Unexpected upstream sample geometry')
    original = np.moveaxis(data, 0, 3)
    affine = np.eye(4)
    affine[:3, :3] = np.asarray(header['space directions'])[1:].T
    affine[:3, 3] = header['space origin']
    image = nib.load(subject / 'input/data.nii.gz')
    orientation = nib.orientations.ornt_transform(nib.io_orientation(affine), nib.io_orientation(image.affine))
    oriented = nib.orientations.apply_orientation(original, orientation)
    expected_affine = affine @ nib.orientations.inv_ornt_aff(orientation, original.shape[:3])
    np.testing.assert_array_equal(oriented, np.asarray(image.dataobj))
    np.testing.assert_allclose(image.affine, expected_affine, atol=1e-5, rtol=0)
    gradients = np.array([[float(v) for v in header[f'DWMRI_gradient_{i:04d}'].split()]
                          for i in range(data.shape[0])]).T
    norms = np.linalg.norm(gradients, axis=0)
    expected_bvals = np.rint(norms ** 2 * float(header['DWMRI_b-value']))
    gradients /= np.where(norms, norms, 1)
    world = np.asarray(header['measurement frame']).T @ gradients
    rotation = image.affine[:3, :3] / np.linalg.norm(image.affine[:3, :3], axis=0)
    expected_bvecs = rotation.T @ world
    if np.linalg.det(image.affine[:3, :3]) > 0:
        expected_bvecs[0] *= -1
    np.testing.assert_allclose(np.loadtxt(subject / 'input/bvals'), expected_bvals, atol=1, rtol=0)
    np.testing.assert_allclose(np.loadtxt(subject / 'input/bvecs'), expected_bvecs, atol=1e-5, rtol=0)
    outputs = subject / 'outputs/02_microstructure/dti'
    qc = json.loads((outputs / 'dti_qc.json').read_text())
    if qc.get('automatic_qc_passed') is not True or not all(qc.get('checks', {}).values()):
        raise ValueError('Recorded DTI output QC failed')
    summary, maps = {}, {}
    for metric in ('FA', 'MD', 'AD', 'RD', 'L1', 'L2', 'L3', 'Trace'):
        volume = nib.load(outputs / f'slicer-sample_dti_{metric}.nii.gz')
        values = np.asarray(volume.dataobj)
        if not np.isfinite(values).all() or values.shape != image.shape[:3]:
            raise ValueError('Invalid scalar output: ' + metric)
        np.testing.assert_allclose(volume.affine, image.affine, atol=1e-5, rtol=0)
        maps[metric] = values
        summary[metric] = dict(minimum=float(values.min()), maximum=float(values.max()))
    np.testing.assert_allclose(maps['AD'], maps['L1'], atol=1e-7, rtol=1e-5)
    np.testing.assert_allclose(maps['MD'], (maps['L1'] + maps['L2'] + maps['L3']) / 3, atol=1e-7, rtol=1e-5)
    np.testing.assert_allclose(maps['RD'], (maps['L2'] + maps['L3']) / 2, atol=1e-7, rtol=1e-5)
    if not ((maps['FA'] >= 0) & (maps['FA'] <= 1)).all():
        raise ValueError('FA is outside [0, 1]')
    manifest = json.loads((subject / 'outputs/00_run_metadata/official_sample_orchestration_manifest.json').read_text())
    return dict(status='passed', source='Slicer SampleData DWIVolume', source_sha256=hashes,
                shape=list(image.shape), voxel_values_exact_after_orientation=True,
                affine_max_abs_error=float(np.abs(image.affine - expected_affine).max()),
                gradient_count=data.shape[0], nonzero_shells=[1000], scalar_summary=summary,
                automatic_qc_passed=True, human_review='pending',
                independent_scalar_relations_checked=['AD=L1', 'MD=mean(L1,L2,L3)', 'RD=mean(L2,L3)', 'FA in [0,1]'],
                trace_clamp_boundary_voxels=qc.get('trace_clamp_boundary_voxels'),
                task_seconds={task['name']: task.get('runtime_seconds') for task in manifest['tasks']},
                scope='Import geometry/voxel/gradient consistency and DTI scalar integrity on one upstream sample; no redistribution of data')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--subject', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source, args.subject)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
