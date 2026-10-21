"""Opt-in real managed PNL mask check; never writes into the source subject."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.brain_mask import BrainMaskConfig, generate_brain_mask
from shared.managed_runtimes import provision, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--subject-input", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    args.report.mkdir(parents=True, exist_ok=True)
    record = provision(("pnl_cnn",), root=args.runtime_root, accept_pnl_terms=True)
    write_json(args.report / "verified-runtime.json", record)
    config = BrainMaskConfig(**{name: Path(value) for name, value in record["external_dependencies"].items()})
    inputs = args.subject_input.resolve()
    mask = (args.report / "generated-mask.nii.gz").resolve()
    if mask.is_relative_to(inputs):
        raise ValueError("Acceptance output must not be inside source inputs")
    result = generate_brain_mask(inputs / "data.nii.gz", inputs / "bvals", inputs / "bvecs", mask,
                                config=config, force=True, log=lambda line: print(line, flush=True))
    write_json(args.report / "acceptance.json", result)
    print(json.dumps({"status": result["status"], "qc": result["qc"],
                      "seconds": result["runtime_seconds"], "device": result["device_execution"]}), flush=True)


if __name__ == "__main__":
    main()
