#!/usr/bin/env python3
"""Explain raw MK-Curve exclusions without fitting, clipping or rewriting maps."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_pipeline_cohort import digest, write_json


def audit(record_path):
    import nibabel as nib
    import numpy as np
    from microstructure.mkcurve import metric_validity
    record = json.loads(record_path.read_text())
    mask_path = Path(record['inputs']['mask']['path'])
    reference = nib.load(str(mask_path))
    mask = reference.get_fdata() > 0
    count = int(mask.sum())
    captured = {str(record_path): digest(record_path), str(mask_path): digest(mask_path)}

    mask_checks = {}

    def load(key, *, binary=False):
        path = Path(record['maps'][key])
        image = nib.load(str(path))
        if image.shape != reference.shape or not np.allclose(image.affine, reference.affine, rtol=0, atol=1e-4):
            raise ValueError(f'MK-Curve native-grid mismatch: {key}')
        captured[str(path)] = digest(path)
        values = np.asarray(image.dataobj)
        if binary:
            mask_checks[key] = {'binary': bool(np.isin(values, (0, 1)).all()),
                                'zero_outside_brain': bool((values[~mask] == 0).all())}
        return values[mask]

    maps = {key: load('corrected_' + key) for key in ('fa', 'md', 'ad', 'rd', 'mk', 'ak', 'rk', 'e1', 'e2', 'e3')}
    curves = load('curve_valid_mask', binary=True).astype(bool)
    residual = load('corrected_nrmse')
    joint = load('corrected_valid_mask', binary=True).astype(bool)
    # Saved coefficients use MATLAB/F order; spatial scalar maps use native array order.
    coefficients_path = Path(record['auxiliary_files']['corrected_coefficients'])
    coefficients = np.load(coefficients_path, mmap_mode='r')
    if coefficients.shape != (count, 22):
        raise ValueError('Coefficient/mask voxel ordering is inconsistent')
    finite_volume = np.zeros(mask.shape, dtype=bool)
    coordinates = np.unravel_index(np.flatnonzero(mask.ravel(order='F')), mask.shape, order='F')
    finite_volume[coordinates] = np.isfinite(coefficients).all(axis=1)
    captured[str(coefficients_path)] = digest(coefficients_path)
    valid = metric_validity(maps, finite_volume[mask], curves, residual)
    saved_masks = {}
    require_saved_masks = record.get('backend', {}).get('port_version', 1) >= 2
    for key, expected in valid.items():
        name = 'corrected_' + key + '_valid_mask'
        if name not in record['maps']:
            saved_masks[key] = {'present': False, 'required': require_saved_masks}
            continue
        actual = load(name, binary=True)
        checks = mask_checks[name]
        saved_masks[key] = {'present': True, 'required': require_saved_masks, **checks,
                            'matches_recomputed': bool(np.array_equal(actual, expected)),
                            'mismatched_voxels': int(np.count_nonzero(actual != expected))}
        if key in record.get('metric_valid_voxels', {}):
            saved_masks[key]['record_count_matches'] = int(expected.sum()) == record['metric_valid_voxels'][key]
    details, union = {}, ~finite_volume[mask] | ~curves | ~np.isfinite(residual)
    for key, values in maps.items():
        lo, hi = (0, 1) if key == 'fa' else ((0, 3) if key in {'mk', 'ak', 'rk'} else (0, .005))
        bad = ~np.isfinite(values) | (values < lo) | (values > hi)
        union |= bad
        details[key] = {'nonfinite': int((~np.isfinite(values)).sum()), 'below_min': int((values < lo).sum()),
                        'above_max': int((values > hi).sum()), 'range': [lo, hi],
                        'per_metric_valid_voxels': int(valid[key].sum()),
                        'per_metric_invalid_voxels': int((~valid[key]).sum()),
                        'otherwise_valid_excluded_by_joint_gate': int((valid[key] & ~joint).sum())}
    unchanged = all(digest(path) == value for path, value in captured.items())
    joint_reproduced = bool(np.array_equal(~union, joint))
    saved_masks_passed = all((not item['required']) if not item['present'] else
                            all(item.get(check, True) for check in
                                ('binary', 'zero_outside_brain', 'matches_recomputed', 'record_count_matches'))
                            for item in saved_masks.values())
    audit_passed = (unchanged and joint_reproduced and saved_masks_passed
                    and all(all(item.values()) for item in mask_checks.values()))
    return {'kind': 'mkcurve_raw_validity_audit', 'brain_voxels': count, 'joint_invalid_voxels': int((~joint).sum()),
            'joint_mask_reproduced': joint_reproduced, 'metrics': details,
            'saved_metric_masks': saved_masks, 'saved_metric_masks_required': require_saved_masks,
            'saved_masks_well_formed': all(all(item.values()) for item in mask_checks.values()),
            'validity_audit_passed': audit_passed,
            'nonfinite_coefficients': int((~finite_volume[mask]).sum()), 'invalid_curves': int((~curves).sum()),
            'nonfinite_residuals': int((~np.isfinite(residual)).sum()), 'source_sha256': captured,
            'source_unchanged': unchanged, 'all_voxels_fit_valid': bool(joint.all()),
            'scope': 'Read-only bounds audit. Per-metric eligibility is not a refit or a claim that excluded values became valid.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Refusing to overwrite an existing audit')
    outcome = audit(args.record.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.report, outcome)
    print(json.dumps({key: outcome[key] for key in ('brain_voxels', 'joint_invalid_voxels', 'metrics')}, indent=2))
    raise SystemExit(0 if outcome['validity_audit_passed'] else 1)
