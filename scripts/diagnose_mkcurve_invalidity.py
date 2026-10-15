#!/usr/bin/env python3
"""Locate invalid raw MK-Curve estimates and refit invalid samples with QR."""

import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def diagnose(args):
    import nibabel as nib
    import numpy as np
    from scipy.ndimage import distance_transform_edt
    from microstructure.mkcurve import _fit_chunk, repair_nonpositive
    from microstructure.mkcurve_inputs import _prepare_inputs
    from microstructure.mkcurve_tensor import design_matrix
    from scripts.prepare_scientific_review import fingerprint
    from scripts.validate_scientific_followup import compare_arrays

    started = time.monotonic()
    record = json.loads(args.record.read_text())
    inputs = {key: Path(value['path']) for key, value in record['inputs'].items()}
    source_paths = [args.record, *inputs.values(), args.segmentation, *map(Path, record['maps'].values())]
    before = {str(path.resolve()): fingerprint(path) for path in source_paths}
    mask_image = nib.load(inputs['mask'])
    mask = np.asarray(mask_image.dataobj) > 0
    segmentation = nib.load(args.segmentation)
    if segmentation.shape != mask.shape or not np.allclose(segmentation.affine, mask_image.affine):
        raise ValueError('Segmentation and MK-Curve inputs must share the native grid')
    labels = np.asarray(segmentation.dataobj)
    maps = {key: np.asarray(nib.load(path).dataobj) for key, path in record['maps'].items()}
    invalid = mask & (maps['corrected_valid_mask'] == 0)
    reasons, union = {}, np.zeros(mask.shape, dtype=bool)
    for key in ('fa', 'md', 'ad', 'rd', 'mk', 'ak', 'rk', 'e1', 'e2', 'e3'):
        low, high = (0, 1) if key == 'fa' else (0, 3) if key in ('mk', 'ak', 'rk') else (0, .005)
        values = maps['corrected_' + key]
        failure = mask & (~np.isfinite(values) | (values < low) | (values > high))
        union |= failure
        reasons[key] = dict(nonfinite=int(np.count_nonzero(mask & ~np.isfinite(values))),
                            below_range=int(np.count_nonzero(mask & (values < low))),
                            above_range=int(np.count_nonzero(mask & (values > high))),
                            range=[low, high], voxels=int(failure.sum()))
    curve_bad = mask & (maps['curve_valid_mask'] == 0)
    residual_bad = mask & ~np.isfinite(maps['corrected_nrmse'])
    union |= curve_bad | residual_bad
    distance = distance_transform_edt(mask, sampling=nib.affines.voxel_sizes(mask_image.affine))
    tissues = {}
    for value, name in ((0, 'background'), (1, 'WM'), (2, 'GM'), (3, 'CSF')):
        region = mask & (labels == value)
        bad = invalid & region
        tissues[name] = dict(mask_voxels=int(region.sum()), invalid_voxels=int(bad.sum()),
                             invalid_fraction=float(bad.sum() / region.sum()) if region.any() else None)
    indices = np.flatnonzero(mask.ravel(order='F'))
    bad_positions = np.flatnonzero(invalid.ravel(order='F')[indices])
    positions = bad_positions[np.linspace(0, len(bad_positions) - 1, min(len(bad_positions), args.samples), dtype=int)]
    coordinates = np.unravel_index(indices[positions], mask.shape, order='F')
    parity = {}
    if len(positions):
        with tempfile.TemporaryDirectory(prefix='mkcurve-qr-', dir=args.output_dir) as temporary:
            prepared, _, _ = _prepare_inputs(*(inputs[key] for key in ('dwi', 'bval', 'bvec', 'mask')),
                                             Path(temporary), record['settings']['b0_threshold'],
                                             record['settings']['max_bvalue'], allow_nonfinite=True)
            image = nib.load(prepared[0], mmap='c')
            data = image.dataobj.get_unscaled()
            repair_nonpositive(data, mask)
            design = design_matrix(np.loadtxt(prepared[1]), np.loadtxt(prepared[2]).T)
            grid = np.loadtxt(record['auxiliary_files']['grid'])
            original, corrected, curves, expected = _fit_chunk((data[coordinates].copy(), design, grid,
                                                              record['settings']['threshold'], 'reference'))
            for key, coefficients in (('original_coefficients', original), ('corrected_coefficients', corrected)):
                actual = np.load(record['auxiliary_files'][key], mmap_mode='r')[positions]
                parity[key] = compare_arrays(coefficients, actual, rtol=2e-6, atol=2e-8)
            for key in ('abnormal_mask', 'curve_valid_mask', 'corrected_valid_mask'):
                parity[key] = dict(passed=bool(np.array_equal(expected[key], maps[key][coordinates])))
            for key in ('corrected_fa', 'corrected_mk', 'corrected_ak', 'corrected_rk'):
                parity[key] = compare_arrays(expected[key], maps[key][coordinates])
            if isinstance(data, np.memmap):
                data._mmap.close()
    unchanged = all(fingerprint(Path(path)) == value for path, value in before.items())
    return dict(kind='mkcurve_invalidity_diagnosis', status='diagnosis_complete', record=str(args.record.resolve()),
                sources=list(before.values()), inputs_unchanged=unchanged, invalid_voxels=int(invalid.sum()),
                invalid_fraction=float(invalid.sum() / mask.sum()), reasons=reasons,
                curve_nonfinite_voxels=int(curve_bad.sum()), nonfinite_residual_voxels=int(residual_bad.sum()),
                failure_union_matches_invalid_mask=bool(np.array_equal(union, invalid)),
                invalid_not_explained_by_stored_map_criteria=int(np.count_nonzero(invalid & ~union)),
                tissues=tissues, within_2mm_of_brainmask_boundary=int(np.count_nonzero(invalid & (distance <= 2))),
                sampled_invalid_voxels=len(positions), sample_ijk=np.column_stack(coordinates).tolist(),
                reference_parity=parity, targeted_reference_qc_passed=bool(parity) and all(item['passed'] for item in parity.values()) and unchanged,
                human_review='pending', raw_maps_modified=False, runtime_seconds=time.monotonic() - started,
                limitations=['Out-of-range unconstrained estimates are invalid for quantification, not proof of normal anatomy.',
                             'Signal repairs occur only in the original author-style working-copy protocol.',
                             'Counts across metric failure reasons overlap and must not be added.',
                             'DDSeg tissue labels are predictions, not ground truth.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--segmentation', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=128)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    result = diagnose(args)
    (args.output_dir / 'invalidity.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('invalid_voxels', 'reasons', 'tissues', 'reference_parity', 'targeted_reference_qc_passed')}, indent=2))
    raise SystemExit(0 if result['targeted_reference_qc_passed'] else 1)
