from __future__ import annotations

import unittest

from shared.ui_error_dialogs import format_actionable_error_message


class UiErrorDialogsTest(unittest.TestCase):
    def test_formats_actionable_error_sections(self) -> None:
        message = format_actionable_error_message(
            title="Environment Check Failed",
            what="The dependency scan failed.",
            why="A configured path raised an exception.",
            next_step="Clear stale paths and scan again.",
            auto_fix="Python packages can be installed on demand.",
            details=RuntimeError("bad path"),
        )
        self.assertTrue(message.startswith("Environment Check Failed\n\n"))
        self.assertIn("What happened:\nThe dependency scan failed.", message)
        self.assertIn("Why:\nA configured path raised an exception.", message)
        self.assertIn("What to do next:\nClear stale paths and scan again.", message)
        self.assertIn("Automatic fix:\nPython packages can be installed on demand.", message)
        self.assertIn("Details:\nbad path", message)


if __name__ == "__main__":
    unittest.main()
