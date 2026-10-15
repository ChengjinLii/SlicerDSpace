"""Dependency-free acceptance gate for previously decoded scalar products."""

import json
from pathlib import Path


def _signature(path):
    path = Path(path).resolve()
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def scalar_qc_current(qc_path: Path, maps: list[Path]) -> bool:
    """Changed files or old/failed records require fresh numerical validation."""
    try:
        record = json.loads(Path(qc_path).read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            return False
        checks = record.get("checks")
        if (record.get("status") != "completed" or record.get("automatic_qc_passed") is not True
                or not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values())):
            return False
        for source in (record.get("source_signature") or {}).values():
            if source != _signature(source["path"]):
                return False
        return record.get("output_artifacts") == {str(Path(path).resolve()): _signature(path) for path in maps}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False
