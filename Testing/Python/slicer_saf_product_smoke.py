"""Read-only native SlicerDMRI load of a real SAF VTK, in an isolated scene."""

import json
import os
from pathlib import Path
import sys
import traceback

import numpy as np
import qt
import slicer
import vtk
from vtk.util.numpy_support import vtk_to_numpy


def run():
    report = Path(os.environ.get('SLICERDDSURFER_SAF_VALIDATION_REPORT',
                                str(Path(os.environ.get('SLICERDDSURFER_SMOKE_ROOT', '.')) / 'saf_product.json')))
    try:
        module_dir = Path(os.environ.get('SLICERDDSURFER_EXTENSION_MODULE_DIR') or os.environ['SLICERDDSURFER_STAGED_MODULE_DIR'])
        sys.path.insert(0, str(module_dir))
        from tractography.saf_backend.provenance import IMPLEMENTATION_REVISION
        from tractography.saf_backend.Filters.streamlineXmesh.endpoint_vertices import closest_endpoint_vertices

        # Execute the corrected indexing helper in Slicer's actual Python.
        vertices = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.],
                             [10., 0., 0.], [11., 0., 0.], [10., 1., 0.]])
        faces = np.array([[0, 1, 2], [3, 4, 5]])
        tracks = [np.array([[.05, .05, .1], [1., .02, .1]]),
                  np.array([[10., 1., .1], [11., .02, .1]])]
        paired = closest_endpoint_vertices(vertices, faces, tracks, np.array([[np.nan, 1], [0, 1]]))
        assert np.array_equal(paired, [[0, 6], [2, 5]])
        directory = Path(os.environ['SLICERDDSURFER_SAF_VALIDATION_DIR'])
        source = directory / 'SAF.vtk'
        qc = json.loads((directory / 'saf_qc.json').read_text())
        reader = vtk.vtkPolyDataReader()
        reader.SetFileName(str(source))
        reader.Update()
        original = reader.GetOutput()
        node = slicer.util.loadFiberBundle(str(source))
        assert node and node.IsA('vtkMRMLFiberBundleNode'), 'Native SlicerDMRI fiber loading unavailable'
        loaded = node.GetPolyData()
        before = vtk_to_numpy(original.GetPoints().GetData())
        after = vtk_to_numpy(loaded.GetPoints().GetData())
        assert np.array_equal(before, after), 'Fiber loading changed native RAS coordinates'
        assert loaded.GetNumberOfLines() == qc['streamline_count']
        result = {'status': 'passed', 'implementation_revision': IMPLEMENTATION_REVISION,
                  'source': str(source), 'slicer_version': slicer.app.applicationVersion,
                  'node_class': node.GetClassName(), 'streamline_count': loaded.GetNumberOfLines(),
                  'point_coordinates_exact': True, 'indexing_helper_gold_pass': True,
                  'scope': 'Native reader/indexing smoke only, no new tractography or anatomical certification.'}
        slicer.mrmlScene.RemoveNode(node)
        code = 0
    except Exception:
        result = {'status': 'failed', 'error': traceback.format_exc()}
        code = 2
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
    slicer.app.exit(code)


qt.QTimer.singleShot(3000, run)
