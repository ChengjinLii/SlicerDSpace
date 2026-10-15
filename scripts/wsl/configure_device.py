"""Choose and verify CPU/CUDA wheels in the isolated WSL runtime, not Slicer."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

TORCH_VERSION = "2.11.0"
TORCH_INDEXES = {"cpu": "https://download.pytorch.org/whl/cpu",
                 "cuda": "https://download.pytorch.org/whl/cu126"}
FSL_CUDA_PACKAGE = "fsl-eddy-cuda=2602.0=h1a432fe_1"


def cuda_available():
    if os.environ.get("CUDA_VISIBLE_DEVICES") in {"", "-1"}:
        return False
    command = shutil.which("nvidia-smi")
    if not command and Path("/usr/lib/wsl/lib/nvidia-smi").is_file():
        command = "/usr/lib/wsl/lib/nvidia-smi"
    if not command:
        return False
    check = subprocess.run([command, "-L"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15)
    if check.returncode:
        raise RuntimeError("WSL GPU discovery failed; fix the Windows NVIDIA/WSL driver or explicitly select CPU: " + check.stderr.strip())
    return "GPU " in check.stdout


def device_plan(requested="auto", gpu_available=None):
    if requested not in {"auto", "cpu", "cuda"}:
        raise ValueError("Device must be auto, cpu or cuda")
    detected = False if requested == "cpu" else cuda_available() if gpu_available is None else gpu_available
    if requested == "cuda" and not detected:
        raise RuntimeError("CUDA requested but no GPU is visible inside WSL; no CPU fallback")
    resolved = "cuda" if detected else "cpu"
    flavor = "cu126" if resolved == "cuda" else "cpu"
    return {"kind": "slicerdsurfer_wsl_device_plan", "status": "planned",
            "requested": requested, "resolved": resolved, "torch_version": TORCH_VERSION,
            "torch_requirement": f"torch=={TORCH_VERSION}+{flavor}",
            "torch_index": TORCH_INDEXES[resolved],
            "fsl_cuda_package": FSL_CUDA_PACKAGE if resolved == "cuda" else None,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "scientific_validation": "not_inferred_from_installation"}


def configure(plan):
    subprocess.run([sys.executable, "-m", "pip", "install", plan["torch_requirement"],
                    "--index-url", plan["torch_index"]], check=True)
    # Probe in a fresh interpreter after installation; never trust a stale
    # previously imported CPU torch or a driver's presence alone.
    probe = subprocess.run([sys.executable, "-c",
                            "import json,sys,torch; "
                            "cuda=bool(torch.cuda.is_available()); "
                            "torch.empty(1,device='cuda:0') if sys.argv[1]=='cuda' and cuda else None; "
                            "print(json.dumps({'version':torch.__version__,'cuda_available':cuda,'cuda_version':torch.version.cuda}))",
                            plan["resolved"]], check=True, capture_output=True, text=True, timeout=60)
    actual = json.loads(probe.stdout)
    if actual["version"] != plan["torch_requirement"].split("==", 1)[1]:
        raise RuntimeError("WSL PyTorch wheel version differs from the selected device plan")
    if plan["resolved"] == "cuda" and not actual["cuda_available"]:
        raise RuntimeError("CUDA wheel installed but GPU execution is unavailable; no CPU fallback")
    return dict(plan, status="ready", actual_runtime=actual)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    try:
        plan = device_plan(args.device)
        result = configure(plan) if args.execute else plan
    except Exception as exc:
        result = {"kind": "slicerdsurfer_wsl_device_plan", "status": "failed",
                  "requested": args.device, "error": str(exc)}
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
