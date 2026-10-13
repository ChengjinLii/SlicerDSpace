"""Independent geometric fixtures for documented SAF port corrections."""

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tractography/saf_backend'))


class SAFScientificPortTest(unittest.TestCase):
    def test_multiple_asymmetric_tracks_choose_their_own_endpoint_vertices(self):
        from Testing.Python.saf_reference_acceptance import fixture
        from Filters.streamlineXmesh.crop_streamlines_outside_mesh_fast import crop_streamlines_outside_mesh_fast
        from Filters.streamlineXmesh.crop_streamlines_outside_mesh_complete import crop_streamlines_outside_mesh_complete

        data = fixture()
        for crop in (crop_streamlines_outside_mesh_fast, crop_streamlines_outside_mesh_complete):
            with self.subTest(mode=crop.__name__):
                _, _, vertices, _ = crop(data['vertices'], data['faces'] - 1, list(data['tracks'].flat), False, False)
                np.testing.assert_array_equal(vertices, [[1, 5, 4, 8, 3, 7], [2, 6, 4, 8, 3, 7]])

    def test_missing_crossing_keeps_zero_and_does_not_shift_other_endpoints(self):
        from Filters.streamlineXmesh.endpoint_vertices import closest_endpoint_vertices

        vertices = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.],
                             [10., 0., 0.], [11., 0., 0.], [10., 1., 0.]])
        faces = np.array([[0, 1, 2], [3, 4, 5]])
        tracks = [np.array([[.05, .05, .1], [1., .02, .1]]),
                  np.array([[10., 1., .1], [11., .02, .1]])]
        result = closest_endpoint_vertices(vertices, faces, tracks, np.array([[np.nan, 1], [0, 1]]))
        np.testing.assert_array_equal(result, [[0, 6], [2, 5]])

    def test_rejected_short_tracks_preserve_original_indices(self):
        import Filters.filters_GG_HH as module

        tracks = [np.zeros((1, 3)), np.zeros((3, 3)), np.zeros((2, 3))]
        dwi = SimpleNamespace(sl_tracks=tracks, cv=np.array([[0., 0., 0.]]), cvk=np.ones(1),
                              cvt=np.ones(1), cvh=np.ones(1, dtype=bool), cvi=np.array([17]), saf=SimpleNamespace())
        ps = SimpleNamespace(force=False, gg_margin=0., dgn=False, quiet=True, logt=[])
        with mock.patch.object(module, 'find_closest_vertex', return_value=(np.ones(2, dtype=int), np.zeros(2))):
            module.filters_GG_HH(ps, SimpleNamespace(DWI=dwi))
        np.testing.assert_array_equal(dwi.saf.t_gghh, [[0, 17, 0], [0, 17, 0]])
        np.testing.assert_array_equal(dwi.saf.h, [[False, True, False], [False, True, False]])
        self.assertEqual(dwi.saf.m.shape, (2, 3))

    def test_all_short_tracks_do_not_call_clustering(self):
        import Filters.filters_GG_HH as module

        dwi = SimpleNamespace(sl_tracks=[np.zeros((2, 3))], saf=SimpleNamespace())
        with mock.patch.object(module, 'coordinate_clustering') as clustering:
            module.filters_GG_HH(SimpleNamespace(), SimpleNamespace(DWI=dwi))
        clustering.assert_not_called()
        np.testing.assert_array_equal(dwi.saf.t_gghh, np.zeros((2, 1)))

    def test_hard_split_weights_use_original_not_filtered_indices(self):
        import Filters.filters_saf as module

        saf = SimpleNamespace(t_gwg=np.array([[1, 0, 2], [3, 0, 4]]),
                              t_gghh=np.array([[0, 0, 1, 0, 2], [0, 0, 3, 0, 4]]),
                              pg=np.zeros(5, dtype=bool), pre_c=np.array([4, 2, 4]))
        tracks = [np.array([[0., 0., 0.], [1., 0., 0.]])] * 3
        dwi = SimpleNamespace(saf=saf, sl_tracks=tracks, sl_info={}, sl_weights='pre_GWG.wts')
        with tempfile.TemporaryDirectory() as directory:
            ps = SimpleNamespace(work_dir=directory, logt=[])
            with mock.patch.object(module, 'read_tsf', return_value=np.array([7., 11.])), \
                 mock.patch.object(module, 'write_tsf') as write, \
                 mock.patch.object(module, 'write_mrtrix_tracks'):
                module.filters_saf(ps, dwi)
        np.testing.assert_array_equal(saf.w, [11., 11.])
        np.testing.assert_array_equal(write.call_args.args[0], [11., 11.])

    def test_pial_filter_skips_empty_hemispheres(self):
        import Filters.filters_PG as module

        mesh = SimpleNamespace(pial=np.zeros((3, 3)), faces=np.array([[0, 1, 2]]), usedv=np.ones(3, dtype=bool))
        saf = SimpleNamespace(t_gghh=np.zeros((2, 0)), h=np.zeros((2, 0), dtype=bool), pg=None)
        dwi = SimpleNamespace(rh=mesh, lh=mesh, saf=saf, sl_tracks=[])
        ps = SimpleNamespace(force=True, pialfilter=True, fastx=True, quiet=True, logt=[])
        with mock.patch.object(module, 'crop_streamlines_outside_mesh_fast') as crop:
            module.filters_PG(ps, dwi)
        crop.assert_not_called()
        self.assertEqual(saf.pg.size, 0)

    def test_pial_filter_rejects_source_when_no_chain_survives(self):
        import Filters.filters_PG as module

        mesh = SimpleNamespace(pial=np.zeros((3, 3)), faces=np.array([[0, 1, 2]]), usedv=np.ones(3, dtype=bool))
        saf = SimpleNamespace(t_gghh=np.ones((2, 1)), h=np.ones((2, 1), dtype=bool), pg=None)
        dwi = SimpleNamespace(rh=mesh, lh=mesh, saf=saf, sl_tracks=[np.zeros((3, 3))])
        ps = SimpleNamespace(force=True, pialfilter=True, fastx=True, quiet=True, logt=[])
        with mock.patch.object(module, 'crop_streamlines_outside_mesh_fast', side_effect=AssertionError('No streamlines have survived GWG filtering')):
            module.filters_PG(ps, dwi)
        np.testing.assert_array_equal(saf.pg, [True])

    def test_resume_rejects_legacy_or_different_implementation(self):
        from shared.orchestrator import _saf_complete
        from tractography.saf_backend.provenance import implementation_record

        qc = {'status': 'completed', 'streamline_count': 1,
              'scientific_output_summary': {'streamline_count': 1, 'all_points_finite': True, 'length_mm': {'max': 20.}}}
        manifest = {'status': 'completed', 'parameters': {'maxlen': 40.}}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'SAF.tck').write_text('test fixture')
            (out / 'SAF.vtk').write_text('test fixture')
            def save():
                (out / 'saf_qc.json').write_text(json.dumps(qc))
                (out / 'saf_manifest.json').write_text(json.dumps(manifest))
            save()
            with mock.patch('shared.orchestrator.tractography_readable', return_value=True):
                self.assertFalse(_saf_complete(out))
                qc['implementation'] = implementation_record()
                manifest['implementation'] = implementation_record()
                save()
                self.assertTrue(_saf_complete(out))
                manifest['implementation']['revision'] = 'older'
                save()
                self.assertFalse(_saf_complete(out))


if __name__ == '__main__':
    unittest.main()
