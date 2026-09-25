"""Cache-backed sha256 verification for model asset files.

Model checkpoints are loaded with ``torch.load()`` elsewhere in this
codebase; a file planted at a path the asset resolver trusts (see
``shared/model_assets.py``) is effectively arbitrary code execution once
loaded. Verifying every checkpoint's sha256 against the recorded digest in
``models/assets_manifest.json`` closes that gap. Hashing large weight files
on every call would be slow, so the verified digest is cached per file
identity (path + mtime + size) and only recomputed when the file actually
changes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

DEFAULT_CACHE_FILENAME = "model_asset_sha256_cache.json"


class ModelAssetIntegrityError(RuntimeError):
    """Raised when a resolved model asset file does not match its manifest digest.

    This is a hard error, not a "try the next location" condition: an
    existing file at a trusted-looking path whose content does not match
    the recorded sha256 is either corrupted or tampered with, and callers
    (which hand the returned path straight to ``torch.load()``) have no way
    to tell "missing" apart from "wrong content" unless this is raised
    instead of silently falling back.
    """


def sha256_of_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the sha256 hex digest of a file's contents."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_identity(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def load_sha256_cache(cache_path: Path) -> dict[str, Any]:
    """Return the on-disk digest cache, or an empty cache if unreadable."""

    try:
        loaded = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def save_sha256_cache(cache_path: Path, cache: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def cached_sha256_of_file(path: Path, cache: dict[str, Any]) -> str:
    """Return ``path``'s sha256, reusing ``cache[str(path)]`` while mtime/size match."""

    key = str(path)
    mtime_ns, size = _file_identity(path)
    entry = cache.get(key)
    if isinstance(entry, dict) and entry.get("mtime_ns") == mtime_ns and entry.get("size") == size:
        digest = entry.get("sha256")
        if isinstance(digest, str):
            return digest
    digest = sha256_of_file(path)
    cache[key] = {"mtime_ns": mtime_ns, "size": size, "sha256": digest}
    return digest


def verify_against_manifest(
    path: Path,
    relative_key: str,
    manifest_records: dict[str, Any],
    *,
    cache: Optional[dict[str, Any]] = None,
) -> tuple[bool, str]:
    """Verify ``path``'s sha256 against ``manifest_records[relative_key]``.

    Returns ``(True, reason)`` when the file matches its recorded digest, or
    when there is no manifest record for ``relative_key`` at all (nothing to
    compare against -- callers decide whether that is acceptable for their
    use case). Returns ``(False, reason)`` only when a record exists and the
    digest does not match: that is the tampered/wrong-file case this exists
    to catch.
    """

    record = manifest_records.get(relative_key)
    if not isinstance(record, dict) or "sha256" not in record:
        return True, f"no manifest record for {relative_key!r}; not verified"
    expected = record["sha256"]
    working_cache = cache if cache is not None else {}
    actual = cached_sha256_of_file(path, working_cache)
    if actual != expected:
        return False, f"sha256 mismatch for {relative_key!r}: expected {expected}, got {actual}"
    return True, f"sha256 verified for {relative_key!r}"
