#!/usr/bin/env python3
"""Build release artifact metadata for GitHub/DOI archives."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.download_model_assets import build_asset_lockfile, load_manifest, resolve_asset_plan, verify_asset_plan


ASSET_EXCLUSION_PATTERNS = (
    "Resources/Data/ckpts/**",
    "Resources/Data/template/**",
    "Resources/Data/100HCP-population-mean-T2.nii.gz",
    "surface/template/**",
    "segmentation/weights/**",
    "parcellation/weights/**",
    "anatomy/parcellation/conversion/tests/data/**",
    "anatomy/surface/template/**",
    "anatomy/surface/weights/**",
    "anatomy/segmentation/weights/**",
    "anatomy/parcellation/weights/**",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build release metadata artifacts for SlicerDSpace.")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "ignore" / "releases" / "v0.1.0")
    parser.add_argument("--profile", default="core", help="Model asset profile to describe.")
    parser.add_argument("--release-validation-report", type=Path, help="Optional release_validation_report.json to copy.")
    parser.add_argument("--verify-assets", action="store_true", help="Fail if selected model assets are missing or pointer-only.")
    return parser


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git_value(args: list[str]) -> str:
    import subprocess

    from shared.external_process import text_subprocess_kwargs

    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=False, stdout=subprocess.PIPE, **text_subprocess_kwargs()
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(REPO_ROOT / "models" / "assets_manifest.json")
    plan = resolve_asset_plan(manifest, args.profile)
    verification = verify_asset_plan(REPO_ROOT, plan)
    if args.verify_assets and not verification["ok"]:
        print(json.dumps({"asset_verification": verification}, indent=2, sort_keys=True), file=sys.stderr)
        return 3

    lockfile = build_asset_lockfile(REPO_ROOT, plan)
    _write_json(output_dir / f"model_assets_{args.profile}_lock.json", lockfile)

    archive_manifest = {
        "kind": "slicerdsurfer_code_only_release_archive_manifest",
        "version": 1,
        "git_commit": _git_value(["rev-parse", "HEAD"]),
        "git_describe": _git_value(["describe", "--tags", "--always", "--dirty"]),
        "asset_profile": args.profile,
        "asset_verification": verification,
        "code_archive_policy": (
            "Public DOI archives should include source code, documentation, release metadata and validation reports. "
            "Exclude model weights, templates and validation fixtures unless redistribution and DOI-archive terms are confirmed."
        ),
        "asset_exclusion_patterns": list(ASSET_EXCLUSION_PATTERNS),
        "required_metadata_files": [
            "LICENSE.txt",
            "CITATION.cff",
            "codemeta.json",
            ".zenodo.json",
            "docs/release/RELEASE.md",
            "docs/assets/MODEL_ASSETS.md",
            "docs/assets/MODEL_ASSET_TERMS.md",
            "docs/release/RELEASE_NOTES_v0.1.0.md",
        ],
    }
    _write_json(output_dir / "code_only_archive_manifest.json", archive_manifest)

    exclusion_notes = [
        "# Asset Exclusion Checklist",
        "",
        "Exclude these asset classes from a public DOI archive unless redistribution and archive terms are confirmed:",
        "",
        *[f"- `{pattern}`" for pattern in ASSET_EXCLUSION_PATTERNS],
        "",
        "Use `docs/assets/MODEL_ASSET_TERMS.md` as the terms decision record.",
        "",
    ]
    (output_dir / "asset_exclusion_checklist.md").write_text("\n".join(exclusion_notes), encoding="utf-8")

    if args.release_validation_report:
        report = args.release_validation_report.expanduser().resolve()
        if not report.is_file():
            raise FileNotFoundError(f"Release validation report not found: {report}")
        shutil.copy2(report, output_dir / "release_validation_report.json")

    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
