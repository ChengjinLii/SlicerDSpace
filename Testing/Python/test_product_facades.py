#!/usr/bin/env python3
"""Smoke tests for product-level workflow facades."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ProductFacadeTest(unittest.TestCase):
    def test_workflow_catalog_has_expected_areas(self) -> None:
        from workflow_catalog import WORKFLOW_AREAS

        keys = [area.key for area in WORKFLOW_AREAS]
        self.assertEqual(
            keys,
            [
                "surface",
                "parcellation",
                "segmentation",
                "microstructure",
                "tractography",
                "connectome",
            ],
        )

    def test_surface_facade_exports_core_aliases(self) -> None:
        from surface import (
            SurfaceConfig,
            SurfacePostprocessingConfig,
            SurfacePredictionConfig,
            SurfacePreprocessingConfig,
            run_surface,
            run_surface_postprocessing,
            run_surface_prediction,
            run_surface_preprocessing,
        )

        self.assertIsNotNone(SurfaceConfig)
        self.assertIsNotNone(SurfacePreprocessingConfig)
        self.assertIsNotNone(SurfacePredictionConfig)
        self.assertIsNotNone(SurfacePostprocessingConfig)
        self.assertTrue(callable(run_surface))
        self.assertTrue(callable(run_surface_preprocessing))
        self.assertTrue(callable(run_surface_prediction))
        self.assertTrue(callable(run_surface_postprocessing))

    def test_facade_modules_are_importable_without_forcing_heavy_dependencies(self) -> None:
        import microstructure
        import parcellation
        import preprocessing
        import segmentation
        import shared

        self.assertIn("MicrostructureConfig", microstructure.__all__)
        self.assertIn("ParcellationConfig", parcellation.__all__)
        self.assertIn("run_preprocessing_pipeline", preprocessing.__all__)
        self.assertIn("SegmentationConfig", segmentation.__all__)
        self.assertIn("ProductOrchestratorConfig", shared.__all__)
        self.assertIn("run_subject_products", shared.__all__)
        self.assertIn("validate_subject_inputs", shared.__all__)

    def test_planned_packages_expose_plans(self) -> None:
        from connectome import ConnectomeConfig, PLANNED_WORKFLOWS as CONNECTOME_WORKFLOWS, run_connectome
        from tractography import (
            BundleParcellationConfig,
            ACTPrepConfig,
            TractographyACTConfig,
            TractographyBundleParcellationConfig,
            PLANNED_WORKFLOWS as TRACTOGRAPHY_WORKFLOWS,
            TractographyDTIConfig,
            TractographySAFConfig,
            TractographyTractCloudConfig,
            TractographyWMQLConfig,
            TractographyWMAConfig,
            inspect_mrtrix_backend,
            inspect_saf_backend,
            inspect_tractcloud_backend,
            inspect_wmql_backend,
            inspect_wma_backend,
            inspect_wma_org_atlas,
            run_act_tracking,
            run_act_prep,
            run_bundle_parcellation_pipeline,
            run_dti_tracking,
            run_saf_pipeline,
            run_tractcloud_parcellation_pipeline,
            run_wmql_bundle_segmentation_pipeline,
            run_wma_org_atlas_pipeline,
        )

        self.assertGreaterEqual(len(TRACTOGRAPHY_WORKFLOWS), 3)
        self.assertIsNotNone(TractographyACTConfig)
        self.assertIsNotNone(ACTPrepConfig)
        self.assertIsNotNone(TractographyDTIConfig)
        self.assertIsNotNone(TractographySAFConfig)
        self.assertIsNotNone(TractographyWMAConfig)
        self.assertIsNotNone(TractographyTractCloudConfig)
        self.assertIsNotNone(TractographyWMQLConfig)
        self.assertIsNotNone(TractographyBundleParcellationConfig)
        self.assertIsNotNone(BundleParcellationConfig)
        self.assertTrue(callable(run_act_tracking))
        self.assertTrue(callable(run_act_prep))
        self.assertTrue(callable(run_dti_tracking))
        self.assertTrue(callable(run_saf_pipeline))
        self.assertTrue(callable(inspect_mrtrix_backend))
        self.assertTrue(callable(inspect_saf_backend))
        self.assertTrue(callable(inspect_tractcloud_backend))
        self.assertTrue(callable(inspect_wmql_backend))
        self.assertTrue(callable(inspect_wma_backend))
        self.assertTrue(callable(inspect_wma_org_atlas))
        self.assertTrue(callable(run_wma_org_atlas_pipeline))
        self.assertTrue(callable(run_tractcloud_parcellation_pipeline))
        self.assertTrue(callable(run_wmql_bundle_segmentation_pipeline))
        self.assertTrue(callable(run_bundle_parcellation_pipeline))
        self.assertIsNotNone(ConnectomeConfig)
        self.assertTrue(callable(run_connectome))
        self.assertGreaterEqual(len(CONNECTOME_WORKFLOWS), 1)


if __name__ == "__main__":
    unittest.main()
