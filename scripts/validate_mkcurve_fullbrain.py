#!/usr/bin/env python3
"""Full-mask MK-Curve execution and independent pivoted-QR sample audit."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(args):
    import nibabel as nib
    import numpy as np
    from microstructure.dki import DkiConfig, _signature, inspect_dki_inputs
    from microstructure.mkcurve import run_mkcurve, repair_nonpositive, _fit_chunk
    from microstructure.mkcurve_inputs import _prepare_inputs
    from microstructure.mkcurve_tensor import design_matrix
    from shared.pipeline import RawInputBundle
    from scripts.audit_scientific_outputs import _audit_mkcurve
    from scripts.validate_scientific_followup import compare_arrays

    source = args.subject_root / 'input'
    inputs = dict(dwi=source / 'data.nii.gz', bval=source / 'bvals', bvec=source / 'bvecs', mask=source / 'nodif_brain_mask.nii.gz')
    before = {key: _signature(path) for key, path in inputs.items()}
    raw = RawInputBundle(args.subject_root, args.subject_id, source, *inputs.values())
    eligibility = inspect_dki_inputs(DkiConfig(args.subject_id, raw, args.output_dir / 'eligibility', fit_method='MKCURVE', max_bvalue=2500.))
    if not eligibility['eligible']:
        raise ValueError(eligibility)
    started = time.monotonic()
    record = run_mkcurve(*inputs.values(), args.output_dir / 'fit', max_bvalue=2500.,
                        voxels_per_chunk=args.chunk, num_workers=args.workers, solver='batched', log=lambda s: print(s, flush=True))
    fit_seconds = time.monotonic() - started
    reference_image = nib.load(inputs['mask'])
    mask = np.asarray(reference_image.dataobj) > 0
    checks = []
    _audit_mkcurve(record['record_path'], reference_image, checks)
    indices = np.flatnonzero(mask.ravel(order='F'))
    positions = np.linspace(0, len(indices) - 1, min(args.sample_voxels, len(indices)), dtype=int)
    coordinates = np.unravel_index(indices[positions], mask.shape, order='F')
    grid = np.loadtxt(record['auxiliary_files']['grid'])
    with tempfile.TemporaryDirectory(prefix='reference-', dir=args.output_dir) as temporary:
        prepared, _, _ = _prepare_inputs(*inputs.values(), Path(temporary), 50., 2500., allow_nonfinite=True)
        image = nib.load(prepared[0], mmap='c')
        data = image.dataobj.get_unscaled()
        repair_nonpositive(data, mask)
        design = design_matrix(np.loadtxt(prepared[1]), np.loadtxt(prepared[2]).T)
        original, corrected, curves, expected = _fit_chunk((data[coordinates].copy(), design, grid, .5, 'reference'))
        parity = {'original_coefficients': compare_arrays(original, np.load(record['auxiliary_files']['original_coefficients'], mmap_mode='r')[positions], rtol=2e-6, atol=2e-8),
                  'corrected_coefficients': compare_arrays(corrected, np.load(record['auxiliary_files']['corrected_coefficients'], mmap_mode='r')[positions], rtol=2e-6, atol=2e-8),
                  'full_curves': compare_arrays(curves, np.load(record['auxiliary_files']['curve'], mmap_mode='r')[:, positions], rtol=2e-6, atol=2e-6)}
        for key, values in expected.items():
            actual = np.asarray(nib.load(record['maps'][key]).dataobj)[coordinates]
            parity[key] = compare_arrays(values, actual, rtol=2e-5, atol=2e-6)
        if isinstance(data, np.memmap):
            data._mmap.close()
    unchanged = before == {key: _signature(path) for key, path in inputs.items()}
    passed = all(row['passed'] for row in checks) and all(row['passed'] for row in parity.values()) and unchanged
    return dict(kind='mkcurve_full_brain_acceptance', status='passed' if passed else 'failed',
                automatic_integrity_qc_passed=passed, human_review='pending',
                computational_scope='Complete original brain mask; adaptive author grid; no subsampling, smoothing or parameter filling',
                record=record['record_path'], inputs=before, inputs_unchanged=unchanged, eligibility=eligibility,
                runtime_seconds=fit_seconds, mask_voxels=int(mask.sum()), corrected_voxels=record['corrected_voxels'],
                corrected_valid_voxels=record['corrected_valid_voxels'], quantitative_domain_all_voxels_valid=record['automatic_qc_passed'],
                sample_voxels=len(positions), sample_ijk=np.column_stack(coordinates).tolist(), checks=checks, reference_parity=parity)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subject-root', type=Path, required=True)
    parser.add_argument('--subject-id', default='100307')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--chunk', type=int, default=256)
    parser.add_argument('--sample-voxels', type=int, default=128)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('Use a new evidence directory')
    args.output_dir.mkdir(parents=True)
    evidence = args.output_dir / 'acceptance.json'
    evidence.write_text(json.dumps(dict(status='running', created_at=datetime.now(timezone.utc).isoformat())) + '\n')
    try:
        result = run(args)
    except Exception as exc:
        evidence.write_text(json.dumps(dict(status='failed', error=f'{type(exc).__name__}: {exc}'), indent=2) + '\n')
        raise
    evidence.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'runtime_seconds', 'mask_voxels', 'corrected_valid_voxels')}, indent=2))
    raise SystemExit(0 if result['status'] == 'passed' else 1)
