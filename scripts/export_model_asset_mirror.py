#!/usr/bin/env python3
"""Export verified model assets into an upload-ready mirror directory."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from download_model_assets import (
    DEFAULT_MANIFEST,
    REPO_ROOT,
    _git_head,
    _is_lfs_pointer,
    _sha256,
    load_manifest,
    resolve_asset_plan,
    verify_asset_plan,
)


def _copy_asset(source: Path, target: Path, *, mode: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    if mode == "symlink":
        target.symlink_to(source.resolve())
    elif mode == "hardlink":
        try:
            target.hardlink_to(source)
        except OSError:
            shutil.copy2(source, target)
    else:
        shutil.copy2(source, target)


def export_asset_mirror(
    *,
    repo_root: Path,
    output_dir: Path,
    profile: str | None,
    manifest_path: Path,
    mode: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    plan = resolve_asset_plan(manifest, profile)
    verification = verify_asset_plan(repo_root, plan)
    if not verification["ok"]:
        raise RuntimeError(
            "Selected assets are not ready for mirror export: "
            + json.dumps(verification, sort_keys=True)
        )

    records: list[dict[str, Any]] = []
    for relative in plan.required_paths:
        source = repo_root / relative
        target = output_dir / relative
        record = plan.asset_records.get(relative, {})
        entry = {
            "path": relative,
            "size_bytes": source.stat().st_size,
            "sha256": _sha256(source),
            "expected_size_bytes": record.get("size_bytes"),
            "expected_sha256": record.get("sha256"),
            "source_ids": list(record.get("source_ids", plan.source_ids)),
        }
        records.append(entry)
        if not dry_run:
            _copy_asset(source, target, mode=mode)
            if _is_lfs_pointer(target):
                raise RuntimeError(f"Exported file is still a Git LFS pointer: {relative}")

    exported_manifest = {
        "kind": "slicerdsurfer_model_asset_mirror",
        "version": 1,
        "schema": "slicerddsurfer.model_assets.mirror.v1",
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_commit": _git_head(repo_root),
        "profile": plan.profile,
        "resolved_profiles": list(plan.resolved_profiles),
        "asset_groups": list(plan.asset_groups),
        "terms_notices": list(plan.terms_notices),
        "mirror_layout": "repository-relative paths",
        "copy_mode": mode,
        "dry_run": dry_run,
        "records": records,
    }
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "asset_mirror_manifest.json").write_text(
            json.dumps(exported_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tsv_lines = ["path\tsize_bytes\tsha256"]
        tsv_lines.extend(f"{item['path']}\t{item['size_bytes']}\t{item['sha256']}" for item in records)
        (output_dir / "asset_mirror_index.tsv").write_text("\n".join(tsv_lines) + "\n", encoding="utf-8")
    return exported_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export verified SlicerDDSurfer model assets into a directory that can be uploaded "
            "to SlicerDDSurfer-models, Hugging Face, Zenodo, OSF, Figshare, or object storage."
        )
    )
    parser.add_argument("--profile", "-p", default="core", help="Asset profile to export. Defaults to core.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Asset manifest JSON path.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root containing materialized assets.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Destination mirror directory.")
    parser.add_argument("--mode", choices=("copy", "hardlink", "symlink"), default="copy", help="Export mode. Defaults to copy.")
    parser.add_argument("--dry-run", action="store_true", help="Verify and print the export plan without writing files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = export_asset_mirror(
            repo_root=args.repo_root.expanduser().resolve(),
            output_dir=args.output_dir.expanduser().resolve(),
            profile=args.profile,
            manifest_path=args.manifest.expanduser().resolve(),
            mode=args.mode,
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0
    except RuntimeError as exc:
        print(f"[model-assets] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
