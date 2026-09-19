"""Fail-closed, format-aware contracts shared by planning and execution."""

import json
from pathlib import Path


def readable_output(path: Path) -> bool:
    """Decode scientific data, not just headers or completion filenames."""
    try:
        if not path.is_file() or path.stat().st_size == 0:
            return False
        name = path.name.lower()
        if name.endswith((".nii", ".nii.gz", ".mgz")):
            import nibabel as nib
            import numpy as np

            img = nib.load(str(path))
            data = np.asanyarray(img.dataobj)
            return bool(data.size and np.isfinite(data).all()
                        and np.isfinite(img.affine).all()
                        and abs(np.linalg.det(img.affine[:3, :3])) > 1e-12)
        if name.endswith(".stl"):
            import numpy as np
            import trimesh

            mesh = trimesh.load(str(path), process=False)
            return bool(len(mesh.vertices) and len(mesh.faces) and np.isfinite(mesh.vertices).all())
        if name.endswith(".json"):
            record = json.loads(path.read_text())
            return isinstance(record, dict) and bool(record) and record.get("status") not in {
                "failed", "running", "planned", "partial_failed", "cancelled"
            }
        return True
    except Exception:
        return False


def outputs_readable(paths) -> bool:
    return all(readable_output(Path(path)) for path in paths)


def tractography_readable(tck: Path, trk: Path, weights: Path | None = None) -> bool:
    try:
        import nibabel as nib
        import numpy as np

        counts = []
        for path in dict.fromkeys((tck, trk)):
            count = 0
            for streamline in nib.streamlines.load(str(path), lazy_load=True).streamlines:
                if len(streamline) < 2 or not np.isfinite(streamline).all():
                    return False
                count += 1
            counts.append(count)
        if not counts[0] or len(set(counts)) != 1:
            return False
        if weights is not None:
            values = np.loadtxt(weights, ndmin=1)
            if values.ndim != 1 or values.size != counts[0]:
                return False
            if not np.isfinite(values).all() or (values < 0).any() or not (values > 0).any():
                return False
        return True
    except Exception:
        return False
def vtp_streamline_count(path):
    """Decode VTP geometry; return None for corruption or unavailable VTK.

    Empty but valid polydata returns zero. A Piece header alone is not evidence
    that the appended/compressed geometry is readable.
    """
    try:
        import numpy as np
        from vtkmodules.vtkIOXML import vtkXMLPolyDataReader
        from vtkmodules.util.numpy_support import vtk_to_numpy

        reader = vtkXMLPolyDataReader()
        errors = []
        reader.AddObserver("ErrorEvent", lambda *_: errors.append(True))
        reader.SetFileName(str(path))
        if not reader.CanReadFile(str(path)):
            return None
        reader.Update()
        if errors or reader.GetErrorCode():
            return None
        data = reader.GetOutput()
        points = data.GetPoints()
        if points is not None and not np.isfinite(vtk_to_numpy(points.GetData())).all():
            return None
        if data.GetNumberOfVerts() or data.GetNumberOfPolys() or data.GetNumberOfStrips():
            return None
        lines = data.GetLines()
        count = data.GetNumberOfLines()
        offsets = vtk_to_numpy(lines.GetOffsetsArray())
        connectivity = vtk_to_numpy(lines.GetConnectivityArray())
        if len(offsets) != count + 1 or offsets[0] != 0 or offsets[-1] != len(connectivity):
            return None
        if count and (np.any(np.diff(offsets) < 2) or np.any(connectivity < 0)
                      or np.any(connectivity >= data.GetNumberOfPoints())):
            return None
        return count
    except (ImportError, OSError, ValueError, RuntimeError, AttributeError, IndexError):
        return None
