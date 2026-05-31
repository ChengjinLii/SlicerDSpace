import numpy as np
import nibabel.freesurfer.io as fsio


def get_surface_transform(surf_file):
    """Return the FreeSurfer surface volume-geometry transform.

    Prefer nibabel metadata parsing because FreeSurfer surfaces are binary and
    can contain non-UTF8 bytes before the embedded volume-info text block.
    """

    try:
        _, _, metadata = fsio.read_geometry(surf_file, read_metadata=True)
        if all(key in metadata for key in ("xras", "yras", "zras", "cras")):
            return np.column_stack(
                [metadata["xras"], metadata["yras"], metadata["zras"], metadata["cras"]]
            ).astype(float)
    except Exception:
        pass

    with open(surf_file, "rb") as f:
        nline = ""
        while True:
            line = f.readline()
            if not line:
                raise RuntimeError("unable to extract the surface transform")
            try:
                nline = line.decode("utf-8").strip()
            except UnicodeDecodeError:
                continue
            if len(nline) >= 4 and nline[:4] == "xras":
                break
        tfmatrix = np.zeros((3, 4), dtype=float)
        for i in range(4):
            vals = nline[4:].replace("=", " ").split()
            if len(vals) >= 3:
                tfmatrix[:, i] = np.array(vals[:3], dtype=float)
            while True:
                line = f.readline()
                if not line:
                    break
                try:
                    nline = line.decode("utf-8").strip()
                    break
                except UnicodeDecodeError:
                    continue
    return tfmatrix
