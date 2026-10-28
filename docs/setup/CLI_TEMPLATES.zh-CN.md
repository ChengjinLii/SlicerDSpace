<div align="center">

# 命令行模板

**选择路线、检查计划，再执行分析**

[首页](../../README.zh-CN.md) | [快速开始](QUICKSTART.zh-CN.md) | [批量实验](EXPERIMENTS.zh-CN.md) | [平台支持](SUPPORT_MATRIX.zh-CN.md) | [English](CLI_TEMPLATES.md)

</div>

---

## 从这里开始

| 任务 | 模板 |
| --- | --- |
| 导入 DICOM、NIfTI 或 NRRD | [输入准备](#输入准备) |
| 生成掩膜或校正 DWI | [掩膜和预处理](#掩膜和预处理) |
| DDSeg、DDParcel、DDSurfer 或皮层后处理 | [解剖重建](#解剖重建) |
| DTI、FW、NODDI、DKI 或 MK-Curve | [微结构](#微结构) |
| DTI、UKF、CSD/ACT 或 SAF | [纤维追踪](#纤维追踪) |
| WMQL、WMA、TractCloud 及来源选择 | [束分析](#束分析和显式来源) |
| 连接组或组合路线 | [连接组](#连接组和组合路线) |
| 多被试或参数对照 | [批量实验](#多被试和参数实验) |
| 脑区分析或报告 | [结果](#脑区分析和报告) |

以下使用 Linux/macOS 的 Bash，或已明确配置的 WSL 环境；原生 PowerShell 示例见后文。
先替换路径。`REPO` 可以是源码仓库，也可以是安装后包含 `shared/` 和 `scripts/`
的 `qt-scripted-modules` 目录。`SLICER` 指向真正的 Slicer 启动程序。

<!-- cli-setup: bash -->
```bash
export SLICER="/path/to/Slicer"
export REPO="/path/to/SlicerDSpace"
export SUBJECT="/path/to/prepared/sub-01"
export SUBJECT_ID="sub-01"
export OUTPUTS="/path/to/analysis/sub-01"
export ASSETS="/path/to/SlicerDDSurfer-models"
DEPENDENCY_ARGS=()
# If needed, export dependency paths from the GUI, then uncomment:
# DEPENDENCY_ARGS=(--dependency-config "/path/to/dependency_paths.json")

pipeline() {
  local run_name="$1"
  shift
  "$SLICER" --launch PythonSlicer "$REPO/shared/run_subject_pipeline_cli.py" \
    --no-user-config --strict-environment \
    --subject-root "$SUBJECT" --subject-id "$SUBJECT_ID" \
    --output-root "$OUTPUTS/$run_name" --run-name "$run_name" \
    --model-assets-dir "$ASSETS" "${DEPENDENCY_ARGS[@]}" "$@"
}
```

每条路线使用独立输出目录。保持**同一条命令、同一运行名和参数**：先将 `--plan`
换成 `--doctor` 检查依赖，再检查 `--plan`，确认后换成 `--execute`。
Doctor/plan 可以写入元数据，不执行科学模型。`--strict-environment` 在依赖缺失时停止，
避免只执行所选路线的一部分。

模板不读取已保存的 GUI 运行默认值。如需复用 GUI 配置的外部路径，在
**环境与安装 > 更多选项 > 导出依赖配置** 中导出，并设置 `DEPENDENCY_ARGS`；
也可用 `--help` 中列出的显式路径参数。按[托管环境配置](MANAGED_SETUP.zh-CN.md)
只准备选定依赖和模型。资源下载、许可确认与正式分析分开进行。

大多数模板使用已检查的原生掩膜（`provided`）；需要生成时明确改选 DIPY 或 PNL。
已有掩膜优先使用。掩膜及可复用缓存位于被试根目录，仅换输出目录不能隔离掩膜生成对照；
比较掩膜方法时使用独立输入副本。

---

## 输入准备

DICOM 目录应只包含目标扩散序列；NIfTI 需要配套 bval/bvec；NRRD/NHDR 应保留梯度元数据。
使用新的目标被试目录。先预览，确认后移除 `--dry-run` 导入；已有标准化输入受覆盖保护。

<!-- cli-template: import-dicom -->
```bash
"$SLICER" --launch PythonSlicer "$REPO/scripts/prepare_inputs.py" \
  --source "/path/to/diffusion_DICOM" --source-kind dicom \
  --subject-root "$SUBJECT" --subject-id "$SUBJECT_ID" --dry-run
```

<!-- cli-template: import-nifti -->
```bash
"$SLICER" --launch PythonSlicer "$REPO/scripts/prepare_inputs.py" \
  --source "/path/to/dwi.nii.gz" --source-kind nifti \
  --bval "/path/to/dwi.bval" --bvec "/path/to/dwi.bvec" \
  --mask "/path/to/reviewed_mask.nii.gz" \
  --subject-root "$SUBJECT" --subject-id "$SUBJECT_ID" --dry-run
```

<!-- cli-template: import-nrrd -->
```bash
"$SLICER" --launch PythonSlicer "$REPO/scripts/prepare_inputs.py" \
  --source "/path/to/dwi.nhdr" --source-kind nrrd --backend dwiconvert \
  --subject-root "$SUBJECT" --subject-id "$SUBJECT_ID" --dry-run
```

标准输入包括 `input/data.nii.gz`、`input/bvals`、`input/bvecs`，以及可选的
`input/dwi.json`、`input/nodif_brain_mask.nii.gz`。检查体积数、梯度方向、空间几何和有限值。
NRRD uint16 只在已检查的 int16 数值范围内无损转换；溢出时导入器拒绝转换。

---

## 掩膜和预处理

选择一种掩膜方法，缺少掩膜时才生成。PNL 需要配置好的 TensorFlow/ANTs 环境；
DIPY 不需要权重或外部掩膜程序；MRtrix 和 SynthStrip 各有依赖。
某个方法失败时不会自动改用另一个方法。

<!-- cli-template: mask-pnl -->
```bash
pipeline mask_pnl --targets validation --brain-mask-backend pnl_cnn \
  --brain-mask-device auto --plan
```

<!-- cli-template: mask-dipy -->
```bash
pipeline mask_dipy --targets validation --brain-mask-backend dipy --plan
```

<!-- cli-template: mask-mrtrix -->
```bash
pipeline mask_mrtrix --targets validation --brain-mask-backend mrtrix --plan
```

<!-- cli-template: mask-synthstrip -->
```bash
pipeline mask_synthstrip --targets validation --brain-mask-backend synthstrip \
  --postprocess-freesurfer-home "/path/to/freesurfer" --brain-mask-device auto --plan
```

可选的 DIPY 去噪、Gibbs 和运动校正：

<!-- cli-template: preproc-dipy -->
```bash
pipeline preproc_dipy --targets validation,preprocessing \
  --brain-mask-backend provided --preprocessing-backend dipy \
  --preprocessing-dipy-denoise-method mppca --plan
```

MRtrix/FSL 路线使用真实采集参数。下面的 `j-`、`0.05` 和反向相位编码 b0
仅为示例，必须按采集协议替换。

<!-- cli-template: preproc-fsl -->
```bash
pipeline preproc_fsl --targets validation,preprocessing \
  --brain-mask-backend provided --preprocessing-backend mrtrix_fsl \
  --preprocessing-phase-encoding-direction j- --preprocessing-readout-time 0.05 \
  --preprocessing-reverse-phase-b0 "/path/to/matched_reverse_b0.nii.gz" --plan
```

需要将校正后数据用于后续计算时，把下游 targets 放进**同一条命令**，例如
`validation,preprocessing,segmentation,parcellation,surface`。
独立的新运行不会仅凭早先存在的预处理结果就自动采用它；以计划/运行记录的实际输入路径为准。

---

## 解剖重建

需要匹配的模型资源和兼容 PyTorch。工作流自动处理共享原生 DTI 准备步骤。
按需要选择组织分割、脑区分区或皮层表面。

<!-- cli-template: anatomy-seg -->
```bash
pipeline ddseg --targets validation,segmentation --brain-mask-backend provided --plan
```

<!-- cli-template: anatomy-parcel -->
```bash
pipeline ddparcel --targets validation,parcellation --brain-mask-backend provided --plan
```

<!-- cli-template: anatomy-surface -->
```bash
pipeline ddsurfer --targets validation,surface --brain-mask-backend provided \
  --surface-device auto --surface-precision fp32 --plan
```

<!-- cli-template: anatomy-combined -->
```bash
pipeline anatomy --targets validation,segmentation,parcellation,surface \
  --brain-mask-backend provided --ddseg-device auto --surface-device auto --plan
```

表面重建加皮层后处理、厚度/曲率和图谱映射。配置许可组件运行包及个人激活文件；
该路线不强制安装完整版 FreeSurfer。

<!-- cli-template: anatomy-postprocess -->
```bash
pipeline anatomy_post --targets validation,segmentation,parcellation,surface,surface_postprocess \
  --brain-mask-backend provided --postprocess-mode whole \
  --postprocess-runtime "/path/to/verified/surface-components" \
  --postprocess-license-file "/path/to/personal/license.txt" --plan
```

复用已完成的原生表面时，通过 `--postprocess-native-dir`，以及需要时的
`--postprocess-mri-dir`，传入运行记录中的准确路径。参见[表面组件](SURFACE_COMPONENTS.zh-CN.md)。
不要把模板空间表面当成原生输入。

---

## 微结构

DTI 为默认项。可选 FW/NODDI/DKI 有各自的采样与拟合检查；NODDI 和 DKI 需要适用的多壳层数据。
检查适用性记录、有效体素掩膜和排除的拟合，不要用显示用图像替代有效性判断。

<!-- cli-template: micro-dti -->
```bash
pipeline dti --targets validation,microstructure --microstructure-stages dti \
  --brain-mask-backend provided --micro-fit-method wls --plan
```

明确使用轻量掩膜生成及 DTI：

<!-- cli-template: micro-dti-light -->
```bash
pipeline dti_light --targets validation,microstructure --microstructure-stages dti \
  --brain-mask-backend dipy --plan
```

<!-- cli-template: micro-fw -->
```bash
pipeline freewater --targets validation,microstructure \
  --microstructure-stages dti,freewater --brain-mask-backend provided --plan
```

<!-- cli-template: micro-noddi -->
```bash
pipeline noddi --targets validation,microstructure \
  --microstructure-stages dti,noddi --brain-mask-backend provided --plan
```

<!-- cli-template: micro-dki -->
```bash
pipeline dki_wls --targets validation,microstructure --microstructure-stages dti,dki \
  --dki-fit-method WLS --brain-mask-backend provided --plan
```

<!-- cli-template: micro-mkcurve -->
```bash
pipeline mkcurve --targets validation,microstructure --microstructure-stages dti,dki \
  --dki-fit-method MKCURVE --brain-mask-backend provided --plan
```

`MKCURVE` 是 Python 移植版，无需 MATLAB。`MKCURVE_MATLAB` 是另行配置路径的作者参考路线。

<!-- cli-template: micro-parallel -->
```bash
pipeline micro_multi --targets validation,microstructure \
  --microstructure-stages dti,freewater,noddi,dki --dki-fit-method WLS \
  --max-parallel-models 2 --brain-mask-backend provided --plan
```

最后一条明确请求四种模型。先完成共同前提，再并发适用且独立的可选拟合；这不是默认行为。

---

## 纤维追踪

DTI 确定性追踪使用 SlicerDMRI/原生 DTI 准备及 DIPY。
`--select-streamlines` 不等同于 UKF 的追踪预算。

<!-- cli-template: tract-dti -->
```bash
pipeline tracks_dti --targets validation,tractography --tractography-backend dti_det \
  --brain-mask-backend provided --select-streamlines 1000000 \
  --dti-min-length-mm 10 --dti-max-length-mm 250 --plan
```

UKF 自动调用已安装的 UKFTractography 扩展/CLI，并使用 SlicerDMRI。
采用作者默认参数，下面仅调整线程预算：

<!-- cli-template: tract-ukf -->
```bash
pipeline tracks_ukf --targets validation,tractography --tractography-backend ukf \
  --brain-mask-backend provided --ukf-parameters '{"numThreads":8}' --plan
```

CSD/ACT 需要 MRtrix 和兼容解剖输入，同时计算与流线匹配的 SIFT2 权重：

<!-- cli-template: tract-csd -->
```bash
pipeline tracks_csd --targets validation,segmentation,parcellation,tractography \
  --tractography-backend csd_act --brain-mask-backend provided \
  --select-streamlines 1000000 --tckgen-seeding dynamic --mrtrix-nthreads 8 --plan
```

SAF 使用 CSD 输入和通过检查的原生表面/后处理：

<!-- cli-template: tract-saf -->
```bash
pipeline tracks_saf --targets validation,segmentation,parcellation,surface,surface_postprocess,tractography \
  --tractography-backend saf --brain-mask-backend provided \
  --postprocess-runtime "/path/to/verified/surface-components" \
  --postprocess-license-file "/path/to/personal/license.txt" --plan
```

<!-- cli-template: tract-multiple -->
```bash
pipeline tracks_compare --targets validation,segmentation,parcellation,tractography \
  --tractography-backend csd_act,ukf --brain-mask-backend provided --plan
```

多追踪后端依次执行，各有 `<run>__<backend>` 记录，不合并流线。
MRtrix 可用 `--mrtrix-seed 42` 进行确定性对照，这会强制 `tckgen -nthreads 0`，可能变慢；
SIFT2 仍使用配置的线程数。种子不意味着其他后端也完全确定。

---

## 束分析和显式来源

以下示例自动生成 UKF 全脑流线。全脑输入、束分析方法和图谱/资源分别选择。

<!-- cli-template: bundle-wmql -->
```bash
pipeline bundles_wmql --targets validation,parcellation,tractography,bundles \
  --tractography-backend ukf --bundle-backend wmql --bundle-tractography-backend ukf \
  --wmql-query-preset official --brain-mask-backend provided --plan
```

官方 WMQL 规则默认执行全部输出查询；选择束子集示例：

<!-- cli-template: bundle-wmql-subset -->
```bash
pipeline bundles_wmql_subset --targets validation,parcellation,tractography,bundles \
  --tractography-backend ukf --bundle-backend wmql --bundle-tractography-backend ukf \
  --wmql-query-selection AF,CST,UF,cc_4 --brain-mask-backend provided --plan
```

<!-- cli-template: bundle-wma -->
```bash
pipeline bundles_wma --targets validation,tractography,bundles \
  --tractography-backend ukf --bundle-backend wma --bundle-tractography-backend ukf \
  --slicer-executable "$SLICER" --brain-mask-backend provided --plan
```

<!-- cli-template: bundle-tractcloud -->
```bash
pipeline bundles_tractcloud --targets validation,tractography,bundles \
  --tractography-backend ukf --bundle-backend tractcloud --bundle-tractography-backend ukf \
  --tractcloud-device auto --tractcloud-batch-size 2048 --brain-mask-backend provided --plan
```

<!-- cli-template: bundle-multiple -->
```bash
pipeline bundles_compare --targets validation,parcellation,tractography,bundles \
  --tractography-backend csd_act,ukf --bundle-backend wmql,wma,tractcloud \
  --bundle-tractography-backend ukf --slicer-executable "$SLICER" \
  --brain-mask-backend provided --plan
```

最后一条的全部束方法都使用 UKF；独立 CSD 路线不接收束分析任务。
比较其他来源时改 `--bundle-tractography-backend`，并使用新运行名。
非 UKF 来源的 WMA 覆盖率需单独检查。稀疏/空束保留在 QC 中；SAF 不作为全脑束分析来源。

复用已有兼容全脑 VTK/VTP 输入：

<!-- cli-template: bundle-existing -->
```bash
pipeline wma_existing --targets validation,bundles --bundle-backend wma \
  --wma-input-tractography "/path/to/reviewed_whole_brain.vtp" \
  --slicer-executable "$SLICER" --brain-mask-backend provided --plan
```

显式 WMA/TractCloud 输入文件不可与 `--bundle-tractography-backend` 同时指定。
使用完整定量流线，不能用经过数量裁剪的场景预览替代；检查坐标与协议兼容性。

---

## 连接组和组合路线

DTI 流线加 Python 计数/标量加权连接组：

<!-- cli-template: connectome-python -->
```bash
pipeline connectome_python --targets validation,microstructure,parcellation,tractography,connectome \
  --tractography-backend dti_det --connectome-backend python \
  --brain-mask-backend provided --plan
```

CSD/ACT 加匹配的 SIFT2 权重和 MRtrix 连接组：

<!-- cli-template: connectome-sift2 -->
```bash
pipeline connectome_sift2 --targets validation,segmentation,parcellation,tractography,connectome \
  --tractography-backend csd_act --connectome-backend mrtrix \
  --brain-mask-backend provided --select-streamlines 1000000 --plan
```

解剖、微结构、UKF、WMQL 与 Python 连接组组合路线：

<!-- cli-template: combined -->
```bash
pipeline combined --targets validation,microstructure,segmentation,parcellation,surface,tractography,bundles,connectome \
  --microstructure-stages dti --tractography-backend ukf --bundle-backend wmql \
  --bundle-tractography-backend ukf --connectome-backend python \
  --brain-mask-backend provided --plan
```

需要预处理时，在同一条命令 targets 中加 `preprocessing`，并配置后端/采集参数。
后处理和可选微结构模型仍需明确选择，本组合不会隐含运行它们。

---

## 多被试和参数实验

每名已准备被试使用同一配置；根据总 RAM/显存需求，从一到两个并发被试开始。
默认生成计划，加 `--execute` 才执行计算。未指定 `--continue-on-error` 时，
一次失败后停止提交新任务，等待已运行任务结束。

<!-- cli-template: cohort -->
```bash
"$SLICER" --launch PythonSlicer "$REPO/scripts/run_batch_pipeline.py" \
  --batch-root "/path/to/prepared_study" --output-root "/path/to/cohort_results" \
  --run-name cohort_dti --jobs 2 --no-user-config --strict-environment \
  --targets validation,microstructure --microstructure-stages dti --brain-mask-backend provided
```

命名参数组合参见[实验请求示例](examples/dti_experiments.json)。替换其中的绝对路径，
JSON 不展开 `$VARIABLES`。使用新的实验输出目录；所有组合先校验再提交，
分别保存输出并记录失败和未启动的任务。
需要时在请求的 `base_args` 中设置共用的显式依赖路径（例如 `--model-assets-dir`）。
`options` 和每个组合的 `args` 用于科学参数，身份、输出路径和执行模式由调度器管理。

<!-- cli-template: experiments -->
```bash
"$SLICER" --launch PythonSlicer "$REPO/scripts/run_experiments.py" \
  --request "/path/to/edited_experiment_request.json"
```

加 `--execute` 才执行。一个被试的不同组合串行，被试间可以并发。
GUI **高级设置 > 实验与批处理** 支持相同请求。被试并发数 `--jobs`
与单被试模型并发数 `--max-parallel-models` 是两个层级，资源占用可能相乘。
详见[批量实验](EXPERIMENTS.zh-CN.md)。

---

## 脑区分析和报告

已完成的单被试运行使用其记录路径，不扫描公共输出目录。
上述封装把元数据写到 `$OUTPUTS/<run>/00_run_metadata/<run>_orchestration_manifest.json`。
多追踪变体和实验各有子运行记录。

<!-- cli-template: region-inspect -->
```bash
"$SLICER" --launch PythonSlicer "$REPO/scripts/analyze_regions.py" \
  --inspect "/path/to/run_orchestration_manifest.json" --catalog "/path/to/region_catalog.json"
```

从目录清单中选择真实 label ID 和 metric/task key，修改[脑区请求](examples/region_request.json)。
使用新的输出目录，检查请求后执行：

<!-- cli-template: region-run -->
```bash
"$SLICER" --launch PythonSlicer "$REPO/scripts/analyze_regions.py" \
  --request "/path/to/edited_region_request.json"
```

脑区分析复用适用的参数图、完整流线和矩阵，不重新拟合模型；
图谱中不存在的脑区、失败或过时来源会被拒绝。

<!-- cli-template: report -->
```bash
"$SLICER" --launch PythonSlicer "$REPO/scripts/generate_subject_report.py" \
  --subject-root "$SUBJECT" --output-root "$OUTPUTS/dti" --run-name dti \
  --manifest "$OUTPUTS/dti/00_run_metadata/dti_orchestration_manifest.json"
```

检查任务状态、QC、排除的拟合数、束覆盖率和声明的输出签名。
在 **结果与 QC** 中选择相应运行并加载/复用节点。CLI 不直接修改已打开的 Slicer 场景；
重新生成报告不会将失败 QC 改为通过。

---

## 原生 PowerShell

参数使用数组，不直接复制 Bash 的续行符和 JSON 引号写法。
PNL、MRtrix/FSL、SAF 和原生表面后处理需先核对平台支持。

<!-- cli-setup: powershell -->
```powershell
$Slicer = 'C:\Apps\Slicer\Slicer.exe'
$Repo = 'C:\work\SlicerDSpace'
$Subject = 'D:\study\sub-01'
$SubjectId = 'sub-01'
$Outputs = 'D:\analysis\sub-01'
$Assets = 'D:\SlicerDDSurfer-models'
$DependencyArgs = @()
# $DependencyArgs = @('--dependency-config', 'D:\configs\dependencies.json')

function Invoke-DDSurfer {
    param([string]$Run, [string[]]$RouteArgs)
    & $Slicer --launch PythonSlicer "$Repo\shared\run_subject_pipeline_cli.py" `
        --no-user-config --strict-environment `
        --subject-root $Subject --subject-id $SubjectId `
        --output-root (Join-Path $Outputs $Run) --run-name $Run `
        --model-assets-dir $Assets @DependencyArgs @RouteArgs
    if ($LASTEXITCODE -ne 0) { throw "SlicerDSpace exited with $LASTEXITCODE" }
}

Invoke-DDSurfer -Run 'dti_light' -RouteArgs @(
    '--targets', 'validation,microstructure', '--microstructure-stages', 'dti',
    '--brain-mask-backend', 'dipy', '--plan'
)
```

---

## 复用、取消和帮助

默认可复用匹配的已完成结果；比较方法时用新的运行名/输出路径。
`--no-resume` 请求重算，不消除 QC 失败。不要把删缓存或调低科学阈值当作通用修复。
GUI 取消只停止所属任务树；Agent/终端应保留自己启动的进程/进程组句柄，
先等待清理，避免终止其他 Slicer/Python 会话。

选项有差异时，以**已安装版本**的帮助为准：

```bash
"$SLICER" --launch PythonSlicer "$REPO/shared/run_subject_pipeline_cli.py" --help
"$SLICER" --launch PythonSlicer "$REPO/scripts/prepare_inputs.py" --help
"$SLICER" --launch PythonSlicer "$REPO/scripts/run_batch_pipeline.py" --help
```

本页标记的模板由本地回归测试读取并检查参数及路线选择；这不代替每条路线的真实数据验收。
