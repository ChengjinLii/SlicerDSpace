"""Existing DIPY fit, dense versus object-per-voxel metric evaluation."""

from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import nibabel as nib
import numpy as np
from test_microstructure_dki import synthetic_case,write_case
from microstructure.dki import DkiConfig,run_dki
from shared.pipeline import RawInputBundle


class DkiDenseMetricsTest(unittest.TestCase):
    def test_complete_export_matches_author_for_ols_and_wls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            paths=write_case(root,synthetic_case(noisy=True))
            raw=RawInputBundle(root,'test',root/'input',*[paths[k] for k in ('dwi','bval','bvec','mask')])
            for method in ('WLS','OLS'):
                reference=run_dki(DkiConfig('test',raw,root/(method+'ref'),fit_method=method,dense_metrics=False))
                optimized=run_dki(DkiConfig('test',raw,root/(method+'opt'),fit_method=method,dense_metrics=True))
                for key in reference.outputs:
                    if key in ('manifest','qc','progress'):
                        continue
                    images=[nib.load(str(result.outputs[key])) for result in (reference,optimized)]
                    np.testing.assert_array_equal(images[0].affine,images[1].affine)
                    np.testing.assert_array_equal(np.asanyarray(images[0].dataobj),np.asanyarray(images[1].dataobj))

    def test_unknown_dipy_version_retains_original_metric_route(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            paths=write_case(root,synthetic_case(noisy=True))
            raw=RawInputBundle(root,'test',root/'input',*[paths[k] for k in ('dwi','bval','bvec','mask')])
            reference=run_dki(DkiConfig('test',raw,root/'reference',dense_metrics=False))
            with patch('dipy.__version__','9.0.0'):
                fallback=run_dki(DkiConfig('test',raw,root/'fallback',dense_metrics=True))
            qc=json.loads(fallback.qc_path.read_text())
            self.assertFalse(qc['dense_metrics_supported'])
            self.assertEqual(qc['metric_evaluation'],'DIPY per-voxel metrics')
            for key in reference.outputs:
                if key in ('manifest','qc','progress'):
                    continue
                images=[nib.load(str(result.outputs[key])) for result in (reference,fallback)]
                np.testing.assert_array_equal(np.asanyarray(images[0].dataobj),np.asanyarray(images[1].dataobj))


if __name__=='__main__':
    unittest.main()
