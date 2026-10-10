#!/usr/bin/env python3
"""Compatibility entry point for anatomy.surface.postprocess_docker."""

from __future__ import annotations

import sys

from anatomy.surface.postprocess_docker import (
    REQUIRED_MRI_FILES,
    copy_file,
    main,
    parse_args,
    run_docker,
    run_postprocess,
    stage_subject_inputs,
)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
