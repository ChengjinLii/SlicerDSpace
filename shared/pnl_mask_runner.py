"""Run external PNL inference with explicit, recorded TensorFlow device selection.

This standalone launcher runs in the user's PNL Python, never Slicer Python.
It leaves upstream files, weights and scientific processing unchanged.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys


def select_device(requested: str, tf=None) -> dict:
    if requested not in ("auto", "cpu", "cuda"):
        raise ValueError("PNL device must be auto, cpu or cuda")
    if requested == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
        return {"requested": requested, "resolved": "cpu", "reason": "Explicit CPU selection"}
    if tf is None:
        try:
            import tensorflow as tf
        except ImportError as exc:
            if requested == "cuda":
                raise RuntimeError("PNL GPU requested but TensorFlow could not be imported") from exc
            os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
            return {"requested": requested, "resolved": "cpu", "reason": "TensorFlow unavailable; upstream runtime must validate dependencies"}
    gpus = tf.config.list_physical_devices("GPU")
    details = {"requested": requested, "tensorflow_version": tf.__version__,
               "visible_gpus": [gpu.name for gpu in gpus],
               "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES")}
    if not gpus:
        if requested == "cuda":
            raise RuntimeError("PNL GPU requested but external TensorFlow has no visible CUDA GPU; check CUDA libraries and container GPU access")
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
        return dict(details, resolved="cpu", reason="No CUDA GPU visible to external TensorFlow")
    # Use only the first GPU allowed by the caller/container, with incremental
    # allocation. Never unmask scheduler-restricted GPUs or reserve all VRAM.
    tf.config.set_visible_devices(gpus[:1], "GPU")
    tf.config.experimental.set_memory_growth(gpus[0], True)
    tf.config.set_soft_device_placement(False)
    return dict(details, resolved="cuda", selected_gpu=gpus[0].name,
                reason="First visible CUDA GPU; memory growth enabled")


def upstream_code(script: Path):
    source = script.read_bytes()
    tree = ast.parse(source, filename=str(script))
    repaired = 0
    for index, node in enumerate(tree.body):
        if not isinstance(node, ast.Try):
            continue
        names = {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}
        if {"DEVICE_ID_LIST", "CUDA_VISIBLE_DEVICES", "DEVICE_ID"} <= names:
            # Known upstream startup bug: undefined DEVICE_ID_LIST silently
            # disables CUDA. Replace only this device-selection try/except,
            # not the CNN, registration, aggregation or cleanup code.
            replacement = ast.parse("print('PNL device managed by SlicerDDSurfer launcher', flush=True)").body[0]
            tree.body[index] = ast.copy_location(replacement, node)
            repaired += 1
    if repaired > 1:
        raise RuntimeError("Ambiguous upstream PNL device-selection blocks")
    ast.fix_missing_locations(tree)
    return compile(tree, str(script), "exec"), {
        "upstream_sha256": hashlib.sha256(source).hexdigest(),
        "device_selection_compatibility_fix": bool(repaired),
        "scientific_code_modified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("upstream_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
    code, record = upstream_code(args.script)
    try:
        record.update(select_device(args.device))
    except Exception as exc:
        record.update(requested=args.device, status="blocked", error=str(exc))
        args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        raise
    for package in ("tensorflow", "keras"):
        try:
            record[package + "_package_version"] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("PNL device: " + json.dumps(record, sort_keys=True), flush=True)
    upstream_args = args.upstream_args
    if upstream_args[:1] == ["--"]:
        upstream_args = upstream_args[1:]
    sys.argv = [str(args.script), *upstream_args]
    sys.path.insert(0, str(args.script.parent))
    exec(code, {"__name__": "__main__", "__file__": str(args.script), "__package__": None})


if __name__ == "__main__":
    main()
