#!/bin/bash

set -euo pipefail

log_echo() {
    mkdir -p "$(dirname "${LOG_FILE}")"
    echo -e "$@" | tee -a "${LOG_FILE}"
}

stage_enabled() {
    local step="$1"
    [[ ",${STAGES}," == *",${step},"* ]]
}

hemi_requested() {
    local hemi_short="$1"
    case "${MODE}" in
        whole) return 0 ;;
        left) [ "${hemi_short}" = "lh" ] ;;
        right) [ "${hemi_short}" = "rh" ] ;;
        *) return 1 ;;
    esac
}

canonical_paths_init() {
    if [ "${NEST_SUBJECT_OUTPUTS:-1}" = "0" ]; then
        OUTPUT_SUBJECT_ROOT="${OUTPUTS_DIR}"
    else
        OUTPUT_SUBJECT_ROOT="${OUTPUTS_DIR}/${SUBJECT_ID}"
    fi
    STRUCTURAL_ROOT="${OUTPUT_SUBJECT_ROOT}/03_structural/ddsurfer/postprocess"
    STATS_ROOT="${OUTPUT_SUBJECT_ROOT}/05_statistics/ddsurfer/postprocess"
    WORK_SUBJECTS_DIR="${STRUCTURAL_ROOT}/_subjects"
    SUBJECT_PATH="${WORK_SUBJECTS_DIR}/${SUBJECT_ID}"
    INPUT_SUBJECT_DIR="${INPUTS_DIR}/${SUBJECT_ID}"
    LOG_DIR="${STRUCTURAL_ROOT}/logs"
    LOG_FILE="${LOG_DIR}/pipeline_${SUBJECT_ID}.log"
    MANIFEST_JSON="${STRUCTURAL_ROOT}/manifest.json"
    QC_JSON="${STRUCTURAL_ROOT}/qc.json"
    PROVENANCE_JSON="${STRUCTURAL_ROOT}/provenance.json"
    VALIDATION_JSON="${STRUCTURAL_ROOT}/validation.json"
    FSAVERAGE_DIR="${STRUCTURAL_ROOT}/fsaverage"
    mkdir -p "${STRUCTURAL_ROOT}" "${STATS_ROOT}" "${WORK_SUBJECTS_DIR}" "${LOG_DIR}" "${FSAVERAGE_DIR}"
}

input_surface_paths_for_mode() {
    REQUIRED_INPUTS=(
        "${INPUT_SUBJECT_DIR}/mri/DDSurfer-wmparc.nii.gz"
        "${INPUT_SUBJECT_DIR}/mri/brain.mgz"
    )
    case "${MODE}" in
        whole)
            REQUIRED_INPUTS+=(
                "${INPUT_SUBJECT_DIR}/surf/${SUBJECT_ID}_predicted_wm_lh_orig.stl"
                "${INPUT_SUBJECT_DIR}/surf/${SUBJECT_ID}_predicted_wm_rh_orig.stl"
                "${INPUT_SUBJECT_DIR}/surf/${SUBJECT_ID}_predicted_pial_lh_orig.stl"
                "${INPUT_SUBJECT_DIR}/surf/${SUBJECT_ID}_predicted_pial_rh_orig.stl"
            )
            ;;
        left)
            REQUIRED_INPUTS+=(
                "${INPUT_SUBJECT_DIR}/surf/${SUBJECT_ID}_predicted_wm_lh_orig.stl"
                "${INPUT_SUBJECT_DIR}/surf/${SUBJECT_ID}_predicted_pial_lh_orig.stl"
            )
            ;;
        right)
            REQUIRED_INPUTS+=(
                "${INPUT_SUBJECT_DIR}/surf/${SUBJECT_ID}_predicted_wm_rh_orig.stl"
                "${INPUT_SUBJECT_DIR}/surf/${SUBJECT_ID}_predicted_pial_rh_orig.stl"
            )
            ;;
    esac
}

validate_inputs() {
    input_surface_paths_for_mode
    log_echo "\n=== Step: validate_inputs ==="
    "${PYTHON_BIN}" "${PYTHON_VALIDATE_SCRIPT}" \
        --subject-id "${SUBJECT_ID}" \
        --mode "${MODE}" \
        --input-subject-dir "${INPUT_SUBJECT_DIR}" \
        --output-json "${VALIDATION_JSON}"
}

ensure_freesurfer_env() {
    if [ -z "${FREESURFER_HOME:-}" ] && command -v recon-all >/dev/null 2>&1; then
        FREESURFER_HOME=$(cd "$(dirname "$(command -v recon-all)")/.." && pwd)
        export FREESURFER_HOME
    fi
    if ! command -v recon-all >/dev/null 2>&1; then
        if [ -n "${FREESURFER_HOME:-}" ] && [ -f "${FREESURFER_HOME}/SetUpFreeSurfer.sh" ]; then
            set +e
            set +u
            # shellcheck disable=SC1090
            source "${FREESURFER_HOME}/SetUpFreeSurfer.sh"
            set -euo pipefail
        fi
    fi
    if ! command -v mris_sphere >/dev/null 2>&1; then
        log_echo "ERROR: FreeSurfer command mris_sphere is unavailable. Set --freesurfer-home or export FREESURFER_HOME."
        return 1
    fi
    if [ -z "${FREESURFER_HOME:-}" ] || [ ! -d "${FREESURFER_HOME}/subjects/fsaverage" ]; then
        log_echo "ERROR: FREESURFER_HOME is unresolved or missing fsaverage subjects."
        return 1
    fi
    export SUBJECTS_DIR="${WORK_SUBJECTS_DIR}"
    if [ -n "${FREESURFER_HOME:-}" ] && [ -d "${FREESURFER_HOME}/subjects/fsaverage" ] && [ ! -e "${SUBJECTS_DIR}/fsaverage" ]; then
        ln -s "${FREESURFER_HOME}/subjects/fsaverage" "${SUBJECTS_DIR}/fsaverage"
    fi
}

cleanup_runtime_links() {
    # fsaverage is needed only while FreeSurfer commands are running.  Leaving
    # its absolute WSL symlink on an NTFS output tree makes Windows traversal
    # fail with WinError 1920.
    if [ -L "${WORK_SUBJECTS_DIR}/fsaverage" ]; then
        rm -f "${WORK_SUBJECTS_DIR}/fsaverage"
    fi
}

check_python_deps() {
    "${PYTHON_BIN}" - <<'PY'
import nibabel  # noqa: F401
import numpy  # noqa: F401
import trimesh  # noqa: F401
PY
}

safe_stage_item() {
    local src="$1"
    local dest="$2"
    mkdir -p "$(dirname "${dest}")"
    case "${STAGE_MODE}" in
        symlink)
            if [ -e "${dest}" ] || [ -L "${dest}" ]; then
                return 0
            fi
            ln -s "${src}" "${dest}"
            ;;
        copy|inplace)
            if [ -L "${dest}" ]; then
                rm -f "${dest}"
            fi
            cp -aL "${src}" "${dest}"
            ;;
        *)
            log_echo "ERROR: Unsupported STAGE_MODE=${STAGE_MODE}"
            return 1
            ;;
    esac
}

stage_inputs() {
    log_echo "\n=== Step: stage_inputs ==="
    if [ "${STAGE_MODE}" = "inplace" ]; then
        SUBJECT_PATH="${INPUT_SUBJECT_DIR}"
        export SUBJECTS_DIR="${INPUTS_DIR}"
        log_echo "Using inplace mode: SUBJECT_PATH=${SUBJECT_PATH}"
        return 0
    fi

    export SUBJECTS_DIR="${WORK_SUBJECTS_DIR}"
    mkdir -p "${SUBJECT_PATH}/mri" "${SUBJECT_PATH}/surf"
    safe_stage_item "${INPUT_SUBJECT_DIR}/mri/DDSurfer-wmparc.nii.gz" "${SUBJECT_PATH}/mri/DDSurfer-wmparc.nii.gz"
    safe_stage_item "${INPUT_SUBJECT_DIR}/mri/brain.mgz" "${SUBJECT_PATH}/mri/brain.mgz"
    for hemi in lh rh; do
        hemi_requested "${hemi}" || continue
        for surface in wm pial; do
            local name="${SUBJECT_ID}_predicted_${surface}_${hemi}_orig.stl"
            if [ -f "${INPUT_SUBJECT_DIR}/surf/${name}" ]; then
                safe_stage_item "${INPUT_SUBJECT_DIR}/surf/${name}" "${SUBJECT_PATH}/surf/${name}"
            fi
        done
    done
}

convert_surfaces() {
    log_echo "\n=== Step: convert_surfaces ==="
    "${PYTHON_BIN}" "${PYTHON_CONVERT_SCRIPT}" --subject_id "${SUBJECT_ID}" --subjects_dir "${SUBJECTS_DIR}" --mode "${MODE}"
}

run_fs_surface_build_for_hemi() {
    local hemi_short="$1"
    local surf_dir="${SUBJECT_PATH}/surf"
    local mri_dir="${SUBJECT_PATH}/mri"
    local label_dir="${SUBJECT_PATH}/label"
    local stats_dir="${SUBJECT_PATH}/stats"
    mkdir -p "${surf_dir}" "${mri_dir}" "${label_dir}" "${stats_dir}"

    local output_white="${surf_dir}/${hemi_short}.white"
    local output_pial="${surf_dir}/${hemi_short}.pial"
    local output_smoothwm="${surf_dir}/${hemi_short}.smoothwm"
    local output_inflated_fs="${surf_dir}/${hemi_short}.inflated"
    local output_sphere_fs="${surf_dir}/${hemi_short}.sphere"
    local output_sphere_reg_fs="${surf_dir}/${hemi_short}.sphere.reg"
    local thickness_file="${surf_dir}/${hemi_short}.thickness"
    local curv_file="${surf_dir}/${hemi_short}.curv"
    local sulc_file="${surf_dir}/${hemi_short}.sulc"
    local area_white_file="${surf_dir}/${hemi_short}.area"
    local area_pial_file="${surf_dir}/${hemi_short}.area.pial"
    local cortex_label="${label_dir}/${hemi_short}.cortex.label"
    local h_white_file="${surf_dir}/${hemi_short}.white.H"
    local k_white_file="${surf_dir}/${hemi_short}.white.K"
    local h_pial_file="${surf_dir}/${hemi_short}.pial.H"
    local k_pial_file="${surf_dir}/${hemi_short}.pial.K"
    local h_inflated_file="${surf_dir}/${hemi_short}.inflated.H"
    local k_inflated_file="${surf_dir}/${hemi_short}.inflated.K"

    [ -f "${output_smoothwm}" ] || cp "${output_white}" "${output_smoothwm}"
    [ -f "${h_white_file}" ] && [ -f "${k_white_file}" ] || mris_curvature -w "${output_white}" >> "${LOG_FILE}" 2>&1
    [ -f "${h_pial_file}" ] && [ -f "${k_pial_file}" ] || mris_curvature -w "${output_pial}" >> "${LOG_FILE}" 2>&1
    [ -f "${sulc_file}" ] && [ -f "${output_inflated_fs}" ] || mris_inflate "${output_white}" "${output_inflated_fs}" >> "${LOG_FILE}" 2>&1
    [ -f "${h_inflated_file}" ] && [ -f "${k_inflated_file}" ] || mris_curvature -w "${output_inflated_fs}" >> "${LOG_FILE}" 2>&1
    [ -f "${output_sphere_fs}" ] || mris_sphere "${output_inflated_fs}" "${output_sphere_fs}" >> "${LOG_FILE}" 2>&1
    [ -f "${output_sphere_reg_fs}" ] || mris_register "${output_sphere_fs}" "${FREESURFER_HOME}/average/${hemi_short}.average.curvature.filled.buckner40.tif" "${output_sphere_reg_fs}" >> "${LOG_FILE}" 2>&1
    [ -f "${thickness_file}" ] || "${PYTHON_BIN}" "${PYTHON_THICKNESS_SCRIPT}" --subjects_dir "${SUBJECTS_DIR}" --subject_id "${SUBJECT_ID}" --hemi "${hemi_short}" --calc_thickness >> "${LOG_FILE}" 2>&1
    [ -f "${area_white_file}" ] || "${PYTHON_BIN}" "${PYTHON_AREA_SCRIPT}" --surf "${output_white}" --out_area "${area_white_file}" >> "${LOG_FILE}" 2>&1
    [ -f "${area_pial_file}" ] || "${PYTHON_BIN}" "${PYTHON_AREA_SCRIPT}" --surf "${output_pial}" --out_area "${area_pial_file}" >> "${LOG_FILE}" 2>&1
    if [ ! -f "${cortex_label}" ]; then
        mri_label2label --srclabel "${FREESURFER_HOME}/subjects/fsaverage/label/${hemi_short}.cortex.label" --srcsubject fsaverage --trgsubject "${SUBJECT_ID}" --trglabel "${cortex_label}" --regmethod surface --hemi "${hemi_short}" >> "${LOG_FILE}" 2>&1
    fi
    [ -f "${curv_file}" ] || cp "${h_white_file}" "${curv_file}"
}

build_fs_surfaces() {
    log_echo "\n=== Step: build_fs_surfaces ==="
    for hemi in lh rh; do
        hemi_requested "${hemi}" || continue
        run_fs_surface_build_for_hemi "${hemi}"
    done
}

parse_csv_to_array() {
    local csv="$1"
    IFS=',' read -r -a PARSED_CSV <<< "${csv}"
}

project_annotations() {
    log_echo "\n=== Step: project_annotations ==="
    parse_csv_to_array "${ATLASES}"
    local label_dir="${SUBJECT_PATH}/label"
    mkdir -p "${label_dir}"
    for hemi in lh rh; do
        hemi_requested "${hemi}" || continue
        for annot_base in "${PARSED_CSV[@]}"; do
            local source_annot_file="${FREESURFER_HOME}/subjects/fsaverage/label/${hemi}.${annot_base}.annot"
            local target_annot_file="${label_dir}/${hemi}.${annot_base}.annot"
            local ctab_file="${label_dir}/${hemi}.${annot_base}.ctab"
            if [ ! -f "${target_annot_file}" ] && [ -f "${source_annot_file}" ]; then
                mri_surf2surf --srcsubject fsaverage --trgsubject "${SUBJECT_ID}" --hemi "${hemi}" --sval-annot "${source_annot_file}" --tval "${target_annot_file}" >> "${LOG_FILE}" 2>&1
            fi
            if [ -f "${target_annot_file}" ]; then
                "${PYTHON_BIN}" "${PYTHON_EXTRACT_CTAB_SCRIPT}" --annot_file "${target_annot_file}" --output_ctab "${ctab_file}" >> "${LOG_FILE}" 2>&1
            fi
        done
    done
}

extract_labels() {
    log_echo "\n=== Step: extract_labels ==="
    parse_csv_to_array "${ATLASES}"
    local label_dir="${SUBJECT_PATH}/label"
    for hemi in lh rh; do
        hemi_requested "${hemi}" || continue
        for annot_base in "${PARSED_CSV[@]}"; do
            local annot_file="${label_dir}/${hemi}.${annot_base}.annot"
            local regions_subdir="${label_dir}/regions_${annot_base}"
            if [ -f "${annot_file}" ] && [ ! -d "${regions_subdir}" ]; then
                mkdir -p "${regions_subdir}"
                mri_annotation2label --subject "${SUBJECT_ID}" --hemi "${hemi}" --annotation "${annot_base}" --outdir "${regions_subdir}" >> "${LOG_FILE}" 2>&1
            fi
        done
    done
}

compute_stats() {
    log_echo "\n=== Step: compute_stats ==="
    parse_csv_to_array "${ATLASES}"
    local surf_dir="${SUBJECT_PATH}/surf"
    local mri_dir="${SUBJECT_PATH}/mri"
    local label_dir="${SUBJECT_PATH}/label"
    local stats_dir="${SUBJECT_PATH}/stats"
    mkdir -p "${stats_dir}"
    for hemi in lh rh; do
        hemi_requested "${hemi}" || continue
        local output_wmparc_stats="${stats_dir}/${hemi}.wmparc.stats"
        if [ ! -f "${output_wmparc_stats}" ]; then
            mri_segstats --seg "${mri_dir}/DDSurfer-wmparc.nii.gz" --ctab "${FREESURFER_HOME}/FreeSurferColorLUT.txt" --surf-wm-vol --sum "${output_wmparc_stats}" >> "${LOG_FILE}" 2>&1
        fi
        for annot_base in "${PARSED_CSV[@]}"; do
            local annot_file="${label_dir}/${hemi}.${annot_base}.annot"
            local ctab_file="${label_dir}/${hemi}.${annot_base}.ctab"
            local output_stats="${stats_dir}/${hemi}.${annot_base}.stats"
            if [ -f "${annot_file}" ] && [ -f "${ctab_file}" ]; then
                declare -a python_cmd=("${PYTHON_REGIONAL_STATS_SCRIPT}" --annot_file "${annot_file}" --ctab_file "${ctab_file}" --hemi "${hemi}" --out_stats_file "${output_stats}")
                [ -f "${surf_dir}/${hemi}.thickness" ] && python_cmd+=(--thickness "${surf_dir}/${hemi}.thickness")
                [ -f "${surf_dir}/${hemi}.area.pial" ] && python_cmd+=(--area "${surf_dir}/${hemi}.area.pial")
                [ -f "${surf_dir}/${hemi}.curv" ] && python_cmd+=(--curv "${surf_dir}/${hemi}.curv")
                [ -f "${surf_dir}/${hemi}.sulc" ] && python_cmd+=(--sulc "${surf_dir}/${hemi}.sulc")
                [ -f "${surf_dir}/${hemi}.white.K" ] && python_cmd+=(--gauscurv "${surf_dir}/${hemi}.white.K")
                "${PYTHON_BIN}" "${python_cmd[@]}" >> "${LOG_FILE}" 2>&1
            fi
        done
    done
}

resample_fsaverage() {
    log_echo "\n=== Step: resample_fsaverage ==="
    local surf_dir="${SUBJECT_PATH}/surf"
    mkdir -p "${FSAVERAGE_DIR}"
    declare -a metrics_to_resample=("thickness" "curv" "sulc" "area.pial")
    for hemi in lh rh; do
        hemi_requested "${hemi}" || continue
        for metric_basename in "${metrics_to_resample[@]}"; do
            local source_metric_file="${surf_dir}/${hemi}.${metric_basename}.mgh"
            if [ ! -f "${source_metric_file}" ]; then
                source_metric_file="${surf_dir}/${hemi}.${metric_basename}"
            fi
            local output_metric_fsaverage="${surf_dir}/${hemi}.${metric_basename}.fsaverage.mgh"
            if [ -f "${source_metric_file}" ] && [ ! -f "${output_metric_fsaverage}" ]; then
                mri_surf2surf --s "${SUBJECT_ID}" --hemi "${hemi}" --sval "${source_metric_file}" --trgsubject fsaverage --tval "${output_metric_fsaverage}" >> "${LOG_FILE}" 2>&1
            fi
            if [ -f "${output_metric_fsaverage}" ]; then
                local public_metric="${FSAVERAGE_DIR}/$(basename "${output_metric_fsaverage}")"
                if [ -L "${public_metric}" ]; then
                    rm -f "${public_metric}"
                fi
                cp -fL "${output_metric_fsaverage}" "${public_metric}"
            fi
        done
    done
}

materialize_directory() {
    local src="$1"
    local dest="$2"
    local temporary="${dest}.tmp.$$"
    rm -rf "${temporary}"
    mkdir -p "${temporary}"
    cp -aL "${src}/." "${temporary}/"
    if [ -L "${dest}" ]; then
        rm -f "${dest}"
    elif [ -e "${dest}" ]; then
        rm -rf "${dest}"
    fi
    mv "${temporary}" "${dest}"
}

sync_outputs() {
    log_echo "\n=== Step: sync_outputs ==="
    local structural_links=(mri surf label)
    mkdir -p "${STATS_ROOT}"
    for name in "${structural_links[@]}"; do
        if [ -e "${SUBJECT_PATH}/${name}" ]; then
            materialize_directory "${SUBJECT_PATH}/${name}" "${STRUCTURAL_ROOT}/${name}"
        fi
    done
    mkdir -p "${LOG_DIR}"
    if [ -e "${SUBJECT_PATH}/stats" ]; then
        materialize_directory "${SUBJECT_PATH}/stats" "${STATS_ROOT}/stats"
    fi
}

write_reports() {
    local freesurfer_available="false"
    command -v mris_sphere >/dev/null 2>&1 && freesurfer_available="true"
    "${PYTHON_BIN}" "${PYTHON_REPORT_SCRIPT}" \
        --subject-id "${SUBJECT_ID}" \
        --mode "${MODE}" \
        --input-subject-dir "${INPUT_SUBJECT_DIR}" \
        --structural-root "${STRUCTURAL_ROOT}" \
        --stats-root "${STATS_ROOT}" \
        --subject-path "${SUBJECT_PATH}" \
        --log-file "${LOG_FILE}" \
        --stages "${STAGES}" \
        --atlases "${ATLASES}" \
        --freesurfer-home "${FREESURFER_HOME:-}" \
        --stage-mode "${STAGE_MODE}" \
        --freesurfer-available "${freesurfer_available}" \
        --validation-json "${VALIDATION_JSON}" \
        --manifest-json "${MANIFEST_JSON}" \
        --qc-json "${QC_JSON}" \
        --provenance-json "${PROVENANCE_JSON}"
}
