"""GUI and CLI share the same manifest-configured surface pipeline."""
from dataclasses import dataclass
from pathlib import Path
from shared.environment import resolve_auto_torch_device


@dataclass
class PipelineResult:
    generated_models: list[Path]


class SurfaceLogicMixin:
    def _validate_resources(self):
        from .pipeline import SurfaceConfig, inspect_surface_resources
        resources = inspect_surface_resources(SurfaceConfig('', Path('.'), Path('.'),
            template_dir=self.template_dir, checkpoint_root=self.checkpoint_root,
            registration_atlas=self.registration_atlas))
        if not resources['available']:
            raise FileNotFoundError('DDSurfer resources invalid: ' + ', '.join(resources['missing']))

    def process(self, parameters, logCallback=None):
        from .pipeline import SurfaceConfig, run_surface
        if logCallback is not None:
            self.logCallback = logCallback
        self.setupPythonRequirements()
        subject = parameters.subjectId.strip()
        input_root = Path(parameters.inputDirectory).expanduser().resolve()
        inspected = self._resolve_subject_input(input_root, subject)
        override = Path(parameters.outputDirectory).expanduser().resolve() if parameters.outputDirectory.strip() else None
        output = self._resolve_optional_output_dir(override,
            subject_root=Path(inspected['subject_root']) if inspected['subject_root'] is not None else None,
            task_name='ddsurfer')
        result = run_surface(SurfaceConfig(subject, input_root, output,
            predict_mode=parameters.predictMode, device=resolve_auto_torch_device(parameters.device or 'auto'),
            template_dir=self.template_dir, checkpoint_root=self.checkpoint_root,
            registration_atlas=self.registration_atlas, execute=True,
            cleanup_intermediates=bool(parameters.cleanupIntermediates)), log=self.log)
        return PipelineResult(list(result.generated_models))
