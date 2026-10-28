from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.extension_runtime.runtime_resources import runtime_files
from scripts.package_slicer_extension import package_extension
from scripts.stage_slicer_extension import stage_extension


ROOT = Path(__file__).resolve().parents[2]
OMITTED = (
    "docs/site/index.html",
    "docs/website/README.md",
    "website/index.html",
    "Testing/Python/test_runtime_distribution.py",
    "docs/release/PERFORMANCE_OPTIMIZATIONS.md",
    "docs/release/benchmarks/complete_models_20261020.json",
    "scripts/benchmark_complete_models.py",
    "scripts/build_performance_site.py",
    "scripts/audit_performance_upstreams.py",
    "docs/site/performance.html",
    "docs/site/assets/data/performance.json",
    "scripts/benchmark_future_candidate.py",
)


class RuntimeDistributionTest(unittest.TestCase):
    def test_runtime_manifest_keeps_code_and_excludes_maintainer_material(self) -> None:
        files = set(runtime_files(ROOT))
        self.assertTrue({"microstructure/freewater_wls.py", "tractography/wma_transform.py",
                         "licenses/DIPY.txt", "scripts/run_wma_registration.py"} <= files)
        self.assertTrue(files.isdisjoint(OMITTED))
        self.assertFalse(any(path.startswith("scripts/benchmark_") for path in files))
        self.assertEqual(
            {path for path in files if path.startswith("docs/release/benchmarks/")},
            {f"docs/release/benchmarks/module_runtimes_{date}.csv"
             for date in ("20261013", "20261015", "20261017")},
        )

    def test_optional_sparse_checkout_contains_every_runtime_resource(self) -> None:
        git = shutil.which("git")
        if not git:
            self.skipTest("Git is unavailable")
        files = set(runtime_files(ROOT))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def run(*args: str, input: str | None = None) -> str:
                result = subprocess.run([git, "-c", "commit.gpgsign=false", *args], cwd=root,
                                        input=input, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout

            run("init", "--quiet")
            for relative in sorted(files | set(OMITTED)):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"fixture {relative}\n", encoding="utf-8")
            selection = "scripts/extension_runtime/runtime_checkout.txt"
            (root / selection).write_bytes((ROOT / selection).read_bytes())
            run("add", ".")
            run("-c", "user.name=Distribution test", "-c", "user.email=test@example.invalid",
                "commit", "--quiet", "-m", "Local resource fixture")
            omitted_objects = {relative: run("rev-parse", f"HEAD:{relative}").strip()
                               for relative in OMITTED}
            run("config", "uploadpack.allowFilter", "true")
            checkout = root / "runtime-checkout"
            run("clone", "--quiet", "--no-checkout", "--filter=blob:none", "--depth", "1",
                root.as_uri(), str(checkout))
            root = checkout
            patterns = run("show", f"HEAD:{selection}")
            run("sparse-checkout", "set", "--no-cone", "--stdin", input=patterns)
            run("checkout")
            for relative in files:
                self.assertTrue((root / relative).is_file(), relative)
            for relative in OMITTED:
                self.assertFalse((root / relative).exists(), relative)
            missing = set(run("rev-list", "--objects", "--all", "--missing=print").splitlines())
            for relative, oid in omitted_objects.items():
                self.assertIn("?" + oid, missing, f"Unnecessary blob downloaded: {relative}")
            run("sparse-checkout", "disable")
            self.assertTrue((root / "docs/release/PERFORMANCE_OPTIMIZATIONS.md").is_file())

    def test_actual_plugin_archive_does_not_contain_reports_or_web_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged = stage_extension(root / "staged", slicer_version="Slicer-5.10",
                                     clean=True, link_mode="copy")
            archive_path = root / "SlicerDSpace.tar.gz"
            package_extension(Path(str(staged["extension_root"])), archive_path)
            with tarfile.open(archive_path, "r:gz") as archive:
                names = set(archive.getnames())
            prefix = "SlicerDSpace/lib/Slicer-5.10/qt-scripted-modules/"
            for relative in runtime_files(ROOT):
                self.assertIn(prefix + relative, names)
            for relative in OMITTED:
                self.assertNotIn(prefix + relative, names)

    def test_benchmark_harness_runs_outside_the_installation(self) -> None:
        from scripts.benchmark_complete_models import stage_benchmark_harness
        with tempfile.TemporaryDirectory() as tmp:
            harness = stage_benchmark_harness(Path(tmp))
            self.assertEqual(harness.read_bytes(), (ROOT/'scripts/benchmark_complete_models.py').read_bytes())
            process = subprocess.run([sys.executable, str(harness), '--help'],
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stdout+process.stderr)
            self.assertIn('--stages', process.stdout)
        self.assertNotIn('scripts/benchmark_complete_models.py', runtime_files(ROOT))


if __name__ == "__main__":
    unittest.main()
