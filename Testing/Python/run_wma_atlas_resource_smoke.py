#!/usr/bin/env python3
"""Opt-in WMA atlas compatibility checks; requires verified optional atlas data."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.run_wma_atlas import append_with_atlas_groups
from shared.optional_assets import verified_resource_directory
from tractography.wma_atlases import atlas_definition, atlas_output_contract, validate_group_hemispheres


def run(family, asset_root, wma_root):
    definition = atlas_definition(family)
    root = verified_resource_directory(definition['profile'], asset_root=asset_root)
    if root is None:
        raise ValueError('Prepare the complete verified atlas before loading its spectral model')
    sys.path.insert(0, str(wma_root))
    import numpy as np
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    import whitematteranalysis as wma

    cluster = root / definition['directories'][1]
    contract = atlas_output_contract(family, cluster)
    hemisphere_check = validate_group_hemispheres(cluster, contract['groups'])
    registration = wma.io.read_polydata(str(root / definition['directories'][0] / 'registration_atlas.vtk'))
    assert registration.GetNumberOfLines() > 0 and registration.GetNumberOfPoints() > 0
    assert np.isfinite(vtk_to_numpy(registration.GetPoints().GetData())).all()
    registration_counts = {'streamlines': registration.GetNumberOfLines(),
                           'points': registration.GetNumberOfPoints(), 'finite_coordinates': True}
    del registration
    started = time.monotonic()
    atlas = wma.cluster.load_atlas(str(cluster), 'atlas')
    assert atlas.centroids.shape[0] == 800 and np.isfinite(atlas.centroids).all()
    mask = np.zeros(atlas.nystrom_polydata.GetNumberOfLines(), dtype=bool)
    mask[np.linspace(0, len(mask) - 1, 32, dtype=int)] = True
    sample = wma.filter.mask(atlas.nystrom_polydata, mask, preserve_point_data=True, preserve_cell_data=True)
    classified, labels, colors, embedding = wma.cluster.spectral_atlas_label(sample, atlas, number_of_jobs=1)
    assert classified.GetNumberOfLines() == 32 and len(labels) == 32
    assert labels.min() >= 0 and labels.max() < 800
    assert np.isfinite(embedding).all() and np.isfinite(colors).all()
    spectral_seconds = time.monotonic() - started
    author = wma_root / 'bin/wm_append_clusters_to_anatomical_tracts.py'
    checks = []
    with tempfile.TemporaryDirectory(prefix='wma-atlas-smoke-') as temporary:
        work = Path(temporary)
        separated, output = work / 'separated', work / 'AnatomicalTracts'
        original = {}
        for category in ('left_hemisphere', 'right_hemisphere', 'commissural'):
            directory = separated / ('tracts_' + category)
            directory.mkdir(parents=True)
            for index in range(1, 801):
                filename = f'cluster_{index:05d}.vtp'
                sign = -1 if category == 'left_hemisphere' else 1
                coordinates = np.array([[sign * index, 1, 2], [sign * index, 3, 4]], dtype=np.float64)
                points = vtk.vtkPoints()
                points.SetDataTypeToDouble()
                for point in coordinates:
                    points.InsertNextPoint(*point)
                lines = vtk.vtkCellArray()
                lines.InsertNextCell(2)
                lines.InsertCellPoint(0)
                lines.InsertCellPoint(1)
                data = vtk.vtkPolyData()
                data.SetPoints(points)
                data.SetLines(lines)
                scalar = vtk.vtkDoubleArray()
                scalar.SetName('test_scalar')
                scalar.InsertNextValue(index / 1000)
                scalar.InsertNextValue(index / 1000)
                data.GetPointData().AddArray(scalar)
                writer = vtk.vtkXMLPolyDataWriter()
                writer.SetFileName(str(directory / filename))
                writer.SetInputData(data)
                assert writer.Write() == 1
                original[(category, filename)] = coordinates
        started = time.monotonic()
        append_with_atlas_groups(author, contract['groups'], [str(separated), str(cluster), str(output)])
        append_seconds = time.monotonic() - started
        for kind, names in contract['groups'].items():
            for name in names:
                # Independent of WMA's MRML reader: preserve storage-node order.
                clusters = re.findall(r'fileName="[^"\n]*(cluster_[0-9]{5}\.vtp)"',
                                      (cluster / (name + '.mrml')).read_text())
                assert clusters, name
                for side in (('left', 'right') if kind == 'hemispheric' else ('commissural',)):
                    category = side + '_hemisphere' if side in ('left', 'right') else side
                    filename = name + ('_' + side if side in ('left', 'right') else '') + '.vtp'
                    reader = vtk.vtkXMLPolyDataReader()
                    reader.SetFileName(str(output / filename))
                    reader.Update()
                    data = reader.GetOutput()
                    expected = np.concatenate([original[(category, item)] for item in clusters])
                    assert np.array_equal(vtk_to_numpy(data.GetPoints().GetData()), expected), filename
                    assert data.GetNumberOfLines() == len(clusters), filename
                    expected_scalar = np.repeat([int(item[8:13]) / 1000 for item in clusters], 2)
                    assert np.array_equal(vtk_to_numpy(data.GetPointData().GetArray('test_scalar')), expected_scalar)
                    assert np.array_equal(vtk_to_numpy(data.GetPointData().GetArray('cluster_idx')),
                                          np.repeat(np.arange(len(clusters)), 2))
                    checks.append(filename)
        assert sorted(path.name for path in output.glob('*.vtp')) == contract['expected_tract_files']
    return {'schema': 'wma_atlas_resource_smoke.v1', 'status': 'passed', 'atlas_family': family,
            'registration_geometry': registration_counts,
            'hemisphere_check': hemisphere_check, 'test_fibers': 32, 'tract_files': sorted(checks),
            'author_append_sha256': hashlib.sha256(author.read_bytes()).hexdigest(),
            'extraction_index_sha256': hashlib.sha256((root / 'extracted_resource_index.json').read_bytes()).hexdigest(),
            'embedding_sha256': hashlib.sha256(embedding.tobytes()).hexdigest(),
            'vtk': vtk.vtkVersion.GetVTKVersion(), 'spectral_seconds': spectral_seconds, 'append_seconds': append_seconds,
            'checks': {'finite_spectral_output': True, 'bundle_inventory_exact': True,
                       'point_coordinates_exact': True, 'point_attributes_exact': True, 'streamline_order_exact': True},
            'scope': 'Verified published spectral data with 32 reference fibers; real author appender with synthetic geometry. Subject registration and anatomical acceptance are separate.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family', choices=('east-west', 'naba'), required=True)
    parser.add_argument('--asset-root', type=Path, required=True)
    parser.add_argument('--wma-root', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.family, args.asset_root.expanduser().resolve(), args.wma_root.expanduser().resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'family': args.family, 'tract_files': len(result['tract_files'])}))


if __name__ == '__main__':
    main()
