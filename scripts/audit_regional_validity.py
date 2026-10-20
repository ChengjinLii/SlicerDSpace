#!/usr/bin/env python3
"""Independently verify that invalid raw MK-Curve estimates never enter ROI tables."""

import argparse
import csv
import json
from pathlib import Path
import sys
import time

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from microstructure.pipeline import _compute_roi_stats, _roi_validity_mask, roi_statistics_current
from scripts.prepare_scientific_review import fingerprint


def audit_statistics(json_path, csv_path, *, required_metrics=()):
    """Read exported tables and independently recompute every estimate; never repair."""

    started = time.monotonic()
    checks = {'current_table_contract': roi_statistics_current(
        json_path, csv_path, required_metrics=required_metrics)}
    result = dict(kind='regional_statistics_readonly_audit', status='failed', checks=checks,
                  automatic_qc_passed=False, human_review='pending', read_only=True,
                  statistics=str(json_path.resolve()), csv=str(csv_path.resolve()), failures=[])
    if not checks['current_table_contract']:
        result['failures'].append(dict(failure='Legacy, stale, missing or inconsistent regional tables'))
        return result
    payload = json.loads(json_path.read_text())
    atlas_path = Path(payload['roi_label_map'])
    atlas = nib.load(atlas_path)
    labels = atlas.get_fdata(dtype=np.float64)
    checks['discrete_nonempty_atlas'] = bool(labels.ndim == 3 and np.isfinite(labels).all()
        and np.all(labels >= 0) and np.allclose(labels, np.rint(labels), rtol=0, atol=1e-3)
        and np.any(labels > 0))
    if not checks['discrete_nonempty_atlas']:
        return result
    labels = np.rint(labels).astype(np.int64)
    expected_labels = set(np.unique(labels[labels > 0]).tolist())
    rows = {int(row['label_id']): row for row in payload['rows']}
    checks['all_regions_retained_once'] = set(rows) == expected_labels and len(rows) == len(payload['rows'])
    paths = {str(path.resolve()): path for path in (json_path, csv_path, atlas_path)}
    for source in payload['source_signatures'].values():
        path = Path(source['path'])
        paths[str(path.resolve())] = path
    before = {key: fingerprint(path) for key, path in paths.items()}

    def load_mask(path):
        image = nib.load(path)
        values = image.get_fdata(dtype=np.float64)
        if (values.shape != labels.shape or not np.allclose(image.affine, atlas.affine, rtol=0, atol=1e-4)
                or not np.isfinite(values).all() or not np.isin(values, (0, 1)).all()):
            raise ValueError(f'Invalid native binary mask: {path}')
        return values.astype(bool)

    brain = load_mask(payload['brain_mask']) if payload.get('brain_mask') else np.ones(labels.shape, dtype=bool)
    failures = result['failures']
    comparisons, coverage = 0, {}
    for key, name in payload['feature_maps'].items():
        image = nib.load(name)
        values = image.get_fdata(dtype=np.float64)
        if values.shape != labels.shape or not np.allclose(image.affine, atlas.affine, rtol=0, atol=1e-4):
            failures.append(dict(metric=key, failure='Scalar does not share the native atlas grid'))
            continue
        valid = brain & np.isfinite(values)
        policy = payload.get('validity_policy', {}).get(key)
        needs_mask = key in {'fw_tissue_fa', 'fw_tissue_md', 'noddi_ndi', 'noddi_odi'} or key.startswith(('dki_', 'mkcurve_'))
        if needs_mask and policy != 'explicit_validity_mask':
            failures.append(dict(metric=key, failure='Conditional tissue/raw metric lacks explicit validity'))
            continue
        if policy == 'explicit_validity_mask':
            valid &= load_mask(payload['source_signatures'][f'mask:{key}']['path'])
        valid_total, excluded_total = 0, 0
        for label in sorted(expected_labels):
            if label not in rows:
                continue
            row, region = rows[label], labels == label
            samples = values[region & valid]
            total, count = int(region.sum()), int(samples.size)
            valid_total += count
            excluded_total += total - count
            expected = dict(valid_voxel_count=count, excluded_voxel_count=total-count, valid_fraction=count/total)
            if row.get('roi_voxel_count') != total:
                failures.append(dict(metric=key, label=label, failure='Anatomical ROI voxel count'))
            if key == payload.get('voxel_count_basis') and row.get('voxel_count') != count:
                failures.append(dict(metric=key, label=label, failure='Legacy count basis'))
            expected.update(dict(mean=float(samples.mean()), std=float(samples.std()),
                                 min=float(samples.min()), max=float(samples.max())) if count else
                            {name: None for name in ('mean', 'std', 'min', 'max')})
            for suffix, value in expected.items():
                actual = row.get(f'{key}_{suffix}')
                matches = actual is None if value is None else actual is not None and np.isclose(
                    actual, value, rtol=0 if 'count' in suffix else 2e-6, atol=0 if 'count' in suffix else 1e-10)
                if not matches:
                    failures.append(dict(metric=key, label=label, failure=suffix, expected=value, actual=actual))
                comparisons += 1
        coverage[key] = dict(valid_voxels=valid_total, excluded_voxels=excluded_total)
    checks['independent_counts_and_estimates'] = not failures
    checks['files_unchanged'] = all(fingerprint(path) == before[key] for key, path in paths.items())
    passed = all(checks.values())
    result.update(status='passed' if passed else 'failed', automatic_qc_passed=passed,
                  regions=len(rows), metrics=len(payload['feature_maps']), comparisons=comparisons,
                  coverage=coverage, sources=list(before.values()), runtime_seconds=time.monotonic()-started,
                  scope='Native-grid numerical regional statistics and exclusion only; not fitting or anatomical certification')
    return result


def audit(record_path, atlas_path, output):
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=False)
    record = json.loads(record_path.read_text())
    if record.get('status') != 'completed':
        raise ValueError('A completed MK-Curve record is required')
    names = ('fa', 'md', 'ad', 'rd', 'mk', 'ak', 'rk')
    maps = {f'mkcurve_corrected_{name}': Path(record['maps']['corrected_' + name]) for name in names}
    mask_path = Path(record['maps']['corrected_valid_mask'])
    brain_path = Path(record['inputs']['mask']['path'])
    paths = [record_path, atlas_path, mask_path, brain_path, *maps.values()]
    before = {str(path.resolve()): fingerprint(path) for path in paths}
    reference = next(iter(maps.values()))
    valid = _roi_validity_mask(mask_path, reference)
    brain = _roi_validity_mask(brain_path, reference)
    if np.any(valid & ~brain):
        raise ValueError('Corrected validity mask extends beyond the original brain mask')
    _compute_roi_stats(metric_paths=maps, roi_label_map=atlas_path, lut_path=None,
                       csv_path=output / 'regional_mkcurve.csv', json_path=output / 'regional_mkcurve.json',
                       validity_mask_paths={key: mask_path for key in maps})
    statistics = json.loads((output / 'regional_mkcurve.json').read_text())
    labels = np.rint(nib.load(atlas_path).get_fdata()).astype(int)
    rows = {int(row['label_id']): row for row in statistics['rows']}
    with (output / 'regional_mkcurve.csv').open() as stream:
        csv_rows = {int(row['label_id']): row for row in csv.DictReader(stream)}
    expected_labels = set(np.unique(labels[labels > 0]).tolist())
    failures, empty = [], []
    if set(rows) != expected_labels or set(csv_rows) != expected_labels:
        failures.append(dict(failure='Missing or unexpected atlas regions in exported tables'))
    comparisons = 0
    for key, path in maps.items():
        values = nib.load(path).get_fdata(dtype=np.float64)
        metric = key.removeprefix('mkcurve_corrected_')
        upper = 1 if metric == 'fa' else 3 if metric in {'mk', 'ak', 'rk'} else .005
        if not (np.isfinite(values[valid]).all() and np.all((values[valid] >= 0) & (values[valid] <= upper))):
            failures.append(dict(metric=key, failure='Valid mask includes out-of-range raw estimates'))
        for label in sorted(expected_labels):
            if label not in rows or label not in csv_rows:
                continue
            region = labels == label
            samples = values[region & valid & np.isfinite(values)]
            row = rows[label]
            count, total = int(samples.size), int(region.sum())
            expected = dict(valid_voxel_count=count, excluded_voxel_count=total - count, valid_fraction=count / total)
            for suffix, value in expected.items():
                if not np.isclose(row[f'{key}_{suffix}'], value, rtol=0, atol=1e-12):
                    failures.append(dict(metric=key, label=label, failure=suffix))
            if not count:
                empty.append(dict(metric=key, label=label))
                estimates = {suffix: None for suffix in ('mean', 'std', 'min', 'max')}
            else:
                estimates = dict(mean=float(samples.mean()), std=float(samples.std()),
                                 min=float(samples.min()), max=float(samples.max()))
            for suffix, value in estimates.items():
                actual = row[f'{key}_{suffix}']
                csv_value = csv_rows[label][f'{key}_{suffix}']
                matches = (actual is None and csv_value == '') if value is None else (
                    actual is not None and np.isclose(actual, value, rtol=2e-6, atol=1e-10)
                    and np.isclose(float(csv_value), value, rtol=2e-6, atol=1e-10))
                if not matches:
                    failures.append(dict(metric=key, label=label, failure=suffix, expected=value, actual=actual))
                comparisons += 1
    checks = dict(all_atlas_regions_reported=set(rows) == expected_labels == set(csv_rows),
                  input_brain_count_matches_record=int(brain.sum()) == record['mask_voxels'],
                  valid_count_matches_record=int(valid.sum()) == record['corrected_valid_voxels'],
                  explicit_validity_masks_for_all_metrics=all(statistics['validity_policy'][key] == 'explicit_validity_mask' for key in maps),
                  independent_counts_estimates_and_empty_cells_match=not failures,
                  source_files_unchanged=all(fingerprint(Path(path)) == value for path, value in before.items()))
    return dict(kind='mkcurve_regional_validity_audit', status='passed' if all(checks.values()) else 'failed',
                automatic_quantitative_exclusion_qc_passed=all(checks.values()), checks=checks,
                original_all_voxels_valid_flag=record.get('automatic_qc_passed'),
                brain_voxels=int(brain.sum()), valid_voxels=int(valid.sum()), excluded_voxels=int((brain & ~valid).sum()),
                regions=len(rows), scalar_maps=len(maps), independent_estimate_comparisons=comparisons,
                failures=failures, empty_estimates=empty, sources=list(before.values()),
                runtime_seconds=time.monotonic() - started, raw_maps_modified=False, human_review='pending',
                scope='Valid-mask exclusion and correct ROI statistics, NOT all-voxel fitting validity or expert anatomical acceptance')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--record', type=Path)
    source.add_argument('--statistics', type=Path, help='Read-only audit of an existing regional JSON/CSV pair')
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--atlas', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    if args.record and args.atlas is None:
        parser.error('--record requires --atlas')
    if args.output_dir.exists():
        raise FileExistsError('Choose a new audit directory; previous evidence is preserved')
    try:
        if args.statistics:
            args.output_dir.mkdir(parents=True)
            result = audit_statistics(args.statistics.resolve(), (args.csv or args.statistics.with_suffix('.csv')).resolve())
        else:
            result = audit(args.record.resolve(), args.atlas.resolve(), args.output_dir.resolve())
    except Exception as exc:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        result = dict(kind='regional_statistics_audit', status='failed', automatic_qc_passed=False,
                      error=f'{type(exc).__name__}: {exc}', human_review='pending')
    (args.output_dir / 'acceptance.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in ('sources', 'empty_estimates')}, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
