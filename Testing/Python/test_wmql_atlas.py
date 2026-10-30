"""Physical-space derivation, non-WM preservation and cache-integrity contracts."""

import json
from pathlib import Path
import tempfile
import unittest

import nibabel as nib
import numpy as np
from scipy.spatial.distance import cdist

from tractography.wmql_atlas import derive_territories, prepare_ddparcel_atlas, prepared_atlas_current


def image(affine=None):
    data = np.zeros((13, 5, 3), np.int16)
    data[2:6, 1:4, 1] = 2
    data[7:11, 1:4, 1] = 41
    data[1, 1, 1], data[1, 3, 1] = 1001, 1002
    data[11, 1, 1], data[11, 3, 1] = 2001, 2002
    data[6, 2, 1], data[6, 0, 1] = 192, 4
    result = nib.Nifti1Image(data, np.eye(4) if affine is None else affine)
    result.header.set_xyzt_units('mm')
    return result


class WmqlAtlasTests(unittest.TestCase):
    def test_world_space_derivation_matches_independent_brute_force(self):
        for affine in (np.eye(4), np.diag([-2.5, 1.5, 2, 1]),
                       np.array([[1.5, .2, 0, 10], [.3, 1.7, .1, -12], [0, .1, 2, 5], [0, 0, 0, 1]])):
            original = image(affine)
            data = np.asarray(original.dataobj)
            prepared, counts = derive_territories(original)
            for wm, base, deep in ((2, 1000, 5001), (41, 2000, 5002)):
                seeds = np.argwhere((data > base) & (data < base + 36))
                voxels = np.argwhere(data == wm)
                distances = cdist(nib.affines.apply_affine(affine, voxels),
                                  nib.affines.apply_affine(affine, seeds))
                for voxel, distances_to_seeds in zip(voxels, distances):
                    closest = distances_to_seeds.min()
                    expected = (int(data[tuple(seeds[np.isclose(distances_to_seeds, closest,
                                                                atol=1e-10, rtol=0)].T)].min()) + 2000
                                if closest <= 5 else deep)
                    self.assertEqual(prepared[tuple(voxel)], expected)
            protected = ~np.isin(data, (2, 41, 192))
            np.testing.assert_array_equal(prepared[protected], data[protected])
            self.assertEqual(prepared.dtype, np.int16)
            self.assertEqual(counts['left']['generic_wm_voxels'], 12)
        self.assertEqual(derive_territories(image())[0][6, 2, 1], 192)

    def test_deterministic_ties_and_closed_five_mm_boundary(self):
        data = np.asarray(image().dataobj).copy()
        prepared, _ = derive_territories(image())
        self.assertEqual(prepared[2, 2, 1], 3001)
        original = image(np.diag([2.5, 1, 1, 1]))
        prepared, _ = derive_territories(original)
        self.assertEqual(prepared[3, 1, 1], 3001)  # exactly 5 mm
        self.assertEqual(prepared[4, 1, 1], 5001)

    def test_rejects_wrong_schema_units_and_missing_hemisphere(self):
        cases = []
        wrong_schema = image()
        np.asarray(wrong_schema.dataobj)[0, 0, 0] = 3001
        cases.append((wrong_schema, 'schema'))
        wrong_units = image()
        wrong_units.header.set_xyzt_units('meter')
        cases.append((wrong_units, 'millimetre'))
        missing = image()
        np.asarray(missing.dataobj)[np.asarray(missing.dataobj) == 41] = 0
        cases.append((missing, 'right'))
        fractional = image()
        values = np.asarray(fractional.dataobj).astype(np.float32)
        values[0, 0, 0] = .25
        cases.append((nib.Nifti1Image(values, fractional.affine, fractional.header), 'integer'))
        for bad, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                derive_territories(bad)

    def test_content_cache_checks_source_output_implementation_and_geometry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'native.nii.gz'
            nib.save(image(), source)
            before = source.read_bytes()
            output, record = prepare_ddparcel_atlas(source, root / 'cache')
            self.assertTrue(prepared_atlas_current(record, source))
            same, second = prepare_ddparcel_atlas(source, root / 'cache')
            self.assertEqual(same, output)
            self.assertTrue(second['cache_reused'])
            output.write_bytes(b'truncated-image')
            self.assertFalse(prepared_atlas_current(record, source))
            repaired, receipt = prepare_ddparcel_atlas(source, root / 'cache')
            self.assertEqual(repaired, output)
            self.assertFalse(receipt['cache_reused'])
            self.assertTrue(prepared_atlas_current(receipt, source))
            self.assertFalse(prepared_atlas_current(dict(receipt, implementation_sha256='old'), source))
            self.assertEqual(source.read_bytes(), before)
            changed = image()
            np.asarray(changed.dataobj)[0, 0, 0] = 16
            nib.save(changed, source)
            self.assertFalse(prepared_atlas_current(record, source))
            different, _ = prepare_ddparcel_atlas(source, root / 'cache')
            self.assertNotEqual(different, output)

    def test_cli_opt_in_keeps_the_native_default(self):
        from shared.run_subject_pipeline_cli import build_parser
        from shared.orchestrator import ProductOrchestratorConfig, _validate_tractography_settings
        from tractography.wmql import WMQLConfig, _validate_wmql_config
        parser = build_parser()
        required = ['--subject-root', '/tmp/subject', '--subject-id', 'test']
        self.assertEqual(parser.parse_args(required).wmql_atlas_mode, 'native')
        self.assertEqual(parser.parse_args(required + ['--wmql-atlas-mode', 'ddparcel_wm']).wmql_atlas_mode,
                         'ddparcel_wm')
        self.assertEqual(WMQLConfig.__dataclass_fields__['atlas_mode'].default, 'native')
        with self.assertRaisesRegex(ValueError, 'Unknown WMQL atlas mode'):
            _validate_tractography_settings(ProductOrchestratorConfig('test', Path('/tmp'), (), wmql_atlas_mode='bad'))
        with self.assertRaisesRegex(ValueError, 'bundled catalogue'):
            _validate_wmql_config(WMQLConfig('test', Path('/tmp/a.vtk'), Path('/tmp/a.nii.gz'), Path('/tmp/out'),
                                            atlas_mode='ddparcel_wm', query_preset='author'), {})


if __name__ == '__main__':
    unittest.main()
