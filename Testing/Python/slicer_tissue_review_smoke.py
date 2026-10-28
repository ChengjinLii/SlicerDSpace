"""Native editable DDSeg copies preserve geometry, edits and quantitative sources."""

import hashlib
import json
import os
from pathlib import Path
import traceback

import numpy as np
import qt
import slicer
import vtk


def run():
    root = Path(os.environ['SLICERDSPACE_SMOKE_ROOT'])
    try:
        from shared.result_scene import clear_run, register_node
        from shared.run_history import SUBJECT_MANIFEST_KIND
        from shared.segmentation_review import editable_tissue_copy
        slicer.util.selectModule('SlicerDSpace')
        source = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLabelMapVolumeNode', 'synthetic_tissue')
        labels = np.zeros((5, 6, 7), dtype=np.uint8)
        labels[1, 1:4, 1:4], labels[2, 1:4, 1:4], labels[3, 1:4, 1:4] = 1, 2, 3
        slicer.util.updateVolumeFromArray(source, labels)
        matrix = vtk.vtkMatrix4x4()
        matrix.DeepCopy((0, -2, 0, 10, 1.5, 0, 0, -20, 0, 0, 2.5, 30, 0, 0, 0, 1))
        source.SetIJKToRASMatrix(matrix)
        parent = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'synthetic_parent')
        parent_matrix = vtk.vtkMatrix4x4()
        parent_matrix.SetElement(0, 3, 100)
        parent.SetMatrixTransformToParent(parent_matrix)
        source.SetAndObserveTransformNodeID(parent.GetID())
        file = root / 'tissue.nii.gz'
        assert slicer.util.saveNode(source, str(file))
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        manifest = root / 'run.json'
        manifest.write_text(json.dumps({'kind': SUBJECT_MANIFEST_KIND, 'version': 1,
            'subject_id': 'synthetic', 'run_name': 'Test1', 'status': 'completed',
            'tasks': [{'name': 'segmentation.ddseg', 'status': 'completed', 'outputs': {'labels': str(file)}}]}))
        run_id = str(manifest.resolve())
        register_node(slicer, source, run_id, 'synthetic', 'Test1', 'segmentation.ddseg', str(file))
        copy = editable_tissue_copy(slicer, source)
        owner = slicer.modules.slicerdspace.widgetRepresentation().self()
        owner._latestResultManifestPath = str(manifest)
        owner._manage_result_scene('edit_tissue')
        assert slicer.modules.segmenteditor.widgetRepresentation().self().editor.segmentationNode().GetID() == copy.GetID()
        slicer.util.selectModule('SlicerDSpace')
        assert copy.IsA('vtkMRMLSegmentationNode')
        assert copy.GetTransformNodeID() == parent.GetID()
        assert copy.GetSegmentation().GetNumberOfSegments() == 3
        for value in (1, 2, 3):
            np.testing.assert_array_equal(slicer.util.arrayFromSegmentBinaryLabelmap(copy, 'tissue_' + str(value), source), labels == value)
        edited = (labels == 1).astype(np.uint8)
        edited[0, 0, 0] = 1
        slicer.util.updateSegmentBinaryLabelmapFromArray(edited, copy, 'tissue_1', source)
        assert editable_tissue_copy(slicer, source).GetID() == copy.GetID()
        np.testing.assert_array_equal(slicer.util.arrayFromSegmentBinaryLabelmap(copy, 'tissue_1', source), edited)
        np.testing.assert_array_equal(slicer.util.arrayFromVolume(source), labels)
        assert hashlib.sha256(file.read_bytes()).hexdigest() == before
        assert copy.GetAttribute('SlicerDDSurfer.QCState') == 'manual_revision_not_assessed'
        copy_id = copy.GetID()
        assert clear_run(slicer, run_id) == 1
        assert slicer.mrmlScene.GetNodeByID(copy_id) is not None
        assert slicer.util.saveScene(str(root / 'review.mrb'))
        slicer.mrmlScene.Clear(0)
        assert slicer.util.loadScene(str(root / 'review.mrb'))
        assert slicer.util.getNode('synthetic_tissue_review').GetSegmentation().GetNumberOfSegments() == 3
        print('TISSUE_REVIEW_COPY_GEOMETRY_EDITS_OWNERSHIP=True', flush=True)
        slicer.app.exit(0)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


qt.QTimer.singleShot(5000, run)
