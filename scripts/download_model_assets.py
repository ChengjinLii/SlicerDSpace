#!/usr/bin/env python3
"""Download and verify SlicerDDSurfer model assets from a manifest."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "models" / "assets_manifest.json"
LFS_POINTER_HEADER = b"version https://git-lfs.github.com/spec/v1"


@dataclass(frozen=True)
class AssetPlan:
    profile: str
    resolved_profiles: tuple[str, ...]
    all_lfs: bool
    include_patterns: tuple[str, ...]
    required_paths: tuple[str, ...]
    external_overrides: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "resolved_profiles": list(self.resolved_profiles),
            "all_lfs": self.all_lfs,
            "include_patterns": list(self.include_patterns),
            "required_paths": list(self.required_paths),
            "external_overrides": list(self.external_overrides),
        }


def _dedupe(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    return json.loads(path.expanduser().read_text(encoding="utf-8"))


def resolve_asset_plan(manifest: dict[str, Any], profile: str | None = None) -> AssetPlan:
    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("Asset manifest must contain a profiles object.")
    selected = profile or str(manifest.get("default_profile") or "core")
    seen: set[str] = set()
    resolved_profiles: list[str] = []
    include_patterns: list[str] = []
    required_paths: list[str] = []
    external_overrides: list[str] = []
    all_lfs = False

    def visit(name: str) -> None:
        nonlocal all_lfs
        if name in seen:
            return
        profile_data = profiles.get(name)
        if not isinstance(profile_data, dict):
            raise ValueError(f"Unsupported asset profile: {name}")
        alias = profile_data.get("alias_for")
        if alias:
            visit(str(alias))
            resolved_profiles.append(name)
            seen.add(name)
            return
        seen.add(name)
        resolved_profiles.append(name)
        if profile_data.get("all_lfs"):
            all_lfs = True
        for child in profile_data.get("include_profiles", []):
            visit(str(child))
        include_patterns.extend(str(value) for value in profile_data.get("include_patterns", []))
        required_paths.extend(str(value) for value in profile_data.get("required_paths", []))
        external_overrides.extend(str(value) for value in profile_data.get("external_overrides", []))

    visit(selected)
    return AssetPlan(
        profile=selected,
        resolved_profiles=_dedupe(resolved_profiles),
        all_lfs=all_lfs,
        include_patterns=_dedupe(include_patterns),
        required_paths=_dedupe(required_paths),
        external_overrides=_dedupe(external_overrides),
    )


def _run(command: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _check_git_checkout(repo_root: Path) -> None:
    result = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root, check=False)
    if result.returncode != 0:
        raise RuntimeError("This script must run inside a Git checkout.")


def _check_git_lfs(repo_root: Path) -> None:
    result = _run(["git", "lfs", "version"], cwd=repo_root, check=False)
    if result.returncode != 0:
        raise RuntimeError("Git LFS is required. Install Git LFS, then rerun this script.")


def _git_lfs_files(repo_root: Path) -> tuple[str, ...]:
    try:
        result = _run(["git", "lfs", "ls-files", "-n"], cwd=repo_root, check=False)
    except OSError:
        return ()
    if result.returncode != 0:
        return ()
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _is_lfs_pointer(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            return stream.read(256).startswith(LFS_POINTER_HEADER)
    except OSError:
        return False


def verify_asset_plan(repo_root: Path, plan: AssetPlan) -> dict[str, Any]:
    lfs_files = _git_lfs_files(repo_root)
    checked: list[str] = []
    if plan.all_lfs:
        checked.extend(lfs_files)
    elif plan.include_patterns:
        checked.extend(path for path in lfs_files if _matches_any(path, plan.include_patterns))
    checked.extend(plan.required_paths)
    checked = list(_dedupe(checked))

    missing: list[str] = []
    pointers: list[str] = []
    for relative in checked:
        path = repo_root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        if _is_lfs_pointer(path):
            pointers.append(relative)

    return {
        "checked_count": len(checked),
        "missing": missing,
        "lfs_pointers": pointers,
        "ok": bool(checked) and not missing and not pointers,
    }


def download_asset_plan(repo_root: Path, plan: AssetPlan) -> None:
    _check_git_checkout(repo_root)
    _check_git_lfs(repo_root)
    _run(["git", "lfs", "install", "--local"], cwd=repo_root)
    if plan.all_lfs:
        print("[model-assets] Downloading all Git LFS objects.")
        subprocess.run(["git", "lfs", "pull"], cwd=repo_root, check=True)
        return
    include_csv = ",".join(plan.include_patterns)
    print(f"[model-assets] profile={plan.profile}")
    print(f"[model-assets] include={include_csv}")
    subprocess.run(["git", "lfs", "pull", f"--include={include_csv}", "--exclude="], cwd=repo_root, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download SlicerDDSurfer model weights and templates through Git LFS.")
    parser.add_argument("--profile", "-p", help="Asset profile to download. Defaults to manifest default_profile.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Asset manifest JSON path.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root. Defaults to this checkout.")
    parser.add_argument("--no-verify", action="store_true", help="Skip post-download pointer/missing-file verification.")
    parser.add_argument("--verify-only", action="store_true", help="Do not download; only verify selected assets already exist.")
    parser.add_argument("--print-plan", action="store_true", help="Print the resolved manifest plan as JSON and exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.expanduser().resolve()
    try:
        manifest = load_manifest(args.manifest)
        plan = resolve_asset_plan(manifest, args.profile)
        if args.print_plan:
            print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
            return 0
        if not args.verify_only:
            download_asset_plan(repo_root, plan)
        if not args.no_verify:
            result = verify_asset_plan(repo_root, plan)
            if not result["ok"]:
                print(json.dumps({"profile": plan.profile, "verification": result}, indent=2, sort_keys=True), file=sys.stderr)
                return 3
            print(f"[model-assets] Verified {result['checked_count']} file(s) for profile={plan.profile}.")
        if plan.external_overrides:
            print("[model-assets] Optional external override env vars: " + ", ".join(plan.external_overrides))
        print("[model-assets] Done.")
        return 0
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"[model-assets] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
