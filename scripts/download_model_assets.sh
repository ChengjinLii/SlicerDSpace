#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PROFILE="core"
VERIFY=1

usage() {
  cat <<'USAGE'
Download SlicerDDSurfer model weights and template assets through Git LFS.

Usage:
  scripts/download_model_assets.sh [--profile PROFILE] [--no-verify]

Profiles:
  surface       DDSurfer checkpoints, templates, and registration atlas.
  segmentation  DDSeg CNN weights.
  parcellation  DDParcel weights.
  core          surface + segmentation + parcellation assets. Default.
  quick-gate    Alias for core.
  test-fixtures Parcellation conversion test fixtures only.
  all           Every Git LFS object tracked by this repository.

Examples:
  scripts/download_model_assets.sh --profile core
  scripts/download_model_assets.sh --profile segmentation
  scripts/download_model_assets.sh --profile all --no-verify
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile|-p)
      PROFILE="${2:-}"
      shift 2
      ;;
    --no-verify)
      VERIFY=0
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$PROFILE" ]]; then
  echo "--profile requires a value." >&2
  exit 2
fi

cd "$REPO_ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "This script must run inside a Git checkout." >&2
  exit 2
fi
if ! command -v git-lfs >/dev/null 2>&1 && ! git lfs version >/dev/null 2>&1; then
  echo "Git LFS is required. Install Git LFS, then rerun this script." >&2
  exit 2
fi

include_patterns=()
case "$PROFILE" in
  surface)
    include_patterns=(
      "Resources/Data/100HCP-population-mean-T2.nii.gz"
      "Resources/Data/ckpts/hcp/**"
      "Resources/Data/template/**"
      "surface/template/**"
    )
    ;;
  segmentation)
    include_patterns=("segmentation/weights/**")
    ;;
  parcellation)
    include_patterns=("parcellation/weights/**")
    ;;
  core|quick-gate)
    include_patterns=(
      "Resources/Data/100HCP-population-mean-T2.nii.gz"
      "Resources/Data/ckpts/hcp/**"
      "Resources/Data/template/**"
      "surface/template/**"
      "segmentation/weights/**"
      "parcellation/weights/**"
    )
    ;;
  test-fixtures)
    include_patterns=("parcellation/conversion/tests/data/**")
    ;;
  all)
    include_patterns=()
    ;;
  *)
    echo "Unsupported profile: $PROFILE" >&2
    usage >&2
    exit 2
    ;;
esac

git lfs install --local

if [[ "$PROFILE" == "all" ]]; then
  echo "[model-assets] Downloading all Git LFS objects."
  git lfs pull
else
  include_csv="$(IFS=,; echo "${include_patterns[*]}")"
  echo "[model-assets] profile=$PROFILE"
  echo "[model-assets] include=$include_csv"
  git lfs pull --include="$include_csv" --exclude=""
fi

matches_profile() {
  local path="$1"
  case "$PROFILE" in
    surface)
      [[ "$path" == "Resources/Data/100HCP-population-mean-T2.nii.gz" \
        || "$path" == Resources/Data/ckpts/hcp/* \
        || "$path" == Resources/Data/template/* \
        || "$path" == surface/template/* ]]
      ;;
    segmentation)
      [[ "$path" == segmentation/weights/* ]]
      ;;
    parcellation)
      [[ "$path" == parcellation/weights/* ]]
      ;;
    core|quick-gate)
      [[ "$path" == "Resources/Data/100HCP-population-mean-T2.nii.gz" \
        || "$path" == Resources/Data/ckpts/hcp/* \
        || "$path" == Resources/Data/template/* \
        || "$path" == surface/template/* \
        || "$path" == segmentation/weights/* \
        || "$path" == parcellation/weights/* ]]
      ;;
    test-fixtures)
      [[ "$path" == parcellation/conversion/tests/data/* ]]
      ;;
    all)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

if [[ "$VERIFY" == "1" ]]; then
  missing=0
  checked=0
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    if ! matches_profile "$path"; then
      continue
    fi
    checked=$((checked + 1))
    if [[ ! -f "$path" ]]; then
      echo "[model-assets] missing: $path" >&2
      missing=1
      continue
    fi
    if LC_ALL=C grep -aqm1 "^version https://git-lfs.github.com/spec/v1$" "$path"; then
      echo "[model-assets] still an LFS pointer: $path" >&2
      missing=1
    fi
  done < <(git lfs ls-files -n)

  if [[ "$checked" -eq 0 ]]; then
    echo "[model-assets] No LFS files matched profile=$PROFILE." >&2
    exit 3
  fi
  if [[ "$missing" -ne 0 ]]; then
    echo "[model-assets] Verification failed for profile=$PROFILE." >&2
    exit 3
  fi
  echo "[model-assets] Verified $checked file(s) for profile=$PROFILE."
fi

echo "[model-assets] Done."
