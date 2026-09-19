"""Collection-level output completion contracts."""

import tempfile
import unittest
from pathlib import Path

from shared.output_contracts import outputs_readable


class OutputCollectionContractTest(unittest.TestCase):
    def test_empty_collection_cannot_mark_work_complete(self):
        self.assertFalse(outputs_readable([]))
        self.assertFalse(outputs_readable(iter(())))

    def test_generators_and_mixed_validity(self):
        with tempfile.TemporaryDirectory() as tmp:
            valid = Path(tmp) / "complete.json"
            valid.write_text('{"status": "completed"}')
            missing = Path(tmp) / "missing.json"
            self.assertTrue(outputs_readable(str(p) for p in [valid]))
            self.assertFalse(outputs_readable(p for p in [valid, missing]))


if __name__ == "__main__":
    unittest.main()
