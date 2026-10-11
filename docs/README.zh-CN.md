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
| [配置](setup/USER_CONFIG.md) | GUI/CLI 共用设置 |
| [Linux](setup/LINUX_HPC.md)、[Windows](setup/WINDOWS.md)、[macOS](setup/MACOS.md) | 平台设置与边界 |
| [模型资源](assets/MODEL_ASSETS.md) | Profile、下载与校验 |
| [资源授权](assets/MODEL_ASSET_TERMS.md) | 文件校验与再分发许可分别审查 |
| [代码与第三方授权](assets/CODE_LICENSES.zh-CN.md) | 原许可证、固定来源与分发条件 |
| [外部依赖](setup/EXTERNAL_DEPENDENCIES.md) | 外部软件与路线前提 |

---

## 维护者指南

- [扩展准备状态](release/EXTENSION_READINESS.zh-CN.md)：资源打包、SDK 构建与发布门禁。
- [发布流程](release/RELEASE.md)：代码归档、资源、标签与证据。
- [目录结构](architecture/REPOSITORY_LAYOUT.md)：解剖、微结构与连接分析源码。
- [产品架构](architecture/PRODUCT_ARCHITECTURE.md)：模块与路线职责。

---

## 历史验证记录

[10 月 12 日复核](release/DISTRIBUTION_VALIDATION_20261012.md)记录许可、干净克隆、
隔离安装和 SDK 阻塞。[10 月 11 日记录](release/DISTRIBUTION_VALIDATION_20261011.md)
保留前一轮工作树验证；其测试数量与本轮限定范围的 Git 快照不同。

[科学计算与 GUI 验证](release/SLICER_ACCEPTANCE_20261007.md)、
[简洁界面验证](release/UI_SIMPLIFICATION_20261008.md)、
[DDSurfer 同步](release/DDSURFER_SYNC_20261005.md)为带日期记录。
旧报告中的 Beginner/向导描述不再指导当前界面。

文档采用 DDSurfer 的居中标题、导航和分隔线风格。固定同步的上游 Markdown
及第三方许可证原文不改写，避免破坏源码哈希与授权记录。
