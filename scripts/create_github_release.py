#!/usr/bin/env python3
"""Create the SlicerDDSurfer GitHub Release page and upload release artifacts.

The script uses the GitHub REST API directly so maintainers do not need the
GitHub CLI. It intentionally defaults to a draft release because model-asset
redistribution and DOI-archive rights are tracked separately.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPOSITORY = "ChengjinLii/SlicerDDSurfer"
DEFAULT_TAG = "v0.1.0"
DEFAULT_TITLE = "SlicerDDSurfer v0.1.0"
DEFAULT_NOTES = REPO_ROOT / "docs" / "release" / "GITHUB_RELEASE_DRAFT_v0.1.0.md"
DEFAULT_ARTIFACT_NAMES = (
    "model_assets_core_lock.json",
    "code_only_archive_manifest.json",
    "asset_exclusion_checklist.md",
    "release_validation_report.json",
)


@dataclass(frozen=True)
class ReleasePlan:
    repository: str
    tag: str
    title: str
    notes_file: Path
    assets: tuple[Path, ...]
    draft: bool
    prerelease: bool
    reuse_existing: bool
    replace_existing_assets: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "tag": self.tag,
            "title": self.title,
            "notes_file": self.notes_file.as_posix(),
            "assets": [path.as_posix() for path in self.assets],
            "draft": self.draft,
            "prerelease": self.prerelease,
            "reuse_existing": self.reuse_existing,
            "replace_existing_assets": self.replace_existing_assets,
        }


def default_assets(repo_root: Path, tag: str) -> tuple[Path, ...]:
    artifact_dir = repo_root / "release_artifacts" / tag
    return tuple(artifact_dir / name for name in DEFAULT_ARTIFACT_NAMES)


def build_release_plan(args: argparse.Namespace) -> ReleasePlan:
    tag = str(args.tag or DEFAULT_TAG)
    assets = list(default_assets(REPO_ROOT, tag))
    assets.extend(args.asset or [])
    if args.fresh_clone_report:
        assets.append(args.fresh_clone_report)

    return ReleasePlan(
        repository=str(args.repository or DEFAULT_REPOSITORY),
        tag=tag,
        title=str(args.title or DEFAULT_TITLE),
        notes_file=(args.notes_file or DEFAULT_NOTES).expanduser().resolve(),
        assets=tuple(path.expanduser().resolve() for path in assets),
        draft=not bool(args.publish),
        prerelease=not bool(args.final),
        reuse_existing=bool(args.reuse_existing),
        replace_existing_assets=bool(args.replace_existing_assets),
    )


def validate_plan(plan: ReleasePlan) -> None:
    if "/" not in plan.repository:
        raise ValueError("Repository must be in owner/name form.")
    if not plan.notes_file.is_file():
        raise FileNotFoundError(f"Release notes file not found: {plan.notes_file}")
    missing = [path.as_posix() for path in plan.assets if not path.is_file()]
    if missing:
        raise FileNotFoundError("Release artifact(s) not found: " + ", ".join(missing))


def release_payload(plan: ReleasePlan) -> dict[str, Any]:
    body = plan.notes_file.read_text(encoding="utf-8")
    return {
        "tag_name": plan.tag,
        "name": plan.title,
        "body": body,
        "draft": plan.draft,
        "prerelease": plan.prerelease,
    }


def _github_token() -> str | None:
    return (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip() or None


def _api_request(
    method: str,
    url: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    data: bytes | None = None,
    content_type: str = "application/json",
) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SlicerDDSurfer-release-script",
    }
    request_data = data
    if payload is not None:
        request_data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif data is not None:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=request_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {url} failed: HTTP {exc.code}: {details}") from exc


def get_existing_release(plan: ReleasePlan, *, token: str) -> dict[str, Any] | None:
    owner_repo = urllib.parse.quote(plan.repository, safe="/")
    tag = urllib.parse.quote(plan.tag, safe="")
    url = f"https://api.github.com/repos/{owner_repo}/releases/tags/{tag}"
    try:
        return _api_request("GET", url, token=token)
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):
            return None
        raise


def create_release(plan: ReleasePlan, *, token: str) -> dict[str, Any]:
    existing = get_existing_release(plan, token=token)
    if existing is not None:
        if plan.reuse_existing:
            return existing
        raise RuntimeError(f"Release for tag {plan.tag} already exists. Use --reuse-existing to upload assets to it.")
    owner_repo = urllib.parse.quote(plan.repository, safe="/")
    return _api_request(
        "POST",
        f"https://api.github.com/repos/{owner_repo}/releases",
        token=token,
        payload=release_payload(plan),
    )


def upload_asset(release: dict[str, Any], asset: Path, *, token: str) -> dict[str, Any]:
    upload_url = str(release.get("upload_url") or "").split("{", 1)[0]
    if not upload_url:
        raise RuntimeError("GitHub release response did not include upload_url.")
    name = urllib.parse.quote(asset.name)
    label = urllib.parse.quote(asset.name)
    content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
    data = asset.read_bytes()
    return _api_request(
        "POST",
        f"{upload_url}?name={name}&label={label}",
        token=token,
        data=data,
        content_type=content_type,
    )


def list_release_assets(release: dict[str, Any], *, token: str) -> list[dict[str, Any]]:
    assets_url = str(release.get("assets_url") or "")
    if not assets_url:
        return []
    result = _api_request("GET", assets_url, token=token)
    return result if isinstance(result, list) else []


def delete_release_asset(asset: dict[str, Any], *, token: str) -> None:
    url = str(asset.get("url") or "")
    if not url:
        raise RuntimeError(f"Release asset has no delete URL: {asset.get('name')}")
    _api_request("DELETE", url, token=token)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create the SlicerDDSurfer GitHub Release and upload artifacts.")
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY, help="GitHub repository in owner/name form.")
    parser.add_argument("--tag", default=DEFAULT_TAG, help="Release tag. Defaults to v0.1.0.")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="Release title.")
    parser.add_argument("--notes-file", type=Path, default=DEFAULT_NOTES, help="Markdown release body.")
    parser.add_argument("--asset", action="append", type=Path, help="Additional artifact to upload. Can be repeated.")
    parser.add_argument("--fresh-clone-report", type=Path, help="fresh_clone_smoke_report.json to upload.")
    parser.add_argument("--publish", action="store_true", help="Create a non-draft release. Default is draft.")
    parser.add_argument("--final", action="store_true", help="Do not mark the release as prerelease.")
    parser.add_argument("--reuse-existing", action="store_true", help="Upload assets to an existing release for the tag.")
    parser.add_argument("--replace-existing-assets", action="store_true", help="Delete same-named release assets before uploading.")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print the planned GitHub API action.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan = build_release_plan(args)
        validate_plan(plan)
        payload = release_payload(plan)
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "kind": "slicerdsurfer_github_release_plan",
                        "version": 1,
                        "plan": plan.to_dict(),
                        "payload": {key: value for key, value in payload.items() if key != "body"},
                        "body_characters": len(payload["body"]),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        token = _github_token()
        if not token:
            raise RuntimeError("Set GITHUB_TOKEN or GH_TOKEN, or run with --dry-run to validate the release plan.")
        release = create_release(plan, token=token)
        existing_assets = {str(item.get("name") or ""): item for item in list_release_assets(release, token=token)}
        uploaded = []
        for asset in plan.assets:
            existing = existing_assets.get(asset.name)
            if existing is not None:
                if not plan.replace_existing_assets:
                    raise RuntimeError(
                        f"Release asset already exists: {asset.name}. Use --replace-existing-assets to replace it."
                    )
                delete_release_asset(existing, token=token)
            uploaded.append(upload_asset(release, asset, token=token))
        print(
            json.dumps(
                {
                    "kind": "slicerdsurfer_github_release_result",
                    "version": 1,
                    "html_url": release.get("html_url"),
                    "tag": plan.tag,
                    "uploaded_assets": [item.get("name") for item in uploaded],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        print(f"[github-release] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
