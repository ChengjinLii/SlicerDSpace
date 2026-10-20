#!/usr/bin/env python3
"""Verify that the public Pages artifact cannot include private project documents."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def audit(root=ROOT):
    site = root / "docs/site"
    allowed_top = {".nojekyll", "index.html", "404.html"}
    allowed_extensions = {
        "assets/css": {".css"},
        "assets/js": {".js"},
        "assets/img": {".png", ".jpg"},
        "assets/fonts": {".woff2", ".txt"},
        "media": {".mp4", ".srt"},
    }
    problems = []
    files, total = [], 0
    if not site.is_dir() or site.is_symlink():
        problems.append("docs/site must be a real, dedicated directory")
    for path in sorted(site.rglob("*")):
        relative = path.relative_to(site).as_posix()
        if path.is_symlink():
            problems.append("Symlinks are not public website artifacts: " + relative)
            continue
        if path.is_dir():
            continue
        parent = path.parent.relative_to(site).as_posix()
        if relative not in allowed_top and path.suffix.lower() not in allowed_extensions.get(parent, set()):
            problems.append("Unexpected public file: " + relative)
        files.append(relative)
        total += path.stat().st_size
    for name in allowed_top:
        if name not in files:
            problems.append("Missing public entry: " + name)
    return dict(
        status="pass" if not problems else "fail",
        artifact_path="docs/site",
        file_count=len(files),
        total_bytes=total,
        findings=problems,
        scope="Allowlisted public assets only; no private documentation, experiments or source tree",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = audit(args.root.resolve())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "pass" else 1)
