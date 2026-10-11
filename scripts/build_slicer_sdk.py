#!/usr/bin/env python3
"""Opt-in SDK configure/build/CTest/CPack validation; never publishes packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import time

try:
    from scripts.audit_extension_package import audit_package
except ModuleNotFoundError:
    from audit_extension_package import audit_package


def build(args):
    source = args.source_root.resolve()
    output = args.build_dir.resolve()
    if output == source or output in source.parents:
        raise ValueError("Build directory must not replace the source tree")
    output.mkdir(parents=True, exist_ok=True)
    evidence = {"kind": "slicerdsurfer_sdk_build", "status": "running", "platform": platform.platform(),
                "source_root": str(source), "slicer_dir": str(args.slicer_dir.resolve()),
                "steps": [], "packages": [], "clean_install_test": "NOT_RUN",
                "scientific_workflows": "NOT_RUN", "sdk_authenticity": "Maintainer-supplied Slicer build tree; must be reviewed separately"}
    try:
        if (output / "CMakeCache.txt").exists() or any(output.glob("*.tar.gz")) or any(output.glob("*.zip")):
            evidence["status"] = "blocked"
            raise ValueError("Use a fresh build directory; existing caches/packages could contaminate release evidence")
        if not (args.slicer_dir / "SlicerConfig.cmake").is_file():
            evidence["status"] = "blocked"
            raise FileNotFoundError("SlicerConfig.cmake missing: provide a real Slicer SDK/build tree, not the application binary directory")
        config_hash = hashlib.sha256((args.slicer_dir / "SlicerConfig.cmake").read_bytes()).hexdigest()
        evidence["slicer_config_sha256"] = config_hash
        evidence["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        evidence["working_tree_patch_sha256"] = hashlib.sha256(subprocess.check_output(["git", "diff", "HEAD"], cwd=source)).hexdigest()
        commands = [
            [args.cmake, "-S", str(source), "-B", str(output), f"-DSlicer_DIR={args.slicer_dir.resolve()}", "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=ON"],
            [args.cmake, "--build", str(output), "--config", "Release", "--parallel", str(args.jobs)],
            [args.ctest, "--test-dir", str(output), "-C", "Release", "--output-on-failure"],
            [args.cpack, "--config", str(output / "CPackConfig.cmake"), "-C", "Release", "-G", args.package_generator],
        ]
        for name, command in zip(("configure", "build", "ctest", "cpack"), commands):
            log = output / f"sdk-{name}.log"
            started = time.monotonic()
            with log.open("w", encoding="utf-8") as stream:
                try:
                    completed = subprocess.run(command, cwd=output, stdout=stream, stderr=subprocess.STDOUT, timeout=args.timeout, check=False)
                    code = completed.returncode
                except subprocess.TimeoutExpired:
                    code = 124
            evidence["steps"].append({"name": name, "command": command, "returncode": code, "seconds": time.monotonic() - started, "log": str(log)})
            if code:
                raise RuntimeError(f"SDK {name} failed; see {log}")
        suffix = ".zip" if args.package_generator == "ZIP" else ".tar.gz"
        packages = sorted(output.glob("*" + suffix))
        if not packages:
            raise RuntimeError("CPack did not produce a package")
        evidence["packages"] = [audit_package(package, source) for package in packages]
        if any(package["status"] != "pass" for package in evidence["packages"]):
            raise RuntimeError("SDK package resource audit failed")
        evidence["status"] = "pass"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        if evidence["status"] != "blocked":
            evidence["status"] = "fail"
        evidence["error"] = str(exc)
    finally:
        (output / "sdk_build_report.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slicer-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--package-generator", choices=("TGZ", "ZIP"), default="TGZ")
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--ctest", default="ctest")
    parser.add_argument("--cpack", default="cpack")
    args = parser.parse_args(argv)
    result = build(args)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
