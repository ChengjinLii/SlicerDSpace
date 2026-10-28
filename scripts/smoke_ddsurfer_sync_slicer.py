"""Run with Slicer --python-script; verify module resources and surface loading."""
import json
import os
from pathlib import Path
import traceback

import numpy as np
import slicer


def main():
    from anatomy.surface.pipeline import SurfaceConfig, inspect_surface_resources
    from shared.module_logic import SharedLogicMixin
    import trimesh
    root = Path(os.environ['DDSURFER_SYNC_VALIDATION_ROOT'])
    assets = Path(os.environ['SLICERDSPACE_MODEL_ASSETS_DIR'])
    resources = inspect_surface_resources(SurfaceConfig('100307', root, root, model_assets_dir=assets))
    if not resources['available']:
        raise ValueError(resources['missing'])
    native = root / 'raw/pred_results_SlicerDSpace/native/100307'
    bounds = {}
    logic = SharedLogicMixin()
    for hemi in ('lh', 'rh'):
        for kind, token in (('white', 'wm'), ('pial', 'pial')):
            master = trimesh.load(str(native / f'{hemi}.{kind}.obj'), process=False)
            for suffix in ('.stl', '_orig.stl'):
                path = native / f'100307_predicted_{token}_{hemi}{suffix}'
                before = set(n.GetID() for n in slicer.util.getNodesByClass('vtkMRMLModelNode'))
                if not logic._load_model_node(path, kind, '100307'):
                    raise ValueError(f'Slicer failed to load {path}')
                node = next(n for n in slicer.util.getNodesByClass('vtkMRMLModelNode') if n.GetID() not in before)
                actual = np.asarray(node.GetPolyData().GetBounds()).reshape(3, 2).T
                error = float(np.max(np.abs(actual - master.bounds)))
                if error > 0.001:
                    raise ValueError(f'RAS/LPS loading error: {path}: {error} mm')
                bounds[path.name] = dict(max_bounds_error_mm=error, points=node.GetPolyData().GetNumberOfPoints())
    report = dict(passed=True, upstream_commit=resources['upstream_commit'], module_available=bool(slicer.modules.slicerdspace), loaded=bounds)
    (root / 'slicer_scene_smoke.json').write_text(json.dumps(report, indent=2) + '\n')


try:
    main()
except Exception:
    traceback.print_exc()
    slicer.app.exit(1)
else:
    slicer.app.exit(0)
