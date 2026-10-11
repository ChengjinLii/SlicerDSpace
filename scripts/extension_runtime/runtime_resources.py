"""Runtime file selection shared by staging and CMake contract tests."""

from __future__ import annotations

import json
from pathlib import Path


def runtime_files(root: Path) -> list[str]:
    root = root.resolve()
    spec = json.loads((root / "scripts/extension_runtime/runtime_resources.json").read_text(encoding="utf-8"))
    if spec["version"] != 1:
        raise ValueError("Unsupported runtime resource manifest version")
    selected = set(spec["files"])
    for tree in spec["trees"]:
        for pattern in tree["patterns"]:
            selected.update(path.relative_to(root).as_posix() for path in (root / tree["root"]).rglob(pattern) if path.is_file())
    result = []
    for relative in sorted(selected):
        path = root / relative
        if any(part in spec["excluded_components"] for part in Path(relative).parts):
            continue
        if any(relative == prefix or relative.startswith(prefix + "/") for prefix in spec["excluded_prefixes"]):
            continue
        if not path.is_file():
            raise FileNotFoundError(f"Required runtime resource is missing: {relative}")
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Runtime resource escapes source tree: {relative}")
        result.append(relative)
    return result
