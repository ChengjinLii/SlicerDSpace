#!/usr/bin/env python3
"""Build read-only anatomical review plates; never grant scientific acceptance."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def fingerprint(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return dict(path=str(path), sha256=digest.hexdigest(), size=path.stat().st_size)


def prepare(args):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.backends.backend_pdf import PdfPages
    import nibabel as nib
    import numpy as np
    from scripts.audit_bundle_products import tracks_from_file

    args.output_dir.mkdir(parents=True, exist_ok=False)
    sources, plates = {}, []

    def capture(path):
        record = fingerprint(path)
        sources[record['path']] = record
        return record

    capture(args.reference)
    image = nib.as_closest_canonical(nib.load(args.reference))
    if len(image.shape) != 3 or not np.allclose(image.affine[:3, :3], np.diag(np.diag(image.affine[:3, :3])), atol=1e-4):
        raise ValueError('Review reference must be 3D and axis-aligned RAS; no implicit resampling is allowed.')
    reference = np.asarray(image.dataobj)
    brain = np.isfinite(reference) & (reference > 0)
    if args.brain_mask:
        capture(args.brain_mask)
        mask_image = nib.as_closest_canonical(nib.load(args.brain_mask))
        if mask_image.shape != image.shape or not np.allclose(mask_image.affine, image.affine, atol=1e-4):
            raise ValueError('Brain mask and reference do not share their native grid')
        mask = np.asarray(mask_image.dataobj)
        if not np.isin(mask, [0, 1]).all():
            raise ValueError('Review brain mask must be binary')
        brain = mask > 0
    positive = reference[np.isfinite(reference) & (reference > 0)]
    if not positive.size:
        raise ValueError('Review reference is empty')
    vmax = float(np.percentile(positive, 99))
    bounds = np.array(nib.affines.apply_affine(image.affine, [[0, 0, 0], np.array(image.shape) - 1]))
    occupied = np.argwhere(brain)
    if not len(occupied):
        raise ValueError('Review brain mask is empty')
    slices = ((occupied.min(axis=0) + occupied.max(axis=0)) // 2).tolist()
    midpoint = nib.affines.apply_affine(image.affine, slices)
    axes_spec = [(0, (1, 2), 'Sagittal', 'A (mm)', 'S (mm)'),
                 (1, (0, 2), 'Coronal', 'R (mm)', 'S (mm)'),
                 (2, (0, 1), 'Axial', 'R (mm)', 'A (mm)')]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.titleweight': 'medium'})

    with PdfPages(args.output_dir / 'review_plates.pdf') as pdf:
        def save(fig, name, detail):
            file = f'{len(plates) + 1:03d}_{name}.png'
            fig.savefig(args.output_dir / file, dpi=180, facecolor='white', bbox_inches='tight')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            plates.append(dict(image=file, **detail))

        def volume_plate(name, path, categorical=False):
            capture(path)
            scalar_image = nib.as_closest_canonical(nib.load(path))
            if scalar_image.shape != image.shape or not np.allclose(scalar_image.affine, image.affine, atol=1e-4):
                raise ValueError(f'Unmatched review grid (no silent resampling): {path}')
            scalar = np.asarray(scalar_image.dataobj)
            domain = brain & np.isfinite(scalar)
            values = scalar[domain]
            if not values.size:
                raise ValueError(f'No finite scalar values: {path}')
            lower, upper = (float(np.min(values)), float(np.max(values))) if categorical else tuple(map(float, np.percentile(values, [1, 99])))
            if lower == upper:
                upper = lower + 1
            fig, axes = plt.subplots(1, 3, figsize=(10, 3.8))
            for ax, (axis, dims, title, xlabel, ylabel) in zip(axes, axes_spec):
                extent = [bounds[0, dims[0]], bounds[1, dims[0]], bounds[0, dims[1]], bounds[1, dims[1]]]
                base = np.take(reference, slices[axis], axis=axis).T
                cut = np.take(scalar, slices[axis], axis=axis).T
                ax.imshow(base, origin='lower', extent=extent, cmap='gray', vmin=0, vmax=vmax, interpolation='nearest')
                visible = np.take(brain, slices[axis], axis=axis).T
                if categorical:
                    visible &= cut != 0
                overlay = np.ma.array(cut, mask=~visible | ~np.isfinite(cut))
                display = ax.imshow(overlay, origin='lower', extent=extent, cmap='tab20' if categorical else 'viridis',
                                    vmin=lower, vmax=upper, alpha=.6 if categorical else 1, interpolation='nearest')
                ax.set(title=f'{title}: voxel {slices[axis]}', xlabel=xlabel, ylabel=ylabel)
            fig.suptitle(name + ' | pending anatomical review', color='#243d4b')
            if not categorical:
                fig.colorbar(display, ax=axes, fraction=.02, pad=.03)
            save(fig, 'volume', dict(name=name, source=str(Path(path).resolve()), kind='label_overlay' if categorical else 'scalar',
                                    display_range=[lower, upper], display_only_percentile_clipping=not categorical,
                                    interpolation='nearest', underlay='reference', underlay_opacity=1,
                                    overlay_opacity=.6 if categorical else 1))

        for specification in args.volume:
            name, path = specification.split('=', 1)
            volume_plate(name, Path(path))
        for specification in args.label:
            name, path = specification.split('=', 1)
            volume_plate(name, Path(path), categorical=True)
        if args.surface_qc:
            import vtk
            from vtk.util.numpy_support import vtk_to_numpy
            capture(args.surface_qc)
            qc = json.loads(args.surface_qc.read_text())
            fig, axes = plt.subplots(1, 3, figsize=(10, 3.8))
            for ax, (axis, dims, title, xlabel, ylabel) in zip(axes, axes_spec):
                extent = [bounds[0, dims[0]], bounds[1, dims[0]], bounds[0, dims[1]], bounds[1, dims[1]]]
                ax.imshow(np.take(reference, slices[axis], axis=axis).T, origin='lower', extent=extent,
                          cmap='gray', vmin=0, vmax=vmax, interpolation='nearest')
                ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
            for name, item in qc['surfaces'].items():
                if item['coordinate_space'] != 'native_scanner_RAS_mm':
                    raise ValueError('Only explicitly native RAS master surfaces may be overlaid')
                path = Path(item['indexed_master'])
                capture(path)
                reader = vtk.vtkOBJReader()
                reader.SetFileName(str(path))
                reader.Update()
                if not reader.GetOutput().GetNumberOfPolys():
                    raise ValueError(f'Empty surface: {path}')
                for ax, (axis, dims, *_rest) in zip(axes, axes_spec):
                    plane = vtk.vtkPlane()
                    plane.SetOrigin(*midpoint)
                    normal = [0, 0, 0]
                    normal[axis] = 1
                    plane.SetNormal(*normal)
                    cutter = vtk.vtkCutter()
                    cutter.SetInputConnection(reader.GetOutputPort())
                    cutter.SetCutFunction(plane)
                    cutter.Update()
                    cut = cutter.GetOutput()
                    if cut.GetNumberOfPoints():
                        points = vtk_to_numpy(cut.GetPoints().GetData())
                        cells = cut.GetLines()
                        cells.InitTraversal()
                        ids, segments = vtk.vtkIdList(), []
                        while cells.GetNextCell(ids):
                            segments.append(points[[ids.GetId(i) for i in range(ids.GetNumberOfIds())]][:, dims])
                        ax.add_collection(LineCollection(segments, colors='#51b6df' if name.endswith('white') else '#eeaf6d', linewidths=.6))
            fig.suptitle('Native surface intersections | blue: white, orange: pial | review pending')
            save(fig, 'surfaces', dict(name='Native cortical surface boundaries', kind='world_RAS_plane_intersections',
                                      source=str(args.surface_qc.resolve()), underlay='reference slice', expert_approved=False))
        for manifest_path in args.bundle_manifest:
            capture(manifest_path)
            manifest = json.loads(manifest_path.read_text())
            summary = manifest['outputs']['summary']
            files = summary.get('bundle_files') or summary.get('anatomical_tract_files') or []
            for value in files:
                path = Path(value)
                if not any(tract in path.name.lower() for tract in ('cst', 'af.', 'af_', 'cc4')):
                    continue
                capture(path)
                tracks = tracks_from_file(path)
                chosen = np.linspace(0, len(tracks) - 1, min(len(tracks), args.max_tracks), dtype=int) if len(tracks) else []
                fig, axes = plt.subplots(1, 3, figsize=(10, 3.8))
                for ax, (axis, dims, title, xlabel, ylabel) in zip(axes, axes_spec):
                    extent = [bounds[0, dims[0]], bounds[1, dims[0]], bounds[0, dims[1]], bounds[1, dims[1]]]
                    projection = np.nanmax(reference, axis=axis).T
                    ax.imshow(projection, origin='lower', extent=extent, cmap='gray', vmin=0, vmax=vmax, alpha=.45, interpolation='nearest')
                    ax.add_collection(LineCollection([np.asarray(tracks[i])[:, dims] for i in chosen], colors='#246b87', linewidths=.45, alpha=.55))
                    ax.set(xlim=extent[:2], ylim=extent[2:], title=f'{title} projection', xlabel=xlabel, ylabel=ylabel)
                    ax.set_aspect('equal')
                fig.suptitle(f'{path.name} | {len(chosen)}/{len(tracks)} tracks | review pending')
                save(fig, 'bundle', dict(name=path.name, source=str(path.resolve()), manifest=str(manifest_path.resolve()),
                                        kind='orthogonal_projection_NOT_slices', total_tracks=len(tracks), preview_tracks=len(chosen),
                                        selection='deterministic evenly spaced file indices; preview only',
                                        underlay='reference maximum intensity projection', source_coordinate_system='RAS'))
        if args.mkcurve_record:
            capture(args.mkcurve_record)
            record = json.loads(args.mkcurve_record.read_text())
            for key in ('original_mk', 'corrected_mk', 'original_fa', 'corrected_fa', 'abnormal_mask', 'corrected_valid_mask'):
                volume_plate('MK-Curve ' + key, Path(record['maps'][key]), categorical=key.endswith('mask'))

    unchanged = all(fingerprint(Path(path)) == saved for path, saved in sources.items())
    receipt = dict(kind='scientific_review_packet', generated_at=datetime.now(timezone.utc).isoformat(),
                   status='review_pending', human_review='pending', reviewer=None, scientific_accepted=False,
                   sources=list(sources.values()), sources_unchanged=unchanged, reference=str(args.reference.resolve()),
                   axial_coronal_sagittal_indices=slices, world_ras_mm=midpoint.tolist(), plates=plates,
                   limitations=['Preview plots are not expert anatomical approval or validation against ground truth.',
                                'Scalars retain all finite in-brain values; display bounds do not alter NIfTI data.',
                                'A projection superposes different depths and cannot prove cortical endpoints.'])
    if not unchanged:
        raise RuntimeError('A source changed while review plates were being generated')
    (args.output_dir / 'review_packet.json').write_text(json.dumps(receipt, indent=2) + '\n')
    form = dict(status='pending', reviewer_name=None, qualifications=None, reviewed_at=None,
                packet_sha256=fingerprint(args.output_dir / 'review_packet.json')['sha256'],
                decisions=[dict(plate=p['image'], accepted=None, notes='') for p in plates],
                checklist=['Verify left/right and image/tract coordinate correspondence.',
                           'Inspect cortical boundaries, tissue/region labels and scalar invalidity.',
                           'Review brainstem, internal capsule, motor cortex and possible tract outliers.',
                           'Review native 3D products, not just these projections.'])
    (args.output_dir / 'manual_review.json').write_text(json.dumps(form, indent=2) + '\n')
    lines = ['# Anatomical Review Packet', '', '**Status: pending expert review, not scientific acceptance.**', '',
             '[All Plates (PDF)](review_plates.pdf) | [Provenance](review_packet.json) | [Review Form](manual_review.json)', '',
             'Reference and results are not resampled. Scalar display bounds are 1st/99th percentiles, except categorical masks.',
             'Nearest-neighbor display; no smoothing, hole filling or source changes. Bundle plates are orthogonal projections, not slices.', '']
    for plate in plates:
        lines.extend([f'## {plate["name"]}', '', f'![{plate["name"]}]({plate["image"]})', ''])
    (args.output_dir / 'README.md').write_text('\n'.join(lines))
    print(json.dumps(dict(status=receipt['status'], plates=len(plates), sources_unchanged=unchanged,
                          output=str(args.output_dir.resolve())), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path, help='Native 3D FA or b0')
    parser.add_argument('--brain-mask', type=Path, help='Explicit native brain mask, recommended to retain zero-valued tissue')
    parser.add_argument('--volume', action='append', default=[], help='NAME=PATH, native scalar map')
    parser.add_argument('--label', action='append', default=[], help='NAME=PATH, native label map')
    parser.add_argument('--bundle-manifest', type=Path, action='append', default=[])
    parser.add_argument('--mkcurve-record', type=Path)
    parser.add_argument('--surface-qc', type=Path, help='Current native surface QC naming indexed RAS masters')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--max-tracks', type=int, default=1000)
    args = parser.parse_args()
    if args.max_tracks < 1:
        parser.error('--max-tracks must be positive')
    prepare(args)
