"""The lightweight option uses DIPY directly, with unchanged native geometry."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import nibabel as nib
import numpy as np
from dipy.segment.mask import median_otsu

from shared.brain_mask import BrainMaskConfig, generate_brain_mask, inspect_brain_mask_backend
from shared.environment import EnvironmentDoctorConfig, build_dependency_specs


class DipyMaskTest(unittest.TestCase):
    def test_native_mask_matches_dipy_and_never_runs_external_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            grid = np.indices((32,32,32))
            baseline = (np.sum((grid - 16) ** 2, axis=0) < 100).astype(np.float32) * 100
            dwi = np.stack((baseline, baseline * 2, baseline * 4), axis=-1)
            affine = np.diag([1.5, 1.5, 2, 1])
            nib.save(nib.Nifti1Image(dwi, affine), root / 'dwi.nii.gz')
            np.savetxt(root / 'bvals', [0,0,1000])
            np.savetxt(root / 'bvecs', [[0,0,1],[0,0,0],[0,0,0]])
            config = BrainMaskConfig(backend='dipy')
            with patch('shared.brain_mask._run') as external:
                result = generate_brain_mask(root/'dwi.nii.gz', root/'bvals', root/'bvecs', root/'mask.nii.gz', config=config)
            external.assert_not_called()
            expected = median_otsu(baseline * 1.5, median_radius=4, numpass=4, dilate=1, autocrop=False)[1]
            actual = nib.load(root/'mask.nii.gz')
            np.testing.assert_array_equal(actual.dataobj, expected)
            np.testing.assert_array_equal(actual.affine, affine)
            self.assertEqual(result['backend'], 'dipy')
            self.assertTrue(result['qc']['geometry_pass'])
            self.assertEqual(result['device_execution']['resolved'], 'cpu')
            self.assertEqual(result['qc']['human_review'], 'pending')
            reused = generate_brain_mask(root/'dwi.nii.gz', root/'bvals', root/'bvecs', root/'mask.nii.gz', config=config)
            self.assertEqual(reused['status'], 'reused')

    def test_native_inspection_and_dependencies(self):
        status = inspect_brain_mask_backend(BrainMaskConfig(backend='dipy'), system='Windows')
        self.assertTrue(status['available'])
        self.assertEqual(status['tool_paths'], {})
        specs = build_dependency_specs(EnvironmentDoctorConfig(repo_root=Path(__file__).resolve().parents[2], targets=('validation',), brain_mask_backend='dipy', brain_mask_required=True))
        self.assertTrue(any(s.key == 'python:dipy' for s in specs))
        self.assertFalse(any(s.kind == 'command' for s in specs))
