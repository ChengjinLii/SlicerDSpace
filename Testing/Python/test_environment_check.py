"""The GUI worker must preserve the synchronous doctor's exact contract."""

from pathlib import Path
import tempfile
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from shared.environment import DependencyStatus, EnvironmentDoctorResult, TargetEnvironmentStatus
from shared.environment_check import check_config, config_from_dict, result_from_dict
from shared.ui_input_defaults import subject_folder_defaults


class EnvironmentCheckTests(unittest.TestCase):
    def test_unavailable_report_directory_is_inline_error_without_worker(self):
        from shared.ui_environment_check import start_environment_check
        states, failures = [], []
        owner = SimpleNamespace(_pipelineActive=False,
            _update_environment_result_label=lambda *args: None,
            _environment_check_kwargs=lambda: {}, _environment_check_signature=lambda options: (),
            _environment_report_dir_from_kwargs=lambda options: None,
            _setStatus=lambda *args: states.append(args), appendLog=lambda message: None)
        with patch.dict(sys.modules, {'slicer': SimpleNamespace()}), \
                patch('shared.ui_setup_jobs.start_setup_job') as start:
            self.assertFalse(start_environment_check(owner, on_failure=lambda *args: failures.append(args)))
        start.assert_not_called()
        self.assertEqual(states[-1][0], 'error')
        self.assertEqual(failures[-1][0], 'failed')
        self.assertIn('writable output directory', states[-1][1])

    def test_selected_options_survive_serialization_without_subject_argument_leaks(self):
        import json
        values = check_config({'targets': ('validation', 'microstructure_noddi'), 'subject_root': Path('/subject'),
                               'model_assets_dir': Path('/assets'), 'python_path_entries': (Path('/python'),),
                               'microstructure_run_noddi': True, 'microstructure_run_dki': True,
                               'dki_fit_method': 'MKCURVE', 'tractography_backend': 'csd_act,ukf'},
                              repo_root=Path('/repo'), output_dir=Path('/reports'), loaded_modules=('dwitodtiestimation',))
        config = config_from_dict(json.loads(json.dumps(values, default=str)))
        self.assertEqual(config.model_assets_dir, Path('/assets'))
        self.assertEqual(config.python_path_entries, (Path('/python'),))
        self.assertEqual(config.loaded_slicer_modules, ('dwitodtiestimation',))
        self.assertEqual(config.tractography_backend, 'csd_act,ukf')
        self.assertTrue(config.run_noddi and config.run_dki)
        self.assertFalse(config.run_free_water)
        self.assertEqual(config.dki_fit_method, 'MKCURVE')

    def test_result_roundtrip_retains_failures_details_and_target_readiness(self):
        report = EnvironmentDoctorResult('linux', 'Linux', '/python', ('validation',),
            (DependencyStatus('test', 'path', 'model', 'missing', True, ('validation',), {'reason': 'absent'}),),
            (TargetEnvironmentStatus('validation', 'blocked', ('test',), ()),), 1, ('numpy',), ('models',))
        decoded = result_from_dict(report.to_dict())
        self.assertEqual(decoded, report)
        self.assertEqual(decoded.blocked_targets, ('validation',))
        with self.assertRaises(ValueError):
            result_from_dict({'kind': 'other', 'version': 1})

    def test_folder_picker_only_fills_empty_id_and_handles_canonical_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            subject = Path(tmp) / 'sub-01'
            inputs = subject / 'input'
            inputs.mkdir(parents=True)
            for name in ('data.nii.gz', 'bvals', 'bvecs'):
                (inputs / name).touch()
            self.assertEqual(subject_folder_defaults(str(inputs)), (str(subject), 'sub-01'))
            self.assertEqual(subject_folder_defaults(str(subject), 'custom'), (str(subject), 'custom'))
            self.assertEqual(subject_folder_defaults(str(inputs), batch=True), (str(inputs), ''))
            self.assertEqual(subject_folder_defaults('/not/a/directory', 'custom'), ('/not/a/directory', 'custom'))


if __name__ == '__main__':
    unittest.main()
