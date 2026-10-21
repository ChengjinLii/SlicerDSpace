"""Validate PNL model deserialization in its own Python, without patient data."""

import json
from pathlib import Path
import sys


def main():
    import tensorflow as tf
    import keras
    import conversion
    import nibabel as nib
    import numpy as np
    from pnl_mask_runner import select_device

    device = select_device("auto", tf=tf)
    root = Path(sys.argv[1])
    if tf.__version__ != "2.15.1" or not keras.__version__.startswith("2.15."):
        raise RuntimeError("PNL runtime requires the reviewed TensorFlow/Keras versions")
    template = nib.load(str(root / "IITmean_b0_256.nii.gz"))
    if template.shape != (256, 256, 256):
        raise RuntimeError("Unexpected PNL template grid")
    for view in ("axial", "coronal", "sagittal"):
        model = keras.models.model_from_json((root / "CompNetBasicModel.json").read_text())
        model.load_weights(str(next(root.glob(f"weights-{view}-improvement-*.h5"))))
        outputs = model(tf.zeros((1, 256, 256, 1)), training=False)
        if not all(np.isfinite(value.numpy()).all() for value in outputs):
            raise RuntimeError("PNL synthetic forward check produced nonfinite values")
        keras.backend.clear_session()
    print("[PNL setup] Model/forward checks passed: " + json.dumps(device), flush=True)


if __name__ == "__main__":
    main()
