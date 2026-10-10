from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from anatomy.segmentation.inference import combine_views, normalize_class_scores
from anatomy.segmentation.config import DDSegConfig
from anatomy.segmentation.qc import DDSEG_PROBABILITY_SEMANTICS, write_ddseg_qc_record


class SegmentationInferenceTest(unittest.TestCase):
    def test_final_logit_normalization_preserves_labels(self) -> None:
        axial = np.linspace(-4.0, 8.0, num=32, dtype=np.float32).reshape(2, 2, 2, 4)
        sagittal = axial.copy()
        coronal = axial.copy()
        combined = combine_views(axial, sagittal, coronal)
        probabilities = normalize_class_scores(combined["prob_maps"])

        np.testing.assert_array_equal(np.argmax(probabilities, axis=3), combined["labels"])
        np.testing.assert_allclose(probabilities.sum(axis=3), 1.0, atol=1e-6)
        self.assertGreaterEqual(float(probabilities.min()), 0.0)
        self.assertLessEqual(float(probabilities.max()), 1.0)

    def test_normalization_rejects_non_volume_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "4D NHWC"):
            normalize_class_scores(np.zeros((2, 4), dtype=np.float32))

    def test_completed_ddseg_writes_probability_qc_contract(self) -> None:
        labels = np.asarray([[[1, 2, 3]]], dtype=np.int16)
        probabilities = np.zeros((1, 1, 3, 4), dtype=np.float32)
        probabilities[..., 0] = 0.1
        probabilities[0, 0, 0, 1] = 0.9
        probabilities[0, 0, 1, 2] = 0.9
        probabilities[0, 0, 2, 3] = 0.9

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            outputs = {
                name: output_dir / f"{name}.nii.gz"
                for name in ("segmentation", "gm_probability", "wm_probability", "csf_probability")
            }
            for path in outputs.values():
                path.write_bytes(b"output")
            write_ddseg_qc_record(
                DDSegConfig(
                    input_mask_nii=output_dir / "mask.nii.gz",
                    parameter_type="DTI",
                    output_folder=output_dir,
                    weights_dir=output_dir / "weights",
                ),
                labels=labels,
                probability_maps=probabilities,
                outputs=outputs,
            )
            qc = json.loads((output_dir / "ddseg_qc.json").read_text(encoding="utf-8"))

        self.assertEqual(qc["status"], "completed")
        self.assertEqual(qc["probability_semantics"], DDSEG_PROBABILITY_SEMANTICS)
        self.assertEqual(qc["probability_qc"]["tissue_mass_valid_fraction"], 1.0)
        self.assertEqual(qc["probability_qc"]["label_agreement"], 1.0)

    def test_ddseg_qc_rejects_mismatched_probability_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            with self.assertRaisesRegex(ValueError, "matching four-class"):
                write_ddseg_qc_record(
                    DDSegConfig(
                        input_mask_nii=output_dir / "mask.nii.gz",
                        parameter_type="DTI",
                        output_folder=output_dir,
                        weights_dir=output_dir / "weights",
                    ),
                    labels=np.ones((2, 2, 2), dtype=np.int16),
                    probability_maps=np.ones((2, 2, 2, 3), dtype=np.float32),
                    outputs={},
                )


if __name__ == "__main__":
    unittest.main()
