#!/usr/bin/env python3
"""Create a clean, rooted archive for local Slicer Extension Manager tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path


EXCLUDED_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache"}
EXCLUDED_FILE_NAMES = {"extension_staging_manifest.json"}
EXCLUDED_FILE_SUFFIXES = {".pyc", ".pyo"}


def _is_excluded(path: Path, extension_root: Path) -> bool:
    relative = path.relative_to(extension_root)
    return (
        any(part in EXCLUDED_DIR_NAMES for part in relative.parts)
        or path.name in EXCLUDED_FILE_NAMES
        or path.suffix.lower() in EXCLUDED_FILE_SUFFIXES
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_extension(extension_root: Path, output_path: Path) -> dict[str, object]:
    """Package a staged extension with the top-level directory Slicer expects."""

    root = extension_root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Staged extension root does not exist: {root}")
    module_files = sorted(root.glob("lib/Slicer-*/qt-scripted-modules/SlicerDDSurfer.py"))
    if len(module_files) != 1:
        raise ValueError(f"Expected exactly one staged SlicerDDSurfer.py, found {len(module_files)}")
    if not (root / "SlicerDDSurfer.s4ext").is_file():
        raise FileNotFoundError(f"Extension metadata is missing: {root / 'SlicerDDSurfer.s4ext'}")

    output = output_path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    members = [root]
    members.extend(path for path in sorted(root.rglob("*")) if not _is_excluded(path, root))
    with tarfile.open(output, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        for path in members:
            relative = path.relative_to(root)
            archive_name = Path(root.name) / relative
            info = archive.gettarinfo(path.as_posix(), arcname=archive_name.as_posix())
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            if path.is_file():
                with path.open("rb") as stream:
                    archive.addfile(info, stream)
            else:
                archive.addfile(info)

    payload = {
        "kind": "slicerdsurfer_extension_package",
        "version": 1,
        "extension_name": root.name,
        "extension_root": root.as_posix(),
        "archive": output.as_posix(),
        "archive_size_bytes": output.stat().st_size,
        "archive_sha256": _sha256(output),
        "member_count": len(members),
        "module_file": module_files[0].relative_to(root).as_posix(),
        "excluded_directory_names": sorted(EXCLUDED_DIR_NAMES),
        "excluded_file_names": sorted(EXCLUDED_FILE_NAMES),
        "excluded_file_suffixes": sorted(EXCLUDED_FILE_SUFFIXES),
    }
    manifest_path = output.with_name(output.name + ".manifest.json")
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload["manifest_path"] = manifest_path.as_posix()
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extension-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = package_extension(args.extension_root, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
