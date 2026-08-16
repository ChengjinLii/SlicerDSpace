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
    def test_reusing_run_name_archives_previous_manifest_and_plan(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            run_name = "repeatable-run"
            first = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("microstructure",),
                    run_name=run_name,
                    execute=False,
                )
            )
            first_manifest = json.loads(first.run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(first_manifest["targets"], ["microstructure"])
            self.assertEqual(first_manifest["previous_run_records"], {})

            second = run_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("surface_postprocess",),
                    run_name=run_name,
                    execute=False,
                )
            )
            second_manifest = json.loads(second.run_manifest_path.read_text(encoding="utf-8"))
            archived = second_manifest["previous_run_records"]

            self.assertEqual(second_manifest["targets"], ["surface_postprocess"])
            self.assertEqual(set(archived), {"orchestration_manifest", "run_plan"})
            for path in archived.values():
                self.assertTrue(Path(path).is_file())
            archived_manifest = json.loads(Path(archived["orchestration_manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(archived_manifest["targets"], ["microstructure"])

    def test_unhandled_stage_error_writes_failed_orchestration_manifest(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            config = ProductOrchestratorConfig(
                subject_id="100307",
                subject_root=subject_root,
                targets=("surface",),
                run_name="failure-checkpoint",
                execute=True,
            )
            with mock.patch(
                "shared.orchestrator._run_subject_products_impl",
                side_effect=RuntimeError("synthetic stage failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "synthetic stage failure"):
                    run_subject_products(config)

            manifest_path = (
                subject_root
                / "outputs"
                / "00_run_metadata"
                / "failure-checkpoint_orchestration_manifest.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["failure"]["type"], "RuntimeError")
            self.assertEqual(manifest["failure"]["message"], "synthetic stage failure")

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

    def test_rejects_invalid_microstructure_free_water_chunk_size(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "microstructure_free_water_chunk_size"):
                run_subject_products(
                    ProductOrchestratorConfig(
                        subject_id="100307",
                        subject_root=subject_root,
                        targets=("microstructure",),
                        execute=False,
                        microstructure_free_water_chunk_size=0,
                    )
                )

            with self.assertRaisesRegex(ValueError, "microstructure_free_water_engine"):
                run_subject_products(
                    ProductOrchestratorConfig(
                        subject_id="100307",
                        subject_root=subject_root,
                        targets=("microstructure",),
                        execute=False,
                        microstructure_free_water_engine="invalid",
                    )
                )

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
            atlas_t2 = Path(tmp) / "atlas_t2.nii.gz"
            atlas_t2.write_text("atlas", encoding="utf-8")

            plan = plan_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("segmentation", "parcellation", "tractography", "bundles", "connectome"),
                    execute=True,
                    atlas_t2=atlas_t2,
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

    def test_task_from_result_preserves_generated_path_outputs(self) -> None:
        from shared import orchestrator

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            class _BackendResult:
                def __init__(self) -> None:
                    self.output_dir = root / "bundles"
                    self.matrix_path = root / "connectome.csv"
                    self.manifest_path = root / "manifest.json"
                    self.qc_path = root / "qc.json"
                    self.command = ("tool", "--flag")
                    self.executed = True
                    self.backend_status = {"available": True}

            task = orchestrator._task_from_result("connectome.streamline_count", _BackendResult())

            self.assertEqual(
                task.outputs,
                {
                    "output_dir": (root / "bundles").as_posix(),
                    "matrix_path": (root / "connectome.csv").as_posix(),
                    "manifest_path": (root / "manifest.json").as_posix(),
                    "qc_path": (root / "qc.json").as_posix(),
                },
            )
            self.assertNotIn("command", task.outputs)
            self.assertGreater(len(task.outputs), 0)

    def test_output_tree_semantics_marks_unselected_directories(self) -> None:
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

            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            audit = json.loads(Path(manifest["output_tree_audit_path"]).read_text(encoding="utf-8"))
            semantics = json.loads(Path(manifest["output_tree_semantics_path"]).read_text(encoding="utf-8"))
            self.assertNotIn("04_tractography", audit["expected_top_dirs"])
            by_path = {entry["path"]: entry for entry in semantics["entries"]}
            self.assertEqual(by_path["04_tractography"]["state"], "not_selected_absent")
            self.assertTrue(by_path["02_microstructure"]["selected"])

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
            profile = manifest["performance_profile"]
            self.assertEqual(profile["schema"], "slicerddsurfer.performance_profile.v1")
            self.assertTrue(Path(manifest["performance_profile_path"]).is_file())
            self.assertIn("slowest_tasks", profile)
            self.assertIn("largest_top_dirs", profile)
            self.assertTrue(any(row["path"] == "00_run_metadata" for row in profile["top_dirs"]))
            report_paths = manifest["report_paths"]
            output_tree_report_paths = manifest["output_tree_report_paths"]
            report_html = Path(report_paths["report_html"])
            output_tree_html = Path(output_tree_report_paths["report_html_latest"])
            qc_summary = json.loads(Path(report_paths["qc_summary_json"]).read_text(encoding="utf-8"))
            self.assertIn("Performance Profile", report_html.read_text(encoding="utf-8"))
            self.assertTrue(output_tree_html.is_file())
            self.assertIn("Annotated output tree", report_html.read_text(encoding="utf-8"))
            self.assertEqual(qc_summary["performance_profile"]["schema"], "slicerddsurfer.performance_profile.v1")
            self.assertIn("00_run_metadata", qc_summary["output_tree"]["top_dirs"])

    def test_dry_run_does_not_probe_auto_torch_devices(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            with mock.patch(
                "shared.orchestrator.resolve_auto_torch_device",
                side_effect=AssertionError("dry-run must not probe torch devices"),
            ):
                result = run_subject_products(
                    ProductOrchestratorConfig(
                        subject_id="100307",
                        subject_root=subject_root,
                        targets=("segmentation", "surface", "tractcloud"),
                        ddseg_device="auto",
                        surface_device="auto",
                        tractcloud_device="auto",
                        execute=False,
                    )
                )

            manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["resolved_ddseg_device"], "not_resolved_execute_false")
            self.assertEqual(manifest["resolved_surface_device"], "not_resolved_execute_false")
            self.assertEqual(manifest["resolved_tractcloud_device"], "not_resolved_execute_false")

    def test_dry_run_supports_dti_tractography_backend(self) -> None:
        from shared import ProductOrchestratorConfig, run_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")
            existing_tractogram = (
                subject_root
                / "outputs"
                / "04_tractography"
                / "tractograms"
                / "dti_det"
                / "windows_full"
                / "existing.trk"
            )
            existing_tractogram.parent.mkdir(parents=True)
            existing_tractogram.write_text("existing", encoding="utf-8")

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
            self.assertTrue(existing_tractogram.is_file())

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

    def test_wma_plan_consumes_the_selected_csd_tractogram_after_tractography(self) -> None:
        from shared import ProductOrchestratorConfig, plan_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")
            slicer_executable = Path(tmp) / "Slicer"
            slicer_executable.write_text("", encoding="utf-8")
            atlas_dir = Path(tmp) / "ORG-Atlases"
            atlas_dir.mkdir()
            mrtrix_bin = Path(tmp) / "mrtrix" / "bin"
            mrtrix_bin.mkdir(parents=True)
            (mrtrix_bin / "tckconvert").write_text("", encoding="utf-8")

            plan = plan_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("segmentation", "tractography", "wma"),
                    bundle_backend="wma",
                    execute=True,
                    wma_atlas_dir=atlas_dir,
                    slicer_executable=slicer_executable,
                    mrtrix_bin_dir=mrtrix_bin,
                ),
                write=False,
            )

            items = {item.target: item for item in plan.items}
            self.assertEqual(items["tractography"].status, "will_run")
            self.assertEqual(items["wma"].status, "will_run")
            self.assertEqual(items["wma"].dependencies["input_tractography"], "will_run:tractography")
            self.assertTrue(items["wma"].inputs["input_tractography"].endswith("_csd_act_ifod2.tck"))

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

    def test_saf_plan_only_accepts_current_csd_tractography_as_future_fod(self) -> None:
        from shared import ProductOrchestratorConfig, plan_subject_products, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")
            fs_dir = Path(tmp) / "freesurfer_subject"
            fs_dir.mkdir()

            dti_plan = plan_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("tractography", "saf"),
                    tractography_backend="dti_det",
                    saf_fs_dir=fs_dir,
                    execute=True,
                    resume=False,
                )
            )
            dti_items = {item.target: item for item in dti_plan.items}
            self.assertEqual(dti_items["tractography"].status, "will_run")
            self.assertEqual(dti_items["saf"].status, "blocked")
            self.assertEqual(dti_items["saf"].dependencies["fod"], "missing")

            layout = subject_layout(subject_root)
            layout.ddseg.mkdir(parents=True, exist_ok=True)
            for name in (
                "SegmentationMap_GMWMCSF.nii.gz",
                "ProbabilisticMap_GM.nii.gz",
                "ProbabilisticMap_WM.nii.gz",
                "ProbabilisticMap_CSF.nii.gz",
            ):
                (layout.ddseg / name).write_text(name, encoding="utf-8")

            csd_plan = plan_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("tractography", "saf"),
                    tractography_backend="csd_act",
                    saf_fs_dir=fs_dir,
                    execute=True,
                    resume=False,
                )
            )
            csd_items = {item.target: item for item in csd_plan.items}
            self.assertEqual(csd_items["tractography"].status, "will_run")
            self.assertEqual(csd_items["saf"].status, "will_run")
            self.assertEqual(csd_items["saf"].dependencies["fod"], "will_run:tractography.csd_act")

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

    def test_tractcloud_selected_with_saf_uses_same_run_output(self) -> None:
        from shared import ProductOrchestratorConfig, plan_subject_products, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            layout = subject_layout(subject_root)
            old_saf_dir = layout.saf / "old-run"
            old_saf_dir.mkdir(parents=True)
            (old_saf_dir / "SAF.vtk").write_text("old vtk", encoding="utf-8")

            run_name = "new-run"
            csd_dir = layout.csd / run_name
            csd_dir.mkdir(parents=True)
            (csd_dir / "100307_wmfod_norm.mif").write_text("fod", encoding="utf-8")
            fs_dir = Path(tmp) / "native-dmri-surfaces"
            fs_dir.mkdir()

            plan = plan_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("saf", "tractcloud"),
                    run_name=run_name,
                    saf_fs_dir=fs_dir,
                    execute=True,
                    resume=False,
                )
            )

            items = {item.target: item for item in plan.items}
            self.assertEqual(items["saf"].status, "will_run")
            self.assertEqual(items["tractcloud"].status, "will_run")
            self.assertEqual(
                items["tractcloud"].inputs["input_tractography"],
                items["saf"].outputs["tractogram_vtk"],
            )
            self.assertEqual(items["tractcloud"].dependencies["input_tractography"], "will_run:saf")
            self.assertNotEqual(
                items["tractcloud"].inputs["input_tractography"],
                (old_saf_dir / "SAF.vtk").resolve(),
            )

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
                return _FakeResult(config.output_dir)

            with mock.patch("tractography.run_saf", side_effect=_fake_run_saf):
                result = run_subject_products(
                    ProductOrchestratorConfig(
                        subject_id="100307",
                        subject_root=subject_root,
                        targets=("saf",),
                        execute=True,
                    )
                )

            self.assertIn("-select 1000000", captured["tckgen_options"])
            self.assertIn("-seed_image", captured["tckgen_options"])
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

    def test_surface_postprocess_plan_requires_native_surfaces_and_wmparc(self) -> None:
        from shared import ProductOrchestratorConfig, plan_subject_products, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")
            config = ProductOrchestratorConfig(
                subject_id="100307",
                subject_root=subject_root,
                targets=("surface_postprocess",),
                execute=True,
                resume=False,
            )

            missing_surface = {item.target: item for item in plan_subject_products(config).items}
            self.assertEqual(missing_surface["surface_postprocess"].status, "blocked")
            self.assertIn("*_orig.stl", missing_surface["surface_postprocess"].reason)

            layout = subject_layout(subject_root)
            native_dir = layout.ddsurfer / "pred_results_SlicerDDSurfer" / "native" / "100307"
            native_dir.mkdir(parents=True)
            for surface in ("wm", "pial"):
                for hemisphere in ("lh", "rh"):
                    (native_dir / f"100307_predicted_{surface}_{hemisphere}_orig.stl").write_text(
                        "surface",
                        encoding="utf-8",
                    )
            layout.ddparcel.mkdir(parents=True)

            missing_wmparc = {item.target: item for item in plan_subject_products(config).items}
            self.assertEqual(missing_wmparc["surface_postprocess"].status, "blocked")
            self.assertIn("wmparc", missing_wmparc["surface_postprocess"].reason)

            (layout.ddparcel / "100307-DDSurfer-wmparc.nii.gz").write_text("labels", encoding="utf-8")
            ready = {item.target: item for item in plan_subject_products(config).items}
            self.assertEqual(ready["surface_postprocess"].status, "will_run")

    def test_surface_postprocess_plan_accepts_selected_upstream_products(self) -> None:
        from shared import ProductOrchestratorConfig, plan_subject_products

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")
            atlas_t2 = Path(tmp) / "atlas.nii.gz"
            atlas_t2.write_text("atlas", encoding="utf-8")

            plan = plan_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    targets=("surface", "parcellation", "surface_postprocess"),
                    atlas_t2=atlas_t2,
                    execute=True,
                    resume=False,
                )
            )
            items = {item.target: item for item in plan.items}

            self.assertEqual(items["surface"].status, "will_run")
            self.assertEqual(items["parcellation"].status, "will_run")
            self.assertEqual(items["surface_postprocess"].status, "will_run")
            self.assertEqual(items["surface_postprocess"].dependencies["surface"], "will_run")
            self.assertEqual(items["surface_postprocess"].dependencies["parcellation"], "will_run")

    def test_surface_postprocess_resume_and_fresh_run_require_all_core_files(self) -> None:
        from shared import ProductOrchestratorConfig, plan_subject_products, run_subject_products, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            layout = subject_layout(subject_root)
            post_dir = layout.ddsurfer_postprocess
            (post_dir / "mri").mkdir(parents=True)
            (post_dir / "surf").mkdir()
            (post_dir / "mri" / "brain.mgz").write_text("brain", encoding="utf-8")
            for hemisphere in ("lh", "rh"):
                for surface in ("white", "pial", "inflated", "sphere", "curv"):
                    (post_dir / "surf" / f"{hemisphere}.{surface}").write_text("surface", encoding="utf-8")
            (post_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
            (post_dir / "qc.json").write_text('{"status":"completed"}\n', encoding="utf-8")

            resume_config = ProductOrchestratorConfig(
                subject_id="100307",
                subject_root=subject_root,
                targets=("surface_postprocess",),
                execute=True,
                resume=True,
            )
            self.assertEqual(plan_subject_products(resume_config).items[0].status, "skipped")

            (post_dir / "surf" / "rh.curv").unlink()
            left_resume_config = ProductOrchestratorConfig(
                subject_id="100307",
                subject_root=subject_root,
                targets=("surface_postprocess",),
                execute=True,
                resume=True,
                postprocess_mode="left",
            )
            self.assertEqual(plan_subject_products(left_resume_config).items[0].status, "skipped")
            self.assertNotEqual(plan_subject_products(resume_config).items[0].status, "skipped")
            (post_dir / "surf" / "rh.curv").write_text("surface", encoding="utf-8")

            (post_dir / "surf" / "lh.curv").unlink()
            self.assertNotEqual(plan_subject_products(resume_config).items[0].status, "skipped")

            native_dir = layout.ddsurfer / "pred_results_SlicerDDSurfer" / "native" / "100307"
            native_dir.mkdir(parents=True)
            for hemisphere in ("lh", "rh"):
                for surface in ("wm", "pial"):
                    (native_dir / f"100307_predicted_{surface}_{hemisphere}_orig.stl").write_text("surface", encoding="utf-8")
            layout.ddparcel.mkdir(parents=True)
            (layout.ddparcel / "100307-DDSurfer-wmparc.nii.gz").write_text("labels", encoding="utf-8")

            class _IncompleteResult:
                def __init__(self) -> None:
                    self.structural_root = post_dir
                    self.stats_root = layout.ddsurfer_postprocess_stats
                    self.staged_input_dir = post_dir / "input"
                    self.manifest_path = post_dir / "manifest.json"
                    self.qc_path = post_dir / "qc.json"

            class _FakePostprocessConfig:
                def __init__(self, **kwargs) -> None:
                    self.__dict__.update(kwargs)

            import surface

            with mock.patch.dict(
                surface.__dict__,
                {
                    "DDSurferPostprocessConfig": _FakePostprocessConfig,
                    "run_ddsurfer_postprocess": mock.Mock(return_value=_IncompleteResult()),
                },
            ):
                fresh_result = run_subject_products(
                    ProductOrchestratorConfig(
                        subject_id="100307",
                        subject_root=subject_root,
                        targets=("surface_postprocess",),
                        execute=True,
                        resume=False,
                    )
                )
            self.assertEqual(fresh_result.tasks[0].status, "failed")
            self.assertIn("required non-empty", fresh_result.tasks[0].reason)

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
            (seg_dir / "ddseg_qc.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "probability_semantics": "four_class_softmax_tissue_channels_v1",
                        "probability_qc": {
                            "finite_and_bounded": True,
                            "tissue_mass_valid_fraction": 1.0,
                            "label_agreement": 1.0,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
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
            wmql_bundle = wmql_dir / "100307_desc-wmql_CST.left.trk"
            wmql_bundle.write_text("bundle", encoding="utf-8")
            (wmql_dir / "wmql_qc.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "output_summary": {"bundle_files": [wmql_bundle.as_posix()]},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (wmql_dir / "wmql_manifest.json").write_text("{}\n", encoding="utf-8")
            (conn_dir / "100307-connectome-streamline_count_qc.json").write_text(
                '{"status": "completed", "node_count": 2, "edge_count": 1}\n', encoding="utf-8"
            )
            (conn_dir / "100307-connectome-streamline_count_manifest.json").write_text("{}\n", encoding="utf-8")
            (conn_dir / "100307-connectome-streamline_count.csv").write_text(
                "source_node,target_node,streamline_count\n10,20,1\n", encoding="utf-8"
            )
            (conn_dir / "100307-connectome-nodes.tsv").write_text(
                "node_id\tlabel\tname\n10\t10\tLeft\n20\t20\tRight\n", encoding="utf-8"
            )

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

    def test_resume_rejects_deleted_wmql_and_connectome_products(self) -> None:
        from shared import ProductOrchestratorConfig, plan_subject_products, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            run_name = "resume_artifacts"
            layout = subject_layout(subject_root)
            layout.ddparcel.mkdir(parents=True)
            (layout.ddparcel / "100307-DDSurfer-wmparc.nii.gz").write_text("parcel", encoding="utf-8")
            tract_dir = layout.tractograms_dti_det / run_name
            tract_dir.mkdir(parents=True)
            (tract_dir / "100307-dti-deterministic.trk").write_text("tractogram", encoding="utf-8")

            wmql_dir = layout.bundles_wmql / run_name
            wmql_dir.mkdir(parents=True)
            bundle = wmql_dir / "100307_desc-wmql_CST.left.trk"
            bundle.write_text("bundle", encoding="utf-8")
            (wmql_dir / "wmql_qc.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "output_summary": {"bundle_files": [bundle.as_posix()]},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            conn_dir = layout.connectome / run_name
            conn_dir.mkdir(parents=True)
            conn_qc = conn_dir / "100307-connectome-streamline_count_qc.json"
            conn_matrix = conn_dir / "100307-connectome-streamline_count.csv"
            conn_nodes = conn_dir / "100307-connectome-nodes.tsv"
            conn_qc.write_text('{"status": "completed", "node_count": 2, "edge_count": 1}\n', encoding="utf-8")
            conn_matrix.write_text("source_node,target_node,streamline_count\n10,20,1\n", encoding="utf-8")
            conn_nodes.write_text("node_id\tlabel\tname\n10\t10\tLeft\n20\t20\tRight\n", encoding="utf-8")

            config = ProductOrchestratorConfig(
                subject_id="100307",
                subject_root=subject_root,
                targets=("bundles", "connectome"),
                run_name=run_name,
                tractography_backend="dti_det",
                execute=True,
                resume=True,
            )
            complete_plan = plan_subject_products(config)
            self.assertEqual({item.target: item.status for item in complete_plan.items}, {"bundles": "skipped", "connectome": "skipped"})

            conn_matrix.write_text("source_node,target_node,streamline_count\n", encoding="utf-8")
            conn_nodes.write_text("node_id\tlabel\tname\n", encoding="utf-8")
            header_only_plan = plan_subject_products(config)
            self.assertEqual({item.target: item.status for item in header_only_plan.items}["connectome"], "will_run")

            conn_nodes.write_text("node_id\tlabel\tname\n10\t10\tLeft\n20\t20\tRight\n", encoding="utf-8")
            bundle.write_text("", encoding="utf-8")
            conn_matrix.write_text("", encoding="utf-8")
            empty_plan = plan_subject_products(config)
            empty_statuses = {item.target: item.status for item in empty_plan.items}
            self.assertEqual(empty_statuses["bundles"], "will_run")
            self.assertEqual(empty_statuses["connectome"], "will_run")

            bundle.write_text("bundle", encoding="utf-8")
            conn_matrix.write_text("source_node,target_node,streamline_count\n10,20,1\n", encoding="utf-8")
            bundle.unlink()
            conn_matrix.unlink()
            incomplete_plan = plan_subject_products(config)
            statuses = {item.target: item.status for item in incomplete_plan.items}
            self.assertEqual(statuses["bundles"], "will_run")
            self.assertEqual(statuses["connectome"], "will_run")

    def test_plan_resume_uses_external_output_root_for_structural_dependencies(self) -> None:
        from shared import ProductOrchestratorConfig, plan_subject_products, subject_layout

        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "100307"
            output_root = Path(tmp) / "external_outputs" / "100307"
            input_dir = subject_root / "input"
            input_dir.mkdir(parents=True)
            for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
                (input_dir / name).write_text("x", encoding="utf-8")

            layout = subject_layout(subject_root, output_root=output_root)
            layout.ddseg.mkdir(parents=True)
            for name in (
                "SegmentationMap_GMWMCSF.nii.gz",
                "ProbabilisticMap_GM.nii.gz",
                "ProbabilisticMap_WM.nii.gz",
                "ProbabilisticMap_CSF.nii.gz",
            ):
                (layout.ddseg / name).write_text(name, encoding="utf-8")
            (layout.ddseg / "ddseg_qc.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "probability_semantics": "four_class_softmax_tissue_channels_v1",
                        "probability_qc": {
                            "finite_and_bounded": True,
                            "tissue_mass_valid_fraction": 1.0,
                            "label_agreement": 1.0,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            layout.ddparcel.mkdir(parents=True)
            for name in (
                "100307-DDSurfer-wmparc.nii.gz",
                "100307-DDSurfer-wmparc-Reg.mgz",
                "100307-dti-FractionalAnisotropy-Reg-NormMasked.nii.gz",
                "100307-dti-Trace-Reg-NormMasked.nii.gz",
                "100307-dti-MinEigenvalue-Reg-NormMasked.nii.gz",
                "100307-dti-MidEigenvalue-Reg-NormMasked.nii.gz",
            ):
                (layout.ddparcel / name).write_text(name, encoding="utf-8")

            surface_dir = layout.ddsurfer / "pred_results_SlicerDDSurfer" / "native" / "100307"
            surface_dir.mkdir(parents=True)
            for name in (
                "100307_predicted_wm_lh.stl",
                "100307_predicted_wm_rh.stl",
                "100307_predicted_pial_lh.stl",
                "100307_predicted_pial_rh.stl",
            ):
                (surface_dir / name).write_text(name, encoding="utf-8")

            plan = plan_subject_products(
                ProductOrchestratorConfig(
                    subject_id="100307",
                    subject_root=subject_root,
                    output_root=output_root,
                    targets=("segmentation", "parcellation", "surface", "tractography", "connectome"),
                    execute=True,
                    resume=True,
                ),
                write=False,
            )

            statuses = {item.target: item.status for item in plan.items}
            reasons = {item.target: item.reason for item in plan.items}
            dependencies = {item.target: item.dependencies for item in plan.items}
            self.assertEqual(statuses["segmentation"], "skipped")
            self.assertEqual(statuses["parcellation"], "skipped")
            self.assertEqual(statuses["surface"], "skipped")
            self.assertEqual(statuses["tractography"], "will_run")
            self.assertEqual(statuses["connectome"], "will_run")
            self.assertEqual(dependencies["tractography"]["segmentation"], "available")
            self.assertEqual(dependencies["connectome"]["parcellation"], "available")
            self.assertEqual(dependencies["connectome"]["tractogram"], "will_run")
            self.assertNotIn("missing DDSeg", reasons["tractography"])
            self.assertNotIn("missing parcellation", reasons["connectome"])
            self.assertEqual(plan.output_root, output_root.resolve())

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
