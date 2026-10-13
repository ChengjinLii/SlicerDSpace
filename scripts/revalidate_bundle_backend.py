#!/usr/bin/env python3
"""Re-run an existing real WMQL/TractCloud configuration in a new directory."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError('Use a new directory so old scientific results are preserved.')
    m = json.loads(args.manifest.read_text())
    common = dict(subject_id=m['subject_id'], input_tractography=Path(m['input_tractography']),
                  output_dir=args.output_dir, execute=True)
    if m['kind'] == 'wmql_bundle_segmentation':
        from tractography.wmql import WMQLConfig, run_wmql_bundle_segmentation
        python = Path(m['backend']['commands']['python'])
        if python.name == 'python-real' and python.with_name('PythonSlicer').is_file():
            # The GUI's python-real requires launcher settings outside Slicer.
            python = python.with_name('PythonSlicer')
        cfg = WMQLConfig(**common, atlas_path=Path(m['atlas_path']), query_path=Path(m['query_path']),
                         query_selection=tuple(m['query_selection']), threshold=m['threshold'],
                         length_threshold=m['length_threshold'],
                         tract_querier_root=Path(m['backend']['root']),
                         python_executable=python)
        result = run_wmql_bundle_segmentation(cfg, log=print)
    elif m['kind'] == 'tractcloud_parcellation':
        from tractography.tractcloud import TractCloudConfig, run_tractcloud_parcellation
        cfg = TractCloudConfig(**common, tractcloud_root=Path(m['tractcloud_root']),
                              python_executable=Path(m['backend']['python_executable']),
                              include_other=m['include_other'], device=m['device'],
                              batch_size=m['batch_size'], data_dir=Path(m['data_dir']),
                              create_mrb=m['create_mrb'])
        from dataclasses import replace
        cfg = replace(cfg, random_seed=m.get('random_seed', 0))
        result = run_tractcloud_parcellation(cfg, log=print)
    else:
        raise ValueError('Only existing WMQL and TractCloud runs are supported.')
    qc = json.loads(result.qc_path.read_text())
    print(json.dumps(qc, indent=2))
    return 0 if qc['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
