"""Archive fixtures exercise layout only; they are not SDK-produced packages."""

import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

from scripts.extension_runtime.archive_layout import inspect_archive_layout


class ArchiveLayoutTest(unittest.TestCase):
    def test_cpack_style_tgz_and_zip_roots_are_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = "test-cpack-style-root/lib/Slicer-5.10/qt-scripted-modules/"
            tgz = root / "fixture.tar.gz"
            with tarfile.open(tgz, "w:gz") as stream:
                item = tarfile.TarInfo(base + "SlicerDDSurfer.py")
                item.size = 1
                stream.addfile(item, io.BytesIO(b"x"))
            self.assertEqual(inspect_archive_layout(tgz)["status"], "pass")
            archive = root / "fixture.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr(base + "SlicerDDSurfer.py", "x")
                stream.writestr(base + "SlicerDDSurfer.pyc", "compiled fixture")
            result = inspect_archive_layout(archive)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["bytecode_count"], 1)

    def test_unsafe_paths_and_multiple_modules_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "fixture.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                for name in ("one/qt-scripted-modules/SlicerDDSurfer.py",
                             "two/qt-scripted-modules/SlicerDDSurfer.py", "../escape"):
                    stream.writestr(name, "x")
            result = inspect_archive_layout(archive)
            self.assertEqual(result["status"], "fail")
            self.assertIn("../escape", result["unsafe"])

    def test_development_tree_and_missing_module_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "fixture.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("lib/qt-scripted-modules/SlicerDDSurfer.py", "x")
                stream.writestr("lib/qt-scripted-modules/tests/test_fixture.py", "x")
            self.assertEqual(inspect_archive_layout(archive)["status"], "fail")
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("README.txt", "not a module")
            self.assertEqual(inspect_archive_layout(archive)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
