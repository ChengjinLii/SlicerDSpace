#!/usr/bin/env python3
"""Check active first-party Markdown links, screenshots and compact-UI wording."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def active_docs(root):
    paths = [root / name for name in ("README.md", "README.zh-CN.md", "THIRD_PARTY_NOTICES.md")]
    for directory in ("docs/setup", "docs/assets", "docs/architecture"):
        paths.extend(sorted((root / directory).glob("*.md")))
    paths.extend(root / name for name in (
        "docs/README.md", "docs/README.zh-CN.md", "docs/release/RELEASE.md",
        "docs/release/EXTENSION_READINESS.md", "docs/release/EXTENSION_READINESS.zh-CN.md",
        "docs/release/DISTRIBUTION_VALIDATION_20261011.md",
        "docs/release/DISTRIBUTION_VALIDATION_20261012.md",
        "docs/release/MODULE_RUNTIMES_20261013.md",
        "docs/release/MODULE_RUNTIMES_20261013.zh-CN.md",
        "docs/release/GPU_POLICY_20261013.md",
        "docs/release/PLATFORM_AUDIT_20261015.md",
        "docs/release/BUNDLE_QC_20261015.md",
        "docs/release/BUNDLE_QC_20261015.zh-CN.md",
        "docs/release/WMQL_CST_20261015.md",
        "docs/release/WMQL_CST_20261015.zh-CN.md",
        "docs/release/PIPELINE_QC_20261015.md",
        "docs/release/PIPELINE_QC_20261015.zh-CN.md",
        "docs/release/MODULE_RUNTIMES_20261015.md",
        "docs/release/MODULE_RUNTIMES_20261015.zh-CN.md",
        "docs/release/SCIENTIFIC_CLOSURE_20261015.md",
        "docs/release/SCIENTIFIC_CLOSURE_20261015.zh-CN.md",
        "docs/release/CSD_ACT_DIAGNOSIS_20261015.md",
        "docs/release/CSD_ACT_DIAGNOSIS_20261015.zh-CN.md",
        "docs/release/PERFORMANCE_OPTIMIZATIONS.md",
        "docs/release/PERFORMANCE_OPTIMIZATIONS.zh-CN.md"))
    return paths


def audit(root=ROOT):
    findings = []
    paths = active_docs(root)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(root).as_posix()
        if not text.startswith('<div align="center">') or "\n---\n" not in text:
            findings.append({"file": relative, "error": "Missing centered masthead or section divider"})
        filtered = []
        fence = None
        for line in text.splitlines():
            match = re.match(r"\s*([\x60~]{3,})", line)
            if match:
                marker = match.group(1)[0]
                fence = None if fence == marker else marker
            elif fence is None:
                filtered.append(line)
        content = "\n".join(filtered)
        targets = re.findall(r"\]\(([^)]+)\)", content)
        targets.extend(re.findall(r'(?:src|href)="([^"]+)"', content))
        for target in targets:
            target = target.strip()
            if target.startswith("<"):
                target = target[1:].partition(">")[0]
            else:
                target = target.partition(' "')[0]
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            destination = (path.parent / unquote(url.path)).resolve()
            if not destination.is_relative_to(root.resolve()) or not destination.exists():
                findings.append({"file": relative, "error": "Broken local link", "target": target})
        for obsolete in ("click `First-run setup wizard`", "click `Demo / Try with sample data`"):
            if obsolete.lower() in text.lower():
                findings.append({"file": relative, "error": "Obsolete visible UI instruction", "text": obsolete})
    return {"status": "pass" if not findings else "fail", "documents_checked": len(paths),
            "findings": findings, "scope": "Active local links/style/UI wording; no external URL availability or historical report rewriting"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = audit(args.root.resolve())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
