#!/usr/bin/env python3
"""Independently check regional postprocessing against its frozen parent files."""

import argparse
import csv
import itertools
from pathlib import Path
import sys
import time

import nibabel as nib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.region_analysis import inspect_run, native_streamlines, read_json, sha256, write_json


def validate(path):
    start = time.monotonic()
    manifest = read_json(path)
    if manifest.get("status") != "completed":
        raise ValueError("Only a completed regional job can be accepted")
    for category in ("source_sha256", "artifact_sha256"):
        for source, digest in manifest[category].items():
            if sha256(source) != digest:
                raise ValueError("Changed file: " + source)
    request = manifest["request"]
    catalog = inspect_run(
        request["source_manifest"], atlas_override=request.get("atlas_override"), lut_path=request.get("lut_path")
    )
    selected = sorted(set(request["selected_labels"]))
    folder = Path(path).parent
    atlas = nib.load(catalog["atlas"])
    labels = np.asarray(atlas.dataobj)
    actual_mask = nib.load(folder / "selected_regions.nii.gz")
    np.testing.assert_array_equal(actual_mask.affine, atlas.affine)
    np.testing.assert_array_equal(np.asarray(actual_mask.dataobj), np.where(np.isin(labels, selected), labels, 0))
    checks = {"source_and_artifact_hashes": True, "selected_label_map_exact": True}
    statistics = []
    if request.get("metrics"):
        rows = read_json(folder / "selected_microstructure.json")["rows"]
        if [row["label_id"] for row in rows] != selected:
            raise AssertionError("Selected-region statistics order mismatch")
        brain = np.asarray(nib.load(catalog["brain_mask"]).dataobj) > 0
        for key in request["metrics"]:
            spec = catalog["metrics"][key]
            data = nib.load(spec["path"]).get_fdata(dtype=np.float64)
            valid = np.isfinite(data) & brain
            if spec["valid_mask"]:
                valid &= np.asarray(nib.load(spec["valid_mask"]).dataobj) > 0
            for row in rows:
                mask = labels == row["label_id"]
                values = data[mask & valid]
                if row[key + "_valid_voxel_count"] != len(values):
                    raise AssertionError("Valid voxel count differs")
                if row[key + "_excluded_voxel_count"] != int(mask.sum()) - len(values):
                    raise AssertionError("Excluded voxel count differs")
                for statistic, function in (("mean", np.mean), ("std", np.std), ("min", np.min), ("max", np.max)):
                    actual = row[key + "_" + statistic]
                    if len(values):
                        if not np.isclose(actual, function(values), rtol=2e-6, atol=1e-9):
                            raise AssertionError(f"{key} {statistic} differs")
                    elif actual is not None:
                        raise AssertionError("An invalid estimate was filled instead of null")
                statistics.append(
                    dict(label_id=row["label_id"], metric=key, valid_voxels=len(values), mean=row[key + "_mean"])
                )
        checks["independent_boolean_roi_statistics"] = True
    selected_count = None
    maximum_coordinate_error_mm = 0.0
    if request.get("tractogram"):
        source = catalog["tractograms"][request["tractogram"]]
        info = read_json(folder / "selected_tractography.json")
        with Path(info["source_indices"]).open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        indices = [int(row["source_index"]) for row in rows]
        if indices != sorted(set(indices)):
            raise AssertionError("Source indices are not unique and ordered")
        if [int(row["selected_index"]) for row in rows] != list(range(len(rows))):
            raise AssertionError("Selected indices are not consecutive")
        actual = iter(native_streamlines(info["output"])) if info["output"] else iter(())
        wanted = iter(indices)
        current = next(wanted, None)
        input_count = 0
        sentinel = object()
        for index, line in enumerate(native_streamlines(source["path"])):
            input_count += 1
            if index == current:
                result = next(actual, sentinel)
                if result is sentinel or result.shape != line.shape:
                    raise AssertionError("Selected geometry is missing or clipped")
                error = float(np.max(np.abs(line - result)))
                maximum_coordinate_error_mm = max(maximum_coordinate_error_mm, error)
                if error != 0:
                    raise AssertionError("Selected coordinates differ from source")
                current = next(wanted, None)
        if current is not None or next(actual, sentinel) is not sentinel:
            raise AssertionError("Unexpected/missing selected geometry")
        if input_count != info["input_streamlines"] or len(rows) != info["selected_streamlines"]:
            raise AssertionError("Tractogram counts differ")
        if source.get("weights"):
            weights = np.loadtxt(source["weights"], ndmin=1)
            np.testing.assert_array_equal([float(row["sift2_weight"]) for row in rows], weights[indices])
            checks["selected_sift2_weights_exact"] = True
        selected_count = len(rows)
        checks["all_selected_geometry_and_source_indices_exact"] = True
    if request.get("connectome"):
        source = catalog["connectomes"][request["connectome"]]
        with Path(source["matrix"]).open(newline="") as stream:
            reader = csv.reader(stream)
            header = next(reader)
            if header[:2] == ["source_node", "target_node"]:
                original = {tuple(sorted((int(row[0]), int(row[1])))): float(row[2]) for row in reader}
            else:
                dense = np.loadtxt(source["matrix"], delimiter=",", ndmin=2)
                with Path(source["nodes"]).open(newline="") as nodes:
                    node_labels = sorted(int(row["label"]) for row in csv.DictReader(nodes, delimiter="\t"))
                lookup = (
                    {label: i for i, label in enumerate(node_labels)}
                    if len(dense) == len(node_labels)
                    else {label: label - 1 for label in node_labels}
                )
                original = {
                    tuple(sorted((a, b))): float(dense[lookup[a], lookup[b]]) for a in selected for b in node_labels
                }
        with (folder / "selected_connectome_matrix.csv").open(newline="") as stream:
            reader = csv.reader(stream)
            header = next(reader)
            assert [int(value) for value in header[1:]] == selected
            for row, label in itertools.zip_longest(reader, selected):
                if row is None or label is None or int(row[0]) != label:
                    raise AssertionError("Selected matrix labels/order differ")
                for partner, value in zip(selected, row[1:], strict=True):
                    if float(value) != original.get(tuple(sorted((label, partner))), 0.0):
                        raise AssertionError("A connectivity weight changed")
        with (folder / "selected_region_connections.csv").open(newline="") as stream:
            for row in csv.DictReader(stream):
                a, b = int(row["selected_label"]), int(row["partner_label"])
                value = float(list(row.values())[-1])
                if a not in selected or value != original.get(tuple(sorted((a, b))), 0.0):
                    raise AssertionError("A regional connection changed")
        checks["induced_matrix_and_connection_weights_exact"] = True
    return dict(
        status="PASS",
        checks=checks,
        region_ids=selected,
        statistics=statistics,
        selected_streamlines=selected_count,
        maximum_coordinate_error_mm=maximum_coordinate_error_mm,
        postprocessing_runtime_seconds=manifest["runtime_seconds"],
        validation_runtime_seconds=time.monotonic() - start,
        scope="Postprocessing consistency only; no new fit, anatomical or cross-platform acceptance",
        human_review="pending",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    write_json(args.report, validate(args.manifest))
    print("REGIONAL_POSTPROCESSING_VALIDATION_PASS: " + str(args.report), flush=True)


if __name__ == "__main__":
    main()
