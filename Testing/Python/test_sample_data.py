#!/usr/bin/env python3
"""Tests for sample-data registry helpers."""

from __future__ import annotations

import json
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared.sample_data import SampleDataEntry, fetch_sample_source, load_sample_data_registry, sample_data_registry_payload


class SampleDataTest(unittest.TestCase):
    def test_remote_download_is_verified_before_publication(self):
        data = b"synthetic sample archive"
        entry = SampleDataEntry("demo", "Demo", "https://example.org/demo", "url", "CC0",
                                sha256=hashlib.sha256(data).hexdigest())
        with tempfile.TemporaryDirectory() as tmp, patch("urllib.request.urlopen", return_value=io.BytesIO(data)):
            destination = fetch_sample_source(entry, Path(tmp) / "demo")
            self.assertEqual(destination.read_bytes(), data)
            self.assertFalse(list(Path(tmp).glob(".sdds-sample-*")))

    def test_bad_hash_keeps_previous_sample_and_removes_partial_data(self):
        entry = SampleDataEntry("demo", "Demo", "https://example.org/demo", "url", "CC0", sha256="0" * 64)
        with tempfile.TemporaryDirectory() as tmp, patch("urllib.request.urlopen", return_value=io.BytesIO(b"bad")):
            destination = Path(tmp) / "demo"
            destination.write_bytes(b"previous")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                fetch_sample_source(entry, destination, overwrite=True)
            self.assertEqual(destination.read_bytes(), b"previous")
            self.assertFalse(list(Path(tmp).glob(".sdds-sample-*")))

    def test_remote_without_digest_never_downloads(self):
        entry = SampleDataEntry("demo", "Demo", "https://example.org/demo", "url", "CC0")
        with tempfile.TemporaryDirectory() as tmp, patch("urllib.request.urlopen") as download:
            with self.assertRaisesRegex(ValueError, "requires an explicit SHA256"):
                fetch_sample_source(entry, Path(tmp) / "demo")
            download.assert_not_called()

    def test_interrupted_download_never_replaces_previous_file(self):
        entry = SampleDataEntry('demo', 'Demo', 'https://example.org/demo', 'url', 'CC0', sha256='0' * 64)
        with tempfile.TemporaryDirectory() as tmp, patch('urllib.request.urlopen', return_value=io.BytesIO(b'partial')), \
                patch('shutil.copyfileobj', side_effect=OSError('network interrupted')):
            destination = Path(tmp) / 'demo'
            destination.write_bytes(b'previous')
            with self.assertRaises(OSError):
                fetch_sample_source(entry, destination, overwrite=True)
            self.assertEqual(destination.read_bytes(), b'previous')
            self.assertFalse(list(Path(tmp).glob('.sdds-sample-*')))

    def test_local_copy_checks_digest_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, destination = Path(tmp) / "source", Path(tmp) / "destination"
            source.write_bytes(b"local")
            entry = SampleDataEntry("demo", "Demo", str(source), "local", "CC0",
                                    sha256=hashlib.sha256(b"local").hexdigest())
            fetch_sample_source(entry, destination)
            with self.assertRaises(FileExistsError):
                fetch_sample_source(entry, destination)
            self.assertEqual(source.read_bytes(), destination.read_bytes())

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
