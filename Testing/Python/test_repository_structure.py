#!/usr/bin/env python3
"""Repository structure smoke tests."""

from __future__ import annotations

import unittest
import subprocess
import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_PACKAGE_NAMES = (
    "sharedpipeline",
    "ddsurferpipeline",
    "ddparcpipeline",
    "ddsegpipeline",
    "microstructurepipeline",
)
SCAN_ROOTS = (
    "SlicerDDSurfer.py",
    "shared",
    "surface",
    "parcellation",
    "segmentation",
    "microstructure",
    "tractography",
    "connectome",
    "workflow_catalog.py",
    "shared/workflow_catalog.py",
)
ALLOWED_ROOT_FILES = {
    ".gitattributes",
    ".gitignore",
    ".zenodo.json",
    "CITATION.cff",
    "CMakeLists.txt",
    "LICENSE",
    "Makefile",
    "README.md",
    "README.zh-CN.md",
    "SlicerDDSurfer.py",
    "SlicerDDSurfer.s4ext",
    "codemeta.json",
    "pyproject.toml",
    "run_postprocess_docker.py",
    "run_subject_pipeline.py",
    "THIRD_PARTY_NOTICES.md",
    "workflow_catalog.py",
}
FORBIDDEN_TRACKED_PATH_PARTS = (
    "manuscript_nature_protocols",
    "local_reports",
    "release_artifacts",
)
FORBIDDEN_TRACKED_ASSET_PREFIXES = (
    "Resources/Data/",
    "surface/template/",
    "segmentation/weights/",
    "parcellation/weights/",
)
FORBIDDEN_TRACKED_ROOT_PATTERNS = (
    "GOAL_PROGRESS_",
    "LOCAL_RELEASE_VALIDATION_",
)


class RepositoryStructureTest(unittest.TestCase):
    def test_tracked_root_files_stay_small_and_intentional(self) -> None:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        root_files = {
            relative
            for relative in result.stdout.splitlines()
            if relative and "/" not in relative and (REPO_ROOT / relative).is_file()
        }
        self.assertEqual(sorted(root_files - ALLOWED_ROOT_FILES), [])

    def test_root_helpers_remain_thin_compatibility_entry_points(self) -> None:
        for name in ("run_subject_pipeline.py", "run_postprocess_docker.py", "workflow_catalog.py"):
            tree = ast.parse((REPO_ROOT / name).read_text(encoding="utf-8"))
            implementations = [node for node in ast.walk(tree) if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            self.assertEqual(implementations, [], name)

    def test_ci_dependencies_and_local_outputs_have_dedicated_locations(self) -> None:
        self.assertTrue((REPO_ROOT / "scripts/dev/requirements-ci.txt").is_file())
        self.assertFalse((REPO_ROOT / "requirements-ci.txt").exists())
        self.assertFalse((REPO_ROOT / "release_artifacts").exists())
        for name in ("ci.yml", "release.yml"):
            text = (REPO_ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn("-r scripts/dev/requirements-ci.txt", text)

    def test_cache_settings_preserve_scientific_evidence(self) -> None:
        project = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn('cache_dir = "ignore/cache/pytest"', project)
        self.assertIn("PYTHONPYCACHEPREFIX ?= $(CURDIR)/ignore/cache/pycache", makefile)
        cleanup = makefile.split("\nclean-local:\n", 1)[1].split("\nlint:\n", 1)[0]
        self.assertNotIn("ignore/local_reports", cleanup)
        self.assertNotIn("SMOKE_ROOT", cleanup)
        self.assertNotIn("ignore/releases", cleanup)

    def test_non_project_artifacts_are_not_tracked(self) -> None:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        offenders: list[str] = []
        for relative in result.stdout.splitlines():
            parts = relative.split("/")
            if any(part in FORBIDDEN_TRACKED_PATH_PARTS for part in parts):
                offenders.append(relative)
                continue
            name = Path(relative).name
            if relative.endswith(".html") or name in {"goal.md", "goal_completion_audit.md", "AGENTS.md"}:
                offenders.append(relative)
                continue
            if "/" not in relative and any(name.startswith(prefix) for prefix in FORBIDDEN_TRACKED_ROOT_PATTERNS):
                offenders.append(relative)
        self.assertEqual(offenders, [])

    def test_product_code_does_not_reference_legacy_root_packages(self) -> None:
        offenders: list[str] = []
        for relative in SCAN_ROOTS:
            path = REPO_ROOT / relative
            files = [path] if path.is_file() else sorted(path.rglob("*.py"))
            for file_path in files:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                for legacy_name in LEGACY_PACKAGE_NAMES:
                    if legacy_name in text:
                        offenders.append(f"{file_path.relative_to(REPO_ROOT)}: {legacy_name}")
        self.assertEqual(offenders, [])

    def test_third_party_reference_tree_is_gitignored(self) -> None:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "third_party/whitematteranalysis"],
            cwd=REPO_ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_model_assets_are_not_tracked_in_code_repository(self) -> None:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        offenders = [
            relative
            for relative in result.stdout.splitlines()
            if relative.startswith(FORBIDDEN_TRACKED_ASSET_PREFIXES)
        ]
        self.assertEqual(offenders, [])

    def test_reference_sources_are_explicitly_excluded_from_cmake_packaging(self) -> None:
        cmake_text = (REPO_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn(
            'list(FILTER TRACTOGRAPHY_PYTHON_SCRIPTS EXCLUDE REGEX "/slicer_dmri_reference/")',
            cmake_text,
        )

    def test_untracked_files_are_not_large_runtime_artifacts(self) -> None:
        result = subprocess.run(
            ["git", "ls-files", "-o", "--exclude-standard"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        offenders: list[str] = []
        for relative in result.stdout.splitlines():
            path = REPO_ROOT / relative
            if path.is_file() and path.stat().st_size > 5 * 1024 * 1024:
                offenders.append(f"{relative}: {path.stat().st_size} bytes")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
