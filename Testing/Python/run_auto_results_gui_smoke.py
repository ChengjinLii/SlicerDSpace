"""Run automatic-load GUI acceptance with isolated settings and real run manifests."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.slicer_acceptance import private_slicer_home, private_user_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slicer", type=Path, required=True)
    parser.add_argument("--xvfb", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", action="append", type=Path, default=[])
    parser.add_argument("--manifest-root", type=Path)
    parser.add_argument("--dmri-root", type=Path, help="Existing SlicerDMRI lib/Slicer-version directory for native FiberBundle verification")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    manifests = list(args.manifest)
    if args.manifest_root:
        manifests.extend(sorted(args.manifest_root.glob("*/00_run_metadata/snapshot_orchestration_manifest.json")))
    if not manifests or not all(path.is_file() for path in manifests):
        parser.error("Provide existing real run manifests")
    output = args.report.resolve()
    output.mkdir(parents=True, exist_ok=False)
    launcher = private_slicer_home(args.slicer.resolve(), output / "runtime")
    private_user_settings(output)
    config = output / "user_config.json"
    config.write_text(json.dumps({"ui": {"first_run_wizard_shown": True}}))
    listing = output / "source_manifests.json"
    listing.write_text(json.dumps([str(path.resolve()) for path in manifests], indent=2))
    module_dir = output / "module"
    module_dir.mkdir()
    for name in ("SlicerDDSurfer.py", "Resources", "anatomy", "microstructure", "preprocessing",
                 "shared", "tractography", "connectome"):
        source = ROOT / name
        (module_dir / name).symlink_to(source, target_is_directory=source.is_dir())
    env = dict(os.environ, XDG_CONFIG_HOME=str(output / "settings"), XDG_CACHE_HOME=str(output / "cache"),
               SLICERDDSURFER_USER_CONFIG=str(config), SLICERDDSURFER_SMOKE_ROOT=str(output),
               SLICERDDSURFER_AUTO_RESULT_MANIFESTS=str(listing), QT_SCALE_FACTOR="1", QT_AUTO_SCREEN_SCALE_FACTOR="0",
               OMP_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4",
               PATH=str(args.xvfb.parent) + os.pathsep + os.environ.get("PATH", ""))
    command = [str(args.xvfb), "-a", str(args.slicer), "--no-splash", "--ignore-slicerrc",
               "--launcher-ignore-user-additional-settings", "--launcher-additional-settings", str(launcher),
               "--additional-module-paths", str(module_dir)]
    if args.dmri_root:
        dmri = args.dmri_root.resolve()
        command.extend(str(dmri / name) for name in ("qt-loadable-modules", "qt-scripted-modules", "cli-modules"))
        env["SLICERDDSURFER_REQUIRE_NATIVE_DMRI"] = "1"
        env["LD_LIBRARY_PATH"] = str(dmri / "qt-loadable-modules") + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    command += ["--python-script", str(ROOT / "Testing/Python/slicer_auto_results_smoke.py")]
    with (output / "slicer.log").open("w") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise RuntimeError("Automatic-load Slicer smoke timed out")
    print(f"Automatic-load GUI exit={code}; reports: {output}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
