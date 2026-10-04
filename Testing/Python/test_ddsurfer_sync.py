"""Release, coordinate and cache contracts for the current DDSurfer backend."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np
import trimesh

from surface.backend_bridge import BACKEND_ROOT, native_products, runtime_info, sha256, upstream_record
from surface.pipeline import SurfaceConfig, _raw_command, inspect_surface_resources, run_surface

ROOT = Path(__file__).resolve().parents[2]


class DDSurferSyncTests(unittest.TestCase):
    def test_external_runtime_does_not_inherit_slicer_python_home(self):
        completed = SimpleNamespace(returncode=0, stdout='{"python": "external"}\n')
        with patch.dict(os.environ, {'PYTHONHOME': '/Slicer/lib/Python', 'PYTHONPATH': '/Slicer/lib',
                                    'ITK_AUTOLOAD_PATH': '/Slicer/ITKFactories'}):
            with patch('surface.backend_bridge.subprocess.run', return_value=completed) as run:
                self.assertEqual(runtime_info('/independent/bin/python')['python'], 'external')
        environment = run.call_args.kwargs['env']
        self.assertNotIn('PYTHONHOME', environment)
        self.assertNotIn('PYTHONPATH', environment)
        self.assertNotIn('ITK_AUTOLOAD_PATH', environment)

    def test_vendored_sources_match_recorded_snapshot(self):
        record = upstream_record()
        self.assertEqual(len(record['commit']), 40)
        for filename, digest in record['files'].items():
            self.assertEqual(sha256(BACKEND_ROOT / filename), digest, filename)

    def test_snapshot_matches_asset_release(self):
        assets = json.loads((ROOT / 'models/assets_manifest.json').read_text())
        self.assertEqual(assets['ddsurfer_upstream_commit'], upstream_record()['commit'])
        self.assertEqual(len(assets['profiles']['surface']['required_paths']), 9)
        self.assertFalse(any('ckpts/hcp' in p for p in assets['profiles']['surface']['required_paths']))

    def test_prediction_compatibility_accepts_subject_selection(self):
        from surface.prediction import PredictionStageConfig, SurfacePredictor, discover_subject_directories
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'x').mkdir()
            self.assertEqual(discover_subject_directories(root, ['x', 'missing']), {'x': root / 'x'})
            config = PredictionStageConfig('other', 'left', 'all', 'cpu', 0.02, 2, 3,
                root, root, root, root)
            with patch('surface.prediction.run_backend') as run:
                result = SurfacePredictor(config).predict(root / 'x')
            self.assertEqual(result.subject_id, 'x')
            self.assertEqual(run.call_args.args[0][2], 'x')

    def test_failure_always_writes_qc_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            config = SurfaceConfig('x', output, output, checkpoint_root=output / 'missing', execute=True)
            with self.assertRaises(RuntimeError):
                run_surface(config)
            self.assertEqual(json.loads((output / 'surface_manifest.json').read_text())['status'], 'failed')
            qc = json.loads((output / 'surface_qc.json').read_text())
            self.assertFalse(qc['automatic_qc_passed'])

    def test_subject_path_and_precision_are_validated(self):
        for subject, precision in (('../escape', 'auto'), ('x', 'fp16')):
            with self.assertRaises(ValueError):
                run_surface(SurfaceConfig(subject, ROOT, ROOT, precision=precision))

    def test_raw_command_preserves_selected_input_and_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = SimpleNamespace(**{name: root / name for name in ('dwi_path', 'bval_path', 'bvec_path', 'mask_path')})
            for path in vars(bundle).values():
                path.touch()
            resources = dict(checkpoint_root='/weights', template_dir='/templates', registration_atlas='/atlas')
            command, env = _raw_command(SurfaceConfig('x', root, root, input_bundle=bundle,
                device='cuda:1', precision='bf16', slicer_home=root), resources, root)
            self.assertIn('--keep-cache', command)
            self.assertEqual(command[command.index('--dwi') + 1], bundle.dwi_path)
            self.assertEqual(command[command.index('--precision') + 1], 'bf16')
            self.assertEqual(env['DTI_REFERENCE_IMAGE'], '/atlas')

    def test_native_obj_and_lps_stl_have_consistent_coordinates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mesh = trimesh.creation.icosphere(subdivisions=1)
            mesh.vertices += [10, 20, 30]
            for hemi in ('lh', 'rh'):
                for kind in ('white', 'pial'):
                    mesh.export(str(root / f'{hemi}.{kind}.obj'))
            products, qc = native_products(root, 'x', 'all')
            self.assertEqual(len(products), 4)
            self.assertTrue(all(v['watertight'] and v['euler_number'] == 2 for v in qc.values()))
            lps = trimesh.load(str(products[0]), process=False)
            np.testing.assert_allclose(lps.bounds, [[-11, -21, 29], [-9, -19, 31]])
            ras = trimesh.load(str(root / 'x_predicted_wm_lh_orig.stl'), process=False)
            np.testing.assert_allclose(ras.bounds, mesh.bounds)

    def test_white_only_does_not_require_pial(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for hemi in ('lh', 'rh'):
                trimesh.creation.icosphere(subdivisions=1).export(str(root / f'{hemi}.white.obj'))
            products, _ = native_products(root, 'x', 'wm')
            self.assertEqual(len(products), 2)

    def test_topology_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for kind, subdivisions in (('white', 1), ('pial', 2)):
                trimesh.creation.icosphere(subdivisions=subdivisions).export(str(root / f'lh.{kind}.obj'))
            with self.assertRaisesRegex(ValueError, 'correspondence'):
                native_products(root, 'x', 'all')

    def test_postprocess_cache_rejects_legacy_and_modified_surfaces(self):
        from shared.io_layout import subject_layout
        from shared.orchestrator import _surface_postprocess_complete
        from surface.postprocess_release import DDSurferPostprocessConfig, run_ddsurfer_postprocess
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'x'
            layout = subject_layout(root)
            native = layout.ddsurfer / 'pred_results_SlicerDDSurfer/native/x'
            native.mkdir(parents=True)
            for hemi in ('lh', 'rh'):
                for kind in ('white', 'pial'):
                    trimesh.creation.icosphere(subdivisions=1).export(str(native / f'{hemi}.{kind}.obj'))

            def fake_backend(command, **kwargs):
                output = Path(command[command.index('--output-root') + 1]) / 'x'
                for folder in ('logs', 'surf', 'label', 'mri', 'stats', 'fsaverage'):
                    (output / folder).mkdir(parents=True, exist_ok=True)
                (output / 'logs/qc.json').write_text('{}')
                (output / 'mri/brain.mgz').write_text('reference')
                for hemi in ('lh', 'rh'):
                    for kind in ('white', 'pial', 'inflated', 'sphere', 'curv'):
                        (output / 'surf' / f'{hemi}.{kind}').write_text('surface')
                    for atlas in ('aparc', 'aparc.a2009s'):
                        (output / 'label' / f'{hemi}.{atlas}.annot').write_text('annotation')
                        (output / 'stats' / f'{hemi}.{atlas}.stats').write_text('statistics')

            config = DDSurferPostprocessConfig('x', layout.outputs, subject_root=root, native_dir=native)
            with patch('surface.backend_bridge.run_backend', side_effect=fake_backend):
                result = run_ddsurfer_postprocess(config)
                original = json.loads(result.manifest_path.read_text())
                self.assertFalse(original['requires_ddparcel'])
                self.assertTrue(_surface_postprocess_complete(root, 'x'))
                self.assertFalse(_surface_postprocess_complete(root, 'x', atlases=('another_atlas',)))
                self.assertFalse(_surface_postprocess_complete(root, 'x', native_dir=root / 'another_run'))
                legacy = dict(original, upstream_commit='old-version')
                result.manifest_path.write_text(json.dumps(legacy))
                self.assertFalse(_surface_postprocess_complete(root, 'x'))
                result.manifest_path.write_text(json.dumps(original))
                with (native / 'lh.white.obj').open('a') as stream:
                    stream.write('\n# changed surface\n')
                self.assertFalse(_surface_postprocess_complete(root, 'x'))
                rerun = run_ddsurfer_postprocess(config)
                rerun_key = json.loads(rerun.manifest_path.read_text())['cache_key']
                self.assertNotEqual(rerun_key, original['cache_key'])
                self.assertTrue(_surface_postprocess_complete(root, 'x'))
                forced = run_ddsurfer_postprocess(DDSurferPostprocessConfig('x', layout.outputs,
                    subject_root=root, native_dir=native, force=True))
                self.assertNotEqual(json.loads(forced.manifest_path.read_text())['cache_key'],
                                    rerun_key)


if __name__ == '__main__':
    unittest.main()
