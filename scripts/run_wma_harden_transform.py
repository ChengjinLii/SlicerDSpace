"""Run WMA's harden_transform_with_slicer.py in 3D Slicer with a fiber-bundle save that does not depend
on Slicer's default writer choice.

    Slicer --no-main-window --python-script <shim> <author args...>

tractography/wma.py writes the shim, named like the author script, into the folder that it puts first on
PATH for the author pipeline; the shim calls run(<author script>). The author path is not a command-line
argument because Slicer runs a .py positional argument instead of the --python-script file.

3D Slicer 5.12.4 with SlicerDMRI (macOS, 2026-10-23) picks the writer type "TRXFile" for fiber bundles
and has no writer registered for it, so slicer.util.saveNode() wrote no cluster and WMA stopped
("There should be 800 resulting fiber clusters, but only 23 generated"). The author script runs
unchanged; only its .vtp/.vtk fiber-bundle saves go through the fiber bundle storage node.
"""

import runpy
import sys

import slicer


def save_fiber_bundle(node, filename, properties=None, _save=slicer.util.saveNode):
    if node.IsA("vtkMRMLFiberBundleNode") and str(filename).lower().endswith((".vtp", ".vtk")):
        storage = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLFiberBundleStorageNode")
        try:
            storage.SetFileName(str(filename))
            return bool(storage.WriteData(node))
        finally:
            slicer.mrmlScene.RemoveNode(storage)
    return _save(node, filename, properties or {})


def run(author):
    slicer.util.saveNode = save_fiber_bundle
    sys.argv = [str(author), *sys.argv[1:]]
    runpy.run_path(str(author), run_name="__main__")
