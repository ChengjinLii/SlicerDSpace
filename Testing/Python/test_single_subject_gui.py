"""GUI subject policy stays independent from within-subject model parallelism."""
import unittest
from types import SimpleNamespace

from shared.ui_advanced_layout import BATCH_CONTROLS, enforce_single_subject_gui, hide_batch_controls


class SingleSubjectGuiTest(unittest.TestCase):
    def test_legacy_scene_is_migrated_without_changing_model_concurrency(self):
        node = SimpleNamespace(batchMode=True, batchSize=8, maxParallelModels=3,
                               subjectId="sub-01", inputDirectory="/study/sub-01")
        enforce_single_subject_gui(node)
        self.assertFalse(node.batchMode)
        self.assertEqual(node.batchSize, 1)
        self.assertEqual(node.maxParallelModels, 3)
        self.assertEqual(node.inputDirectory, "/study/sub-01")
        enforce_single_subject_gui(node)

    def test_none_node_is_allowed_during_scene_close(self):
        enforce_single_subject_gui(None)

    def test_cohort_controls_are_hidden(self):
        class Widget:
            visible = True
            def hide(self):
                self.visible = False
        owner = SimpleNamespace(ui=SimpleNamespace(**{name: Widget() for name in BATCH_CONTROLS}))
        hide_batch_controls(owner)
        self.assertTrue(all(not getattr(owner.ui, name).visible for name in BATCH_CONTROLS))


if __name__ == "__main__":
    unittest.main()
