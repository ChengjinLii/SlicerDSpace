#!/usr/bin/env python3
"""Pre-release repository audit for SlicerDDSurfer."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
LFS_REQUIRED_SUFFIXES = (
    ".pt",
    ".pkl",
    ".nii.gz",
    ".mgz",
    ".tck",
    ".trk",
    ".vtk",
    ".vtp",
    ".obj",
    ".stl",
)
FORBIDDEN_TRACKED_PREFIXES = (
    "third_party/",
    "SlicerDDSurfer-test/",
    "outputs/",
)
FORBIDDEN_STATUS_PARTS = (
    "/outputs/",
    "/gui_smoke/",
    "/Testing/Temporary/",
)


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    category: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "category": self.category,
            "path": self.path,
            "message": self.message,
        }


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", REPO_ROOT.as_posix(), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _git_lines(args: list[str]) -> list[str]:
    completed = _run_git(args)
    if completed.returncode != 0:
        return []
    return [line for line in completed.stdout.splitlines() if line]


def _status_entries() -> list[dict[str, str]]:
    entries = []
    for line in _git_lines(["status", "--porcelain=v1"]):
        status = line[:2]
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append({"status": status, "path": path})
    return entries


def _tracked_files() -> list[str]:
    return _git_lines(["ls-files"])


def _untracked_files() -> list[str]:
    return [entry["path"] for entry in _status_entries() if entry["status"] == "??"]


def _file_size(path: str) -> int:
    try:
        return (REPO_ROOT / path).stat().st_size
    except OSError:
        return 0


def _matches_suffix(path: str, suffixes: Iterable[str]) -> bool:
    return any(path.endswith(suffix) for suffix in suffixes)


def _read_lfs_patterns() -> set[str]:
    attributes = REPO_ROOT / ".gitattributes"
    patterns: set[str] = set()
    if not attributes.is_file():
        return patterns
    for line in attributes.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        token = line.split()[0]
        if "filter=lfs" in line:
            patterns.add(token)
    return patterns


def _read_text_if_exists(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _extract_cmake_set_items(text: str, variable: str) -> list[str]:
    marker = f"set({variable}"
    start = text.find(marker)
    if start < 0:
        return []
    start = text.find("\n", start)
    end = text.find(")", start)
    if start < 0 or end < 0:
        return []
    items: list[str] = []
    for line in text[start:end].splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if line:
            items.append(line)
    return items


def audit_repository(*, large_file_mb: float = 20.0) -> dict[str, object]:
    issues: list[AuditIssue] = []
    status = _status_entries()
    tracked = _tracked_files()
    untracked = _untracked_files()
    large_threshold = int(large_file_mb * 1024 * 1024)

    if not (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines().__contains__("third_party/"):
        issues.append(
            AuditIssue(
                severity="blocker",
                category="gitignore",
                path=".gitignore",
                message="third_party/ is not ignored.",
            )
        )

    lfs_patterns = _read_lfs_patterns()
    for suffix in LFS_REQUIRED_SUFFIXES:
        if f"*{suffix}" not in lfs_patterns:
            issues.append(
                AuditIssue(
                    severity="blocker",
                    category="lfs",
                    path=".gitattributes",
                    message=f"Missing Git LFS rule for *{suffix}.",
                )
            )

    cmake_text = _read_text_if_exists(REPO_ROOT / "CMakeLists.txt")
    if not cmake_text:
        issues.append(
            AuditIssue(
                severity="blocker",
                category="cmake_packaging",
                path="CMakeLists.txt",
                message="Top-level CMakeLists.txt is missing or unreadable.",
            )
        )
    else:
        scripted_entries = _extract_cmake_set_items(cmake_text, "MODULE_PYTHON_SCRIPTS")
        if scripted_entries != ["${MODULE_NAME}.py"]:
            issues.append(
                AuditIssue(
                    severity="blocker",
                    category="cmake_packaging",
                    path="CMakeLists.txt",
                    message=(
                        "MODULE_PYTHON_SCRIPTS must contain only ${MODULE_NAME}.py. "
                        f"Found: {scripted_entries or 'none'}"
                    ),
                )
            )
        resource_entries = set(_extract_cmake_set_items(cmake_text, "MODULE_PYTHON_RESOURCES"))
        forbidden_top_level_python_resources = {"run_subject_pipeline.py", "workflow_catalog.py"}
        leaked_resources = sorted(forbidden_top_level_python_resources & resource_entries)
        if leaked_resources:
            issues.append(
                AuditIssue(
                    severity="blocker",
                    category="cmake_packaging",
                    path="CMakeLists.txt",
                    message=(
                        "Top-level Python helper resources can be scanned as Slicer modules. "
                        f"Move them under a package directory before packaging: {', '.join(leaked_resources)}."
                    ),
                )
            )
        if "third_party" in cmake_text:
            issues.append(
                AuditIssue(
                    severity="blocker",
                    category="cmake_packaging",
                    path="CMakeLists.txt",
                    message="CMakeLists.txt must not package or reference third_party content.",
                )
            )
        if "SCRIPTS ${MODULE_PYTHON_SCRIPTS}" not in cmake_text:
            issues.append(
                AuditIssue(
                    severity="blocker",
                    category="cmake_packaging",
                    path="CMakeLists.txt",
                    message="slicerMacroBuildScriptedModule must use the audited MODULE_PYTHON_SCRIPTS list.",
                )
            )

    s4ext_text = _read_text_if_exists(REPO_ROOT / "SlicerDDSurfer.s4ext")
    if not s4ext_text:
        issues.append(
            AuditIssue(
                severity="blocker",
                category="extension_descriptor",
                path="SlicerDDSurfer.s4ext",
                message="Slicer extension descriptor is missing or unreadable.",
            )
        )
    else:
        required_s4ext_tokens = (
            "scm git",
            "scmurl ",
            "scmrevision ",
            "depends SlicerDMRI PyTorch",
            "build_subdirectory .",
            "category Diffusion",
            "enabled 1",
        )
        for token in required_s4ext_tokens:
            if token not in s4ext_text:
                issues.append(
                    AuditIssue(
                        severity="blocker",
                        category="extension_descriptor",
                        path="SlicerDDSurfer.s4ext",
                        message=f"Missing required .s4ext entry containing: {token}",
                    )
                )

    for path in tracked:
        if any(path.startswith(prefix) for prefix in FORBIDDEN_TRACKED_PREFIXES):
            issues.append(
                AuditIssue(
                    severity="blocker",
                    category="tracked_forbidden_path",
                    path=path,
                    message="Generated outputs or third_party content should not be tracked.",
                )
            )
        size = _file_size(path)
        if size >= large_threshold and not _matches_suffix(path, LFS_REQUIRED_SUFFIXES):
            issues.append(
                AuditIssue(
                    severity="blocker",
                    category="tracked_large_file",
                    path=path,
                    message=f"Tracked file is {size} bytes and is not covered by the expected LFS suffix list.",
                )
            )

    for path in untracked:
        if any(part in f"/{path}" for part in FORBIDDEN_STATUS_PARTS):
            issues.append(
                AuditIssue(
                    severity="blocker",
                    category="untracked_output",
                    path=path,
                    message="Untracked runtime output should not be committed.",
                )
            )
        size = _file_size(path)
        if size >= large_threshold:
            issues.append(
                AuditIssue(
                    severity="blocker",
                    category="untracked_large_file",
                    path=path,
                    message=f"Untracked file is {size} bytes; confirm it is ignored or stored with Git LFS before release.",
                )
            )

    dirty_source_changes = [
        entry
        for entry in status
        if entry["status"] != "??" and not any(part in f"/{entry['path']}" for part in FORBIDDEN_STATUS_PARTS)
    ]
    if dirty_source_changes:
        issues.append(
            AuditIssue(
                severity="warning",
                category="dirty_worktree",
                path=".",
                message=f"{len(dirty_source_changes)} tracked source file(s) have uncommitted changes.",
            )
        )

    blockers = [issue for issue in issues if issue.severity == "blocker"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    return {
        "kind": "slicerddsurfer_release_audit",
        "repo_root": REPO_ROOT.as_posix(),
        "status_entries": status,
        "tracked_file_count": len(tracked),
        "untracked_file_count": len(untracked),
        "large_file_threshold_mb": large_file_mb,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "issues": [issue.to_dict() for issue in issues],
        "release_ready": not blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--large-file-mb", type=float, default=20.0)
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    parser.add_argument("--warn-only", action="store_true", help="Always exit 0 after printing the audit.")
    args = parser.parse_args(argv)

    report = audit_repository(large_file_mb=args.large_file_mb)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"release_ready={report['release_ready']}")
        print(f"blockers={report['blocker_count']} warnings={report['warning_count']}")
        for issue in report["issues"]:
            print(f"- {issue['severity']} {issue['category']} {issue['path']}: {issue['message']}")
    if args.warn_only:
        return 0
    return 0 if report["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
