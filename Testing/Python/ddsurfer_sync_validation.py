"""Exercise the surface adapter with real inputs without modifying a Slicer scene."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from anatomy.surface.pipeline import SurfaceConfig, run_surface


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--slicer-home', type=Path, required=True)
    parser.add_argument('--python-bin', type=Path)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--auto-mask', action='store_true')
    parser.add_argument('--registered', action='store_true', help='Use existing registered DTI channels.')
    parser.add_argument('--freesurfer-home', type=Path)
    args = parser.parse_args()
    bundle = SimpleNamespace(dwi_path=args.input / 'dwi.nii.gz',
                             bval_path=args.input / 'dwi.bval', bvec_path=args.input / 'dwi.bvec',
                             mask_path=None if args.auto_mask else args.input / 'mask.nii.gz')
    result = run_surface(SurfaceConfig(args.subject, args.input, args.output,
        input_bundle=None if args.registered else bundle, model_assets_dir=args.assets, slicer_home=args.slicer_home,
        python_bin=args.python_bin, device=args.device, execute=True, resume=args.resume,
        auto_mask=args.auto_mask, freesurfer_home=args.freesurfer_home), log=print)
    print(result.manifest_path)
    qc = json.loads(result.qc_path.read_text())
    if not qc.get('automatic_qc_passed'):
        raise RuntimeError('Automatic surface geometry QC failed')


if __name__ == '__main__':
    main()
