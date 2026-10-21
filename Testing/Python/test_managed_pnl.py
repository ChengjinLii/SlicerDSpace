"""Pinned PNL acquisition, archive safety and pre-execution integrity checks."""

from io import BytesIO
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from shared import managed_pnl as pnl, managed_runtimes as runtime


class ManagedPnlTests(unittest.TestCase):
    def archive(self, root, name, kind=None):
        file = root / "fixture.tar.gz"
        with tarfile.open(file, "w:gz") as stream:
            info = tarfile.TarInfo(name)
            if kind:
                info.type = kind
                info.linkname = "/outside"
                stream.addfile(info)
            else:
                info.size = 4
                stream.addfile(info, BytesIO(b"data"))
        return file

    def test_normal_archive_strips_root_and_never_executes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pnl.extract_regular_files(self.archive(root, "root/pipeline/test.py"), root / "installed")
            self.assertEqual((root / "installed/pipeline/test.py").read_bytes(), b"data")

    def test_unsafe_archive_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, kind in (("../escape", None), ("/absolute", None), ("root/../../escape", None),
                               ("root/link", tarfile.SYMTYPE), ("root/link", tarfile.LNKTYPE), ("root/C:\\escape", None)):
                with self.subTest(name=name, kind=kind), self.assertRaises(ValueError):
                    pnl.extract_regular_files(self.archive(root, name, kind), root / "installed")

    def test_existing_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "installed").mkdir()
            (root / "installed/link").symlink_to(root / "outside")
            with self.assertRaises(ValueError):
                pnl.extract_regular_files(self.archive(root, "root/link/file"), root / "installed")
            self.assertFalse((root / "outside").exists())

    def test_model_checksums_precede_model_deserialization(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in pnl.RESOURCE_HASHES:
                file = root / relative
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(b"not a trusted model")
            with patch.object(pnl.subprocess, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "checksum"):
                    pnl.verify_assets(root)
            run.assert_not_called()

    def test_explicit_pnl_terms_precede_all_filesystem_and_download_work(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(runtime, "supported_platform", return_value=True), \
                patch.object(runtime, "ensure_conda") as bootstrap:
            root = Path(temp) / "not-created"
            with self.assertRaises(PermissionError):
                runtime.provision(("pnl_cnn",), root=root)
            self.assertFalse(root.exists())
            bootstrap.assert_not_called()

    def test_unsupported_platform_never_installs_pnl(self):
        with patch.object(runtime, "supported_platform", return_value=False), patch.object(runtime, "ensure_conda") as bootstrap:
            with self.assertRaises(RuntimeError):
                runtime.provision(("pnl_cnn",), accept_pnl_terms=True)
        bootstrap.assert_not_called()

    def test_selected_python_cuda_libraries_are_process_local(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp)
            (prefix / "lib/python3.11/site-packages/nvidia/cudnn/lib").mkdir(parents=True)
            with patch.object(pnl, "external_python_environment", return_value={"LD_LIBRARY_PATH": "/other", "CUDA_VISIBLE_DEVICES": "2"}):
                env = pnl.pnl_python_environment(prefix / "bin/python")
            self.assertIn(str(prefix / "lib/python3.11/site-packages/nvidia/cudnn/lib"), env["LD_LIBRARY_PATH"])
            self.assertEqual(env["CUDA_VISIBLE_DEVICES"], "2")


if __name__ == "__main__":
    unittest.main()
