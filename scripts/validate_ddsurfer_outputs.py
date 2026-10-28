#!/usr/bin/env python3
"""Audit real sync-validation outputs and compare upstream inference meshes."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import nibabel as nib
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from anatomy.surface.backend_bridge import sha256, upstream_record


def mesh_difference(first, second):
    a = trimesh.load(str(first), process=False)
    b = trimesh.load(str(second), process=False)
    if not np.array_equal(a.faces, b.faces) or a.vertices.shape != b.vertices.shape:
        raise ValueError('Surface correspondence differs')
    distances = np.linalg.norm(a.vertices - b.vertices, axis=1)
    return dict(max_mm=float(distances.max()), mean_mm=float(distances.mean()),
                identical_sha256=sha256(first) == sha256(second), faces_equal=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--subject', default='100307')
    args = parser.parse_args()
    work, subject = args.work_root.resolve(), args.subject
    result = dict(subject=subject, upstream_commit=upstream_record()['commit'],
                  inference_parity={}, slicer_source_parity={}, slicer_runtime_comparison={}, normalized_channels={}, native_dti={})
    for hemi in ('left', 'right'):
        for kind in ('wm', 'pial'):
            name = f'{subject}_predicted_{kind}_surface_{hemi}.obj'
            first = work / f'raw/upstream/{subject}/.cache/predictions/mni/{subject}' / name
            second = work / f'reference_predictions/mni/{subject}' / name
            result['inference_parity'][name] = mesh_difference(first, second)
            slicer = work / f'slicer_registered/pred_results_SlicerDSpace/mni/{subject}' / name
            if slicer.is_file():
                result['slicer_runtime_comparison'][name] = mesh_difference(first, slicer)
                reference = work / f'reference_slicer_predictions/mni/{subject}' / name
                if reference.is_file():
                    result['slicer_source_parity'][name] = mesh_difference(slicer, reference)
    for channel in ('FA', 'MidEigenvalue', 'MinEigenvalue', 'MaxEigenvalue', 'MD'):
        first = nib.load(str(work / f'raw/upstream/{subject}/.cache/volumes/{subject}/{subject}-{channel}.nii.gz'))
        second = nib.load(str(work / f'slicer_registered/preprocessed/{subject}/{subject}-{channel}.nii.gz'))
        a, b = first.get_fdata(), second.get_fdata()
        result['normalized_channels'][channel] = dict(shape=list(a.shape), finite=bool(np.isfinite(a).all()),
            max_absolute_difference=float(np.max(np.abs(a-b))), affine_equal=bool(np.array_equal(first.affine, second.affine)))
    for name in ('FA', 'MD', 'MinEigenvalue', 'MidEigenvalue', 'MaxEigenvalue', 'Trace'):
        path = work / f'raw/upstream/{subject}/dti/{subject}-{name}.nii.gz'
        image = nib.load(str(path))
        result['native_dti'][name] = dict(path=str(path), shape=list(image.shape),
            finite=bool(np.isfinite(image.get_fdata()).all()), sha256=sha256(path))
    result['raw_qc'] = json.loads((work / 'raw/surface_qc.json').read_text())
    result['slicer_runtime'] = json.loads((work / 'slicer_registered/surface_manifest.json').read_text()).get('runtime')
    scene_path = work / 'slicer_scene_smoke.json'
    result['slicer_scene'] = json.loads(scene_path.read_text()) if scene_path.is_file() else None
    orchestration_path = work / 'orchestrator_outputs/00_run_metadata/Test1_orchestration_manifest.json'
    result['batch'] = None
    if orchestration_path.is_file():
        batch = json.loads(orchestration_path.read_text())
        from shared.io_layout import anatomy_input_dir
        surface = json.loads((anatomy_input_dir(work / 'orchestrator_outputs', 'ddsurfer') / 'surface_manifest.json').read_text())
        result['batch'] = dict(status=batch['status'], subject_id=batch['subject_id'],
                               tasks=batch['tasks'], runtime=surface.get('runtime'))
    from shared.io_layout import anatomy_input_dir
    post = anatomy_input_dir(work / 'postprocess', 'ddsurfer/postprocess')
    if (post / 'qc.json').is_file():
        result['postprocess_qc'] = json.loads((post / 'qc.json').read_text())
        result['postprocess_metrics'] = {}
        if result['postprocess_qc'].get('status') == 'completed':
            for hemi in ('lh', 'rh'):
                count = result['raw_qc']['surfaces'][f'{hemi}.white']['vertices']
                entry = dict(metrics={}, annotations={})
                for metric in ('thickness', 'curv', 'sulc', 'area.pial'):
                    values = nib.freesurfer.read_morph_data(str(post / 'surf' / f'{hemi}.{metric}'))
                    entry['metrics'][metric] = dict(vertices=len(values), expected_vertices=count,
                        finite=bool(np.isfinite(values).all()), minimum=float(values.min()), maximum=float(values.max()))
                for atlas in ('aparc', 'aparc.a2009s'):
                    indices, _, names = nib.freesurfer.read_annot(str(post / 'label' / f'{hemi}.{atlas}.annot'))
                    entry['annotations'][atlas] = dict(vertices=len(indices), expected_vertices=count,
                        regions=len(names), valid_indices=bool(np.all((indices >= -1) & (indices < len(names)))))
                result['postprocess_metrics'][hemi] = entry
    result['passed'] = (len(result['inference_parity']) == 4 and all(v['max_mm'] == 0 for v in result['inference_parity'].values())
        and len(result['slicer_source_parity']) == 4 and all(v['max_mm'] == 0 for v in result['slicer_source_parity'].values())
        and all(v['finite'] and v['affine_equal'] and v['max_absolute_difference'] == 0
                for v in result['normalized_channels'].values())
        and all(v['finite'] for v in result['native_dti'].values()) and result['raw_qc']['automatic_qc_passed']
        and bool(result['slicer_scene'] and result['slicer_scene']['passed'])
        and bool(result['batch'] and result['batch']['status'] == 'completed')
        and result.get('postprocess_qc', {}).get('status') == 'completed'
        and len(result.get('postprocess_metrics', {})) == 2
        and all(v['finite'] and v['vertices'] == v['expected_vertices']
                for hemi in result.get('postprocess_metrics', {}).values() for v in hemi['metrics'].values())
        and all(v['valid_indices'] and v['vertices'] == v['expected_vertices']
                for hemi in result.get('postprocess_metrics', {}).values() for v in hemi['annotations'].values()))
    (work / 'output_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('raw_qc', 'postprocess_qc', 'native_dti')}, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
