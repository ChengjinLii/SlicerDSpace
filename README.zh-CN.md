# SlicerDDSurfer（中文版）

SlicerDDSurfer 是一个 3D Slicer 扩展模块，整合了多条基于扩散 MRI 的流程：

- **DDSurfer**：根据 DTI 标量图生成 WM / Pial 皮层表面。
- **DDParcel**：101 脑区分割（基于 DTI 特征）。
- **DDSeg**：WM/GM/CSF 分割（多视角 CNN）。
- **Microstructure**：FA/MD、ROI-wise 统计、Free Water、AMICO NODDI。
- **Tractography**：DTI tracking、MRtrix CSD/FOD/ACT、WMQL bundles、WMA、TractCloud wrapper 和 SAF 短联合纤维。
- **Connectome**：基于 tractography + DDParcel 的 streamline-count、SIFT2、length 和标量加权连接矩阵。
- **Surface post-process**：内置 DDSurfer 后处理后端，用于生成 FreeSurfer 风格的 surf/label/stats 结果。

**外部环境与本地配置说明：** [EXTERNAL_DEPENDENCIES.md](EXTERNAL_DEPENDENCIES.md)

**Release-candidate 安装/运行验证：** [RELEASE_CANDIDATE_VALIDATION.md](RELEASE_CANDIDATE_VALIDATION.md)

Slicer UI 和 CLI 都支持外部依赖路径覆盖：Slicer 中在 `Environment & Dependencies` 里设置，并可导入/导出与 CLI 兼容的 JSON 配置；命令行使用对应路径参数，或用 `--dependency-config` / `--save-dependency-config` 复用配置。

每次统一 orchestrator run 结束会自动写：
- `outputs/00_run_metadata/<run_name>_orchestration_manifest.json`
- `outputs/00_run_metadata/output_tree_audit.json`
- `outputs/06_slicer_scene_report/report.html`
- `outputs/06_slicer_scene_report/provenance.json`
- `outputs/06_slicer_scene_report/qc_summary.json`

提交/发布前建议先跑：

```bash
python3 scripts/release_audit.py
```

---

## 统一命令入口

现在推荐通过仓库根目录的统一 CLI 运行：

首次运行或换机器时，先做环境体检：

```bash
python3 run_subject_pipeline.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307 \
  --targets microstructure,tractography,bundles,connectome \
  --microstructure-stages dti \
  --tractography-backend csd_act \
  --bundle-backend wmql \
  --doctor
```

体检会提示当前环境能跑什么、缺什么，并在 `outputs/00_run_metadata/environment/` 写出 Python 安装脚本和外部软件安装说明。完整依赖策略见 [EXTERNAL_DEPENDENCIES.md](EXTERNAL_DEPENDENCIES.md)。

正式执行时，环境 preflight 是按 target 判断的。默认情况下，缺某个可选后端依赖只会 block 受影响的 target，其他依赖齐备的 target 仍会继续运行；blocked target 会写入 orchestration manifest 并记录原因。如果希望任何 selected target 缺依赖都直接中止整次运行，再加 `--strict-environment`。

执行前也可以先生成 target-level run plan：

```bash
python3 run_subject_pipeline.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307 \
  --targets validation,preprocessing,microstructure,tractography,bundles,connectome \
  --microstructure-stages all \
  --bundle-backend all \
  --plan
```

`run_plan.json` 会区分 `will_run`、`skipped`、`blocked`，并把 blocker 分成 `environment`、`data`、`upstream`、`configuration` 等类别。真正运行后，每个 task 还会在 `outputs/00_run_metadata/tasks/<run_name>/<task>/` 下写统一 schema 的 `manifest.json`、`qc.json` 和 `logs/`。
每次 orchestrator run 结束也会写 `outputs/00_run_metadata/output_tree_audit.json`，用于检查 canonical 输出树是否有缺失目录、legacy 顶层输出或异常嵌套。

Slicer UI 中的 `Run Plan & Progress` 面板会在点击 Run 后显示 target 表格；运行中显示当前步骤摘要，运行结束后显示 `completed` / `skipped` / `blocked` / `failed`，并可双击 manifest、QC、logs 路径打开对应文件或目录。
UI 端真正执行 pipeline 时使用后台 `QProcess` 调统一 CLI，不在 Slicer 主线程里直接跑长算法；运行中可以点 `Cancel running job` 停止后台进程，并写 `*_cancelled_orchestration_manifest.json`。

```bash
cd /data/chengjin/SlicerDDSurfer
python3 run_subject_pipeline.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307 \
  --subject-id 100307 \
  --all \
  --execute \
  --preprocessing-backend dipy \
  --tractography-backend csd_act \
  --connectome-backend mrtrix \
  --select-streamlines 100000 \
  --compress-mrtrix-dense
```

这条命令的设计目标就是：**尽量一次生成完整输出文件树**。默认输出到：

```text
<subject-root>/outputs/
```

如果你想只跑一部分，可以用：

```bash
python3 run_subject_pipeline.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307 \
  --targets microstructure,tractography,connectome \
  --skip-targets bundles \
  --tractography-backend dti_det
```

常用开关：
- `--all`：跑完整产品树
- `--targets ...`：只跑指定产品
- `--skip-targets ...`：显式跳过某些产品
- `--execute`：真正执行；不加时只是 dry-run 规划
- `--plan`：只生成环境 preflight + target run plan，不执行算法
- `--no-resume`：关闭已有结果复用
- `--preprocessing-backend dipy|mrtrix_fsl`
- `--preprocessing-force`
- `--output-root ...`：把输出写到自定义目录
- `--microstructure-stages dti|dti,freewater|dti,freewater,noddi|all`
- `--tractography-backend csd_act|dti_det|saf`
- `--bundle-backend wmql|wma|tractcloud|all`
- `--connectome-backend python|mrtrix`
- `--run-free-water` / `--run-noddi`：旧兼容参数，等价于在 `--microstructure-stages` 中加入对应 stage
- `--targets saf,wma,tractcloud`：旧兼容用法；新用法建议通过 `--tractography-backend saf` 和 `--bundle-backend ...` 自动展开
- `--wma-input-tractography` / `--wma-atlas-dir` / `--wma-root`
- `--tractcloud-input-tractography` / `--tractcloud-root`
- `--saf-fs-dir` / `--saf-pregenerated-tractogram`
- `--saf-noregister` / `--saf-register`：SAF 默认不做配准，默认复用 DDSurfer postprocess surface、CSD/FOD 和 brain mask seed；需要 ANTs/FA 注册时显式传 `--saf-register`

当前如果不显式传 `--targets`，默认会规划：
- `preprocessing`
- `microstructure`
- `tractography`
- `bundles`
- `connectome`

`resume` 行为默认开启。统一命令会先扫描每个算法对应的核心产物和 QC/manifest：
- 如果核心结果已存在且 QC 为 `completed`，会自动 `skipped`
- 如果结果不完整，会继续执行或标记 `blocked`
- 用 `--no-resume` 可以强制不复用已有结果

100307 回归命令：

```bash
PYTHON_BIN="/data/chengjin/software/run-slicer.sh --launch PythonSlicer" \
  scripts/run_100307_regression.sh
```

该脚本会检查输入文件树、生成 run plan、执行统一 pipeline、重复运行一次验证 resume、检查 canonical output tree，并确认每个 task 的 normalized manifest/QC/logs 都存在。若只想看 plan，可加 `DRY_RUN=1`。

如果本机已有 MRtrix3 和 TractQuerier，可做完整环境 resume smoke：

```bash
python3 run_subject_pipeline.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307 \
  --subject-id 100307 \
  --targets validation,preprocessing,segmentation,parcellation,surface,microstructure,tractography,bundles,connectome \
  --tractography-backend saf \
  --bundle-backend all \
  --microstructure-stages all \
  --run-name csd_act \
  --mrtrix-bin-dir /data/chengjin/software/mrtrix3_env/bin \
  --tract-querier-root /data/chengjin/SlicerDDSurfer/third_party/tract_querier \
  --execute \
  --print-manifest-only
```

该命令会验证 `SAF`、`WMQL/WMA/TractCloud`、`DTI/Free Water/NODDI` 的统一展开、resume 和 blocked 规则。已有结果会通过 resume 复用；未配置的 optional backend 会单独 `blocked`，不会影响其他 target。

---

## 代码结构

```
SlicerDDSurfer.py              # Slicer ScriptedLoadableModule 入口
CMakeLists.txt
Resources/
  Icons/                        # 模块图标
  UI/                           # SlicerDDSurfer 的 .ui 文件
  Data/
    ckpts/                      # DDSurfer 模型权重（LFS）
    template/                   # DDSurfer 模板

# 最终产品层目录

shared/                       # shared subject-root / DTI / 配准缓存
surface/                      # DDSurfer 预处理 / 预测 / 后处理
parcellation/                 # DDParcel 流程、conversion、data loader、weights
segmentation/                 # DDSeg 包、runner、weights
microstructure/               # FA/MD、ROI-wise 统计、Free Water、NODDI
tractography/                 # DTI、ACT、WMA scaffolds 与规划中的 CSD workflows
connectome/                   # Tractography + DDParcel connectome planning/execution
workflow_catalog.py           # 产品分层与导航元数据
PRODUCT_ARCHITECTURE.md       # 产品层结构说明

surface/ddsurfer_postprocess_release/  # 内置 DDSurfer 后处理后端
```

---

## Slicer 主模块（SlicerDDSurfer.py）

### UI 与导航
- 当前 Slicer UI 围绕统一 `Subject root` 和 `Output directory` 组织。
- 用户只选择目标产品和少量运行参数：`run_name`、tractography backend、bundle backend、microstructure stages、streamlines。
- 外部依赖路径集中在 `Environment & Dependencies`，支持导入/导出 JSON 配置。

### 参数节点
`SlicerDDSurferParameterNode` 保存全部 UI 状态：
- DDSurfer 输入/输出
- DDParcel 输入/输出/Atlas
- DDSeg 输入/权重/设备
- DDSurfer Post-process 参数

### 运行逻辑
- 执行前做依赖 preflight；缺可选后端时只 block 对应 target，其他可运行 target 继续执行
- 用户确认后只自动安装 Python 包到当前 Slicer Python；MRtrix3/FSL/FreeSurfer/WMA/TractCloud 等外部工具只生成安装说明
- 每个 task 写统一 manifest/QC/logs，同时生成 subject-level HTML/provenance/QC summary
- 运行结束后自动加载关键 volume、surface、table 和 tractography bundle；缺 SlicerDMRI loader 时跳过 fiber 加载并记录日志

---

## Surface（`surface/`）

### 1) 预处理（preprocessing.py）
- 复制/标准化 DTI 指标
- mask skull-strip
- resample 到 template
- z-score 标准化
- 输出：`preprocessed/<subject>/` 等

### 2) 预测（prediction.py）
- TANet 模型推理 white/pial
- 160k 初始化模板网格
- Taubin 平滑
- 输出 STL meshes

### 3) 后处理（postprocessing.py）
- 把 mesh 从模板空间映射回原始空间
- SimpleITK + 变换

---

## Parcellation（`parcellation/`）

入口：`parcellation.pipeline.run_ddparcel`

主要步骤：
- NIfTI → NHDR
- DTI 特征提取
- Atlas 配准 + normalize
- DDSurfer_Pred 推理 parcellation

输入结构：
```
<T1w>/Diffusion/
  data.nii.gz
  bvals
  bvecs
  nodif_brain_mask.nii.gz
```

输出：
- Reg / Norm DTI
- DDSurfer-wmparc
- 分区图谱

---

## 输入验证（`shared.validation`）

入口：`shared.validate_subject_inputs`

已实现检查：
- subject-root 必需文件：`input/data.nii.gz`、`input/bvals`、`input/bvecs`、`input/nodif_brain_mask.nii.gz`
- 从 BIDS sidecar（例如 `input/data.json`）读取相位编码方向和读出时间
- bval/bvec 解析、形状检查、b0 数量、shell 汇总、b-vector norm 合理性检查
- 按 workflow group 检查 Python 模块和外部命令依赖
- 在 `outputs/validation/` 写出轻量 QC JSON 报告
- 主 GUI 的 `Validate` 按钮已接入该 shared validation；subject-root 输入会写出 QC report 并记录到日志，不自动安装依赖

100307 smoke 命令：
```bash
python3 Testing/Python/run_input_validation_smoke.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307 \
  --subject-id 100307
```

---

## Segmentation（`segmentation/`）

入口：`segmentation.pipeline::run_ddseg`

流程：
- Slicer CLI DTI 特征提取
- 多视角预测 + 融合
- 输出分割与概率图

输出：
- SegmentationMap_GMWMCSF.nii.gz
- ProbabilisticMap_GM/WN/CSF.nii.gz

---

## Microstructure（`microstructure/`）

入口：`microstructure.pipeline::run_microstructure`

流程：
- 复用 shared native DTI cache 导出 FA/MD
- 用 DIPY 做 Free Water
- 用 AMICO 做 NODDI
- 输出 ROI-wise CSV / JSON

输出：
- FA / MD
- Free Water fraction / tissue FA / tissue MD
- NODDI NDI / ODI / FWF
- ROI-wise microstructure 表

---

## Tractography（`tractography/`）

当前入口：`tractography.run_dti_tracking`、`tractography.run_act_tracking`、`tractography.pipeline.run_wma_org_atlas_pipeline` 和 `tractography.wma.run_wma_org_atlas`

已实现 scaffold：
- 从 `subject_root/input` 准备 DTI tractography manifest 和 QC 占位输出
- 扫描 `cache/native_dti/<fit_method>`，记录 FA/MD/DTI cache 是否可复用
- 固定输出到 `outputs/tractography/`，默认不启动长时间 tracking
- 准备 ACT manifest/QC，按可选 MRtrix3 后端处理
- 构造 MRtrix3 ACT 命令链（`mrconvert`、`dwi2response`、`dwi2fod`、`tckgen`、`tcksift2`），在外部输入齐备时可执行
- 记录 DDParcel/parcellation 作为节点依赖，并检查标准 ACT 所需 5TT/GMWMI
- 不把 DDParcel 本身等同于完整 ACT tissue model
- 将 WMA ORG atlas clustering 包装为可选外部后端
- 通过显式 `wma_root`、`SLICERDDSURFER_WMA_ROOT`、`WMA_ROOT` 或 `PATH` 上的 `wm_apply_ORG_atlas_to_subject.sh` 发现 WMA
- 写出 `wma_org_atlas_manifest.json`
- 写出 `wma_org_atlas_qc.json`，包含后端状态、atlas 结构状态、返回码、运行时间和输出摘要
- 检查 ORG atlas 必需目录：`ORG-RegAtlas-100HCP` 和 `ORG-800FC-100HCP`
- 默认 dry-run；真实运行需要 `execute=True`，并提供有效的 VTK/VTP tractography 和 ORG atlas 路径

后续规划：
- CSD tractography
- 接入 MRtrix3 命令、5TT/GMWMI 生成和小数据验证后再启用真实 ACT

100307 smoke 命令：
```bash
python3 Testing/Python/run_tractography_dti_smoke.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307 \
  --subject-id 100307 \
  --require-native-cache
```

WMA backend / atlas smoke 命令：
```bash
python3 Testing/Python/run_wma_org_atlas_smoke.py \
  --subject-id 100307 \
  --input-tractography /path/to/subject.vtk \
  --atlas-dir /path/to/ORG-Atlases \
  --output-dir /path/to/wma-output \
  --slicer-executable /path/to/Slicer \
  --wma-root /path/to/whitematteranalysis
```

已复制 fixture 检查命令：
```bash
python3 Testing/Python/run_wma_149741_fixture_smoke.py
```

已复制的 WMA-ready tractography fixture：
`/data/chengjin/SlicerDDSurfer-test/149741_wma_act/tractography/149741_ukf_pp_downsampled.vtk`。
完整 WMA clustering 仍需要显式外部 WMA 后端和 ORG atlas 目录。

## Connectome（`connectome/`）

当前入口：`connectome.run_connectome`。

已实现：
- 需要 tractography 文件（`.trk`、`.tck`、`.vtk` 或 `.vtp`）和 DDParcel/parcellation label map。
- 写出 matrix CSV header、nodes TSV header、manifest 和 QC JSON。
- `.tck` 输入可在 MRtrix3 `tck2connectome` 可用时执行。
- `.trk`/`.tck` 和 legacy `.vtk` 支持 Python endpoint-label assignment；`.vtp` 还需要可选 `vtk` Python 模块。
- 默认 dry-run；未请求执行时只做计划和依赖记录。

149741 已复制 fixture 的 connectome 验证命令：
```bash
python3 Testing/Python/run_connectome_149741_smoke.py --execute
```

ACT MRtrix planning smoke：
```bash
python3 Testing/Python/run_act_mrtrix_smoke.py \
  --subject-id 149741 \
  --parcellation-path /data/chengjin/SlicerDDSurfer-test/149741_wma_act/parcellation/wmparc.nii.gz \
  --output-dir /data/chengjin/SlicerDDSurfer-test/149741_wma_act/outputs/act_smoke
```

---

## Docker Post-process

`run_postprocess_docker.py`：
- 整理 DDSurfer 输出
- 调用 postprocess-release docker/run_container.sh

必需输入：
- brain.mgz
- DDSurfer-wmparc.nii.gz
- native STL meshes

---

## 权重（Git LFS）

- `Resources/Data/ckpts/hcp/*.pt`
- `parcellation/weights/*.pkl`
- `segmentation/weights/*.pt`

获取方式：
```bash
git lfs install
git lfs pull
```

---

## 依赖

- 3D Slicer
- PyTorch Extension
- Python packages: nibabel, SimpleITK, trimesh, tqdm, networkx
- Docker + FreeSurfer license（后处理）

这里只是最小摘要。完整的可选后端依赖、环境变量和按 target 划分的安装说明见
[EXTERNAL_DEPENDENCIES.md](EXTERNAL_DEPENDENCIES.md)。

---

## 备注

- DDSurfer 需要 DTI 指标 + mask + 变换矩阵。
- DDParcel/DDSeg 依赖 Slicer 的 DTI 特征提取。
- 产品层结构说明见 [PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md)。
