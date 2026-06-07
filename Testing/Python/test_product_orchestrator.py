#!/usr/bin/env python3
"""Tests for subject-root product orchestration and resume planning."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ProductOrchestratorTest(unittest.TestCase):
    def test_dry_run_plans_microstructure_target(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("microstructure",),
                    execute=False,
                )
            )

            self.assertEqual(len(result.tasks), 1)
            self.assertEqual(result.tasks[0].name, "microstructure.dti")
            self.assertEqual(result.tasks[0].status, "planned")

    def test_dry_run_plans_structural_targets(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("segmentation", "parcellation", "surface"),
                    execute=False,
                )
            )

            statuses = {task.name: task.status for task in result.tasks}
            self.assertEqual(statuses["segmentation.ddseg"], "planned")
            self.assertEqual(statuses["parcellation.ddparcel"], "planned")
            self.assertEqual(statuses["surface.ddsurfer"], "planned")

    def test_dry_run_plans_preprocessing_target(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("preprocessing",),
                    execute=False,
                )
            )

            self.assertEqual(len(result.tasks), 1)
            self.assertEqual(result.tasks[0].name, "preprocessing.dwi")
            self.assertEqual(result.tasks[0].status, "planned")

    def test_dry_run_plans_selected_tractography_bundle_connectome_targets(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("tractography", "bundles", "connectome"),
                    run_name="csd_act_test",
                    execute=False,
                )
            )

            statuses = {task.name: task.status for task in result.tasks}
            self.assertEqual(statuses["tractography.csd_act"], "planned")
            self.assertEqual(statuses["bundles.wmql"], "planned")
            self.assertEqual(statuses["connectome.streamline_count"], "planned")
            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["run_name"], "csd_act_test")
            self.assertEqual(manifest["tractography_backend"], "csd_act")
            self.assertFalse(manifest["execute"])
            self.assertEqual(manifest["select_streamlines"], 100000)
            self.assertEqual(manifest["connectome_backend"], "python")

    def test_preflight_blocked_targets_are_recorded_but_do_not_stop_other_targets(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("microstructure", "tractography", "connectome"),
                    execute=False,
                    preflight_blocked_targets={"tractography": "preflight missing dependencies: MRtrix3"},
                )
            )

            statuses = {task.name: task.status for task in result.tasks}
            self.assertEqual(statuses["tractography.csd_act"], "blocked")
            self.assertEqual(statuses["microstructure.dti"], "planned")
            self.assertEqual(statuses["connectome.streamline_count"], "planned")
            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["preflight_blocked_targets"]["tractography"], "preflight missing dependencies: MRtrix3")
            self.assertNotIn("tractography", manifest["run_targets"])

    def test_run_plan_distinguishes_upstream_and_environment_blockers(self) -> None:
        from shared import ProductOrchestratorConfig, plan_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            plan = plan_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("segmentation", "parcellation", "tractography", "bundles", "connectome"),
                    execute=True,
                    preflight_blocked_targets={"tractography": "preflight missing dependencies: MRtrix3"},
                )
            )

            statuses = {item.target: item.status for item in plan.items}
            categories = {item.target: item.reason_category for item in plan.items}
            self.assertEqual(statuses["segmentation"], "will_run")
            self.assertEqual(statuses["parcellation"], "will_run")
            self.assertEqual(statuses["tractography"], "blocked")
            self.assertEqual(categories["tractography"], "environment")
            self.assertEqual(statuses["bundles"], "blocked")
            self.assertEqual(categories["bundles"], "upstream")
            self.assertEqual(statuses["connectome"], "blocked")
            self.assertEqual(categories["connectome"], "upstream")
            self.assertTrue(plan.run_plan_path.is_file())

    def test_orchestrator_writes_normalized_task_manifest_qc_and_logs(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("microstructure", "tractography"),
                    execute=False,
                    preflight_blocked_targets={"tractography": "preflight missing dependencies: MRtrix3"},
                )
            )

            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(Path(manifest["run_plan_path"]).is_file())
            self.assertTrue(Path(manifest["output_tree_audit_path"]).is_file())
            self.assertIsInstance(manifest["output_tree_warnings"], list)
            self.assertEqual(manifest["run_plan_summary"]["will_run"], 1)
            for task in manifest["tasks"]:
                normalized_manifest = Path(task["normalized_manifest_path"])
                normalized_qc = Path(task["normalized_qc_path"])
                normalized_logs = Path(task["normalized_logs_dir"])
                self.assertTrue(normalized_manifest.is_file())
                self.assertTrue(normalized_qc.is_file())
                self.assertTrue(normalized_logs.is_dir())
                task_manifest = json.loads(normalized_manifest.read_text(encoding="utf-8"))
                self.assertEqual(task_manifest["schema"], "slicerddsurfer.task.v1")
                self.assertIn("inputs", task_manifest)
                self.assertIn("outputs", task_manifest)
                self.assertIn("dependencies", task_manifest)
                self.assertIn("runtime_seconds", task_manifest)

    def test_dry_run_honors_output_root_and_advanced_connectome_options(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            output_root = Path(tmp) / "custom_outputs"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    output_root=output_root,
                    targets=("tractography", "connectome"),
                    run_name="csd_act_100k",
                    execute=False,
                    select_streamlines=100000,
                    connectome_backend="mrtrix",
                    connectome_compress_mrtrix_dense=True,
                )
            )

            self.assertTrue(result.run_manifest_path.is_relative_to(output_root))
            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["output_root"], output_root.resolve().as_posix())
            self.assertEqual(manifest["tractography_backend"], "csd_act")
            self.assertEqual(manifest["select_streamlines"], 100000)
            self.assertEqual(manifest["connectome_backend"], "mrtrix")
            self.assertTrue(manifest["connectome_compress_mrtrix_dense"])

    def test_dry_run_supports_dti_tractography_backend(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("tractography", "bundles", "connectome"),
                    run_name="dti_det_test",
                    tractography_backend="dti_det",
                    connectome_backend="python",
                    execute=False,
                )
            )

            statuses = {task.name: task.status for task in result.tasks}
            self.assertEqual(statuses["tractography.dti_det"], "planned")
            self.assertEqual(statuses["bundles.wmql"], "planned")
            self.assertEqual(statuses["connectome.streamline_count"], "planned")
            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["tractography_backend"], "dti_det")

    def test_microstructure_optional_stage_gates_are_explicit(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("microstructure",),
                    execute=False,
                    microstructure_run_free_water=True,
                    microstructure_run_noddi=True,
                )
            )

            self.assertEqual([task.name for task in result.tasks], ["microstructure.dti", "microstructure.freewater", "microstructure.noddi"])
            self.assertEqual([task.status for task in result.tasks], ["planned", "planned", "planned"])
            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["microstructure_run_free_water"])
            self.assertTrue(manifest["microstructure_run_noddi"])
            self.assertEqual(manifest["microstructure_stages"], ["dti", "freewater", "noddi"])

    def test_bundle_backend_expands_product_target_to_concrete_backends(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "149741"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="149741",
                    subject_root=subject_root,
                    targets=("bundles",),
                    bundle_backend="all",
                    execute=False,
                )
            )

            self.assertEqual([task.name for task in result.tasks], ["bundles.wmql", "bundles.wma", "bundles.tractcloud"])
            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["targets"], ["bundles", "wma", "tractcloud"])
            self.assertEqual(manifest["bundle_backends"], ["wmql", "wma", "tractcloud"])

    def test_saf_tractography_backend_expands_surface_postprocess_and_saf(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("tractography",),
                    tractography_backend="saf",
                    execute=False,
                )
            )

            self.assertEqual([task.name for task in result.tasks], ["surface.ddsurfer_postprocess", "tractography.csd_act", "tractography.saf"])
            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["tractography_backend"], "saf")
            self.assertEqual(manifest["primary_tractography_backend"], "csd_act")

    def test_dry_run_supports_optional_algorithm_targets(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "149741"
            input_dir = subject_root / "input"
            tractography_dir = subject_root / "tractography"
            input_dir.mkdir(parents=True)
            tractography_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")
            (tractography_dir / "149741_ukf_pp_downsampled.vtk").write_text("vtk", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="149741",
                    subject_root=subject_root,
                    targets=("saf", "wma", "tractcloud"),
                    execute=False,
                )
            )

            statuses = {task.name: task.status for task in result.tasks}
            self.assertEqual(statuses["tractography.saf"], "planned")
            self.assertEqual(statuses["bundles.wma"], "planned")
            self.assertEqual(statuses["bundles.tractcloud"], "planned")
            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["targets"], ["saf", "wma", "tractcloud"])

    def test_execute_saf_defaults_to_1m_mask_seeding(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            layout = subject_layout(subject_root)
            csd_dir = layout.csd
            csd_dir.mkdir(parents=True)
            (csd_dir / "100307_wmfod_norm.mif").write_text("fod", encoding="utf-8")

            post_dir = layout.ddsurfer_postprocess
            (post_dir / "mri").mkdir(parents=True)
            (post_dir / "surf").mkdir()
            for name in ("brain.mgz",):
                (post_dir / "mri" / name).write_text(name, encoding="utf-8")
            for name in (
                "lh.white",
                "rh.white",
                "lh.pial",
                "rh.pial",
                "lh.inflated",
                "rh.inflated",
                "lh.sphere",
                "rh.sphere",
                "lh.curv",
                "rh.curv",
            ):
                (post_dir / "surf" / name).write_text(name, encoding="utf-8")
            (post_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
            (post_dir / "qc.json").write_text('{"status":"completed"}\n', encoding="utf-8")

            captured = {}

            class _FakeResult:
                def __init__(self, output_dir: Path) -> None:
                    self.qc_path = output_dir / "saf_qc.json"
                    self.manifest_path = output_dir / "saf_manifest.json"
                    self.saf_tractogram = output_dir / "SAF.tck"
                    self.saf_vtk_path = output_dir / "SAF.vtk"
                    self.streamline_count = 63589
                    self.qc_path.parent.mkdir(parents=True, exist_ok=True)
                    self.qc_path.write_text('{"status":"completed"}\n', encoding="utf-8")
                    self.manifest_path.write_text("{}\n", encoding="utf-8")
                    self.saf_tractogram.write_text("tck", encoding="utf-8")
                    self.saf_vtk_path.write_text("vtk", encoding="utf-8")

            def _fake_run_saf(config, *, log=None):
                captured["tckgen_options"] = config.tckgen_options
                captured["noregister"] = config.noregister
                return _FakeResult(config.output_dir)

            with mock.patch("tractography.run_saf", side_effect=_fake_run_saf):
                result = run_subject_products(
                    ProductOrchestratorConfig(
                        subject_id="100307",
                        subject_root=subject_root,
                        targets=("saf",),
                        execute=True,
                        saf_noregister=True,
                    )
                )

            self.assertIn("-select 1000000", captured["tckgen_options"])
            self.assertIn("-seed_image", captured["tckgen_options"])
            self.assertTrue(captured["noregister"])
            self.assertEqual(result.tasks[0].outputs["streamline_count"], "63589")
            self.assertTrue(result.tasks[0].outputs["tractogram_vtk"].endswith("SAF.vtk"))

    def test_dry_run_supports_surface_postprocess_target(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "877168"
            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="877168",
                    subject_root=subject_root,
                    targets=("surface_postprocess",),
                    execute=False,
                )
            )

            self.assertEqual(len(result.tasks), 1)
            self.assertEqual(result.tasks[0].name, "surface.ddsurfer_postprocess")
            self.assertEqual(result.tasks[0].status, "planned")
            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["targets"], ["surface_postprocess"])

    def test_surface_postprocess_execute_false_preserves_requested_atlases(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "877168"
            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="877168",
                    subject_root=subject_root,
                    targets=("surface_postprocess",),
                    execute=False,
                    postprocess_atlases=("aparc", "aparc.a2009s"),
                )
            )

            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["targets"], ["surface_postprocess"])
            self.assertEqual(manifest["postprocess_atlases"], ["aparc", "aparc.a2009s"])

    def test_resume_skips_completed_existing_outputs(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            layout = subject_layout(subject_root)
            run_name = "csd_act_test"
            csd_dir = layout.csd / run_name
            tract_dir = layout.tractograms / run_name
            wmql_dir = layout.bundles_wmql / run_name
            conn_dir = layout.connectome / run_name
            seg_dir = layout.ddseg
            parcel_dir = layout.ddparcel
            surface_dir = layout.ddsurfer / "pred_results_SlicerDDSurfer" / "native" / "100307"
            for directory in (csd_dir, tract_dir, wmql_dir, conn_dir, seg_dir, parcel_dir, surface_dir):
                directory.mkdir(parents=True)
            for name in (
                "SegmentationMap_GMWMCSF.nii.gz",
                "ProbabilisticMap_GM.nii.gz",
                "ProbabilisticMap_WM.nii.gz",
                "ProbabilisticMap_CSF.nii.gz",
            ):
                (seg_dir / name).write_text(name, encoding="utf-8")
            for name in (
                "100307-DDSurfer-wmparc.nii.gz",
                "100307-DDSurfer-wmparc-Reg.mgz",
                "100307-dti-FractionalAnisotropy-Reg-NormMasked.nii.gz",
                "100307-dti-Trace-Reg-NormMasked.nii.gz",
                "100307-dti-MinEigenvalue-Reg-NormMasked.nii.gz",
                "100307-dti-MidEigenvalue-Reg-NormMasked.nii.gz",
            ):
                (parcel_dir / name).write_text(name, encoding="utf-8")
            for name in (
                "100307_predicted_wm_lh.stl",
                "100307_predicted_wm_rh.stl",
                "100307_predicted_pial_lh.stl",
                "100307_predicted_pial_rh.stl",
            ):
                (surface_dir / name).write_text(name, encoding="utf-8")
            (csd_dir / "csd_act_qc.json").write_text('{"status": "completed"}\n', encoding="utf-8")
            (csd_dir / "csd_act_manifest.json").write_text("{}\n", encoding="utf-8")
            (tract_dir / "100307_csd_act_ifod2.tck").write_text("tck", encoding="utf-8")
            (tract_dir / "100307_csd_act_ifod2.trk").write_text("trk", encoding="utf-8")
            (wmql_dir / "wmql_qc.json").write_text('{"status": "completed"}\n', encoding="utf-8")
            (wmql_dir / "wmql_manifest.json").write_text("{}\n", encoding="utf-8")
            (conn_dir / "100307-connectome-streamline_count_qc.json").write_text('{"status": "completed"}\n', encoding="utf-8")
            (conn_dir / "100307-connectome-streamline_count_manifest.json").write_text("{}\n", encoding="utf-8")

            micro_dir = layout.microstructure_dti
            micro_dir.mkdir(parents=True)
            for suffix in ("FA", "MD", "AD", "RD", "L1", "L2", "L3", "Trace"):
                (micro_dir / f"100307_dti_{suffix}.nii.gz").write_text(suffix, encoding="utf-8")
            (layout.microstructure / "manifest.json").write_text("{}\n", encoding="utf-8")

            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("segmentation", "parcellation", "surface", "microstructure", "tractography", "bundles", "connectome"),
                    run_name=run_name,
                    execute=True,
                    resume=True,
                )
            )

            self.assertEqual([task.status for task in result.tasks], ["skipped", "skipped", "skipped", "skipped", "skipped", "skipped", "skipped"])
            self.assertTrue(all("completed" in task.reason for task in result.tasks))

    def test_execute_blocks_missing_dependencies_instead_of_crashing(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            result = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("segmentation", "parcellation", "surface", "microstructure", "tractography", "bundles", "connectome"),
                    execute=True,
                )
            )

            statuses = {task.name: task.status for task in result.tasks}
            self.assertEqual(statuses["segmentation.ddseg"], "blocked")
            self.assertEqual(statuses["parcellation.ddparcel"], "blocked")
            self.assertEqual(statuses["surface.ddsurfer"], "blocked")
            self.assertEqual(statuses["microstructure.dti"], "blocked")
            self.assertEqual(statuses["tractography.csd_act"], "blocked")
            self.assertEqual(statuses["bundles.wmql"], "blocked")
            self.assertEqual(statuses["connectome.streamline_count"], "blocked")

    def test_execute_saf_auto_discovers_completed_ddsurfer_postprocess_outputs(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "877168"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            layout = subject_layout(subject_root)
            csd_dir = layout.csd
            csd_dir.mkdir(parents=True)
            (csd_dir / "877168_wmfod_norm.mif").write_text("fod", encoding="utf-8")

            micro_dir = layout.microstructure_dti
            micro_dir.mkdir(parents=True)
            (micro_dir / "877168_dti_FA.nii.gz").write_text("fa", encoding="utf-8")

            post_dir = layout.ddsurfer_postprocess
            (post_dir / "mri").mkdir(parents=True)
            (post_dir / "surf").mkdir()
            (post_dir / "label").mkdir()
            (layout.ddsurfer_postprocess_stats / "stats").mkdir(parents=True)
            for name in ("brain.mgz",):
                (post_dir / "mri" / name).write_text(name, encoding="utf-8")
            for name in (
                "lh.white",
                "rh.white",
                "lh.pial",
                "rh.pial",
                "lh.inflated",
                "rh.inflated",
                "lh.sphere",
                "rh.sphere",
                "lh.curv",
                "rh.curv",
            ):
                (post_dir / "surf" / name).write_text(name, encoding="utf-8")
            (post_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
            (post_dir / "qc.json").write_text('{"status":"completed"}\n', encoding="utf-8")

            captured: dict[str, Path] = {}

            class _FakeResult:
                def __init__(self, output_dir: Path) -> None:
                    self.qc_path = output_dir / "saf_qc.json"
                    self.manifest_path = output_dir / "saf_manifest.json"
                    self.saf_tractogram = output_dir / "SAF.tck"
                    self.saf_vtk_path = None
                    self.streamline_count = None
                    self.qc_path.parent.mkdir(parents=True, exist_ok=True)
                    self.qc_path.write_text('{"status":"completed"}\n', encoding="utf-8")
                    self.manifest_path.write_text("{}\n", encoding="utf-8")
                    self.saf_tractogram.write_text("tck", encoding="utf-8")

            def _fake_run_saf(config, *, log=None):
                captured["fs_dir"] = config.fs_dir
                return _FakeResult(config.output_dir)

            with mock.patch("tractography.run_saf", side_effect=_fake_run_saf):
                result = run_subject_products(
                    ProductOrchestratorConfig(
                        subject_id="877168",
                        subject_root=subject_root,
                        targets=("saf",),
                        execute=True,
                    )
                )

            self.assertEqual(result.tasks[0].name, "tractography.saf")
            self.assertEqual(result.tasks[0].status, "completed")
            self.assertEqual(captured["fs_dir"], post_dir)


if __name__ == "__main__":
    unittest.main()
