#!/usr/bin/env python3
"""Stage the predeclared b~1000 single-shell UKF comparison, never edit sources."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prepare(subject, destination):
    import nibabel as nib
    import numpy as np
    from anatomy.parcellation.conversion.nhdr_write import nhdr_write
    from shared.diffusion_io import diffusion_image
    from microstructure.dki import _signature

    inputs = {key: subject / 'input' / filename for key, filename in
              (('dwi', 'data.nii.gz'), ('bval', 'bvals'), ('bvec', 'bvecs'), ('mask', 'nodif_brain_mask.nii.gz'))}
    before = {key: _signature(path) for key, path in inputs.items()}
    values = np.loadtxt(inputs['bval']).reshape(-1)
    directions = np.loadtxt(inputs['bvec'])
    if directions.shape == (3, len(values)):
        directions = directions.T
    selected = np.flatnonzero((values <= 50) | (np.abs(values - 1000) <= 100))
    if np.count_nonzero(values[selected] > 50) < 30:
        raise ValueError('The declared UKF comparison requires at least 30 directions near b=1000')
    destination.mkdir(parents=True, exist_ok=False)
    with diffusion_image(inputs['dwi'], work_dir=destination) as source:
        storage = np.lib.format.open_memmap(destination / 'selected.npy', mode='w+', dtype=np.float32,
                                          shape=(*source.shape[:3], len(selected)))
        for index, volume in enumerate(selected):
            storage[..., index] = source.dataobj[..., int(volume)]
        header = source.header.copy()
        header.set_data_dtype(np.float32)
        nib.save(nib.Nifti1Image(storage, source.affine, header), destination / 'dwi.nii')
        storage._mmap.close()
    baseline = values[selected] <= 50
    selected_values = values[selected].copy()
    selected_vectors = directions[selected].copy()
    selected_values[baseline], selected_vectors[baseline] = 0, 0
    np.savetxt(destination / 'bvals', selected_values[None], fmt='%.10g')
    np.savetxt(destination / 'bvecs', selected_vectors.T, fmt='%.17g')
    mask_image = nib.load(inputs['mask'])
    mask = np.asarray(mask_image.dataobj)
    if not np.isin(mask, (0, 1)).all():
        raise ValueError('Original mask must be binary')
    nib.save(nib.Nifti1Image(mask.astype(np.uint8), mask_image.affine), destination / 'mask.nii')
    for stem in ('dwi', 'mask'):
        nhdr_write(str(destination / f'{stem}.nii'), str(destination / 'bvals') if stem == 'dwi' else None,
                   str(destination / 'bvecs') if stem == 'dwi' else None, str(destination / f'{stem}.nhdr'))
    record = dict(kind='ukf_prespecified_single_shell_input', inputs=before, selected_volumes=selected.tolist(),
                  protocol='All b0<=50 and complete b~1000 +/-100 shell; b0 gradients explicitly zero in working copy',
                  volumes=len(selected), inputs_unchanged=before == {key: _signature(path) for key, path in inputs.items()},
                  outputs={name: str(destination / f'{name}.nhdr') for name in ('dwi', 'mask')})
    (destination / 'preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subject-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.subject_root.resolve(), args.output_dir.resolve())
