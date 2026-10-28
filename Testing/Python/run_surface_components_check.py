"""Fresh real-subject adapter run; explicit local inputs, no dataset downloads."""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    from anatomy.surface.postprocess_release import DDSurferPostprocessConfig, run_ddsurfer_postprocess
    from anatomy.surface.backend_bridge import BACKEND_ROOT, run_backend, sha256
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--license-file', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    config = DDSurferPostprocessConfig('100307', args.output / 'outputs', subject_root=args.output,
        native_dir=args.native, mode='left', runtime=args.runtime, license_file=args.license_file,
        sphere_seed=1234, python_bin=args.python)
    started = time.monotonic()
    result = run_ddsurfer_postprocess(config, log=lambda line: print(line, flush=True))
    elapsed = time.monotonic() - started
    manifest = json.loads(result.manifest_path.read_text())
    qc = json.loads(result.qc_path.read_text())
    command = manifest['command']
    subject = Path(command[command.index('--output-root') + 1]) / '100307'
    comparison_file = args.output / 'comparison.json'
    run_backend(['-m', 'postprocessing.core.compare', '--reference', args.reference,
                 '--candidate', subject, '--hemi', 'left', '--output', comparison_file],
                python_bin=args.python, log=lambda line: print(line, flush=True))
    comparison = json.loads(comparison_file.read_text())
    record = dict(status='passed' if comparison['all_payloads_equal'] and qc['automatic_qc_passed'] else 'failed',
        subject='100307', hemisphere='left', backend='native', adapter_seconds=elapsed,
        checked_files=len(comparison['records']), all_payloads_equal=comparison['all_payloads_equal'],
        automatic_qc_passed=qc['automatic_qc_passed'], human_review='pending',
        sphere_seed=1234, upstream_commit=manifest['upstream_commit'],
        runtime_record_sha256=sha256(args.runtime / 'runtime.json'),
        comparison_sha256=sha256(comparison_file),
        adapter_sha256=sha256(ROOT / 'anatomy/surface/postprocess_release.py'),
        backend_pipeline_sha256=sha256(BACKEND_ROOT / 'postprocessing/pipeline.py'),
        scope='Fresh SlicerDSpace adapter execution against an existing full-FreeSurfer reference; no speedup or population-wide accuracy claim')
    (args.output / 'acceptance.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    return int(record['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
