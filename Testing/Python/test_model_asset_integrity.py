#!/usr/bin/env python3
"""Tests for shared/model_asset_integrity.py's cached sha256 verification."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.model_asset_integrity import (
    cached_sha256_of_file,
    load_sha256_cache,
    save_sha256_cache,
    sha256_of_file,
    verify_against_manifest,
)


class Sha256OfFileTest(unittest.TestCase):
    def test_matches_hashlib_computed_directly_over_the_same_bytes(self) -> None:
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "asset.bin"
            content = b"hello world" * 100000  # larger than one read chunk
            path.write_bytes(content)

            self.assertEqual(sha256_of_file(path), hashlib.sha256(content).hexdigest())


class CachedSha256OfFileTest(unittest.TestCase):
    def test_cache_miss_computes_and_stores_the_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "asset.bin"
            path.write_bytes(b"content-a")
            cache: dict = {}

            digest = cached_sha256_of_file(path, cache)

            self.assertEqual(digest, sha256_of_file(path))
            self.assertIn(str(path), cache)

    def test_cache_hit_avoids_rehashing_when_mtime_and_size_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "asset.bin"
            path.write_bytes(b"content-a")
            cache: dict = {}
            expected_digest = cached_sha256_of_file(path, cache)

            with mock.patch(
                "shared.model_asset_integrity.sha256_of_file", side_effect=AssertionError("should not rehash")
            ):
                digest = cached_sha256_of_file(path, cache)

            self.assertEqual(digest, expected_digest)

    def test_cache_is_invalidated_when_the_file_identity_no_longer_matches(self) -> None:
        # Simulate a file swapped out from under a previously-verified path:
        # rather than relying on filesystem mtime-resolution timing (which
        # can be too coarse to reliably differ within a fast test), plant a
        # stale cache entry directly and confirm it is not trusted once the
        # real file's (mtime, size) no longer matches it.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "asset.bin"
            path.write_bytes(b"content-b-longer")
            cache = {str(path): {"mtime_ns": -1, "size": -1, "sha256": "stale-digest"}}

            digest = cached_sha256_of_file(path, cache)

            self.assertEqual(digest, sha256_of_file(path))
            self.assertNotEqual(digest, "stale-digest")


class Sha256CachePersistenceTest(unittest.TestCase):
    def test_round_trips_through_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "cache.json"
            save_sha256_cache(cache_path, {"a": {"sha256": "deadbeef", "mtime_ns": 1, "size": 2}})

            loaded = load_sha256_cache(cache_path)

            self.assertEqual(loaded["a"]["sha256"], "deadbeef")

    def test_missing_or_corrupt_cache_file_returns_empty_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.json"
            self.assertEqual(load_sha256_cache(missing), {})

            corrupt = Path(tmp) / "corrupt.json"
            corrupt.write_text("{not json", encoding="utf-8")
            self.assertEqual(load_sha256_cache(corrupt), {})


class VerifyAgainstManifestTest(unittest.TestCase):
    def test_passes_when_digest_matches_manifest_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weights" / "model.pt"
            path.parent.mkdir()
            path.write_bytes(b"trusted weights")
            records = {"weights/model.pt": {"sha256": sha256_of_file(path)}}

            ok, reason = verify_against_manifest(path, "weights/model.pt", records)

            self.assertTrue(ok)
            self.assertIn("verified", reason)

    def test_fails_when_digest_does_not_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weights" / "model.pt"
            path.parent.mkdir()
            path.write_bytes(b"a planted, untrusted file")
            records = {"weights/model.pt": {"sha256": "0" * 64}}

            ok, reason = verify_against_manifest(path, "weights/model.pt", records)

            self.assertFalse(ok)
            self.assertIn("mismatch", reason)

    def test_passes_with_no_record_to_compare_against(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weights" / "unlisted.pt"
            path.parent.mkdir()
            path.write_bytes(b"not in the manifest")

            ok, reason = verify_against_manifest(path, "weights/unlisted.pt", {})

            self.assertTrue(ok)
            self.assertIn("not verified", reason)


if __name__ == "__main__":
    unittest.main()
