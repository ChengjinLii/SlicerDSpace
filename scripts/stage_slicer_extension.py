#!/usr/bin/env python3
"""Stage SlicerDDSurfer in an extension-like layout for RC smoke tests."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ENTRIES = (
    "SlicerDDSurfer.py",
    "EXTERNAL_DEPENDENCIES.md",
    "Resources",
    "shared",
    "preprocessing",
    "surface",
    "parcellation",
    "segmentation",
    "microstructure",
    "tractography",
    "connectome",
    "scripts",
)
EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "Testing",
    "tests",
    "third_party",
}
EXCLUDED_FILE_SUFFIXES = {".pyc", ".pyo"}


def _ignore(_src: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in EXCLUDED_DIR_NAMES or name.endswith("~"):
            ignored.add(name)
            continue
        if any(name.endswith(suffix) for suffix in EXCLUDED_FILE_SUFFIXES):
            ignored.add(name)
    return ignored


def _copy_or_link_file(src: Path, dst: Path, *, link_mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if link_mode == "hardlink":
        try:
            os.link(src, dst)
            shutil.copystat(src, dst, follow_symlinks=True)
            return
        except OSError:
            pass
    shutil.copy2(src, dst)


def _copy_tree(src: Path, dst: Path, *, link_mode: str) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    if link_mode == "copy":
        shutil.copytree(src, dst, ignore=_ignore)
        return
    dst.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src):
        root_path = Path(root)
        rel_root = root_path.relative_to(src)
        dirs[:] = [name for name in dirs if name not in EXCLUDED_DIR_NAMES]
        target_root = dst / rel_root
        target_root.mkdir(parents=True, exist_ok=True)
        for file_name in files:
            if file_name in _ignore(root, [file_name]):
                continue
            _copy_or_link_file(root_path / file_name, target_root / file_name, link_mode=link_mode)


def stage_extension(install_root: Path, *, slicer_version: str, clean: bool, link_mode: str) -> dict[str, object]:
    extension_root = install_root.expanduser().resolve() / "SlicerDDSurfer"
    module_dir = extension_root / "lib" / slicer_version / "qt-scripted-modules"
    if clean and extension_root.exists():
        shutil.rmtree(extension_root)
    module_dir.mkdir(parents=True, exist_ok=True)

    for entry in RUNTIME_ENTRIES:
        src = REPO_ROOT / entry
        dst = module_dir / entry
        if not src.exists():
            raise FileNotFoundError(f"Required runtime entry is missing: {src}")
        if src.is_dir():
            _copy_tree(src, dst, link_mode=link_mode)
        else:
            _copy_or_link_file(src, dst, link_mode=link_mode)

    s4ext = REPO_ROOT / "SlicerDDSurfer.s4ext"
    if s4ext.is_file():
        _copy_or_link_file(s4ext, extension_root / "SlicerDDSurfer.s4ext", link_mode=link_mode)

    top_level_py = sorted(path.name for path in module_dir.glob("*.py"))
    manifest = {
        "kind": "slicerdsurfer_extension_staging_manifest",
        "repo_root": REPO_ROOT.as_posix(),
        "extension_root": extension_root.as_posix(),
        "module_dir": module_dir.as_posix(),
        "slicer_version": slicer_version,
        "link_mode": link_mode,
        "top_level_python_files": top_level_py,
        "top_level_python_ok": top_level_py == ["SlicerDDSurfer.py"],
        "runtime_entries": list(RUNTIME_ENTRIES),
    }
    manifest_path = extension_root / "extension_staging_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest["manifest_path"] = manifest_path.as_posix()
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install-root",
        required=True,
        type=Path,
        help="Directory where an extension-like SlicerDDSurfer install tree will be staged.",
    )
    parser.add_argument("--slicer-version", default="Slicer-5.10")
    parser.add_argument("--clean", action="store_true", help="Remove the existing staged extension before staging.")
    parser.add_argument(
        "--link-mode",
        choices=("hardlink", "copy"),
        default="hardlink",
        help="Use hardlinks for fast local staging, or full copies for a standalone staging tree.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = stage_extension(
        args.install_root,
        slicer_version=args.slicer_version,
        clean=bool(args.clean),
        link_mode=args.link_mode,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["top_level_python_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
