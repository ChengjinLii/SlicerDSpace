"""The Agent setup helper accepts selected preparation, never arbitrary execution."""

from pathlib import Path
import runpy
import unittest

HELPER = Path(__file__).resolve().parents[2] / '.agents/skills/slicerdspace/scripts/prepare_in_slicer.py'


class AgentSetupHelperTests(unittest.TestCase):
    def test_staged_resources_must_stay_outside_the_whole_extension(self):
        root = Path.home() / 'extensions/SlicerDSpace'
        module = root / 'lib/Slicer-5.10/qt-scripted-modules'
        lookup = runpy.run_path(str(HELPER))['extension_root']
        self.assertEqual(lookup(module), root.resolve())
        self.assertEqual(lookup(root), root.resolve())

    def setUp(self):
        self.validate = runpy.run_path(str(HELPER))['validate_request']
        self.request = dict(mode='plan', targets=['segmentation'], model_assets_dir=str(Path.home() / 'models'))

    def test_plan_is_the_default_and_storage_choice_is_explicit(self):
        self.assertIs(self.validate(self.request), self.request)
        self.request.pop('mode')
        self.validate(self.request)
        self.request.pop('model_assets_dir')
        with self.assertRaises(ValueError):
            self.validate(self.request)

    def test_invalid_requests_do_not_import_slicer_or_execute_code(self):
        for change in ({'mode': 'execute'}, {'targets': ['all']}, {'targets': 'segmentation'},
                       {'model_assets_dir': 'relative/cache'}, {'parameters': {'cleanup': 'yes'}},
                       {'parameters': {'ddsegDevice': []}}, {'prepare_mask': 'yes'}, {'accept_terms': True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(dict(self.request, **change))

    def test_multiple_selected_methods_and_explicit_mask_preparation(self):
        request = dict(self.request, mode='prepare', targets=['parcellation', 'tractography', 'wma', 'connectome'],
                       prepare_mask=True, parameters={'orchestrationTractographyBackend': 'ukf,csd_act',
                                                     'brainMaskBackend': 'pnl_cnn'})
        self.assertEqual(self.validate(request)['parameters'], request['parameters'])


if __name__ == '__main__':
    unittest.main()
