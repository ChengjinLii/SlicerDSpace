"""Native SlicerDMRI reading and fresh DTI timing on real, isolated data."""

from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import time
import traceback

import numpy as np
import qt
import slicer
import vtk
from vtk.util.numpy_support import vtk_to_numpy


def run():
    destination = Path(os.environ['SLICERDDSURFER_SMOKE_ROOT'])
    try:
        sys.path.insert(0, os.environ['SLICERDDSURFER_EXTENSION_MODULE_DIR'])
        from shared.module_logic import SharedLogicMixin
        from shared.pipeline import find_subject_root, ensure_native_dti_bundle
        configuration = json.loads(Path(os.environ['SLICERDDSURFER_TASKS_CONFIG']).read_text())
        class ReaderLogic(SharedLogicMixin):
            log = staticmethod(print)
        logic = ReaderLogic()
        records = []
        for case in configuration['cases']:
            paths = [Path(p) for p in case['files']]
            started = time.monotonic()
            lines = 0
            maximum_delta = 0.
            for path in paths:
                if path.suffix in {'.trk', '.tck'}:
                    import nibabel as nib
                    tracks = list(nib.streamlines.load(str(path)).streamlines)
                    expected_lines = len(tracks)
                    original_points = np.concatenate(tracks)
                else:
                    reader = vtk.vtkXMLPolyDataReader() if path.suffix == '.vtp' else vtk.vtkPolyDataReader()
                    reader.SetFileName(str(path))
                    reader.Update()
                    original = reader.GetOutput()
                    expected_lines = original.GetNumberOfLines()
                    original_points = vtk_to_numpy(original.GetPoints().GetData())
                assert logic._load_fiber_bundle_node(path, path.stem), str(path)
                node = slicer.util.getNode(path.stem)
                assert node and node.IsA('vtkMRMLFiberBundleNode'), str(path)
                loaded = node.GetPolyData()
                assert loaded.GetNumberOfLines() == expected_lines > 0
                actual_points = vtk_to_numpy(loaded.GetPoints().GetData())
                assert actual_points.shape == original_points.shape, str(path)
                delta = float(np.max(np.abs(actual_points.astype(float) - original_points.astype(float))))
                maximum_delta = max(maximum_delta, delta)
                assert delta <= .001, (str(path), delta)
                lines += loaded.GetNumberOfLines()
                slicer.mrmlScene.RemoveNode(node)
            records.append(dict(module='slicer.load.' + case['backend'], status='completed',
                                subject_id=case['subject_id'], runtime_seconds=time.monotonic() - started,
                                files=len(paths), streamlines=lines, point_coordinates_exact=maximum_delta == 0.,
                                maximum_coordinate_delta_mm=maximum_delta, coordinate_tolerance_mm=.001,
                                scope='SlicerDDSurfer FiberBundle loader plus independent reader comparison; excludes Slicer startup and tract extraction'))
        if not configuration.get('skip_fresh_dti'):
            raw = find_subject_root(Path(configuration['subject_root']), '100307', generate_missing_mask=False)
            raw = replace(raw, subject_root=destination / 'fresh_dti')
            started = time.monotonic()
            bundle = ensure_native_dti_bundle(raw, fit_method='wls', reuse=False, log=print)
            seconds = time.monotonic() - started
            import nibabel as nib
            image = nib.load(str(bundle.fa_nii_path))
            source = nib.load(str(raw.dwi_path))
            fa = np.asarray(image.dataobj)
            assert image.shape == source.shape[:3] and np.allclose(image.affine, source.affine, atol=1e-4)
            assert np.isfinite(fa).all() and fa.min() >= -1e-5 and fa.max() <= 1.00001
            records.append(dict(module='microstructure.native_dti_fresh', subject_id='100307', status='completed',
                                runtime_seconds=seconds, shape=list(source.shape), source=str(raw.dwi_path),
                                source_record=str(bundle.bundle_dir / 'native_dti_timing.json'),
                                scope='Fresh real full-volume SlicerDMRI WLS fitting and six scalar conversions, no cache reuse'))
        result = dict(status='passed', records=records, slicer_version=slicer.app.applicationVersion,
                      scientific_scope='Geometry/integrity and scoped elapsed measurements; not anatomical certification')
        code = 0
    except Exception:
        result = dict(status='failed', error=traceback.format_exc())
        code = 2
    (destination / 'bundle_products.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
    slicer.app.exit(code)


qt.QTimer.singleShot(3000, run)
