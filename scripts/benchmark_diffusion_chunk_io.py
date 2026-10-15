#!/usr/bin/env python3
"""Real read-only slab I/O parity/timing; not a Free Water fitting benchmark."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    stat = path.stat()
    return {"path": str(path.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": digest.hexdigest()}


def run(source, report):
    import nibabel as nib
    import numpy as np
    from nibabel.openers import HAVE_INDEXED_GZIP
    from shared.diffusion_io import diffusion_image

    source, report = source.resolve(), report.resolve()
    before = fingerprint(source)
    image = nib.load(source, mmap="r", keep_file_open=False)
    indices = sorted(set((0, image.shape[2] // 2, image.shape[2] - 1)))
    start = time.perf_counter()
    originals = [np.asarray(image.dataobj[:, :, index:index+1, :], dtype=np.float32) for index in indices]
    baseline_seconds = time.perf_counter() - start
    start = time.perf_counter()
    checks = []
    with diffusion_image(source, report.parent) as opened:
        for index, expected in zip(indices, originals):
            actual = np.asarray(opened.dataobj[:, :, index:index+1, :], dtype=np.float32)
            checks.append({"z": index, "exact_values": bool(np.array_equal(actual, expected, equal_nan=True)),
                           "affine_exact": bool(np.array_equal(opened.affine, image.affine)),
                           "value_sha256": hashlib.sha256(actual.tobytes()).hexdigest()})
    one_pass_seconds = time.perf_counter() - start
    payload = {"kind": "real_diffusion_slab_io_benchmark", "input": before,
               "inputs_unchanged": before == fingerprint(source), "shape": list(image.shape),
               "indexed_gzip_available": bool(HAVE_INDEXED_GZIP), "sampled_z_slices": indices,
               "original_proxy_seconds": baseline_seconds, "one_pass_decode_and_read_seconds": one_pass_seconds,
               "checks": checks, "scope": "Three real slabs including sequential decode. NOT a model-fit or full pipeline speedup."}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dwi", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    run(args.dwi, args.report)
