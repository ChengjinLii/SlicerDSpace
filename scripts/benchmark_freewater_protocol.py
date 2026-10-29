#!/usr/bin/env python3
"""Paired author/current/protocol-reuse FW WLS measurements on native-grid ROIs."""

import argparse
from contextlib import nullcontext
import csv
import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys
import time
from unittest.mock import patch

import dipy
from dipy.core.gradients import gradient_table
from dipy.reconst import fwdti
import nibabel as nib
import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from microstructure import freewater_dispatch, pipeline
from microstructure.freewater_protocol import prepare_wls_protocol
from shared.pipeline import RawInputBundle


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def compare(left, right):
    for key in pipeline.FREE_WATER_KEYS:
        a, b = nib.load(left[0][key]), nib.load(right[0][key])
        np.testing.assert_array_equal(np.asarray(a.dataobj), np.asarray(b.dataobj))
        np.testing.assert_array_equal(a.affine, b.affine)
        assert a.header.get_data_dtype() == b.header.get_data_dtype(), key
    for key in ("status", "automatic_qc_passed", "checks", "validity", "parameters", "summary", "warnings"):
        assert left[1][key] == right[1][key], key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--crop-size", type=int, default=12)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.crop_size < 1 or args.repeats < 3 or args.output.exists():
        parser.error("Use a positive crop, at least three repeats and a fresh output folder")
    args.output.mkdir(parents=True)
    code_files = [ROOT / name for name in ("microstructure/freewater_protocol.py", "microstructure/freewater_wls.py",
        "microstructure/freewater_dispatch.py", "microstructure/pipeline.py", "scripts/benchmark_freewater_protocol.py")]
    code_files.append(Path(fwdti.__file__))
    hashes = {str(path.resolve()): digest(path) for path in code_files}
    dispatch = freewater_dispatch.configure_freewater_dispatch

    def configure(model, method, engine):
        record = dispatch(model, method, engine, reuse_protocol=False)
        assert method == "WLS" and record["enabled"], record
        model.fit_method = prepare_wls_protocol(model.fit_method, model.design_matrix)
        return {**record, "protocol_reuse": True}

    def previous_configure(model, method, engine):
        return dispatch(model, method, engine, reuse_protocol=False)

    variants = ("author", "current", "protocol")
    records = []
    for source in args.source:
        source = source.resolve()
        subject = source.parent.parent.name if source.name == "Diffusion" and source.parent.name == "T1w" else source.parent.name
        work = args.output / subject
        inputs = work / "input"
        inputs.mkdir(parents=True)
        for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
            hashes[str(source / name)] = digest(source / name)
        image = nib.load(source / "data.nii.gz")
        if any(size < args.crop_size for size in image.shape[:3]):
            raise ValueError("Requested crop exceeds native image dimensions")
        crop = tuple(slice((size - args.crop_size) // 2, (size - args.crop_size) // 2 + args.crop_size)
                     for size in image.shape[:3])
        for name in ("data.nii.gz", "nodif_brain_mask.nii.gz"):
            nib.save(nib.load(source / name).slicer[crop], inputs / name)
        for name in ("bvals", "bvecs"):
            shutil.copy2(source / name, inputs / name)
        raw = RawInputBundle(work, subject, inputs, inputs / "data.nii.gz", inputs / "bvals", inputs / "bvecs",
                             inputs / "nodif_brain_mask.nii.gz")
        for path in inputs.iterdir():
            hashes[str(path)] = digest(path)
        mask = nib.load(raw.mask_path).get_fdata() > 0
        signals = nib.load(raw.dwi_path).get_fdata(dtype=np.float32)[mask]
        bvals, bvecs = pipeline._load_bvals_bvecs(raw)
        gtab = gradient_table(bvals, bvecs=bvecs, b0_threshold=50)
        models = {key: fwdti.FreeWaterTensorModel(gtab, fit_method="WLS") for key in variants}
        previous_configure(models["current"], "WLS", "serial")
        configure(models["protocol"], "WLS", "serial")
        raw_parameters = {key: model.fit(signals).model_params for key, model in models.items()}
        for key in variants[1:]:
            np.testing.assert_array_equal(raw_parameters["author"], raw_parameters[key])
        context = models["protocol"].fit_method.__globals__["_protocol_context"]

        def run(key, iteration):
            config = pipeline.MicrostructureConfig(subject, raw, None, work / f"{key}-{iteration}",
                run_free_water=True, free_water_fit_method="WLS", free_water_engine="serial")
            paths = pipeline._output_paths(subject, config.output_dir)
            paths["fwf"].parent.mkdir(parents=True)
            manager = (patch.object(freewater_dispatch, "configure_freewater_dispatch", return_value={"enabled": False})
                       if key == "author" else patch.object(freewater_dispatch, "configure_freewater_dispatch", configure)
                       if key == "protocol" else patch.object(freewater_dispatch, "configure_freewater_dispatch", previous_configure))
            with manager:
                start = time.perf_counter()
                pipeline._compute_free_water_maps(config=config, paths=paths)
                elapsed = time.perf_counter() - start
            return elapsed, (paths, json.loads(paths["free_water_qc"].read_text()))

        warm = {key: run(key, "warm")[1] for key in variants}
        for key in variants[1:]:
            compare(warm["author"], warm[key])
        times = {key: [] for key in variants}
        for iteration in range(args.repeats):
            outputs = {}
            order = variants[iteration % 3:] + variants[:iteration % 3]
            for key in order:
                elapsed, outputs[key] = run(key, iteration)
                times[key].append(elapsed)
            for key in variants[1:]:
                compare(outputs["author"], outputs[key])
        medians = {key: statistics.median(value) for key, value in times.items()}
        records.append(dict(subject_id=subject, crop=list(mask.shape), mask_voxels=int(mask.sum()), measurements=len(bvals),
            median_seconds=medians, times_seconds=times, author_speed_ratio=medians["author"] / medians["protocol"],
            incremental_speed_ratio=medians["current"] / medians["protocol"], exact_raw_parameters=True,
            exact_maps_affines_dtypes_and_qc=True, automatic_qc_passed=outputs["protocol"][1]["automatic_qc_passed"],
            validity=outputs["protocol"][1]["validity"], grid_hits=context.hits, grid_misses=context.misses,
            grid_cache_bytes=context.bytes, grid_cache_budget=context.max_bytes))
        (args.output / "partial.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(json.dumps(records[-1]), flush=True)
    assert all(digest(path) == value for path, value in hashes.items()), "Input/implementation changed"
    report = dict(status="passed", records=records, source_sha256=hashes, source_inputs_unchanged=True,
        author_body_sha256={name: hashlib.sha256(inspect.getsource(inspect.unwrap(getattr(fwdti, name))).encode()).hexdigest()
                            for name in ("wls_iter", "nls_iter")},
        environment=dict(python=sys.version, executable=sys.executable, platform=platform.platform(), dipy=dipy.__version__,
            numpy=np.__version__, scipy=scipy.__version__, threads={key: os.environ.get(key) for key in
                ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}),
        repeats=args.repeats, warmups_per_variant=1, order="Rotated author/current/protocol order",
        scope="Complete native-grid ROI WLS stage including validation, reading, fitting, maps, QC and fresh exports",
        limitation="Shared-host warmed ROI comparison; no full-brain or whole-workflow speedup estimate")
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (args.output / "report.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("subject_id", "mask_voxels", "measurements", "author_seconds", "current_seconds",
            "protocol_seconds", "author_speed_ratio", "incremental_speed_ratio", "exact_raw_parameters", "exact_maps_affines_dtypes_and_qc"))
        writer.writeheader()
        for row in records:
            writer.writerow({**{key: row[key] for key in writer.fieldnames if key in row},
                             **{key + "_seconds": value for key, value in row["median_seconds"].items()}})


if __name__ == "__main__":
    main()
