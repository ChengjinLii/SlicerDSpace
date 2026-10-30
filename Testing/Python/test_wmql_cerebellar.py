"""Regional selection contracts, independent audit, and optional author parity."""

from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import audit_wmql_cerebellar as audit

QUERY_DIR = ROOT / 'tractography/wmql_queries'
ALIASES = QUERY_DIR / 'official/FreeSurfer.qry'


def label_cases():
    left = [8] + [7] * 50 + [16] * 50
    return {
        'left': left,
        'right': [47, 46, 16],
        'bilateral': [8, 7, 16, 46, 47],
        'brainstem_only': [16] * 101,
        'no_brainstem': [8, 7, 7],
        'no_cerebellar_wm': [8, 16, 16],
        'no_cerebellar_endpoint': [16, 7, 16],
        'wm_endpoint': [7, 7, 16],
        'same_cerebellar_endpoints': [8, 7, 16, 8],
        'opposite_endpoint_below_threshold': left[:-1] + [47],
        'supratentorial_endpoint_below_threshold': left[:-1] + [1024],
        'hippocampal_endpoint_below_threshold': left[:-1] + [17],
        'one_brief_interior_supra': [8, 1024] + [7] * 49 + [16] * 49 + [8],
        'two_brief_different_labels': [8, 1024, 2024] + [7] * 48 + [16] * 49 + [8],
        'two_percent_supra': [8, 1024, 1024] + [7] * 48 + [16] * 48 + [8],
        'opposite_crossing': [8, 7, 16, 46, 8],
        'bilateral_missing_right_wm': [8, 7, 16, 47],
        'bilateral_supratentorial': [8, 7, 16, 46, 49, 47],
        'generic_wm_crossing': [8, 7, 2, 16],
        'regional_wm_crossing': [8, 7, 3024, 16],
    }


class PredicateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.supra = audit.supratentorial_labels(ALIASES)

    def test_independent_regional_membership(self):
        expected = {
            'left': {'cerebellar_brainstem.left'},
            'right': {'cerebellar_brainstem.right'},
            'bilateral': {'cerebellar_bilateral'},
            'wm_endpoint': {'cerebellar_brainstem.left'},
            'same_cerebellar_endpoints': {'cerebellar_brainstem.left'},
            'one_brief_interior_supra': {'cerebellar_brainstem.left'},
            'two_brief_different_labels': {'cerebellar_brainstem.left'},
        }
        for name, labels in label_cases().items():
            with self.subTest(name=name):
                self.assertEqual(audit.regional_predicates(labels, 2, self.supra), expected.get(name, set()))

    def test_all_explicit_deep_exclusions_and_wildcards(self):
        required = {2, 41, 3, 42, 9, 48, 10, 49, 11, 50, 12, 51, 13, 52,
                    26, 58, 28, 60, 17, 53, 18, 54, 1024, 2024, 3024, 4024}
        self.assertTrue(required <= self.supra)
        self.assertTrue({7, 8, 16, 46, 47}.isdisjoint(self.supra))
        for label in required:
            with self.subTest(label=label):
                self.assertFalse(audit.regional_predicates([8, 7, label, 16], 2, self.supra))

    def test_threshold_is_inclusive_and_per_numeric_label(self):
        self.assertIn(1024, audit.crossing_labels([1024] * 2 + [16] * 98, 2))
        self.assertNotIn(1024, audit.crossing_labels([1024] + [16] * 99, 2))
        self.assertTrue({1024, 2024}.isdisjoint(audit.crossing_labels([1024, 2024] + [16] * 98, 2)))
        self.assertIn(7, audit.crossing_labels([16, 16], 0))
        for threshold in (-1, 101, float('nan')):
            with self.assertRaises(ValueError):
                audit.crossing_labels([7, 16], threshold)

    def test_rounding_ties_clipping_and_nonidentity_affine(self):
        labels = np.arange(5, dtype=np.int16).reshape(5, 1, 1)
        affine = np.array([[2, 0, 0, 20], [0, 3, 0, -10], [0, 0, 4, 3], [0, 0, 0, 1.]])
        voxels = np.array([[-1, 0, 0], [.5, 0, 0], [1.5, 0, 0], [2.5, 0, 0], [8, 0, 0]])
        points = voxels @ affine[:3, :3].T + affine[:3, 3]
        sampled, outside = audit.sample_labels(points, labels, np.linalg.inv(affine))
        np.testing.assert_array_equal(sampled, [0, 0, 2, 2, 4])
        self.assertEqual(outside, 2)


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.a = np.array([[1., 2., 3.], [2., 3., 4.], [4., 5., 6.]])
        self.b = self.a + [0, .01, 0]

    def test_counter_preserves_duplicates_and_direction(self):
        index = audit.GeometryIndex([self.a, self.a, self.b])
        self.assertTrue(index.compare([self.b[::-1], self.a, self.a[::-1]])['exact_multiset_equal'])
        result = index.compare([self.a, self.b, self.b])
        self.assertFalse(result['passed'])
        self.assertEqual(result['missing_count'], 1)
        self.assertEqual(result['excess_count'], 1)
        self.assertFalse(index.compare([self.a] * 3, subset=True)['passed'])

    def test_ascii_tolerance_matches_full_interior_not_just_endpoints(self):
        index = audit.GeometryIndex([self.a, self.b])
        self.assertTrue(index.compare([self.b[::-1] + 1e-5, self.a + 1e-5])['passed'])
        changed = self.a.copy()
        changed[1, 0] += .01
        self.assertFalse(index.compare([changed, self.b])['passed'])
        self.assertFalse(index.compare([self.a[:2], self.b])['passed'])

    def test_ambiguous_matches_use_one_to_one_assignment(self):
        index = audit.GeometryIndex([self.a, self.a + .0015])
        self.assertTrue(index.compare([self.a + .00075, self.a - .00075])['passed'])
        self.assertTrue(index.compare([self.a + 1e-5], subset=True)['passed'])

    def test_invalid_geometry_is_not_a_membership_pass(self):
        bad = self.a.copy()
        bad[1, 0] = np.nan
        self.assertFalse(audit.GeometryIndex([self.a]).compare([bad])['finite_geometry'])
        self.assertFalse(audit.GeometryIndex([bad]).compare([self.a])['passed'])
        self.assertTrue(audit.GeometryIndex([]).compare([])['passed'])
        self.assertFalse(audit.GeometryIndex([]).compare([self.a])['passed'])


class InventoryTests(unittest.TestCase):
    def test_default_48_and_opt_in_3_51(self):
        from tractography.wmql import WMQLConfig, bundled_wmql_query_path
        from tractography.wmql_protocol import CATALOG_PRESETS, official_query_names, preset_query_names
        self.assertEqual(CATALOG_PRESETS, ('official', 'cerebellar', 'official_cerebellar'))
        official = set(official_query_names())
        regional = set(audit.NAMES)
        self.assertEqual(len(official), 48)
        self.assertEqual(set(preset_query_names()), official)
        self.assertEqual(set(preset_query_names('cerebellar')), regional)
        self.assertEqual(set(preset_query_names('official_cerebellar')), official | regional)
        self.assertEqual(len(preset_query_names('official_cerebellar')), 51)
        self.assertEqual(WMQLConfig.__dataclass_fields__['query_preset'].default, 'official')
        self.assertEqual(bundled_wmql_query_path().name, 'freesurfer_queries.qry')
        self.assertEqual(audit.digest(bundled_wmql_query_path()), audit.OFFICIAL_SHA256)

    def test_selections_are_scoped_to_the_selected_catalogue(self):
        from tractography.wmql_protocol import canonical_wmql_selection
        for preset in ('official', 'cerebellar', 'official_cerebellar'):
            self.assertEqual(canonical_wmql_selection('', preset), ())
            self.assertEqual(canonical_wmql_selection('ALL', preset), ())
        self.assertEqual(canonical_wmql_selection('CEREBELLAR_BRAINSTEM', 'cerebellar'),
                         ('cerebellar_brainstem.left', 'cerebellar_brainstem.right'))
        selection = canonical_wmql_selection('AF,CEREBELLAR_BILATERAL,cst.right', 'official_cerebellar')
        self.assertEqual(selection, ('af.left', 'af.right', 'cerebellar_bilateral', 'cst.right'))
        for selection, preset in (('cerebellar_bilateral', 'official'), ('CST', 'cerebellar'),
                                  ('ICP', 'official_cerebellar'), ('all,AF', 'official_cerebellar')):
            with self.assertRaises(ValueError):
                canonical_wmql_selection(selection, preset)


class OptionalAuthorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        backend = ROOT / 'third_party/tract_querier'
        if not (backend / 'tract_querier/__init__.py').is_file():
            raise unittest.SkipTest('Optional author parser checkout is absent')
        sys.path.insert(0, str(backend))
        cls.addClassCleanup(sys.path.pop, 0)
        try:
            import tract_querier
        except ModuleNotFoundError as exc:
            raise unittest.SkipTest('Optional author parser dependency is absent: ' + str(exc))
        cls.author = tract_querier

    def index(self, sequences):
        crossed, endings = defaultdict(set), (defaultdict(set), defaultdict(set))
        track_labels, endpoint_labels = {}, ({}, {})
        for i, labels in enumerate(sequences):
            # The independent test fixture does not call the audit's predicate/indexer.
            counts = np.bincount(labels)
            track_labels[i] = set(np.where(counts / float(len(labels)) >= .02)[0])
            for label in track_labels[i]:
                crossed[label].add(i)
            for end, label in enumerate((labels[0], labels[-1])):
                endings[end][label].add(i)
                endpoint_labels[end][i] = label
        return SimpleNamespace(crossing_labels_tracts=crossed, crossing_tracts_labels=track_labels,
                               ending_labels_tracts=endings, ending_tracts_labels=endpoint_labels,
                               label_bounding_boxes={})

    def evaluate(self, filename, index, details=False):
        import ast
        body = self.author.queries_preprocess((QUERY_DIR / filename).read_text(),
                                             include_folders=[str(QUERY_DIR), str(QUERY_DIR / 'official')])
        if details:
            evaluator = self.author.EvaluateQueries(index)
            evaluator.visit(ast.Module(body=body, type_ignores=[]))
            return evaluator
        return self.author.eval_queries(body, index)

    def test_independent_predicates_match_actual_author_rules(self):
        cases = list(label_cases().values())
        actual = self.evaluate('cerebellar.qry', self.index(cases))
        supra = audit.supratentorial_labels(ALIASES)
        expected = {name: {i for i, values in enumerate(cases) if name in audit.regional_predicates(values, 2, supra)}
                    for name in audit.NAMES}
        self.assertEqual(actual, expected)
        self.assertEqual(set(actual), set(audit.NAMES))

    def test_combined_keeps_nonempty_cst_and_all_48_author_outputs(self):
        sequences = [[1024, 2, 16], [2024, 41, 16], *label_cases().values()]
        index = self.index(sequences)
        official = self.evaluate('official/freesurfer_queries.qry', index, details=True)
        combined = self.evaluate('official_cerebellar.qry', index, details=True)
        self.assertEqual(len(official.queries_to_save), 48)
        self.assertEqual(len(combined.queries_to_save), 51)
        for side, number in (('left', 0), ('right', 1)):
            name = 'cst.' + side
            self.assertIn(number, official.evaluated_queries_info[name].tracts)
            self.assertNotIn(16, official.evaluated_queries_info['hemisphere.' + side].labels)
            self.assertEqual(official.evaluated_queries_info['hemisphere.' + side].labels,
                             combined.evaluated_queries_info['hemisphere.' + side].labels)
        for name in official.queries_to_save:
            with self.subTest(query=name):
                self.assertEqual(official.evaluated_queries_info[name].tracts,
                                 combined.evaluated_queries_info[name].tracts)


@unittest.skipUnless(importlib.util.find_spec('vtk') and importlib.util.find_spec('nibabel'), 'Optional neuroimaging IO is absent')
class AuditIntegrationTests(unittest.TestCase):
    def setUp(self):
        import nibabel as nib
        self.temp = tempfile.TemporaryDirectory(prefix='private-patient-audit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        snapshot = self.root / 'queries'
        snapshot.mkdir()
        for source in (QUERY_DIR / 'cerebellar.qry', QUERY_DIR / 'cerebellar_regions.qry', ALIASES):
            shutil.copy2(source, snapshot / source.name)
        self.affine = np.array([[2, 0, 0, 20], [0, 3, 0, -10], [0, 0, 4, 3], [0, 0, 0, 1.]])
        data = np.zeros((7, 6, 3), dtype=np.int16)
        tracks = []
        for row, values in enumerate(([8, 7, 16], [47, 46, 16], [8, 7, 16, 46, 47]), start=1):
            data[:len(values), row, 1] = values
            voxels = np.column_stack((np.arange(len(values)), np.full(len(values), row), np.ones(len(values))))
            tracks.append(voxels @ self.affine[:3, :3].T + self.affine[:3, 3])
        self.atlas = self.root / 'private-patient-labels.nii.gz'
        nib.save(nib.Nifti1Image(data, self.affine), self.atlas)
        self.source = self.root / 'private-patient-source.vtk'
        self.write_vtk(self.source, tracks)
        entries = []
        for name, track in zip(('cerebellar_brainstem.left', 'cerebellar_brainstem.right', 'cerebellar_bilateral'), tracks):
            output = self.root / ('private-patient_desc-wmql_' + name + '.vtk')
            self.write_vtk(output, [track])
            entries.append(dict(query_name=name, path=str(output)))
        self.manifest = dict(kind='wmql_bundle_segmentation', status='completed', executed=True,
                             subject_id='private-patient', input_tractography=str(self.source), atlas_path=str(self.atlas),
                             staged_query=str(snapshot / 'cerebellar.qry'), query_path=str(QUERY_DIR / 'cerebellar.qry'),
                             query_snapshot_dependencies={str(p): audit.digest(p) for p in snapshot.glob('*.qry')},
                             requested_queries=list(audit.NAMES), threshold=2., length_threshold=0.,
                             outputs=dict(summary=dict(bundles=entries)))
        self.manifest_path = self.root / 'wmql_manifest.json'
        self.save_manifest()

    def save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def write_vtk(self, path, tracks):
        import vtk
        points, lines = vtk.vtkPoints(), vtk.vtkCellArray()
        points.SetDataTypeToDouble()
        for track in tracks:
            line = vtk.vtkPolyLine()
            line.GetPointIds().SetNumberOfIds(len(track))
            for i, point in enumerate(track):
                line.GetPointIds().SetId(i, points.InsertNextPoint(*point))
            lines.InsertNextCell(line)
        data = vtk.vtkPolyData()
        data.SetPoints(points)
        data.SetLines(lines)
        writer = vtk.vtkPolyDataWriter()
        writer.SetFileName(str(path))
        writer.SetInputData(data)
        writer.SetFileTypeToBinary()
        self.assertEqual(writer.Write(), 1)

    def test_actual_manifest_source_and_affine_with_private_free_receipt(self):
        report = audit.audit(self.manifest_path, minimum=1)
        self.assertTrue(all(report['checks'].values()), report['checks'])
        self.assertEqual(report['source_summary']['streamlines'], 3)
        np.testing.assert_array_equal(report['atlas_geometry']['affine'], self.affine)
        self.assertEqual({r['query_name']: r['expected_count'] for r in report['bundles']}, dict.fromkeys(audit.NAMES, 1))
        public = json.dumps(audit.public_receipt(report))
        self.assertNotIn('private-patient', public)
        self.assertNotIn(str(self.root), public)
        self.assertNotIn(str(ROOT), public)
        self.assertFalse(report['quantification_eligible'])
        self.assertEqual(report['human_review'], 'pending')

    def test_sampling_is_separate_from_predicate_and_geometry_integrity(self):
        report = audit.audit(self.manifest_path)
        self.assertFalse(report['checks']['all_minimum_streamlines'])
        self.assertTrue(report['checks']['full_expected_source_multisets_match'])
        self.assertEqual(report['status'], 'needs_review')

    def test_missing_output_is_compared_to_full_expected_set(self):
        entry = self.manifest['outputs']['summary']['bundles'].pop()
        Path(entry['path']).unlink()
        self.save_manifest()
        report = audit.audit(self.manifest_path, minimum=1)
        self.assertFalse(report['checks']['full_expected_source_multisets_match'])
        bilateral = next(r for r in report['bundles'] if r['query_name'] == 'cerebellar_bilateral')
        self.assertEqual(bilateral['expected_count'], 1)
        self.assertEqual(bilateral['actual_count'], 0)

    def test_source_membership_alone_does_not_establish_query_membership(self):
        entries = self.manifest['outputs']['summary']['bundles']
        shutil.copyfile(entries[1]['path'], entries[0]['path'])
        report = audit.audit(self.manifest_path, minimum=1)
        self.assertTrue(report['checks']['all_outputs_from_source'])
        self.assertFalse(report['checks']['full_expected_source_multisets_match'])
        self.assertFalse(report['checks']['output_regional_predicates_pass'])

    def test_outside_fov_source_is_clipped_but_flagged(self):
        tracks = list(audit.tracks_from_file(self.source))
        voxels = np.array([[100., 4, 1], [101., 4, 1]])
        tracks.append(voxels @ self.affine[:3, :3].T + self.affine[:3, 3])
        self.write_vtk(self.source, tracks)
        report = audit.audit(self.manifest_path, minimum=1)
        self.assertTrue(report['checks']['full_expected_source_multisets_match'])
        self.assertFalse(report['checks']['no_outside_fov_points'])
        self.assertEqual(report['source_summary']['outside_fov_tracks'], 1)
        self.assertEqual(report['source_summary']['outside_fov_points'], 2)

    def test_mutated_snapshot_is_rejected_before_audit(self):
        path = Path(self.manifest['staged_query']).with_name('cerebellar_regions.qry')
        path.write_text(path.read_text() + '\n# modified\n')
        with self.assertRaisesRegex(ValueError, 'snapshot hashes'):
            audit.audit(self.manifest_path)

    def test_unsupported_recorded_rule_is_not_a_false_pass(self):
        path = Path(self.manifest['staged_query']).with_name('cerebellar_regions.qry')
        path.write_text(path.read_text().replace('both_endpoints_in', 'endpoints_in'))
        self.manifest['query_snapshot_dependencies'][str(path)] = audit.digest(path)
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'Unsupported regional predicate'):
            audit.audit(self.manifest_path)

    def test_invalid_affine_and_fractional_labels_are_rejected(self):
        import nibabel as nib
        image = nib.load(self.atlas)
        data = image.get_fdata()
        data[0, 0, 0] = .5
        nib.save(nib.Nifti1Image(data, image.affine), self.atlas)
        with self.assertRaisesRegex(ValueError, 'integer labels'):
            audit.audit(self.manifest_path)
        invalid = SimpleNamespace(shape=(3, 3, 3), affine=np.zeros((4, 4)))
        with self.assertRaisesRegex(ValueError, 'nonsingular affine'):
            audit.atlas_geometry(invalid)


class LauncherTests(unittest.TestCase):
    def test_cli_and_gui_normalization_accept_regional_names_only_in_the_selected_presets(self):
        import contextlib
        import io
        from types import SimpleNamespace
        from unittest.mock import patch
        from shared.run_subject_pipeline_cli import main
        from shared.ui_run_controller import _wmql_selection
        expected = ('cerebellar_brainstem.left', 'cerebellar_brainstem.right')
        for preset in ('cerebellar', 'official_cerebellar'):
            self.assertEqual(_wmql_selection('cerebellar_brainstem', preset), expected)
            captured = []
            with tempfile.TemporaryDirectory() as temporary:
                def plan(config, write=True):
                    captured.append(config)
                    return SimpleNamespace(run_plan_path=Path(temporary) / 'plan.json', to_dict=lambda: {})
                with patch('shared.run_subject_pipeline_cli.plan_subject_products', side_effect=plan), contextlib.redirect_stdout(io.StringIO()):
                    code = main(['--no-user-config', '--subject-root', temporary, '--targets', 'bundles',
                                 '--wmql-query-preset', preset, '--wmql-query-selection', 'cerebellar_brainstem',
                                 '--plan', '--skip-environment-check'])
            self.assertEqual(code, 0)
            self.assertEqual(captured[0].wmql_query_preset, preset)
            self.assertEqual(captured[0].wmql_query_selection, ('cerebellar_brainstem',))


if __name__ == '__main__':
    unittest.main()
