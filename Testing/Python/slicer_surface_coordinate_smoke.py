"""Real Slicer asymmetric surface export/load/save/reload coordinate contract.

Run with Slicer --python-script after adding the staged module directory.
Only synthetic test geometry is created; no scientific output is modified.
"""

import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import qt
import SimpleITK as sitk
import slicer
import trimesh
from vtk.util.numpy_support import vtk_to_numpy


def run():
    try:
        from shared.module_logic import SharedLogicMixin
        from surface.postprocessing import PostprocessingConfig, convert_meshes_to_native_space

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vertices = np.array([[-35., 11., 8.], [-31., 11., 8.], [-35., 17., 8.], [-35., 11., 19.]])
            faces = [[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]]
            atlas = root / "atlas.obj"
            trimesh.Trimesh(vertices=vertices, faces=faces, process=False).export(str(atlas))
            transform = sitk.TranslationTransform(3, [3., -5., 7.])
            tfm = root / "atlas_to_native.tfm"
            sitk.WriteTransform(transform, str(tfm))
            flip = np.array([-1., -1., 1.])
            expected_ras = (vertices * flip + [3., -5., 7.]) * flip
            outputs = convert_meshes_to_native_space(
                PostprocessingConfig("phantom", tfm, root),
                [SimpleNamespace(hemisphere="left", wm_mesh_path=atlas, pial_mesh_path=None)],
            )
            for path in outputs["wm"]:
                before = set(slicer.util.getNodesByClass("vtkMRMLModelNode"))
                assert SharedLogicMixin()._load_model_node(path, "wm", "phantom")
                after = set(slicer.util.getNodesByClass("vtkMRMLModelNode"))
                node = (after - before).pop()
                points = vtk_to_numpy(node.GetPolyData().GetPoints().GetData())
                assert np.allclose(points.min(axis=0), expected_ras.min(axis=0), atol=1e-5)
                assert np.allclose(points.max(axis=0), expected_ras.max(axis=0), atol=1e-5)
                saved = root / (path.stem + "_saved.vtp")
                assert slicer.util.saveNode(node, str(saved))
                reloaded = slicer.util.loadModel(str(saved))
                restored = vtk_to_numpy(reloaded.GetPolyData().GetPoints().GetData())
                assert np.allclose(restored, points, atol=1e-5)
                slicer.mrmlScene.RemoveNode(node)
                slicer.mrmlScene.RemoveNode(reloaded)
        print("SLICERDDSURFER_SURFACE_COORDINATE_ROUNDTRIP=True", flush=True)
        slicer.app.exit(0)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


qt.QTimer.singleShot(3000, run)
