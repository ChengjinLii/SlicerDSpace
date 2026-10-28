"""Record numerical and mesh integrity for real DDSurfer sync validation runs."""
import argparse
import json
from pathlib import Path
import sys

import nibabel as nib
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from anatomy.surface.backend_bridge import sha256, upstream_record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--subject', default='100307')
    args = parser.parse_args()
    report = dict(upstream_commit=upstream_record()['commit'], subject=args.subject, runs={},
                  human_anatomical_review='pending', cross_runtime_vertex_difference_mm={})
    meshes = {}
    for run in ('raw', 'slicer_registered', 'auto_mask'):
        directory = args.root / run
        manifest = json.loads((directory / 'surface_manifest.json').read_text())
        qc = json.loads((directory / 'surface_qc.json').read_text())
        assert manifest['status'] == 'completed' and qc['automatic_qc_passed'], run
        assert manifest['precision'] == 'fp32', run
        values = {}
        native = directory / 'pred_results_SlicerDSpace/native' / args.subject
        for hemi in ('lh', 'rh'):
            for kind in ('white', 'pial'):
                name = f'{hemi}.{kind}'
                path = native / f'{name}.obj'
                mesh = trimesh.load(str(path), process=False)
                assert np.isfinite(mesh.vertices).all() and mesh.is_watertight and mesh.euler_number == 2
                meshes[run, name] = mesh
                values[name] = dict(vertices=len(mesh.vertices), faces=len(mesh.faces),
                    bounds_RAS_mm=mesh.bounds.tolist(), sha256=sha256(path),
                    watertight=True, euler_number=2)
            assert np.array_equal(meshes[run, f'{hemi}.white'].faces, meshes[run, f'{hemi}.pial'].faces)
        scalar_qc = {}
        dti = directory / 'upstream' / args.subject / 'dti'
        if dti.is_dir():
            for path in sorted(dti.glob('*.nii.gz')):
                image = nib.load(str(path))
                data = np.asanyarray(image.dataobj)
                assert np.isfinite(data).all() and np.isfinite(image.affine).all(), path
                scalar_qc[path.name] = dict(shape=list(data.shape), finite=True,
                    min=float(data.min()), max=float(data.max()))
        report['runs'][run] = dict(precision=manifest['precision'], runtime=manifest['runtime'],
            geometry=values, scalar_maps=scalar_qc, upstream_result=manifest.get('upstream_pipeline', {}).get('result'))
    for hemi in ('lh', 'rh'):
        for kind in ('white', 'pial'):
            name = f'{hemi}.{kind}'
            reference, current = meshes['raw', name], meshes['slicer_registered', name]
            assert np.array_equal(reference.faces, current.faces)
            distances = np.linalg.norm(reference.vertices - current.vertices, axis=1)
            report['cross_runtime_vertex_difference_mm'][name] = dict(mean=float(distances.mean()),
                max=float(distances.max()), p95=float(np.percentile(distances, 95)))
    report['passed'] = True
    path = args.root / 'output_audit.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(path)


if __name__ == '__main__':
    main()
