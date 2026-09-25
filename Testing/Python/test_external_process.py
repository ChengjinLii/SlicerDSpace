#!/usr/bin/env python3
"""Tests for shared/external_process.py's subprocess kwargs helper."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.external_process import text_subprocess_kwargs


class TextSubprocessKwargsTest(unittest.TestCase):
    def test_defaults_force_utf8_with_replacement(self) -> None:
        kwargs = text_subprocess_kwargs()
        self.assertEqual(
            kwargs,
            {"text": True, "encoding": "utf-8", "errors": "replace"},
        )

    def test_overrides_are_merged_in(self) -> None:
        kwargs = text_subprocess_kwargs(bufsize=1)
        self.assertEqual(
            kwargs,
            {"text": True, "encoding": "utf-8", "errors": "replace", "bufsize": 1},
        )

    def test_kwargs_are_accepted_by_a_real_subprocess_call(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-c", "print('ok')"],
            capture_output=True,
            check=True,
            **text_subprocess_kwargs(),
        )
        self.assertEqual(completed.stdout.strip(), "ok")

    def test_replace_errors_do_not_raise_on_undecodable_bytes(self) -> None:
        # A byte sequence that is not valid under a non-UTF-8 locale, but
        # would be silently mis-decoded (or raise) without errors="replace"
        # and an explicit encoding. \xff is invalid in UTF-8 on its own.
        script = "import sys; sys.stdout.buffer.write(b'before\\xffafter')"
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            check=True,
            **text_subprocess_kwargs(),
        )
        self.assertIn("before", completed.stdout)
        self.assertIn("after", completed.stdout)


if __name__ == "__main__":
    unittest.main()
