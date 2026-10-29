#!/usr/bin/env python3
"""Run real Linux Slicer smoke tests in isolated settings and X displays."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SMOKES = (
    "extension_install", "environment_button", "gui_operations",
    "dependency_workflow", "demo_workflow", "run_plan_panel",
    "cancel_background", "output_tree_button", "surface_coordinate",
    "extension_manager_install",
    "wmql_protocol",
)
AVAILABLE = (*SMOKES, "real_tasks", "input_preparation", "dicom_root", "tissue_review", "shutdown", "batch", "setup_tree", "model_assets", "results", "preprocessing_cache", "compact_ui", "saf_product", "bundle_products", "parallel_models", "ukf", "regions", "algorithm_labels", "selected_setup", "algorithm_picker", "environment_async", "gui_state", "log_batch", "input_inspection", "surface_runtime", "single_subject", "agent_install", "experiments")


def private_slicer_home(slicer, destination):
    """Keep portable-build revision settings out of the shared installation."""
    environment = subprocess.check_output(
        [str(slicer), "--launcher-dump-environment"], text=True, timeout=30,
    )
    homes = [line.partition("=")[2] for line in environment.splitlines()
             if line.startswith("SLICER_HOME=")]
    if len(homes) != 1:
        raise RuntimeError("The Slicer launcher did not report one SLICER_HOME")
    source = Path(homes[0]).resolve()
    if not (source / "bin/SlicerApp-real").is_file():
        raise RuntimeError(f"Not an installed Slicer runtime: {source}")
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("Slicer", "bin", "lib", "share", "include", "libexec", "resources"):
        target = source / name
        if not target.exists():
            continue
        link = destination / name
        if link.exists() or link.is_symlink():
            if not link.is_symlink() or link.resolve() != target:
                raise RuntimeError(f"Refusing to replace a private-runtime path: {link}")
        else:
            link.symlink_to(target, target_is_directory=target.is_dir())
    (destination / "slicer.org").mkdir(exist_ok=True)
    settings = destination.parent / "launcher-settings.ini"
    if "\n" in str(destination) or "\r" in str(destination):
        raise ValueError("The private runtime path contains an INI newline")
    settings.write_text(f"[EnvironmentVariables]\nSLICER_HOME={destination}\n")
    return settings


def private_user_settings(destination):
    settings = destination / "settings/slicer.org/Slicer.ini"
    settings.parent.mkdir(parents=True, exist_ok=True)
    if not settings.exists():
        settings.write_text(
            "[General]\n"
            f"DatabaseDirectory_0.8.1={destination / 'DICOMDatabase'}\n"
            f"DefaultScenePath={destination}\n"
            "[Extensions]\nAutoUpdateCheck=false\nAutoUpdateInstall=false\n"
            "AutoInstallDependencies=false\n"
            "[ApplicationUpdate]\nAutoUpdateCheck=false\n"
        )
    return settings


def run(args):
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/stage_slicer_extension.py"),
                    "--install-root", str(report / "install"), "--slicer-version", "Slicer-5.10",
                    "--link-mode", "copy"], check=True)
    extension = report / "install/SlicerDSpace"
    module = extension / "lib/Slicer-5.10/qt-scripted-modules"
    archive = getattr(args, 'extension_archive', None)
    if archive is None:
        archive = report / "packages/SlicerDSpace.tar.gz"
        subprocess.run([sys.executable, str(ROOT / "scripts/package_slicer_extension.py"),
                        "--extension-root", str(extension), "--output", str(archive)], check=True)
        archive_origin = 'staging_helper'
    else:
        archive = archive.resolve()
        archive_origin = 'supplied_package'
    subprocess.run([sys.executable, str(ROOT / "scripts/audit_extension_package.py"),
                    str(archive), "--source-root", str(ROOT),
                    "--report", str(report / "package_resource_audit.json")], check=True)
    result = {"kind": "slicer_gui_acceptance", "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "working_tree_patch_sha256": hashlib.sha256(subprocess.check_output(["git", "diff"], cwd=ROOT)).hexdigest(),
              "extension_archive": str(archive), "archive_origin": archive_origin,
              "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "tests": []}
    for name in args.tests:
        script = ROOT / "Testing/Python" / f"slicer_{name}_smoke.py"
        if not script.is_file():
            raise FileNotFoundError(script)
        dest = report / name
        dest.mkdir(parents=True, exist_ok=True)
        script_snapshot = dest / "test_script.py"
        shutil.copy2(script, script_snapshot)
        script_hash = hashlib.sha256(script_snapshot.read_bytes()).hexdigest()
        inspector_snapshot = dest / 'archive_layout.py'
        shutil.copy2(ROOT / 'scripts/extension_runtime/archive_layout.py', inspector_snapshot)
        bootstrap = dest / "settings_bootstrap.py"
        shutil.copy2(ROOT / "Testing/Python/slicer_settings_bootstrap.py", bootstrap)
        runtime_home = dest / "runtime"
        launcher_settings = private_slicer_home(args.slicer, runtime_home)
        private_user_settings(dest)
        (dest / "temp").mkdir(exist_ok=True)
        config = dest / "user_config.json"
        config.write_text(json.dumps({"ui": {"first_run_wizard_shown": True},
                                      "external_dependencies": {"model_assets_dir": str(args.assets)}}))
        env = dict(os.environ, XDG_CONFIG_HOME=str(dest / "settings"), TMPDIR=str(dest / "temp"),
                   SLICERDSPACE_USER_CONFIG=str(config),
                   SLICERDSPACE_SMOKE_ROOT=str(dest),
                   SLICERDSPACE_TEST_SCRIPT=str(script_snapshot),
                   SLICERDSPACE_PRIVATE_SLICER_HOME=str(runtime_home),
                   SLICERDSPACE_MODEL_ASSETS_DIR=str(args.assets),
                   SLICERDSPACE_EXTENSION_MODULE_DIR=str(module),
                   SLICERDSPACE_EXTENSION_ARCHIVE=str(archive),
                   SLICERDSPACE_ARCHIVE_INSPECTOR=str(inspector_snapshot),
                   SLICERDSPACE_AGENT_INSTALL_HELPER=str(ROOT / '.agents/skills/slicerdspace/scripts/enable_in_slicer.py'),
                   SLICERDSPACE_SMOKE_SUBJECT_ROOT=str(args.subject),
                   SLICERDSPACE_SMOKE_SUBJECT_ID="100307",
                   SLICERDSPACE_SMOKE_RUN_NAME="acceptance_plan",
                   SLICERDSPACE_SMOKE_MICROSTRUCTURE_STAGES="dti",
                   SLICERDSPACE_SMOKE_PLAN_ONLY="1",
                   QT_AUTO_SCREEN_SCALE_FACTOR="0", QT_SCALE_FACTOR="1",
                   XDG_CACHE_HOME=str(dest / "cache"),
                   OMP_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4",
                   PATH=str(args.xvfb.parent) + os.pathsep + os.environ.get("PATH", ""))
        if args.tasks_config:
            env["SLICERDSPACE_TASKS_CONFIG"] = str(args.tasks_config.resolve())
        if args.dicom_fixture:
            env["SLICERDSPACE_DICOM_FIXTURE"] = str(args.dicom_fixture.resolve())
        if args.results_report:
            env["SLICERDSPACE_RESULTS_REPORT"] = str(args.results_report.resolve())
        if args.results_expected_cases:
            env["SLICERDSPACE_RESULTS_EXPECTED_CASES"] = str(args.results_expected_cases)
        command = [str(args.xvfb), "-a", str(args.slicer), "--no-splash", "--ignore-slicerrc",
                   "--launcher-ignore-user-additional-settings",
                   "--launcher-additional-settings", str(launcher_settings)]
        paths = [] if name == "extension_manager_install" else [str(module)]
        paths.extend(str(path.resolve()) for path in args.additional_module_paths)
        if paths:
            command += ["--additional-module-paths", *paths]
        command += ["--python-script", str(bootstrap)]
        log = dest / "slicer.log"
        started = time.monotonic()
        timed_out = False
        print(f"START {name}", flush=True)
        with log.open("w") as stream:
            process = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    code = process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    code = process.wait()
        entry = {"name": name, "status": "TIMEOUT" if timed_out else ("PASS" if code == 0 else "FAIL"),
                 "exit_code": code, "seconds": time.monotonic() - started, "command": command,
                 "script_sha256": script_hash, "script_snapshot": str(script_snapshot), "log": str(log)}
        entry['archive_inspector_sha256'] = hashlib.sha256(inspector_snapshot.read_bytes()).hexdigest()
        isolation_record = dest / "settings_isolation.json"
        if isolation_record.exists():
            entry["settings_isolation"] = json.loads(isolation_record.read_text())
        if not entry.get("settings_isolation", {}).get("passed", False):
            entry["status"] = "FAIL" if not timed_out else "TIMEOUT"
        if name == "shutdown" and not timed_out:
            try:
                shutdown = json.loads((dest / "shutdown.json").read_text())
                entry["shutdown"] = shutdown
                if not shutdown["passed"]:
                    entry["status"] = "FAIL"
            except (OSError, ValueError, KeyError):
                entry["status"] = "FAIL"
        result["tests"].append(entry)
        (report / "gui_acceptance.json").write_text(json.dumps(result, indent=2) + "\n")
        print(f"{entry['status']} {name} ({entry['seconds']:.1f}s): {log}", flush=True)
    return 0 if all(test["status"] == "PASS" for test in result["tests"]) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--slicer", required=True, type=Path)
    parser.add_argument("--xvfb", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--subject", required=True, type=Path)
    parser.add_argument("--additional-module-paths", nargs="*", default=[], type=Path)
    parser.add_argument('--extension-archive', type=Path,
                        help='Existing CPack package to install in extension_manager_install; other tests use the staged copy')
    parser.add_argument("--tests", nargs="+", choices=AVAILABLE, default=list(SMOKES))
    parser.add_argument("--tasks-config", type=Path)
    parser.add_argument("--dicom-fixture", type=Path)
    parser.add_argument("--results-report", type=Path)
    parser.add_argument("--results-expected-cases", type=int)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if not args.assets.is_dir():
        parser.error('--assets must be an existing model-assets directory')
    if args.extension_archive is not None and not args.extension_archive.is_file():
        parser.error('--extension-archive must name an existing package')
    if {'real_tasks', 'bundle_products'}.intersection(args.tests) and args.tasks_config is None:
        parser.error('real_tasks / bundle_products require --tasks-config')
    if args.tasks_config is not None and not args.tasks_config.is_file():
        parser.error('--tasks-config must name an existing JSON file')
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
