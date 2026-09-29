"""English/Chinese UI text for the workflow sections, topup fields and Results.

Merged into ``shared.ui_onboarding.TRANSLATIONS`` so the language switch in
"Getting started" covers the new controls too.
"""

from __future__ import annotations


WORKFLOW_TEXT = {
    "en": {
        "section_getting_started": "Getting started",
        "section_inputs": "1. Inputs",
        "section_targets": "2. Targets",
        "section_parameters": "3. Route and parameters",
        "section_run": "4. Run",
        "section_results": "5. Results",
        "topup_group": "Distortion correction (topup)",
        "phase_encoding_direction": "Phase-encoding direction",
        "readout_time": "Total readout time (s)",
        "reverse_phase_b0": "Reverse-PE b=0 image",
        "run_selector_label": "Run",
        "refresh": "Refresh",
        "browse_runs": "Browse…",
        "browse_runs_title": "Choose a run or output folder",
        "no_runs_found": "No runs found — use Browse… to add a run folder",
        "no_run_selected": "No run selected.",
        "no_run_in_progress": "No run in progress",
        "current_stage": "Current stage",
        "run_state_idle": "Idle",
        "run_state_preflight": "Checking environment",
        "run_state_running": "Running",
        "run_state_completed": "Completed",
        "run_state_completed_with_blocks": "Completed with blocked stages",
        "run_state_failed": "Completed with errors",
        "run_state_cancelled": "Cancelled",
        "preprocessing_tooltip": (
            "Optional DWI denoising, Gibbs-ringing removal and motion/eddy correction. "
            "Leave unchecked to run downstream workflows from the original subject input folder."
        ),
        "parcellation_tooltip": "DDParcel aparc and wmparc label maps in native dMRI space.",
        "segmentation_tooltip": "DDSeg white matter, gray matter and CSF segmentation and probability maps.",
        "microstructure_tooltip": "FA and MD maps, ROI statistics, and optional Free Water and NODDI stages.",
        "tractography_tooltip": "DTI deterministic tractogram, or MRtrix3 CSD / FOD / ACT when that backend is available.",
        "bundles_tooltip": "White-matter bundle extraction with WMQL presets, WMA or TractCloud.",
        "connectome_tooltip": "Streamline-count and scalar-weighted structural connectivity matrices.",
    },
    "zh": {
        "section_getting_started": "快速开始",
        "section_inputs": "1. 输入",
        "section_targets": "2. 目标产物",
        "section_parameters": "3. 路线与参数",
        "section_run": "4. 运行",
        "section_results": "5. 结果",
        "topup_group": "畸变校正（topup）",
        "phase_encoding_direction": "相位编码方向",
        "readout_time": "总读出时间（秒）",
        "reverse_phase_b0": "反向相位编码 b=0 图像",
        "run_selector_label": "运行",
        "refresh": "刷新",
        "browse_runs": "浏览…",
        "browse_runs_title": "选择运行目录或输出目录",
        "no_runs_found": "未找到运行记录——点击“浏览…”添加运行目录",
        "no_run_selected": "未选择运行。",
        "no_run_in_progress": "当前没有运行",
        "current_stage": "当前阶段",
        "run_state_idle": "空闲",
        "run_state_preflight": "正在检查环境",
        "run_state_running": "运行中",
        "run_state_completed": "已完成",
        "run_state_completed_with_blocks": "已完成（部分阶段被阻止）",
        "run_state_failed": "完成但有错误",
        "run_state_cancelled": "已取消",
        "preprocessing_tooltip": "可选的 DWI 降噪、Gibbs 伪影去除及运动/涡流校正。不勾选时，下游流程直接使用原始受试者输入目录。",
        "parcellation_tooltip": "原生 dMRI 空间中的 DDParcel aparc 与 wmparc 标签图。",
        "segmentation_tooltip": "DDSeg 白质、灰质、脑脊液分割及概率图。",
        "microstructure_tooltip": "FA、MD 图与 ROI 统计，以及可选的自由水和 NODDI 阶段。",
        "tractography_tooltip": "DTI 确定性纤维追踪；后端可用时运行 MRtrix3 CSD / FOD / ACT。",
        "bundles_tooltip": "使用 WMQL 预设、WMA 或 TractCloud 提取白质纤维束。",
        "connectome_tooltip": "流线计数及标量加权的结构连接矩阵。",
    },
}


WORKFLOW_TEXT_BINDINGS = {
    "gettingStartedCollapsibleButton": "section_getting_started",
    "configurationCollapsibleButton": "section_inputs",
    "targetsCollapsibleButton": "section_targets",
    "parametersCollapsibleButton": "section_parameters",
    "runCollapsibleButton": "section_run",
    "resultsCollapsibleButton": "section_results",
    "preprocessingPhaseEncodingDirectionLabel": "phase_encoding_direction",
    "preprocessingReadoutTimeLabel": "readout_time",
    "preprocessingReversePhaseB0Label": "reverse_phase_b0",
}

WORKFLOW_TOOLTIP_BINDINGS = {
    "targetPreprocessingCheckBox": "preprocessing_tooltip",
    "targetParcellationCheckBox": "parcellation_tooltip",
    "targetSegmentationCheckBox": "segmentation_tooltip",
    "targetMicrostructureCheckBox": "microstructure_tooltip",
    "targetTractographyCheckBox": "tractography_tooltip",
    "targetBundlesCheckBox": "bundles_tooltip",
    "targetConnectomeCheckBox": "connectome_tooltip",
}
