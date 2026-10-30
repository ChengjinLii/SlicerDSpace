"""Official protocol, packaging, selection and honest coverage-status contracts."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


class OfficialWMQLTests(unittest.TestCase):
    def test_pinned_rules_are_packaged_unchanged_without_a_backend_checkout(self):
        from tractography.wmql import (bundled_wmql_query_path, AUTHOR_ALIAS_SHA256, AUTHOR_BUNDLE_QUERY_SHA256,
                                       wmql_query_dependencies, WMQLConfig)
        from scripts.extension_runtime.runtime_resources import runtime_files
        rules = bundled_wmql_query_path()
        self.assertEqual(hashlib.sha256(rules.read_bytes()).hexdigest(), AUTHOR_BUNDLE_QUERY_SHA256)
        self.assertEqual(hashlib.sha256((rules.parent / 'FreeSurfer.qry').read_bytes()).hexdigest(), AUTHOR_ALIAS_SHA256)
        self.assertEqual(len(wmql_query_dependencies(rules, [rules.parent])), 2)
        packaged = runtime_files(ROOT)
        self.assertIn(rules.relative_to(ROOT).as_posix(), packaged)
        self.assertIn((rules.parent / 'FreeSurfer.qry').relative_to(ROOT).as_posix(), packaged)
        self.assertEqual(WMQLConfig.__dataclass_fields__['query_preset'].default, 'official')
        self.assertEqual(WMQLConfig.__dataclass_fields__['query_selection'].default, ())

    def test_query_inventory_and_subsets(self):
        from tractography.wmql_protocol import official_query_names, canonical_wmql_selection
        names = official_query_names()
        self.assertEqual(len(names), 48)
        self.assertTrue({'af.left', 'uf.right', 'cc_4', 'slf_ii.left'} <= set(names))
        self.assertEqual(canonical_wmql_selection(''), ())
        self.assertEqual(canonical_wmql_selection('all'), ())
        self.assertEqual(canonical_wmql_selection('AF,cst.right,cc_4,af.left'),
                         ('af.left', 'af.right', 'cc_4', 'cst.right'))
        for bad in ('NOT_A_BUNDLE', 'all,AF', 'AF.rightt'):
            with self.assertRaisesRegex(ValueError, 'Unknown official WMQL query'):
                canonical_wmql_selection(bad)

    def test_missing_and_sparse_are_not_scientific_passes_but_not_corrupt_files(self):
        from tractography.wmql import _wmql_output_contract_error
        from tractography.wmql_protocol import bundle_assessment
        from shared.result_scene import record_qc_state
        summary = dict(bundle_count=1, bundle_readable_count=1, bundle_nonempty_count=1,
                       bundles=[dict(query_name='af.left', streamline_count=3)])
        requested = ('af.left', 'af.right')
        self.assertIsNone(_wmql_output_contract_error(summary, 2, requested, require_sampling=False))
        self.assertIsNotNone(_wmql_output_contract_error(summary, 2, requested))
        assessment = bundle_assessment(summary, requested, 20)
        self.assertEqual([b['state'] for b in assessment['bundles']], ['insufficient_sampling', 'not_extracted'])
        self.assertFalse(assessment['all_requested_sampling_passed'])
        qc = dict(kind='wmql_bundle_segmentation_qc', version=6, status='completed', official_multibundle=True,
                  execution_passed=True, output_integrity_passed=True, automatic_qc_passed=False,
                  bundle_assessment=assessment)
        self.assertEqual(record_qc_state(qc), 'warning')
        for field, value in [('status', 'failed'), ('error', 'broken'), ('output_integrity_passed', False),
                             ('checks', {'finite': False})]:
            self.assertEqual(record_qc_state(dict(qc, **{field: value})), 'failed')
        self.assertTrue(all(not b['quantification_eligible'] for b in assessment['bundles']))
        corrupt = dict(summary, bundle_readable_count=0)
        self.assertIsNotNone(_wmql_output_contract_error(corrupt, 2, requested, require_sampling=False))

    def test_atlas_labels_checked_without_manufacturing_regional_white_matter(self):
        from tractography.wmql_protocol import atlas_compatibility
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'labels.nii.gz'
            values = np.array([0, 2, 41, 16, 1001, 2001, 1024, 2024], np.int16).reshape(2, 2, 2)
            nib.save(nib.Nifti1Image(values, np.eye(4)), path)
            before = path.read_bytes()
            report = atlas_compatibility(path)
            self.assertFalse(report['anatomical_equivalence_verified'])
            self.assertEqual(report['regional_wm_ids'], [])
            self.assertTrue(report['warnings'])
            self.assertEqual(before, path.read_bytes())
            nib.save(nib.Nifti1Image((values > 0).astype(np.int16), np.eye(4)), path)
            with self.assertRaisesRegex(ValueError, 'regional label IDs'):
                atlas_compatibility(path)

    def test_subset_flows_through_single_and_batch_launch_commands(self):
        from shared.ui_run_controller import build_background_cli_args, build_batch_background_cli_args
        kwargs = dict(subject_root=Path('/tmp/subject'), subject_id='test', run_name='test', targets=('bundles',),
                      tractography_backend='csd_act', bundle_backend='wmql', connectome_backend='python',
                      select_streamlines=1000, ddseg_device='auto', surface_device='auto',
                      wmql_query_selection=('af.left', 'af.right'))
        commands = [build_background_cli_args(kwargs, {}, repo_root=ROOT),
                    build_batch_background_cli_args(kwargs, {}, repo_root=ROOT, batch_root=Path('/tmp/batch'),
                                                    batch_size=1, arrange_inputs='none')]
        for command in commands:
            self.assertEqual(command[command.index('--wmql-query-selection') + 1], 'af.left,af.right')
            self.assertEqual(command[command.index('--wmql-query-preset') + 1], 'official')
        from shared.run_subject_pipeline_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(['--subject-root', '/tmp/subject', '--subject-id', 'test',
                                  '--wmql-query-selection', 'AF,UF'])
        self.assertEqual(args.wmql_query_preset, 'official')
        self.assertEqual(args.wmql_query_selection, 'AF,UF')

    def test_ddparcel_callosal_192_does_not_satisfy_official_alias_requirements(self):
        from tractography.wmql_protocol import atlas_compatibility
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'labels.nii.gz'
            values = np.array([0, 2, 41, 192, 1001, 2001, 1024, 2024], np.int16).reshape(2, 2, 2)
            nib.save(nib.Nifti1Image(values, np.eye(4)), path)
            before = path.read_bytes()
            report = atlas_compatibility(path)
            self.assertEqual(report['label_semantics']['corpus_callosum_192_voxels'], 1)
            self.assertEqual(report['official_callosal_alias_label_ids'], {'left': [], 'right': []})
            self.assertEqual(report['official_queries_with_unavailable_required_labels'], ['cc', 'cc_5', 'cc_6'])
            self.assertTrue(any('label-convention mismatch' in warning for warning in report['warnings']))
            self.assertEqual(path.read_bytes(), before)
            for left, right in ((1004, 2004), (3004, 4004)):
                values.flat[0] = left
                values.flat[3] = right
                nib.save(nib.Nifti1Image(values, np.eye(4)), path)
                report = atlas_compatibility(path)
                self.assertEqual(report['official_callosal_alias_label_ids'], {'left': [left], 'right': [right]})
                self.assertEqual(report['official_queries_with_unavailable_required_labels'], [])
            values.flat[3] = 192
            nib.save(nib.Nifti1Image(values, np.eye(4)), path)
            report = atlas_compatibility(path)
            self.assertEqual(report['official_queries_with_unavailable_required_labels'], ['cc_5', 'cc_6'])
            # cc_4 uses endpoint regions, not the callosal aliases.
            self.assertNotIn('cc_4', report['official_queries_with_unavailable_required_labels'])


if __name__ == '__main__':
    unittest.main()
