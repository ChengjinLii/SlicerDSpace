"""Reject invalid acceptance invocations before installing or launching Slicer."""

from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.slicer_acceptance import main


class SlicerAcceptanceArgumentTests(unittest.TestCase):
    def test_missing_bundle_configuration_fails_before_runtime_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments = ['acceptance', '--report', temporary, '--slicer', 'Slicer', '--xvfb', 'xvfb-run',
                         '--assets', temporary, '--subject', temporary, '--tests', 'bundle_products']
            with patch('sys.argv', arguments), patch('scripts.slicer_acceptance.run') as run, redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main()
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()

    def test_nonexistent_assets_fail_before_runtime_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments = ['acceptance', '--report', temporary, '--slicer', 'Slicer', '--xvfb', 'xvfb-run',
                         '--assets', str(Path(temporary) / 'missing'), '--subject', temporary, '--tests', 'extension_install']
            with patch('sys.argv', arguments), patch('scripts.slicer_acceptance.run') as run, redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit):
                    main()
            run.assert_not_called()

    def test_nonexistent_package_fails_before_runtime_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments = ['acceptance', '--report', temporary, '--slicer', 'Slicer', '--xvfb', 'xvfb-run',
                         '--assets', temporary, '--subject', temporary, '--tests', 'extension_manager_install',
                         '--extension-archive', str(Path(temporary) / 'missing.tar.gz')]
            with patch('sys.argv', arguments), patch('scripts.slicer_acceptance.run') as run, redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit):
                    main()
            run.assert_not_called()

    def test_supplied_package_is_forwarded_without_replacing_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / 'cpack.tar.gz'
            archive.touch()
            arguments = ['acceptance', '--report', temporary, '--slicer', 'Slicer', '--xvfb', 'xvfb-run',
                         '--assets', temporary, '--subject', temporary, '--tests', 'extension_manager_install',
                         '--extension-archive', str(archive)]
            with patch('sys.argv', arguments), patch('scripts.slicer_acceptance.run', return_value=0) as run:
                self.assertEqual(main(), 0)
            self.assertEqual(run.call_args.args[0].extension_archive, archive)


if __name__ == '__main__':
    unittest.main()
