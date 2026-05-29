#!/usr/bin/env python3
"""Run a canonical output-layout smoke test for one subject inside Slicer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--subject-root", required=True)
    parser.add_argument("--subject-id", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    if repo_root.as_posix() not in sys.path:
        sys.path.insert(0, repo_root.as_posix())

    from microstructure.pipeline import MicrostructureConfig, _export_dti_scalar_maps, _output_paths
    from shared.io_layout import materialize_canonical_output_tree, subject_layout
    from shared.pipeline import ensure_native_dti_bundle, find_subject_root
    from shared.validation import InputValidationConfig, validate_subject_inputs

    subject_root = Path(args.subject_root).expanduser().resolve()
    subject_id = args.subject_id
    layout = subject_layout(subject_root)
    canonical_dirs = [
        layout.run_metadata,
        layout.preproc,
        layout.microstructure_dti,
        layout.microstructure_freewater,
        layout.microstructure_noddi,
        layout.ddseg,
        layout.ddsurfer,
        layout.ddparcel,
        layout.registered_to_dwi,
        layout.csd,
        layout.act_prep,
        layout.tract_cloud,
        layout.tractograms_dti_det,
        layout.tractograms_csd_prob,
        layout.tractograms_csd_act,
        layout.bundles_wma,
        layout.bundles_tractcloud,
        layout.bundles_wmql,
        layout.connectome,
        layout.regional_microstructure,
        layout.bundle_profiles,
        layout.slicer_scene_report,
    ]
    for directory in canonical_dirs:
        directory.mkdir(parents=True, exist_ok=True)

    validation = validate_subject_inputs(
        InputValidationConfig(
            subject_id=subject_id,
            input_root=subject_root,
            output_dir=layout.run_metadata / "validation",
            dependency_groups=("core", "microstructure", "tractography"),
            require_phase_encoding=False,
        )
    )
    print(f"validation {validation.status} {validation.report_path}", flush=True)

    raw = find_subject_root(subject_root, subject_id)
    native = ensure_native_dti_bundle(raw, fit_method="wls", reuse=False, log=print)
    print(f"native_bundle {native.bundle_dir}", flush=True)

    config = MicrostructureConfig(
        subject_id=subject_id,
        raw_input_bundle=raw,
        native_bundle=native,
        output_dir=layout.microstructure,
        run_free_water=False,
        run_noddi=False,
        force_recompute=True,
    )
    paths = _output_paths(subject_id, layout.microstructure)
    _export_dti_scalar_maps(config, paths)
    dti_keys = ("fa", "md", "ad", "rd", "l1", "l2", "l3", "trace")
    manifest = {
        "kind": "microstructure_dti_only_layout_regression",
        "version": 1,
        "subject_id": subject_id,
        "native_bundle": native.bundle_dir.resolve().as_posix(),
        "outputs": {key: paths[key].resolve().as_posix() for key in dti_keys},
    }
    (layout.microstructure / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    materialize_canonical_output_tree(subject_root, mode="symlink", archive_legacy=False)
    for key in dti_keys:
        print(f"{key} {paths[key]} {paths[key].is_file()}", flush=True)

    try:
        import slicer

        slicer.app.quit()
    except Exception:
        pass


if __name__ == "__main__":
    main()
