"""English/Chinese UI text for the workflow sections, topup fields and Results.

Merged into ``shared.ui_onboarding.TRANSLATIONS`` so the language switch in
the header covers the new controls too.
"""

from __future__ import annotations


BRAIN_MASK_BACKEND_TEXT_KEYS = {
    "pnl_cnn": "brain_mask_pnl_cnn",
    "synthstrip": "brain_mask_synthstrip",
    "mrtrix": "brain_mask_mrtrix",
    "provided": "brain_mask_provided",
}


WORKFLOW_TEXT = {
    "en": {
        "section_getting_started": "Getting started",
        "section_inputs": "1. Inputs",
        "section_targets": "2. Products",
        "compact_advanced": "Advanced settings",
        "compact_import": "Input import / conversion",
        "compact_parameters": "Analysis parameters",
        "compact_environment": "Environment and models",
        "compact_results": "Results and QC",
        "compact_run": "Run SlicerDDSurfer",
        "compact_log": "Log",
        "compact_preprocessing": "Denoise / Gibbs / motion correction",
        "compact_surface": "DDSurfer white / pial surfaces",
        "compact_postprocess": "FreeSurfer-style refinement",
        "compact_parcellation": "DDParcel regional labels",
        "compact_segmentation": "DDSeg WM / GM / CSF",
        "compact_microstructure": "DTI + optional models",
        "compact_tractography": "Whole-brain tractography",
        "compact_bundles": "WMQL / WMA / TractCloud",
        "compact_connectome": "Structural connectivity matrices",
        "section_parameters": "3. Route and parameters",
        "section_run": "4. Run",
        "section_results": "5. Results",
        "topup_group": "Distortion correction (topup)",
        "phase_encoding_direction": "Phase-encoding direction",
        "readout_time": "Total readout time (s)",
        "reverse_phase_b0": "Reverse-PE b=0 image",
        "brain_mask_backend": "Brain masking",
        "brain_mask_pnl_cnn": "PNL CNN (dMRI)",
        "brain_mask_synthstrip": "SynthStrip",
        "brain_mask_mrtrix": "MRtrix dwi2mask",
        "brain_mask_provided": "Provided mask only",
        "microstructure_dti_always": "DTI (always enabled)",
        "microstructure_fw_option": "FW",
        "microstructure_noddi_option": "NODDI",
        "microstructure_dki_option": "DKI",
        "microstructure_fw_tooltip": "Optional Free Water model. Independent of NODDI and DKI; off by default.",
        "microstructure_noddi_tooltip": "Optional NODDI model. Independent of Free Water and DKI; off by default.",
        "microstructure_dki_tooltip": "Optional diffusion kurtosis analysis. Standard DKI is not MK-Curve; off by default.",
        "dki_fit_method": "DKI fit method",
        "dki_fit_method_tooltip": (
            "WLS/OLS are standard DKI fits. MKCURVE uses the bundled Python port without MATLAB. "
            "MKCURVE_MATLAB is an optional author reference; configure its external paths under Advanced. "
            "All methods require eligible multi-shell data; no silent fallback."
        ),
        "brain_mask_backend_tooltip": (
            "Existing supplied masks are respected. This choice only controls generation of a missing mask. "
            "PNL CNN (dMRI) is the default and requires externally configured Python, official dwi_masking.py, "
            "models and ANTs paths under Advanced > Environment and models > External Runtime Paths. "
            "SynthStrip uses FreeSurfer home; MRtrix uses MRtrix3 bin dir. "
            "Provided mask only requires an existing mask. Missing dependencies or masks cause an error; "
            "there is no automatic fallback to another masking backend."
        ),
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
        "microstructure_tooltip": "DTI maps and ROI statistics by default. Independently enable Free Water, NODDI or DKI under Advanced > Analysis parameters.",
        "tractography_tooltip": "DTI deterministic tractogram, or MRtrix3 CSD / FOD / ACT when that backend is available.",
        "bundles_tooltip": "White-matter bundle extraction with WMQL presets, WMA or TractCloud.",
        "connectome_tooltip": "Streamline-count and scalar-weighted structural connectivity matrices.",
    },
    "zh": {
        "section_getting_started": "快速开始",
        "section_inputs": "1. 输入",
        "section_targets": "2. 分析任务",
        "compact_advanced": "高级设置",
        "compact_import": "输入导入 / 格式转换",
        "compact_parameters": "分析参数",
        "compact_environment": "环境与模型",
        "compact_results": "结果与质控",
        "compact_run": "运行 SlicerDDSurfer",
        "compact_log": "日志",
        "compact_preprocessing": "降噪 / Gibbs / 运动校正",
        "compact_surface": "DDSurfer 白质 / 软脑膜表面",
        "compact_postprocess": "FreeSurfer 风格精细化",
        "compact_parcellation": "DDParcel 脑区标签",
        "compact_segmentation": "DDSeg 白质 / 灰质 / 脑脊液",
        "compact_microstructure": "DTI + 可选模型",
        "compact_tractography": "全脑纤维追踪",
        "compact_bundles": "WMQL / WMA / TractCloud",
        "compact_connectome": "结构连接矩阵",
        "section_parameters": "3. 路线与参数",
        "section_run": "4. 运行",
        "section_results": "5. 结果",
        "topup_group": "畸变校正（topup）",
        "phase_encoding_direction": "相位编码方向",
        "readout_time": "总读出时间（秒）",
        "reverse_phase_b0": "反向相位编码 b=0 图像",
        "brain_mask_backend": "脑掩膜方法",
        "brain_mask_pnl_cnn": "PNL CNN (dMRI)",
        "brain_mask_synthstrip": "SynthStrip",
        "brain_mask_mrtrix": "MRtrix dwi2mask",
        "brain_mask_provided": "仅使用提供的掩膜",
        "microstructure_dti_always": "DTI（始终启用）",
        "microstructure_fw_option": "FW",
        "microstructure_noddi_option": "NODDI",
        "microstructure_dki_option": "DKI",
        "microstructure_fw_tooltip": "可选自由水模型，独立于 NODDI 和 DKI，默认关闭。",
        "microstructure_noddi_tooltip": "可选 NODDI 模型，独立于自由水和 DKI，默认关闭。",
        "microstructure_dki_tooltip": "可选扩散峰度分析，标准 DKI 不等于 MK-Curve，默认关闭。",
        "dki_fit_method": "DKI 拟合方法",
        "dki_fit_method_tooltip": (
            "WLS/OLS 是标准 DKI 拟合。MKCURVE 使用内置 Python 移植版，不需要 MATLAB。"
            "MKCURVE_MATLAB 是可选的作者代码对照后端，可在高级设置中配置外部路径。"
            "所有方法都检查多 shell 数据条件，不会静默回退。"
        ),
        "brain_mask_backend_tooltip": (
            "尊重已有的用户提供掩膜；此选项仅控制缺失掩膜的生成。默认 PNL CNN (dMRI)，"
            "需在“高级设置 > 环境与模型 > 外部运行路径”配置外部 Python、官方 dwi_masking.py、"
            "模型目录和 ANTs 路径。SynthStrip 共用 FreeSurfer 主目录，MRtrix 共用 MRtrix3 bin 目录。"
            "“仅使用提供的掩膜”要求掩膜已存在。依赖或掩膜缺失时明确报错，不会自动切换其他掩膜后端。"
        ),
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
        "microstructure_tooltip": "默认只生成 DTI 标量图和 ROI 统计。在“高级设置 > 分析参数”中独立启用自由水、NODDI 或 DKI。",
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
    "resultsCollapsibleButton": "section_results",
    "preprocessingPhaseEncodingDirectionLabel": "phase_encoding_direction",
    "preprocessingReadoutTimeLabel": "readout_time",
    "preprocessingReversePhaseB0Label": "reverse_phase_b0",
    "brainMaskBackendLabel": "brain_mask_backend",
    "orchestrationDtiStageLabel": "microstructure_dti_always",
    "orchestrationFreeWaterCheckBox": "microstructure_fw_option",
    "orchestrationNoddiCheckBox": "microstructure_noddi_option",
    "orchestrationDkiCheckBox": "microstructure_dki_option",
    "orchestrationDkiFitMethodLabel": "dki_fit_method",
}

WORKFLOW_TOOLTIP_BINDINGS = {
    "brainMaskBackendComboBox": "brain_mask_backend_tooltip",
    "orchestrationFreeWaterCheckBox": "microstructure_fw_tooltip",
    "orchestrationNoddiCheckBox": "microstructure_noddi_tooltip",
    "orchestrationDkiCheckBox": "microstructure_dki_tooltip",
    "orchestrationDkiFitMethodComboBox": "dki_fit_method_tooltip",
    "targetPreprocessingCheckBox": "preprocessing_tooltip",
    "targetParcellationCheckBox": "parcellation_tooltip",
    "targetSegmentationCheckBox": "segmentation_tooltip",
    "targetMicrostructureCheckBox": "microstructure_tooltip",
    "targetTractographyCheckBox": "tractography_tooltip",
    "targetBundlesCheckBox": "bundles_tooltip",
    "targetConnectomeCheckBox": "connectome_tooltip",
}
