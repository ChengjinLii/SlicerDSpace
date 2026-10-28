#!/usr/bin/env python3
"""Prepare upload instructions for an exported model-asset mirror."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_release_evidence import validate_asset_mirror_manifest


def _mirror_manifest_path(mirror_dir: Path) -> Path:
    path = mirror_dir.expanduser().resolve()
    return path if path.name == "asset_mirror_manifest.json" else path / "asset_mirror_manifest.json"


def build_upload_plan(*, mirror_dir: Path, target: str, release_tag: str, repository: str, hf_repo: str, zenodo_record: str) -> dict:
    manifest_path = _mirror_manifest_path(mirror_dir)
    manifest_summary = validate_asset_mirror_manifest(manifest_path)
    root = manifest_path.parent
    records = json.loads(manifest_path.read_text(encoding="utf-8")).get("records", [])
    files = [root / record["path"] for record in records]
    missing = [path.as_posix() for path in files if not path.is_file()]
    if missing:
        raise RuntimeError("Mirror file(s) listed in manifest are missing: " + ", ".join(missing))

    if target == "github-release":
        destination = f"https://github.com/{repository}/releases/tag/{release_tag}"
        commands = [
            f"gh repo create {repository} --private --source {root.as_posix()} --remote origin",
            f"gh release create {release_tag} --repo {repository} --draft " + " ".join(path.as_posix() for path in files),
        ]
    elif target == "huggingface":
        destination = f"https://huggingface.co/datasets/{hf_repo}/tree/{release_tag}"
        commands = [
            f"huggingface-cli repo create {hf_repo} --type dataset",
            f"cd {root.as_posix()} && git init && git lfs install",
            "git add . && git commit -m 'Add SlicerDSpace model assets'",
            f"git remote add origin https://huggingface.co/datasets/{hf_repo}",
            f"git tag {release_tag} && git push origin HEAD:main --tags",
        ]
    else:
        destination = f"https://zenodo.org/records/{zenodo_record}"
        commands = [
            "Create or open the Zenodo draft record in the web UI.",
            f"Upload all files under {root.as_posix()} preserving relative paths when the platform supports it.",
            "After publication, update models/assets_manifest.json with the final Zenodo record URL.",
        ]

    return {
        "kind": "slicerdsurfer_model_asset_upload_plan",
        "version": 1,
        "target": target,
        "destination": destination,
        "mirror_dir": root.as_posix(),
        "manifest": manifest_summary,
        "file_count": len(files),
        "total_size_bytes": sum(path.stat().st_size for path in files),
        "commands": commands,
        "note": "This script does not upload files. It validates the mirror and prints maintainer commands.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mirror-dir", type=Path, required=True, help="Exported asset mirror directory or asset_mirror_manifest.json.")
    parser.add_argument("--target", choices=("github-release", "huggingface", "zenodo"), default="github-release")
    parser.add_argument("--release-tag", default="v0.1.0")
    parser.add_argument("--repository", default="ChengjinLii/SlicerDSpace-models")
    parser.add_argument("--hf-repo", default="ChengjinLii/SlicerDDSurfer-models")
    parser.add_argument("--zenodo-record", default="REPLACE_WITH_RECORD_ID")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan = build_upload_plan(
            mirror_dir=args.mirror_dir,
            target=args.target,
            release_tag=args.release_tag,
            repository=args.repository,
            hf_repo=args.hf_repo,
            zenodo_record=args.zenodo_record,
        )
    except RuntimeError as exc:
        parser.exit(2, f"[model-assets] {exc}\n")
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
