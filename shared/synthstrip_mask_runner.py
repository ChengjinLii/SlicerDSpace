"""GPU-preferred SynthStrip launcher in FreeSurfer's own fspython runtime."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import sys


def select_device(requested, torch):
    if requested not in ("auto", "cpu", "cuda"):
        raise ValueError("Mask device must be auto, cpu or cuda")
    cuda = requested != "cpu" and torch.cuda.is_available()
    if requested == "cuda" and not cuda:
        raise RuntimeError("SynthStrip CUDA requested but FreeSurfer's PyTorch has no visible CUDA GPU")
    if cuda:
        capability = torch.cuda.get_device_capability(0)
        native_arch = "sm_" + str(capability[0]) + str(capability[1])
        cuda_version = tuple(int(part) for part in torch.version.cuda.split(".")[:2])
        if capability[0] >= 9 and cuda_version < (11, 8) and native_arch not in torch.cuda.get_arch_list():
            raise RuntimeError("SynthStrip's PyTorch/CUDA build lacks native support for this GPU and this old runtime was not validated. "
                               "Configure Advanced > SynthStrip Python with a compatible CUDA build, or explicitly select CPU; no automatic fallback.")
        # Check allocation before processing; do not silently retry CPU on errors.
        torch.empty(1, device="cuda:0")
    else:
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    return {"requested": requested, "resolved": "cuda" if cuda else "cpu",
            "torch_version": torch.__version__, "cuda_version": torch.version.cuda,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES")}


def upstream_code(script):
    source = script.read_bytes()
    tree = ast.parse(source, filename=str(script))

    class PreserveVisibility(ast.NodeTransformer):
        count = 0

        def visit_Assign(self, node):
            if len(node.targets) == 1:
                target = node.targets[0]
                slice_value = target.slice if isinstance(target, ast.Subscript) else None
                if isinstance(slice_value, ast.Index):  # FreeSurfer 7.x ships Python 3.8.
                    slice_value = slice_value.value
                if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Attribute)
                        and isinstance(target.value.value, ast.Name) and target.value.value.id == "os"
                        and target.value.attr == "environ"
                        and isinstance(slice_value, ast.Constant) and slice_value.value == "CUDA_VISIBLE_DEVICES"
                        and isinstance(node.value, ast.Constant) and node.value.value == "0"):
                    self.count += 1
                    return ast.copy_location(ast.Pass(), node)
            return self.generic_visit(node)

    transformer = PreserveVisibility()
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, str(script), "exec"), {
        "upstream_sha256": hashlib.sha256(source).hexdigest(),
        "preserved_caller_gpu_visibility": bool(transformer.count), "scientific_code_modified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("upstream_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    import torch
    code, record = upstream_code(args.script)
    try:
        record.update(select_device(args.device, torch))
    except Exception as exc:
        record.update(requested=args.device, status="blocked", error=str(exc))
        args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        raise
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("SynthStrip device: " + json.dumps(record, sort_keys=True), flush=True)
    upstream_args = args.upstream_args[1:] if args.upstream_args[:1] == ["--"] else args.upstream_args
    if record["resolved"] == "cuda":
        upstream_args = [*upstream_args, "-g"]
    sys.argv = [str(args.script), *upstream_args]
    sys.path.insert(0, str(args.script.parent))
    exec(code, {"__name__": "__main__", "__file__": str(args.script), "__package__": None})


if __name__ == "__main__":
    main()
