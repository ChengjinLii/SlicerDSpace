#!/usr/bin/env python3
"""Launch two isolated real Slicer sessions to check brain-mask persistence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.slicer_acceptance import private_slicer_home, private_user_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slicer", type=Path, required=True)
    parser.add_argument("--xvfb", type=Path, required=True, help="Path to xvfb-run")
    parser.add_argument("--report", type=Path, required=True, help="New, unused report directory")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=False)
    launcher_settings = private_slicer_home(args.slicer.resolve(), report / "runtime")
    private_user_settings(report)
    config = report / "user_config.json"
    config.write_text(json.dumps({"ui": {"first_run_wizard_shown": True}}) + "\n")
    (report / "temp").mkdir()
    # Discover only the product module, not repository CLI/helper scripts.
    module_dir = report / "module"
    module_dir.mkdir()
    for name in ("SlicerDDSurfer.py", "Resources", "anatomy", "microstructure", "preprocessing",
                 "shared", "tractography", "connectome"):
        source = REPO / name
        (module_dir / name).symlink_to(source, target_is_directory=source.is_dir())
    env = dict(os.environ, XDG_CONFIG_HOME=str(report / "settings"), XDG_CACHE_HOME=str(report / "cache"),
               TMPDIR=str(report / "temp"), SLICERDDSURFER_USER_CONFIG=str(config),
               SLICERDDSURFER_SMOKE_ROOT=str(report), SLICERDDSURFER_PRIVATE_SLICER_HOME=str(report / "runtime"),
               SLICERDDSURFER_DISABLE_FIRST_RUN_WIZARD="1", QT_AUTO_SCREEN_SCALE_FACTOR="0", QT_SCALE_FACTOR="1",
               PATH=str(args.xvfb.resolve().parent) + os.pathsep + os.environ.get("PATH", ""))
    command = [str(args.xvfb.resolve()), "-a", str(args.slicer.resolve()), "--no-splash", "--ignore-slicerrc",
               "--disable-cli-modules",
               "--launcher-ignore-user-additional-settings", "--launcher-additional-settings", str(launcher_settings),
               "--additional-module-paths", str(module_dir), "--python-script",
               str(REPO / "Testing/Python/slicer_brain_mask_gui_smoke.py")]
    for phase in ("select", "restore"):
        env["SLICERDDSURFER_BRAIN_MASK_SMOKE_PHASE"] = phase
        with (report / f"slicer_{phase}.log").open("w") as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise RuntimeError(f"Slicer {phase} timed out; see {report}")
        record_path = report / f"brain_mask_{phase}.json"
        record = json.loads(record_path.read_text()) if record_path.is_file() else {}
        if code or record.get("status") != "PASS":
            raise RuntimeError(f"Slicer {phase} failed (exit {code}); see {report}")
        print(f"PASS {phase}: {len(record['checks'])} checks", flush=True)
    print(f"Report: {report}", flush=True)


if __name__ == "__main__":
    main()
