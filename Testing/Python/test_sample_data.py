#!/usr/bin/env python3
"""Tests for sample-data registry helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from shared.sample_data import SampleDataEntry, load_sample_data_registry, sample_data_registry_payload


class SampleDataTest(unittest.TestCase):
    def test_registry_payload_round_trips_without_bundled_data(self) -> None:
        entry = SampleDataEntry(
            sample_id="demo",
            label="Demo",
            source="https://example.org/demo.zip",
            source_type="url",
            license="CC-BY-4.0",
            description="external only",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps(sample_data_registry_payload((entry,))), encoding="utf-8")

            loaded = load_sample_data_registry(path)

        self.assertEqual(loaded[0].sample_id, "demo")
        self.assertEqual(loaded[0].source_type, "url")
        self.assertEqual(loaded[0].license, "CC-BY-4.0")

    def test_rejects_unknown_registry_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text('{"kind": "wrong", "entries": []}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unsupported"):
                load_sample_data_registry(path)


if __name__ == "__main__":
    unittest.main()
