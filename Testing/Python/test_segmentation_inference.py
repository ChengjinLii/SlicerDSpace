from __future__ import annotations

import unittest

import numpy as np

from segmentation.inference import combine_views, normalize_class_scores


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


if __name__ == "__main__":
    unittest.main()
