#!/usr/bin/env python3
"""Audit Slicer extension metadata that tends to drift before release."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_EXTENSION_DEPENDS = ("SlicerDMRI", "PyTorch")
REQUIRED_TOP_LEVEL_FILES = (
    "LICENSE",
    "CITATION.cff",
    "codemeta.json",
    ".zenodo.json",
    "MODEL_ASSETS.md",
    "RELEASE.md",
)
REQUIRED_HELP_TERMS = (
    "diffusion",
    "surface",
    "parcellation",
    "segmentation",
    "microstructure",
    "tractography",
    "connectome",
)
REQUIRED_README_TERMS = (
    "MODEL_ASSETS.md",
    "scripts/download_model_assets.sh --profile core",
    "SlicerDMRI",
    "PyTorch",
)


@dataclass(frozen=True)
class AuditFinding:
    key: str
    severity: str
    message: str


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_s4ext(path: Path) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for raw_line in _read(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 1:
            fields.setdefault(parts[0], []).append("")
        else:
            fields.setdefault(parts[0], []).append(parts[1].strip())
    return fields


def parse_cmake_extension_depends(path: Path) -> list[str]:
    text = _read(path)
    match = re.search(r"set\s*\(\s*EXTENSION_DEPENDS\s+([^)]+)\)", text, re.IGNORECASE | re.MULTILINE)
    if not match:
        return []
    return [part for part in re.split(r"\s+", match.group(1).strip()) if part]


def parse_module_metadata(path: Path) -> dict[str, Any]:
    text = _read(path)
    metadata: dict[str, Any] = {}
    simple_fields = {
        "title": r"self\.parent\.title\s*=\s*['\"]([^'\"]+)['\"]",
        "categories": r"self\.parent\.categories\s*=\s*\[([^\]]*)\]",
        "dependencies": r"self\.parent\.dependencies\s*=\s*\[([^\]]*)\]",
        "contributors": r"self\.parent\.contributors\s*=\s*\[([^\]]*)\]",
    }
    for key, pattern in simple_fields.items():
        match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
        metadata[key] = match.group(1).strip() if match else ""

    for key in ("helpText", "acknowledgementText"):
        match = re.search(
            rf"self\.parent\.{key}\s*=\s*\((.*?)\n\s*\)",
            text,
            re.MULTILINE | re.DOTALL,
        )
        if not match:
            match = re.search(rf"self\.parent\.{key}\s*=\s*['\"]([^'\"]+)['\"]", text)
        metadata[key] = match.group(1).strip() if match else ""
    return metadata


def audit(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    findings: list[AuditFinding] = []
    s4ext_path = repo_root / "SlicerDDSurfer.s4ext"
    cmake_path = repo_root / "CMakeLists.txt"
    module_path = repo_root / "SlicerDDSurfer.py"
    readme_path = repo_root / "README.md"

    for relative in REQUIRED_TOP_LEVEL_FILES:
        if not (repo_root / relative).exists():
            findings.append(AuditFinding(relative, "error", f"Missing release metadata file: {relative}"))

    s4ext = parse_s4ext(s4ext_path)
    s4ext_depends = tuple(s4ext.get("depends", [""])[0].split())
    cmake_depends = tuple(parse_cmake_extension_depends(cmake_path))
    if s4ext_depends != cmake_depends:
        findings.append(
            AuditFinding(
                "extension_dependencies",
                "error",
                f"SlicerDDSurfer.s4ext depends {s4ext_depends!r} does not match CMake EXTENSION_DEPENDS {cmake_depends!r}",
            )
        )
    for dependency in REQUIRED_EXTENSION_DEPENDS:
        if dependency not in s4ext_depends:
            findings.append(AuditFinding("extension_dependencies", "error", f"Missing extension dependency: {dependency}"))

    for key in ("scm", "scmurl", "scmrevision", "homepage", "category", "contributors", "description", "enabled"):
        if not s4ext.get(key, [""])[0]:
            findings.append(AuditFinding(f"s4ext:{key}", "error", f"Missing .s4ext field: {key}"))

    metadata = parse_module_metadata(module_path)
    if metadata.get("title") != "SlicerDDSurfer":
        findings.append(AuditFinding("module:title", "error", "Module title should be SlicerDDSurfer"))
    if "Diffusion" not in metadata.get("categories", ""):
        findings.append(AuditFinding("module:categories", "error", "Module should appear under the Diffusion category"))
    if metadata.get("dependencies", "").strip():
        findings.append(
            AuditFinding(
                "module:dependencies",
                "error",
                "Runtime module dependencies should stay empty; dependency doctor reports optional blockers after UI load",
            )
        )
    help_text = metadata.get("helpText", "").lower()
    missing_help_terms = [term for term in REQUIRED_HELP_TERMS if term not in help_text]
    if missing_help_terms:
        findings.append(
            AuditFinding(
                "module:helpText",
                "error",
                f"Module help text is missing workflow terms: {', '.join(missing_help_terms)}",
            )
        )
    if not metadata.get("contributors"):
        findings.append(AuditFinding("module:contributors", "error", "Module contributors are missing"))
    if not metadata.get("acknowledgementText"):
        findings.append(AuditFinding("module:acknowledgementText", "error", "Module acknowledgement text is missing"))

    readme = _read(readme_path)
    missing_readme_terms = [term for term in REQUIRED_README_TERMS if term not in readme]
    if missing_readme_terms:
        findings.append(
            AuditFinding(
                "readme:release_paths",
                "error",
                f"README is missing release/setup terms: {', '.join(missing_readme_terms)}",
            )
        )

    return {
        "status": "pass" if not findings else "fail",
        "error_count": sum(1 for finding in findings if finding.severity == "error"),
        "warning_count": sum(1 for finding in findings if finding.severity == "warning"),
        "s4ext_depends": list(s4ext_depends),
        "cmake_depends": list(cmake_depends),
        "findings": [finding.__dict__ for finding in findings],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Write machine-readable audit output.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root to audit.")
    args = parser.parse_args(argv)

    result = audit(args.repo_root.resolve())
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Slicer extension metadata audit: {result['status']}")
        for finding in result["findings"]:
            print(f"[{finding['severity']}] {finding['key']}: {finding['message']}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
