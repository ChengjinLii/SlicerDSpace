"""Exercise the complete FW comparison harness on small synthetic signals."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest

import nibabel as nib
import numpy as np

from scripts.benchmark_complete_models import compare, worker


class CompleteFreewaterBenchmarkTest(unittest.TestCase):
    def test_original_and_optimized_workers_keep_raw_parameters_qc_and_maps(self):
        from dipy.reconst import fwdti
        original_fit = fwdti.FreeWaterTensorModel.fit
        previous_path = sys.path[:]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root/'input'
                source.mkdir()
                rng = np.random.default_rng(2026)
                vectors = rng.normal(size=(60,3))
                vectors /= np.linalg.norm(vectors,axis=1,keepdims=True)
                vectors = np.vstack((np.zeros((2,3)),vectors))
                bvals = np.r_[0.,0.,np.full(30,1000.),np.full(30,2000.)]
                adc = np.sum(vectors**2*np.array([.0015,.0005,.0003]),axis=1)
                signal = 1000*(.8*np.exp(-bvals*adc)+.2*np.exp(-bvals*.003))
                data = np.broadcast_to(signal,(2,2,2,len(signal))).copy().astype(np.float32)
                nib.save(nib.Nifti1Image(data,np.eye(4)),source/'data.nii.gz')
                nib.save(nib.Nifti1Image(np.ones((2,2,2),np.uint8),np.eye(4)),source/'nodif_brain_mask.nii.gz')
                np.savetxt(source/'bvals',bvals[None,:])
                np.savetxt(source/'bvecs',vectors.T)
                settings = root/'settings.json'
                settings.write_text(json.dumps(dict(source=str(source),subject_id='fixture',
                                                     snapshot=str(Path(__file__).resolve().parents[2]))))
                outputs = []
                for variant in ('optimized','reference'):
                    worker(argparse.Namespace(settings=settings,stage='freewater',variant=variant))
                    outputs.append(json.loads((root/variant/'measurement.json').read_text()))
                    self.assertIs(fwdti.FreeWaterTensorModel.fit,original_fit)
                    self.assertTrue(any(key.startswith('raw_parameters_') for key in outputs[-1]['files']))
                comparison = compare(outputs[1],outputs[0],'freewater')
                self.assertEqual(comparison['status'],'passed')
                self.assertTrue(comparison['qc_equal'])
                self.assertTrue(all(row['exact'] for row in comparison['products']))
        finally:
            sys.path[:] = previous_path


if __name__ == '__main__':
    unittest.main()
