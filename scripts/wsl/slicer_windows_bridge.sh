#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: slicer_windows_bridge.sh WINDOWS_SLICER_EXE [Slicer arguments ...]" >&2
  exit 2
fi

windows_slicer=$1
shift
linux_slicer=$(wslpath -a -u "$windows_slicer")

converted=()
for argument in "$@"; do
  if [[ "$argument" == /* ]]; then
    converted+=("$(wslpath -a -w "$argument")")
  else
    converted+=("$argument")
  fi
done

exec "$linux_slicer" "${converted[@]}"
