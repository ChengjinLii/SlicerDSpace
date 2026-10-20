<div align="center">

# SlicerDDSurfer

**3D Slicer 中的扩散 MRI 分析工作流**

[![CI (main)](https://github.com/ChengjinLii/SlicerDDSurfer/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/ChengjinLii/SlicerDDSurfer/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![License](https://img.shields.io/badge/License-BSD--3--Clause-4D7587)](LICENSE.txt)
[![Slicer](https://img.shields.io/badge/3D_Slicer-5.10-58728B)](https://www.slicer.org/)

[概览](#概览) | [安装](#安装) | [快速开始](#快速开始) | [文档](docs/README.zh-CN.md) | [验证状态](#验证与发布状态) | [引用](#引用) | [English](README.md)

[项目网站](https://chengjinlii.github.io/SlicerDDSurfer/) | [网站发布与贡献记录](https://github.com/ChengjinLii/SlicerDDSurfer/blob/main/docs/website/README.zh-CN.md)

</div>

SlicerDDSurfer 在一个 Slicer 模块中组织扩散 MRI 解剖重建、微结构定量和白质
连接分析。选择所需产品，执行可追溯工作流，再查看影像、QC 报告和运行记录。

**科研软件。** 当前为私有预发布项目，尚未通过官方 Extensions Catalog 分发。
任务完成不等于科学结果正确，也不构成临床诊断依据。

---

## 概览

| 工作流 | 主要结果 | 主要前提 |
| --- | --- | --- |
| 输入准备 | DICOM/NIfTI/NRRD 导入、梯度检查、可选掩膜生成与预处理 | 对应导入或预处理后端 |
| 解剖重建 | DDSeg 组织分割、DDParcel 脑区、DDSurfer 白质与软脑膜表面 | 匹配的模型资源；所选路线需要 PyTorch/SlicerDMRI |
| 微结构分析 | DTI FA/MD/AD/RD、可选 Free-water/NODDI/DKI、区域统计 | 对应依赖和采集适用性检查 |
| 白质通路 | DTI/CSD、ACT/SIFT2、SAF、WMQL/WMA/TractCloud | 对应外部工具及资源 |
| 结构连接组 | 区域矩阵、场景检查、QC 与溯源记录 | 空间一致的分区和流线；SIFT2 路线还需权重 |

只安装**当前所选路线**需要的依赖，不要求首次安装全部外部工具。
MRtrix3、FSL、FreeSurfer 和高级白质束后端均为按需配置，不会静默安装。
详见[能力与平台矩阵](docs/setup/SUPPORT_MATRIX.zh-CN.md)。

**实现来源。** DDSeg 为 MATLAB 到 Python/PyTorch 的改写；SAF、MK-Curve
为原作者 MATLAB 算法的非官方 Python 移植。PNL CNN 掩膜调用已有的官方
Python 后端，不是重写整套 PNLpipeline。见[实现来源与验证边界](docs/architecture/IMPLEMENTATION_PROVENANCE.zh-CN.md)。

---

## 安装

仓库保持私有，请使用已有访问权限的 checkout。以下是**源码 staging 安装**，
不是经过官方 SDK/CPack 验收的扩展包：

```bash
git clone https://github.com/ChengjinLii/SlicerDDSurfer.git
cd SlicerDDSurfer
python3 scripts/stage_slicer_extension.py \
  --install-root ~/SlicerDDSurfer-extension --link-mode copy --clean
```

在 **Edit > Application Settings > Modules** 中，将
`~/SlicerDDSurfer-extension/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules`
展开为绝对路径后加入 **Additional module paths**，重启 Slicer。
若使用其他 Slicer 版本，staging 时设置实际的 `--slicer-version`。
本地 GUI 验证使用 Slicer 5.10。更新代码后需重新 staging 并重启。

按路线从 Extension Manager 安装 **SlicerDMRI** 和 **PyTorch**。
模型与代码分开存放，在 **高级设置 > 环境与模型** 中设置可写的资源目录。
先阅读[资源使用与再分发状态](docs/assets/MODEL_ASSET_TERMS.md)，再下载所需 profile：

```bash
python3 scripts/download_model_assets.py --profile surface \
  --asset-root ~/SlicerDDSurfer-model-assets --source url \
  --source-id slicerdsurfer_models_git
```

完整解剖资源可用 `scripts/download_model_assets.sh --profile core`。
文件可下载、SHA256 正确，不代表已获得公开再分发授权。
详见[模型资源](docs/assets/MODEL_ASSETS.md)与[依赖设置](docs/assets/DEPENDENCY_SETUP_WORKFLOW.md)。

---

## 快速开始

1. 在模块选择器打开 **SlicerDDSurfer**，在标题栏选择中文或英文。
2. 填写 **Subject ID**、**Subject root**，可另选 **Output directory**。
3. 仅勾选本次需要的分析产品。
4. 展开 **高级设置**，设置分析路线、依赖和模型；运行前检查环境。
5. 点击 **Run SlicerDDSurfer**。输入不全会显示红色提示，按日志修正后重试。
6. 成功阶段的关键结果会自动进入当前场景；在 **高级设置 > 结果与 QC** 检查 QC，并按需复用、替换或清除本次加载。

默认界面不显示 Beginner 区，也不自动弹出首次向导。
DICOM/NRRD 等格式转换位于 **高级设置 > 输入导入 / 转换**；
已经准备好的输入无需重复转换。

**高级设置 > 脑区分析（可选）** 可按名称或 ID 选择 DDParcel 脑区，复用已完成的
参数图、完整流线和连接矩阵，计算区域统计、筛选相关流线、导出局部连接。
默认不运行，不重新拟合模型。详见[脑区分析指南](docs/setup/REGIONAL_ANALYSIS.zh-CN.md)。

```text
sub-01/
  input/
    data.nii.gz
    bvals
    bvecs
    nodif_brain_mask.nii.gz   # 可选；生成掩膜需要支持的后端
```

DWI 与掩膜须在同一体素网格，梯度数量须与 DWI 测量一致。
运动校正后的 DWI 必须配套旋转更新后的梯度。
已有输入掩膜会保留；需要生成掩膜时，默认采用 **PNL diffusion CNN**，
不是执行整套 PNL 预处理。在高级设置配置独立 Python、模型与 ANTs 环境，
也可在 **分析参数** 中改选 SynthStrip、MRtrix 或仅使用已有掩膜。
依赖不足会明确提示，不会静默换算法。详见[掩膜设置](docs/setup/brain_mask_gui_config.md)。

微结构**默认仅运行 DTI**，FW、NODDI、DKI 在高级设置分别启用。
DKI 在拟合前检查 b0、非零壳层、梯度方向和设计矩阵秩。
**MK-Curve** 使用内置的作者算法 Python 移植版，不需要 MATLAB；与 DIPY WLS/OLS 是不同路线。
MATLAB 仅保留为可选对照后端，不能把普通 MK 图称为 MK-Curve。详见[微结构说明](docs/setup/MICROSTRUCTURE.zh-CN.md)。
自动显示流线时生成限量 VTK 预览，原始 TCK/TRK 不变；预览不用于定量分析。
追踪默认 CSD/ACT；可在高级设置选择 **UKFTractography**，自动调用已安装的
官方扩展并将流线传给 WMA，不复制 UKF 源码。参数采用作者默认值并可展开修改；
UKF 不套用 CSD 目标流线数。详见 [UKF 接入与默认参数](docs/setup/UKF.zh-CN.md)。
[最小 DTI 教程](docs/setup/QUICKSTART.zh-CN.md)包含明确标识的合成安装测试；
合成数据不是人体科研示例。

---

## 文档

| 任务 | 入口 |
| --- | --- |
| 首次工作流 | [快速开始](docs/setup/QUICKSTART.zh-CN.md) |
| 平台与依赖 | [能力矩阵](docs/setup/SUPPORT_MATRIX.zh-CN.md) · [Linux](docs/setup/LINUX_HPC.md) · [Windows](docs/setup/WINDOWS.md) · [macOS](docs/setup/MACOS.md) |
| 模型资源 | [资源配置](docs/assets/MODEL_ASSETS.md) · [授权状态](docs/assets/MODEL_ASSET_TERMS.md) |
| 结果、取消和 QC | [结果检查](docs/setup/GUI_RESULT_REVIEW.md) |
| GUI/CLI 共用配置 | [配置](docs/setup/USER_CONFIG.md) |
| 源码组织 | [目录结构](docs/architecture/REPOSITORY_LAYOUT.md) |
| 维护者发布验收 | [扩展准备状态](docs/release/EXTENSION_READINESS.zh-CN.md) · [发布流程](docs/release/RELEASE.md) |

只检查环境，不执行算法：

```bash
python3 run_subject_pipeline.py --subject-root /path/to/sub-01 \
  --targets validation,microstructure --microstructure-stages dti --doctor
```

将 `--doctor` 换成 `--plan` 可保存运行计划。
需要 Slicer CLI 模块的执行路线必须使用 Slicer 或其 `PythonSlicer`。

---

## 验证与发布状态

Linux 真实数据与 GUI 验证见[验收记录](docs/release/SLICER_ACCEPTANCE_20261007.md)，
简洁界面另有 [UI 验证记录](docs/release/UI_SIMPLIFICATION_20261008.md)。
这些记录仅覆盖对应代码快照、路线和数据，不代表所有配置均已通过。

[10 月 17 日根因与一次运行队列验收](docs/release/WORKFLOW_GENERALIZATION_20261017.zh-CN.md)
说明 WMQL 默认 `ddparcel_act` 兼容协议（原 DDParcel AF 端点候选＋作者 CST 穿行规则）、
WMA 逐束采样门禁及 MK-Curve 逐指标有效性。它不是完整作者 AF/CST 复现；高级选项仍可
选择 `author` 或 `published_endpoints`。多被试新协议验收仍在运行，不能据此宣称所有结果通过。

[10 月 16 日复核](docs/release/QC_FOLLOWUP_20261016.zh-CN.md)记录新版 CSD／WMA
检查、真实 Linux SDK／CPack 安装验收，以及仍失败的 WMQL 采样和人审边界。
CI 徽章跟踪 main 的 push 检查；
私有仓库的徽章不能供外部公开访问，请以登录后的 Actions 结果为准。

- CMake 与 staging 共用一份运行资源清单，安装包检查核对文件和源文件哈希。
- 快速 CI 和本地安装测试不能替代真实 SDK/CTest/CPack 构建。
- Linux SDK／CPack、隔离 Extension Manager 安装及限定的 DTI 缓存／束加载已通过；不等于空白机器上的完整科学流程验收。
- 尚未认证 Windows/macOS 原生科学工作流或三平台 SDK 构建。
- Extension Index JSON 是 **Tier 1 申请草稿**，不是官方已收录状态。
- 已补齐的第三方源码许可证不等于完整授权清理；仓库公开和模型再分发审查仍是独立门禁。

开发检查可运行 `make test-fast` 与
`python3 scripts/audit_slicer_extension_metadata.py --json`。
SDK 与独立干净安装验收详见[扩展准备状态](docs/release/EXTENSION_READINESS.zh-CN.md)。

---

## 支持

在高级设置的环境区收集诊断信息。提交问题时提供 Slicer 版本、操作系统、
所选路线、失败信息和脱敏日志，删除被试标识及私人路径。
报告默认保留本地，依赖与模型下载需要网络访问。

---

## 引用

SlicerDDSurfer 协议稿件仍在准备。使用 [CITATION.cff](CITATION.cff)
引用实际测试的软件版本，并引用本次使用的方法：
[DDSurfer](https://doi.org/10.1002/advs.76596)、
[DDSeg](https://doi.org/10.1016/j.neuroimage.2021.117934)、
[DDParcel](https://doi.org/10.1109/TMI.2023.3331691)。

---

## 许可证

项目代码采用 **BSD-3-Clause**：[LICENSE.txt](LICENSE.txt)，根目录只保留这一份。
第三方组件各自保留原许可证和声明，不适用项目许可证的统一再授权。
第三方源码单独适用 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 中的条款。
项目许可证不覆盖权重、模板和被试数据；部分组件授权仍待确认，
未形成书面许可记录前不要发布包含这些资产的公开归档。
