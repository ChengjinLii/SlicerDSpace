"""GUI reuse expires promptly and cannot substitute for manual input validation."""

import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from shared.pipeline import inspect_subject_directory
from shared.ui_input_inspection import InputInspectionCache, inspect_input_directory


class InputInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.now = 100.0
        self.inspector = Mock(wraps=inspect_subject_directory)
        self.cache = InputInspectionCache(self.inspector, clock=lambda: self.now)

    def raw(self, root):
        folder = root / "input"
        folder.mkdir(parents=True)
        for name in ("data.nii.gz", "bvals", "bvecs"):
            (folder / name).touch()

    def dicom(self):
        folder = self.root / "series"
        folder.mkdir()
        path = folder / "image.bin"
        path.write_bytes(b"\0" * 128 + b"DICM")
        return path

    def inspect(self, **kwargs):
        return self.cache.inspect(self.root, "subject", **kwargs)

    def test_reuses_one_entry_without_changing_returned_layout(self):
        self.dicom()
        expected = inspect_subject_directory(self.root, "subject")
        for _ in range(20):
            self.assertEqual(self.inspect(), expected)
        self.assertEqual(self.inspector.call_count, 1)
        changed = self.inspect()
        changed["mode"] = "incorrect"
        self.assertEqual(self.inspect(), expected)

    def test_expires_at_one_second_and_on_clock_reversal(self):
        self.inspect()
        self.now += 0.999
        self.inspect()
        self.assertEqual(self.inspector.call_count, 1)
        self.now += 0.001
        self.inspect()
        self.assertEqual(self.inspector.call_count, 2)
        self.now -= 2
        self.inspect()
        self.assertEqual(self.inspector.call_count, 3)

    def test_nested_content_change_requires_expiry_or_manual_refresh(self):
        path = self.dicom()
        self.assertEqual(self.inspect()["mode"], "dicom")
        path.write_bytes(b"\0" * 132)
        self.assertEqual(self.inspect()["mode"], "dicom")
        self.assertEqual(self.inspect(refresh=True)["mode"], "missing")
        path.write_bytes(b"\0" * 128 + b"DICM")
        self.now += 1
        self.assertEqual(self.inspect()["mode"], "dicom")

    def test_direct_and_child_input_changes_invalidate_immediately(self):
        for root in (self.root, self.root / "subject"):
            with self.subTest(root=root):
                self.raw(root)
                self.assertEqual(self.inspect()["subject_root"], root)
                (root / "input/bvals").unlink()
                self.assertEqual(self.inspect()["mode"], "missing")

    def test_raw_layout_does_not_pay_for_cache_fingerprints(self):
        self.raw(self.root)
        self.cache._stamps = Mock(side_effect=AssertionError("Raw layouts do not need fingerprints"))
        for _ in range(20):
            self.assertEqual(self.inspect()["mode"], "subject_root")
        self.assertEqual(self.inspector.call_count, 20)

    def test_subject_or_root_changes_do_not_reuse_previous_entry(self):
        self.inspect()
        self.cache.inspect(self.root, "other-subject")
        other = self.root / "other"
        other.mkdir()
        self.cache.inspect(other, "other-subject")
        self.assertEqual(self.inspector.call_count, 3)

    def test_exception_does_not_leave_a_reusable_stale_entry(self):
        self.inspect()
        self.inspector.side_effect = OSError("disconnected input")
        with self.assertRaises(OSError):
            self.inspect(refresh=True)
        with self.assertRaises(OSError):
            self.inspect()

    def test_widget_caches_are_not_shared(self):
        first, second = SimpleNamespace(), SimpleNamespace()
        self.assertEqual(inspect_input_directory(first, self.root, "subject"),
                         inspect_input_directory(second, self.root, "subject"))
        self.assertIsNot(first._inputInspectionCache, second._inputInspectionCache)

    def test_manual_validation_explicitly_requests_fresh_inspection(self):
        source = Path(__file__).resolve().parents[2] / "anatomy/surface/module_widget.py"
        tree = ast.parse(source.read_text())
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == "validateInputs")
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
        evaluate = Mock(return_value=(True, []))
        owner = SimpleNamespace(_evaluateInputs=evaluate, _pipelineActive=False, ui=SimpleNamespace(),
            _parameterNode=None, _lastStatusMessage="", _setStatus=lambda *args: None,
            _setWidgetError=lambda *args: None, appendLog=lambda *args: None)
        namespace["validateInputs"](owner)
        evaluate.assert_called_with(refresh=False)
        namespace["validateInputs"](owner, manual=True)
        evaluate.assert_called_with(refresh=True)


if __name__ == "__main__":
    unittest.main()
