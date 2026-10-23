#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${PYTHON_BIN:-}" && -n "${SLICER_EXECUTABLE:-}" ]]; then
  SLICER_DIR="$(cd "$(dirname "${SLICER_EXECUTABLE}")" && pwd)"
  for candidate in "${SLICER_DIR}/../bin/PythonSlicer" "${SLICER_DIR}/PythonSlicer"; do
    if [[ -x "$candidate" ]]; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" "$SCRIPT_DIR/install_dependencies.py" --all --platform Darwin "$@"
