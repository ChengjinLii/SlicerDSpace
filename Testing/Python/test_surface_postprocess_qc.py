"""Tiny synthetic meshes exercise integrity only, never anatomical accuracy."""

from pathlib import Path
import tempfile
import unittest

import nibabel as nib
import numpy as np
import trimesh

from anatomy.surface.postprocess_qc import validate_postprocess_outputs


def write_postprocess_fixture(output):
    for folder in ("logs", "surf", "label", "mri", "stats", "fsaverage"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    (output / "logs/qc.json").write_text("{}")
    nib.save(nib.MGHImage(np.zeros((3, 3, 3), dtype=np.float32), np.eye(4)), output / "mri/brain.mgz")
    mesh = trimesh.creation.icosphere(subdivisions=1)
    for hemi in ("lh", "rh"):
        for kind in ("white", "pial", "inflated", "sphere", "sphere.reg"):
            nib.freesurfer.write_geometry(output / "surf" / f"{hemi}.{kind}", mesh.vertices, mesh.faces)
        for kind in ("thickness", "curv", "sulc", "area"):
            nib.freesurfer.write_morph_data(output / "surf" / f"{hemi}.{kind}", np.ones(len(mesh.vertices), dtype=np.float32))
        for atlas in ("aparc", "aparc.a2009s"):
            nib.freesurfer.write_annot(output / "label" / f"{hemi}.{atlas}.annot", np.arange(len(mesh.vertices)) % 2,
                                      np.asarray([[10, 0, 0, 0], [0, 10, 0, 0]]), [b"unknown", b"region"])
            (output / "stats" / f"{hemi}.{atlas}.stats").write_text("# fixture\nregion 20 10 15 1 0.1 0.01\n")


class PostprocessQCTests(unittest.TestCase):
    def test_actual_decode_rejects_bad_morphometry_and_statistics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for corruption in (None, "nan", "negative", "count", "stats"):
                with self.subTest(corruption=corruption):
                    write_postprocess_fixture(root)
                    if corruption in {"nan", "negative", "count"}:
                        path = root / "surf/lh.thickness"
                        values = nib.freesurfer.read_morph_data(path)
                        if corruption == "count":
                            values = values[:-1]
                        else:
                            values[0] = np.nan if corruption == "nan" else -1
                        nib.freesurfer.write_morph_data(path, values)
                    elif corruption == "stats":
                        (root / "stats/lh.aparc.stats").write_text("region 3 nan\n")
                    qc = validate_postprocess_outputs(root, ("lh", "rh"), ("aparc", "aparc.a2009s"))
                    self.assertEqual(qc["automatic_qc_passed"], corruption is None)
                    self.assertEqual(qc["human_review"], "pending")


if __name__ == "__main__":
    unittest.main()
