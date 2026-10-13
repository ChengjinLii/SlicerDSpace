<div align="center">

# SlicerDDSurfer 文档

**安装、运行、检查与复现**

[项目](../README.zh-CN.md) | [快速开始](setup/QUICKSTART.zh-CN.md) | [平台](setup/SUPPORT_MATRIX.zh-CN.md) | [发布](release/EXTENSION_READINESS.zh-CN.md) | [English](README.md)

</div>

首次使用请阅读简洁界面的快速教程。技术参考说明各条路线；
带日期的验证报告保留历史证据，不是当前代码的通用保证。

---

## 用户指南

| 指南 | 内容 |
| --- | --- |
| [快速开始](setup/QUICKSTART.zh-CN.md) | 最小 DTI 工作流与合成安装测试 |
| [能力与平台](setup/SUPPORT_MATRIX.zh-CN.md) | 按路线配置依赖 |
| [结果检查](setup/GUI_RESULT_REVIEW.md) | 按运行加载结果、取消任务与 QC |
| [脑掩膜](setup/brain_mask_gui_config.md) | 默认 PNL CNN、替代后端及外部运行环境 |
| [微结构分析](setup/MICROSTRUCTURE.zh-CN.md) | DTI 默认、独立 FW/NODDI/DKI 与原作者 MK-Curve 边界 |
| [自动加载](setup/AUTOMATIC_RESULTS.md) | 当前运行记录与 RAS VTK 显示预览 |
| [配置](setup/USER_CONFIG.md) | GUI/CLI 共用设置 |
| [Linux](setup/LINUX_HPC.md)、[Windows](setup/WINDOWS.md)、[macOS](setup/MACOS.md) | 平台设置与边界 |
| [模型资源](assets/MODEL_ASSETS.md) | Profile、下载与校验 |
| [资源授权](assets/MODEL_ASSET_TERMS.md) | 文件校验与再分发许可分别审查 |
| [代码与第三方授权](assets/CODE_LICENSES.zh-CN.md) | 原许可证、固定来源与分发条件 |
| [实现来源](architecture/IMPLEMENTATION_PROVENANCE.zh-CN.md) | DDSeg/SAF/MK-Curve 移植与官方 PNL Python 外部适配的区别 |
| [外部依赖](setup/EXTERNAL_DEPENDENCIES.md) | 外部软件与路线前提 |

---

## 维护者指南

- [扩展准备状态](release/EXTENSION_READINESS.zh-CN.md)：资源打包、SDK 构建与发布门禁。
- [发布流程](release/RELEASE.md)：代码归档、资源、标签与证据。
- [目录结构](architecture/REPOSITORY_LAYOUT.md)：解剖、微结构与连接分析源码。
- [产品架构](architecture/PRODUCT_ARCHITECTURE.md)：模块与路线职责。

---

## 历史验证记录

[白质束后端核查](release/BUNDLE_BACKENDS_20261013.zh-CN.md) 区分 WMA 失败结果、
稀疏 WMQL 候选束和固定种子验证的 TractCloud 输出。
[模块运行时间](release/MODULE_RUNTIMES_20261013.zh-CN.md) 汇总历史与补测计时，
不把缓存复用或小 ROI 测量冒充全脑计算耗时。

[SAF Python 核验](release/SAF_PYTHON_20261013.md)记录原版核心函数对照、
有意保留的修正，以及真实纤维的几何检查与可靠性边界。

[最新 DDSurfer 同步](release/DDSURFER_SYNC_20261013.md)记录 RAS 标记、Python 标签导出、
批量 fsaverage 映射及真实结果对照。
[Python MK-Curve 验证](release/MKCURVE_PYTHON_20261012.md)记录 Python 校正路线与独立作者代码对照。

[脑掩膜、微结构与场景验证](release/PIPELINE_MASK_MICROSTRUCTURE_20261012.md)
记录默认 PNL、DKI 适用性、Advanced 独立开关与自动加载；真实 MATLAB MK-Curve
尚未验证，不以标准 MK 或接口测试冒充。

[10 月 12 日复核](release/DISTRIBUTION_VALIDATION_20261012.md)记录许可、干净克隆、
隔离安装和 SDK 阻塞。[10 月 11 日记录](release/DISTRIBUTION_VALIDATION_20261011.md)
保留前一轮工作树验证；其测试数量与本轮限定范围的 Git 快照不同。

[科学计算与 GUI 验证](release/SLICER_ACCEPTANCE_20261007.md)、
[简洁界面验证](release/UI_SIMPLIFICATION_20261008.md)、
[DDSurfer 同步](release/DDSURFER_SYNC_20261005.md)为带日期记录。
旧报告中的 Beginner/向导描述不再指导当前界面。

文档采用 DDSurfer 的居中标题、导航和分隔线风格。固定同步的上游 Markdown
及第三方许可证原文不改写，避免破坏源码哈希与授权记录。
