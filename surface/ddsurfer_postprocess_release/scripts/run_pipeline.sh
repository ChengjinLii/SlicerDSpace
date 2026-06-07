#!/bin/bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/pipeline_steps.sh"

canonical_paths_init
touch "${LOG_FILE}"
write_reports

run_stage() {
    local stage_name="$1"
    shift
    if ! stage_enabled "${stage_name}"; then
        return 0
    fi
    "$@"
    write_reports
}

log_echo "Starting optimized DDSurfer postprocess"
log_echo "Subject=${SUBJECT_ID}"
log_echo "Mode=${MODE}"
log_echo "Stages=${STAGES}"
log_echo "Atlases=${ATLASES}"
log_echo "Inputs=${INPUTS_DIR}"
log_echo "Outputs=${OUTPUTS_DIR}"
log_echo "Stage mode=${STAGE_MODE}"

check_python_deps
write_reports

run_stage "validate_inputs" validate_inputs

run_stage "stage_inputs" stage_inputs

run_stage "convert_surfaces" convert_surfaces

FS_REQUIRED_STAGES="build_fs_surfaces,project_annotations,extract_labels,compute_stats,resample_fsaverage"
if [[ ",${STAGES}," == *",build_fs_surfaces,"* ]] || \
   [[ ",${STAGES}," == *",project_annotations,"* ]] || \
   [[ ",${STAGES}," == *",extract_labels,"* ]] || \
   [[ ",${STAGES}," == *",compute_stats,"* ]] || \
   [[ ",${STAGES}," == *",resample_fsaverage,"* ]]; then
    ensure_freesurfer_env
fi
write_reports

run_stage "build_fs_surfaces" build_fs_surfaces

run_stage "project_annotations" project_annotations

run_stage "extract_labels" extract_labels

run_stage "compute_stats" compute_stats

run_stage "resample_fsaverage" resample_fsaverage

run_stage "sync_outputs" sync_outputs

write_reports

log_echo "Optimized DDSurfer postprocess finished."
