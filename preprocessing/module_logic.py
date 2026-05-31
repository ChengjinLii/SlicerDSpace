"""Slicer logic glue for optional DWI preprocessing."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from preprocessing.pipeline import DwiPreprocessingConfig, DwiPreprocessingResult, run_dwi_preprocessing


class PreprocessingLogicMixin:
    """Expose optional DWI preprocessing to the unified Slicer module."""

    def runDwiPreprocessingPipeline(
        self,
        *,
        subject_id: str,
        input_root: Path,
        output_dir: Optional[Path] = None,
        backend: str = "dipy",
        execute: bool = True,
        skip: bool = False,
        force: bool = False,
        mrtrix_bin_dir: Optional[Path] = None,
        fsl_bin_dir: Optional[Path] = None,
        reverse_phase_b0: Optional[Path] = None,
        phase_encoding_direction: Optional[str] = None,
        readout_time: Optional[float] = None,
    ) -> DwiPreprocessingResult:
        config = DwiPreprocessingConfig(
            subject_id=subject_id,
            input_root=input_root,
            output_dir=output_dir,
            backend=backend,
            execute=execute,
            skip=skip,
            force=force,
            mrtrix_bin_dir=mrtrix_bin_dir,
            fsl_bin_dir=fsl_bin_dir,
            reverse_phase_b0=reverse_phase_b0,
            phase_encoding_direction=phase_encoding_direction,
            readout_time=readout_time,
        )
        result = run_dwi_preprocessing(config, log=self.log)
        self.log(f"[Preproc] {result.status}: {result.output_dir}")
        self.log(f"[Preproc] Manifest: {result.manifest_path}")
        self.log(f"[Preproc] QC: {result.qc_path}")
        if result.final_dwi_path.is_file():
            self._load_scalar_volume_node(result.final_dwi_path, f"{subject_id}_dwi_preprocessed")
        return result
