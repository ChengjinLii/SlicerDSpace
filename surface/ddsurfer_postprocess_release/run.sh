#!/bin/bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export PIPELINE_ROOT="${SCRIPT_DIR}"

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/config/pipeline.conf"

usage() {
    cat <<'EOF'
Usage:
  run.sh --subject-id <id> --mode <left|right|whole> [options]

Compatibility:
  run.sh <subject_id> <left|right|whole>

Options:
  --subject-id ID                 Subject ID
  --mode MODE                     left, right, or whole
  --inputs-dir PATH               Subject input root
  --outputs-dir PATH              Optimized output root
  --stage-mode MODE               copy, symlink, or inplace
  --stages CSV                    Comma-separated stages
  --atlases CSV                   Comma-separated atlases
  --freesurfer-home PATH          FreeSurfer install root
  --python-bin BIN                Python interpreter
  --help                          Show this help

Example:
  bash run.sh --subject-id 877168 --mode whole \
    --stages validate_inputs,stage_inputs,convert_surfaces
EOF
}

SUBJECT_ID=${SUBJECT_ID:-}
MODE=${MODE:-}
STAGES=${STAGES:-${DEFAULT_STAGES}}
ATLASES=${ATLASES:-${DEFAULT_ATLASES}}

if [ $# -eq 2 ] && [[ "${1:-}" != --* ]] && [[ "${2:-}" != --* ]]; then
    SUBJECT_ID=$1
    MODE=$2
else
    while [ $# -gt 0 ]; do
        case "$1" in
            --subject-id)
                SUBJECT_ID=${2:-}
                shift 2
                ;;
            --mode)
                MODE=${2:-}
                shift 2
                ;;
            --inputs-dir)
                INPUTS_DIR=${2:-}
                shift 2
                ;;
            --outputs-dir)
                OUTPUTS_DIR=${2:-}
                shift 2
                ;;
            --stage-mode)
                STAGE_MODE=${2:-}
                shift 2
                ;;
            --stages)
                STAGES=${2:-}
                shift 2
                ;;
            --atlases)
                ATLASES=${2:-}
                shift 2
                ;;
            --freesurfer-home)
                FREESURFER_HOME=${2:-}
                shift 2
                ;;
            --python-bin)
                PYTHON_BIN=${2:-}
                shift 2
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                echo "ERROR: Unknown argument: $1" >&2
                usage >&2
                exit 1
                ;;
        esac
    done
fi

if [ -z "${SUBJECT_ID}" ] || [ -z "${MODE}" ]; then
    usage >&2
    exit 1
fi

case "${MODE}" in
    left|right|whole) ;;
    *)
        echo "ERROR: mode must be left, right, or whole." >&2
        exit 1
        ;;
esac

export SUBJECT_ID
export MODE
export INPUTS_DIR
export OUTPUTS_DIR
export STAGE_MODE
export STAGES
export ATLASES
export FREESURFER_HOME
export PYTHON_BIN
export PYTHON_CONVERT_SCRIPT
export PYTHON_AREA_SCRIPT
export PYTHON_THICKNESS_SCRIPT
export PYTHON_EXTRACT_CTAB_SCRIPT
export PYTHON_REGIONAL_STATS_SCRIPT
export PYTHON_VALIDATE_SCRIPT
export PYTHON_REPORT_SCRIPT

bash "${SCRIPT_DIR}/scripts/run_pipeline.sh"
