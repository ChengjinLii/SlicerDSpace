"""Prepare and compare actual author-Octave and Python executions, no mocked fit."""

import argparse
import json
from pathlib import Path
import sys
import tempfile

import nibabel as nib
import numpy as np
from scipy.io import loadmat, savemat

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from microstructure.dki import _signature, _write_json
from microstructure.mkcurve import run_mkcurve, synthetic_b0_grid, UPSTREAM_COMMIT
from microstructure.mkcurve_inputs import _prepare_inputs
from Testing.Python.test_microstructure_dki import synthetic_case, write_case


def prepare(evidence):
    evidence.mkdir(parents=True, exist_ok=True)
    cases = {"synthetic_b0_perturbed": None,
             "real_hcp100307_roi": ROOT / "ignore/validation/brain_mask_backends_20261012/dki/hcp100307_roi/input"}
    for name, source in cases.items():
        directory = evidence / name
        directory.mkdir(exist_ok=True)
        if source is None:
            case = synthetic_case(noisy=True)
            # Controlled artifact, not a real acquisition or clinical result.
            case["data"][0, 1, :, :4] *= .35
            paths = write_case(directory, case)
        else:
            image = nib.load(source / "data.nii.gz")
            mask_image = nib.load(source / "nodif_brain_mask.nii.gz")
            cropped = np.asarray(image.dataobj)[1:3, 1:3, 1:3, :]
            mask = np.asarray(mask_image.dataobj)[1:3, 1:3, 1:3]
            affine = image.affine.copy()
            affine[:3, 3] = (image.affine @ [1, 1, 1, 1])[:3]
            paths = {key: directory / filename for key, filename in
                     zip(("dwi", "bval", "bvec", "mask"), ("data.nii.gz", "bvals", "bvecs", "mask.nii.gz"))}
            nib.save(nib.Nifti1Image(cropped, affine), paths["dwi"])
            nib.save(nib.Nifti1Image(mask, affine), paths["mask"])
            np.savetxt(paths["bval"], np.loadtxt(source / "bvals"))
            np.savetxt(paths["bvec"], np.loadtxt(source / "bvecs"))
            _write_json(directory / "real_source.json", {key: _signature(source / filename) for key, filename in
                                                        zip(("dwi", "mask"), ("data.nii.gz", "nodif_brain_mask.nii.gz"))})
        arguments = [paths[k] for k in ("dwi", "bval", "bvec", "mask")]
        with tempfile.TemporaryDirectory(dir=directory) as tmp:
            prepared, _, _ = _prepare_inputs(*arguments, Path(tmp), 50., 2500.)
            data = nib.load(prepared[0]).get_fdata()
            mask = nib.load(prepared[3]).get_fdata() > 0
            grid = synthetic_b0_grid(data[..., 0][mask])
            gradients = np.column_stack((np.loadtxt(prepared[2]).T, np.loadtxt(prepared[1])))
            savemat(directory / "reference_input.mat", {"dwi": data, "grad": gradients, "mask": mask, "grid": grid})
        run_mkcurve(*arguments, directory / "python", max_bvalue=2500., log=print)


def compare(evidence, fixture_path=None):
    results = {"upstream_commit": UPSTREAM_COMMIT, "reference_engine": "GNU Octave, unmodified author .m numeric routines",
               "scope": "noisy synthetic artifact and real HCP ROI, not whole-brain/clinical validation", "cases": []}
    all_passed = True
    for directory in sorted(evidence.iterdir()):
        if not directory.is_dir() or not (directory / "reference_input.mat").is_file():
            continue
        author = loadmat(directory / "author_output.mat")
        port = json.loads((directory / "python/mkcurve_record.json").read_text())
        mask = loadmat(directory / "reference_input.mat")["mask"].astype(bool)
        checks = []
        for prefix, alias in (("original", "orig"), ("corrected", "corr")):
            for metric in ("fa", "md", "ad", "rd", "mk", "ak", "rk"):
                actual = nib.load(port["maps"][prefix + "_" + metric]).get_fdata()[mask]
                reference = author[alias + "_" + metric][mask]
                passed = bool(np.allclose(actual, reference, atol=2e-6, rtol=2e-5, equal_nan=True))
                checks.append({"key": prefix + "_" + metric, "passed": passed,
                               "max_abs_difference": float(np.nanmax(np.abs(actual - reference)))})
        curves = np.load(directory / "python/mk_vs_synthetic_b0.npy")
        relative = np.abs(curves - author["curves"]) / np.maximum(1, np.abs(author["curves"]))
        plausible = (author["curves"] >= 0) & (author["curves"] <= 5)
        checks.append({"key": "entire_synthetic_b0_curve", "passed": bool(np.allclose(curves, author["curves"], atol=1e-6, rtol=1e-6)),
                       "max_abs_difference": float(np.max(np.abs(curves - author["curves"]))),
                       "max_scaled_difference": float(relative.max()),
                       "plausible_curve_max_abs_difference": float(np.max(np.abs(curves[plausible] - author["curves"][plausible])))})
        for key, alias in (("zero_mk_b0", "zero_b0"), ("max_mk_b0", "max_b0"), ("max_mk", "max_mk"),
                           ("abnormal_mask", "abnormal"), ("unusual_mask", "unusual"), ("corrected_b0", "corrected_b0")):
            actual = nib.load(port["maps"][key]).get_fdata()[mask]
            reference = author[alias][mask]
            checks.append({"key": key, "passed": bool(np.allclose(actual, reference, atol=2e-4, rtol=1e-6)),
                           "max_abs_difference": float(np.max(np.abs(actual - reference)))})
        passed = all(item["passed"] for item in checks)
        all_passed &= passed
        results["cases"].append({"name": directory.name, "mask_voxels": int(mask.sum()), "passed": passed,
                                 "corrected_voxels": port["corrected_voxels"], "checks": checks,
                                 "reference_output": _signature(directory / "author_output.mat")})
        if fixture_path and directory.name == "synthetic_b0_perturbed" and passed:
            source = loadmat(directory / "reference_input.mat")
            selected = np.flatnonzero(mask.ravel(order="F"))[:4]
            indices = np.unravel_index(selected, mask.shape, order="F")
            signals = source["dwi"][indices]
            tensor = author["orig_dt"][indices]
            _write_json(fixture_path, {
                "scope": "SYNTHETIC ONLY; actual unmodified author numeric routines executed in GNU Octave 7.3.0",
                "upstream_commit": UPSTREAM_COMMIT,
                "reference_output_sha256": _signature(directory / "author_output.mat")["sha256"],
                "signals": signals.tolist(), "gradients": source["grad"].tolist(), "grid": source["grid"].ravel().tolist(),
                "original_tensor": tensor.tolist(),
                "curves": author["curves"][:, :4].tolist(),
                "original_maps": {key: author["orig_" + key][indices].tolist() for key in ("fa", "md", "ad", "rd", "mk", "ak", "rk")},
                "corrected_maps": {key: author["corr_" + key][indices].tolist() for key in ("fa", "md", "ad", "rd", "mk", "ak", "rk")},
                "detection": {key: author[alias][indices].tolist() for key, alias in
                              (("zero_mk_b0", "zero_b0"), ("max_mk_b0", "max_b0"), ("max_mk", "max_mk"),
                               ("abnormal_mask", "abnormal"), ("corrected_b0", "corrected_b0"))}})
    results["passed"] = all_passed and bool(results["cases"])
    _write_json(evidence / "author_parity.json", results)
    print(json.dumps(results, indent=2))
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "compare"))
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--export-fixture", type=Path)
    args = parser.parse_args()
    if args.phase == "prepare":
        prepare(args.evidence.resolve())
    else:
        sys.exit(compare(args.evidence.resolve(), args.export_fixture))
