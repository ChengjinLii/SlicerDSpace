#!/usr/bin/env python3
"""Read-only, per-cluster tracing of WMA CST coverage loss."""

import argparse
import json
from pathlib import Path
import re
import time


def inspect(manifest_path):
    import vtk

    manifest = json.loads(manifest_path.read_text())
    summary = manifest['outputs']['summary']
    atlas = Path(manifest['atlas_dir']) / 'ORG-800FC-100HCP'
    names = sorted(set(re.findall(r'fileName="(cluster_\d+\.vtp)"', (atlas / 'T_CST.mrml').read_text())))
    directories = {'atlas': atlas, **{key: Path(summary[key]) for key in (
        'initial_clusters_dir', 'outlier_removed_dir', 'transformed_clusters_dir',
        'separated_left_hemisphere_dir', 'separated_right_hemisphere_dir', 'separated_commissural_dir')}}
    clusters = []
    for name in names:
        stages = {}
        for stage, directory in directories.items():
            path = directory / name
            if not path.is_file():
                raise FileNotFoundError(f'Missing WMA cluster at {stage}: {path}')
            reader = vtk.vtkXMLPolyDataReader()
            errors = []
            reader.AddObserver('ErrorEvent', lambda *_: errors.append(True))
            reader.SetFileName(str(path))
            reader.Update()
            if errors or reader.GetErrorCode():
                raise ValueError(f'Unreadable WMA cluster at {stage}: {path}')
            data = reader.GetOutput()
            stages[stage] = {'path': str(path), 'streamlines': data.GetNumberOfLines(),
                             'bounds_ras_mm': list(data.GetBounds()) if data.GetNumberOfPoints() else None,
                             'cell_arrays': [data.GetCellData().GetArrayName(i) for i in range(data.GetCellData().GetNumberOfArrays())]}
        clusters.append({'cluster': name, 'stages': stages})
    return {'kind': 'wma_cst_cluster_stage_trace', 'manifest': str(manifest_path.resolve()),
            'clusters': clusters,
            'totals': {key: sum(item['stages'][key]['streamlines'] for item in clusters) for key in directories},
            'scope': 'Exact author CST cluster membership; not anatomical ground truth'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    result = inspect(args.manifest)
    result['seconds'] = time.monotonic() - started
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'totals': result['totals'], 'seconds': result['seconds']}, indent=2))
