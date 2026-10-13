#!/usr/bin/env python3
"""Re-filter a real, archived initial tractogram into a NEW SAF directory."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    from tractography.saf import SAFConfig, run_saf

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-manifest', type=Path, required=True)
    parser.add_argument('--pregenerated', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--mrtrix-bin-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('Use a new output directory; existing scientific products are not overwritten')
    original = json.loads(args.source_manifest.read_text(encoding='utf-8'))
    parameters = original['parameters']
    inputs = original['inputs']
    result = run_saf(SAFConfig(
        subject_id=original['subject_id'], input_root=Path(inputs['subject_root']),
        fs_dir=Path(inputs['fs_dir']['path']), fod_path=Path(inputs['fod']['path']),
        output_dir=args.output_dir, pregenerated_tractogram=args.pregenerated,
        mrtrix_bin_dir=args.mrtrix_bin_dir,
        maxlen=parameters.get('maxlen', 40.),
        notrunc=parameters.get('notrunc', False), fast_intersection=parameters.get('fast_intersection', True),
        gwg_hard=parameters.get('gwg_hard', False), pialfilter=parameters.get('pialfilter', False),
        execute=True, diagnostics=True, force_recompute=True,
    ), log=print)
    print(json.dumps({'output_dir': str(result.output_dir), 'streamline_count': result.streamline_count}))


if __name__ == '__main__':
    main()
