from __future__ import annotations

import hashlib
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.package_slicer_extension import package_extension


class PackageSlicerExtensionTest(unittest.TestCase):
    def test_package_is_rooted_and_excludes_runtime_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extension = root / "SlicerDDSurfer"
            module_dir = extension / "lib" / "Slicer-5.10" / "qt-scripted-modules"
            cache_dir = module_dir / "__pycache__"
            cache_dir.mkdir(parents=True)
            (module_dir / "SlicerDDSurfer.py").write_text("value = 1\n", encoding="utf-8")
            (cache_dir / "SlicerDDSurfer.pyc").write_bytes(b"cache")
            (extension / "SlicerDDSurfer.s4ext").write_text("scm git\n", encoding="utf-8")
            (extension / "extension_staging_manifest.json").write_text("{}\n", encoding="utf-8")
            archive_path = root / "packages" / "SlicerDDSurfer.tar.gz"

            result = package_extension(extension, archive_path)

            with tarfile.open(archive_path, "r:gz") as archive:
                names = archive.getnames()
            self.assertTrue(names)
            self.assertTrue(all(name == "SlicerDDSurfer" or name.startswith("SlicerDDSurfer/") for name in names))
            self.assertIn(
                "SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules/SlicerDDSurfer.py",
                names,
            )
            self.assertFalse(any("__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in names))
            self.assertNotIn("SlicerDDSurfer/extension_staging_manifest.json", names)
            self.assertEqual(result["archive_sha256"], hashlib.sha256(archive_path.read_bytes()).hexdigest())
            self.assertTrue(Path(str(result["manifest_path"])).is_file())


if __name__ == "__main__":
    unittest.main()
