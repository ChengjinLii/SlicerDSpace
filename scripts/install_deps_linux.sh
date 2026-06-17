#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${PYTHON_BIN:-}" && -n "${SLICER_EXECUTABLE:-}" ]]; then
  SLICER_DIR="$(cd "$(dirname "${SLICER_EXECUTABLE}")" && pwd)"
  if [[ -x "${SLICER_DIR}/PythonSlicer" ]]; then
    PYTHON_BIN="${SLICER_DIR}/PythonSlicer"
  fi
fi
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" "$SCRIPT_DIR/install_dependencies.py" --all --platform Linux "$@"
