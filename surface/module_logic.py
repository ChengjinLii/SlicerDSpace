"""Surface workflow logic glue for SlicerDDSurfer."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from shared import ensure_registered_dti_bundle, find_subject_root
from shared.environment import resolve_auto_torch_device


@dataclass
class PipelineResult:
    generated_models: list[Path]


class SurfaceLogicMixin:
    """Logic entrypoints for the main DDSurfer surface workflow."""

    METRIC_PATTERNS = {
        "FractionalAnisotropy": "{subject_id}-dti-FractionalAnisotropy-Reg.nii.gz",
        "MinEigenvalue": "{subject_id}-dti-MinEigenvalue-Reg.nii.gz",
        "MidEigenvalue": "{subject_id}-dti-MidEigenvalue-Reg.nii.gz",
        "MaxEigenvalue": "{subject_id}-dti-MaxEigenvalue-Reg.nii.gz",
        "Trace": "{subject_id}-dti-Trace-Reg.nii.gz",
        "MeanDiffusivity": "{subject_id}-dti-MeanDiffusivity-Reg.nii.gz",
    }

    def _validate_resources(self) -> None:
        if not self.template_volume.exists():
            raise FileNotFoundError(
                f"Template volume missing: {self.template_volume}\n"
                "Set DDSURFER_TEMPLATE_DIR to a directory containing 100307-FA.nii.gz "
                "or place the template under Resources/Data/template."
            )
        if not self.registration_atlas.exists():
            raise FileNotFoundError(
                f"Registration atlas missing: {self.registration_atlas}\n"
                "Expected Resources/Data/100HCP-population-mean-T2.nii.gz for raw-input registration."
            )
        hcp_dir = self.checkpoint_root / "hcp"
        expected = [
            hcp_dir / "DDCSR_white_lh_Full_DualStream_no_b0_Cascaded.pt",
            hcp_dir / "DDCSR_white_rh_Full_DualStream_no_b0_Cascaded.pt",
            hcp_dir / "DDCSR_pial_lh_Full_DualStream_no_b0_Cascaded.pt",
            hcp_dir / "DDCSR_pial_rh_Full_DualStream_no_b0_Cascaded.pt",
        ]
        missing = [path for path in expected if not path.exists()]
        if missing:
            missing_list = "\n".join(str(path) for path in missing)
            raise FileNotFoundError(
                "Missing SlicerDDSurfer checkpoints:\n"
                f"{missing_list}\n"
                "Set DDSURFER_CHECKPOINT_DIR or place checkpoints under Resources/Data/ckpts/hcp."
            )

    def process(self, parameters: Any, logCallback=None) -> PipelineResult:
        if logCallback is not None:
            self.logCallback = logCallback

        self._validate_resources()
        resolved_device = resolve_auto_torch_device(parameters.device or "auto")
        self.log(f"Using torch device: {resolved_device} (requested: {parameters.device or 'auto'})")
        self.log("Checking Python dependencies...")
        try:
            self.setupPythonRequirements()
        except Exception as exc:
            raise RuntimeError("Dependency installation failed. Please check network or PyTorch extension.") from exc
        subject_id = parameters.subjectId.strip()
        if not subject_id:
            raise ValueError("Subject identifier must be provided.")

        input_root = Path(parameters.inputDirectory).expanduser().resolve()
        if not input_root.is_dir():
            raise FileNotFoundError(f"Input directory not found: {input_root}")

        inspected = self._resolve_subject_input(input_root, subject_id)
        subject_root = Path(inspected["subject_root"]) if inspected["subject_root"] is not None else None
        subject_dir = Path(inspected["subject_dir"]).resolve()

        output_override = (
            Path(parameters.outputDirectory).expanduser().resolve()
            if parameters.outputDirectory.strip()
            else None
        )
        output_base = self._resolve_optional_output_dir(
            output_override,
            subject_root=subject_root,
            task_name="ddsurfer",
        )

        preprocessed_root = output_base / "preprocessed"
        predictions_root = output_base / "pred_results_SlicerDDSurfer"
        work_root = output_base
        (output_base / "raw").mkdir(parents=True, exist_ok=True)
        preprocessed_root.mkdir(parents=True, exist_ok=True)
        predictions_root.mkdir(parents=True, exist_ok=True)

        self.log(f"Subject: {subject_id}")
        if subject_root is not None:
            self.log(f"Subject root: {subject_root}")
        self.log(f"Input directory: {subject_dir}")
        self.log(f"Working root: {work_root}")
        self.log(f"Preprocessed root: {preprocessed_root}")
        self.log(f"Predictions root: {predictions_root}")

        if inspected["mode"] == "subject_root":
            raw_bundle = find_subject_root(input_root, subject_id)
            registered_bundle = ensure_registered_dti_bundle(
                raw_bundle,
                atlas_t2=self.registration_atlas,
                fit_method="wls",
                reuse=True,
                log=self.log,
            )
            subject_dir = registered_bundle.bundle_dir
            metric_paths = {
                "FractionalAnisotropy": registered_bundle.fa_reg_path,
                "MinEigenvalue": registered_bundle.min_eig_reg_path,
                "MidEigenvalue": registered_bundle.mid_eig_reg_path,
                "MaxEigenvalue": registered_bundle.max_eig_reg_path,
                "Trace": registered_bundle.trace_reg_path,
                "MeanDiffusivity": registered_bundle.mean_diffusivity_reg_path,
            }
            mask_path = registered_bundle.mask_reg_path
            transform_path = registered_bundle.transform_path
        else:
            def resolve_default(filename: str) -> Path:
                expanded = filename.replace("{subject_id}", subject_id)
                return subject_dir / expanded

            metric_paths = {
                metric: resolve_default(filename)
                for metric, filename in self.METRIC_PATTERNS.items()
            }
            mask_path = resolve_default("{subject_id}-mask-Reg.nii.gz")
            transform_path = resolve_default("{subject_id}-b0ToAtlasT2.tfm")

            missing_inputs = [
                path
                for path in list(metric_paths.values()) + [mask_path, transform_path]
                if not path.exists()
            ]
            if missing_inputs:
                missing_list = "\n".join(str(path) for path in missing_inputs)
                raise FileNotFoundError(f"Required input files missing:\n{missing_list}")

        for metric, path in metric_paths.items():
            self.log(f"{metric} volume: {path}")
        self.log(f"Brain mask: {mask_path}")
        self.log(f"Transform: {transform_path}")

        modules = self._load_pipeline_modules()
        preprocessing = modules["preprocessing"]
        prediction_module = modules["prediction"]
        postprocessing_module = modules["postprocessing"]

        SubjectPreprocessingConfig = preprocessing.SubjectPreprocessingConfig
        SubjectPreprocessingResult = preprocessing.SubjectPreprocessingResult
        preprocess_subject = preprocessing.preprocess_subject

        PredictionStageConfig = prediction_module.PredictionStageConfig
        predict_subject = prediction_module.predict_subject

        PostprocessingConfig = postprocessing_module.PostprocessingConfig
        convert_meshes_to_native_space = postprocessing_module.convert_meshes_to_native_space

        preprocess_config = SubjectPreprocessingConfig(
            subject_id=subject_id,
            metric_paths=metric_paths,
            mask_path=mask_path,
            transform_path=transform_path,
            work_dir=work_root,
            template_volume_path=self.template_volume,
        )
        try:
            preprocess_result: SubjectPreprocessingResult = preprocess_subject(preprocess_config)
        except Exception as exc:  # pragma: no cover - runtime safeguard
            raise RuntimeError(
                "Preprocessing failed. Verify NIfTI/mask/template validity and that nibabel/SimpleITK/numpy are installed."
            ) from exc
        self.log(f"Preprocessed volumes stored in {preprocess_result.preprocessed_dir}")

        prediction_results: list[Any] = []
        for hemisphere in ("left", "right"):
            cfg = PredictionStageConfig(
                subject_id=subject_id,
                hemisphere=hemisphere,
                predict_mode=parameters.predictMode,
            device=resolved_device,
                step_size=0.02,
                n_svf=2,
                n_res=3,
                template_dir=self.template_dir,
                checkpoint_root=self.checkpoint_root,
                input_root=preprocess_result.preprocessed_dir.parent,
                output_root=predictions_root,
            )
            self.log(f"Running prediction for {hemisphere} hemisphere...")
            try:
                prediction_results.append(predict_subject(cfg))
            except Exception as exc:  # pragma: no cover
                raise RuntimeError(
                    "Prediction failed. Ensure PyTorch/trimesh dependencies are installed and device parameters are valid."
                ) from exc

        post_config = PostprocessingConfig(
            subject_id=subject_id,
            transform_path=preprocess_result.transform_copy_path,
            predictions_root=predictions_root,
        )
        self.log("Converting meshes to subject-native space...")
        try:
            native_outputs = convert_meshes_to_native_space(post_config, prediction_results)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Postprocessing failed. Ensure SimpleITK/trimesh dependencies exist and transform/predicted meshes are valid."
            ) from exc

        ras_models: list[Path] = []
        for surface, paths in native_outputs.items():
            for path in paths:
                if path.name.endswith("_orig.stl"):
                    continue
                ras_models.append(path)
                self.log(f"Generated {surface} STL: {path}")
                self._load_model_node(path, surface, subject_id)

        if parameters.cleanupIntermediates:
            self._cleanup_intermediates(work_root, keep_native=True, log=self.log)

        return PipelineResult(generated_models=ras_models)

    def runLocalPostprocess(
        self,
        *,
        subject_id: str,
        native_dir: Path,
        mri_dir: Path,
        repo_path: Optional[Path],
        mode: str,
        force: bool,
        log_callback=None,
    ) -> None:
        if not subject_id:
            raise ValueError("Subject ID must be provided for DDSurfer postprocess.")
        if not native_dir.is_dir():
            raise FileNotFoundError(f"Native output directory not found: {native_dir}")
        if not mri_dir.is_dir():
            raise FileNotFoundError(f"MRI directory not found: {mri_dir}")
        if repo_path is not None and not repo_path.is_dir():
            raise FileNotFoundError(f"DDSurfer postprocess backend directory not found: {repo_path}")

        from surface import DDSurferPostprocessConfig, run_ddsurfer_postprocess

        output_root = native_dir
        for parent in native_dir.parents:
            if parent.name == "outputs" and parent.parent.exists():
                output_root = parent
                break

        run_ddsurfer_postprocess(
            DDSurferPostprocessConfig(
                subject_id=subject_id,
                subject_root=output_root.parent if output_root.name == "outputs" else None,
                native_dir=native_dir,
                mri_dir=mri_dir,
                output_root=output_root,
                backend_root=repo_path,
                mode=mode,
                python_bin=Path(sys.executable),
                force=force,
            ),
            log=log_callback,
        )

    def _cleanup_intermediates(self, work_root: Path, keep_native: bool, log) -> None:
        for folder in ("_exports", "raw", "preprocessed"):
            path = work_root / folder
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                log(f"Removed intermediate directory {path}")

        predictions_dir = work_root / "predictions"
        if not predictions_dir.exists():
            return

        if keep_native:
            for child in predictions_dir.iterdir():
                if child.name == "native":
                    continue
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                    log(f"Removed intermediate directory {child}")
                else:
                    child.unlink(missing_ok=True)
                    log(f"Removed intermediate file {child}")
        else:
            shutil.rmtree(predictions_dir, ignore_errors=True)
            log(f"Removed predictions directory {predictions_dir}")
