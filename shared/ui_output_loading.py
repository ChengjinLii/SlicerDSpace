"""Output and background-process helper functions for the Slicer UI."""

from __future__ import annotations


def qbytearray_to_text(value) -> str:
    """Decode Qt QByteArray-like values to text without raising."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, bytearray):
        return bytes(value).decode("utf-8", errors="replace")
    try:
        return bytes(value).decode("utf-8", errors="replace")
    except Exception:
        pass
    try:
        raw = value.data()
    except Exception:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    if isinstance(raw, bytearray):
        return bytes(raw).decode("utf-8", errors="replace")
    if isinstance(raw, str):
        return raw
    return ""
