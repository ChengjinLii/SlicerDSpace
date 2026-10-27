<h1 align="center">安装与工作流优化记录</h1>
<p align="center"><a href="../../README.zh-CN.md">首页</a> · <a href="../setup/QUICKSTART.zh-CN.md">快速开始</a> · <a href="PRODUCT_POLISH_20261028.md">English</a></p>

---

## 范围

2026 年 10 月 28 日这轮修改改进安装验证、所选后端的依赖检查和真实示例入门，
并整理近期 CLI、论文、插图和网站修改。科学 QC 门槛保持不变。

## 参考项目

| 来源 | 借鉴方式 |
| --- | --- |
| [SlicerTotalSegmentator](https://github.com/lassoan/SlicerTotalSegmentator) | 提供小型入门示例，按所选功能准备环境 |
| [SlicerNNUnet](https://github.com/KitwareMedical/SlicerNNUnet) | 将原生界面集成与模型、运行环境准备分开 |
| [SlicerDMRI](https://github.com/SlicerDMRI/SlicerDMRI) | 复用原生扩散模块，保留扩散图像元数据 |
| [官方 Self Tests](https://slicer.readthedocs.io/en/latest/developer_guide/modules/selftests.html) | 在真实应用内运行已注册的模块测试 |

本轮借鉴这些集成方式，不复制或重新命名其算法实现。

---

## 已完成的改进

**Agent 安装 Skill。** 新增可随仓库分发的
[安装 Skill](../../.agents/skills/slicerddsurfer-install/SKILL.md)。
通过现有运行时清单部署，核对实际加载路径、打开插件界面并运行原生 Self Tests。
持久启用时保留其他模块路径，发现另一份 DDSurfer 安装则停止并说明冲突。
只准备用户选择的分析；下载、许可证及重启由用户明确决定。

**分后端依赖检查。** 多种追踪算法分别保存阻塞原因；CLI 部分执行时，缺少
MRtrix 不再连带阻塞已就绪的 UKF。一次检查内复用相同依赖的探测结果，同时保留
不同任务的报告信息。GUI 仍要求所选功能全部就绪。

**CLI 指定束分析来源。** `--bundle-tractography-backend` 可指定 `csd_act`、
`ukf` 或 `dti_det`；多个追踪方案的结果隔离，束分析只使用选定来源。
保留输入、参数来源记录与现有 QC。快速开始和论文分别说明跨被试 `--jobs`
与单被试微结构 `--max-parallel-models`，避免混淆两级并发。

**无损 NRRD 导入。** 官方真实示例暴露 DWIConvert 不支持 `unsigned_short`
输入的问题。新增受控兼容转换：仅当全部数值均适合 int16 时转换，保留梯度、
测量坐标系及空间信息，记录首次失败；超出范围直接拒绝，不启用有损选项。
未指定 `--force` 时保护已有输入，dry run 不再创建输入目录。

**真实入门路线。** 新增双语
[Slicer Sample Data 教程](../setup/SLICER_SAMPLE_DTI.zh-CN.md)，使用 Slicer
现有 Sample Data 中的 DWIVolume，不在仓库重新分发影像数据。支持矩阵链接
有日期的 Linux SDK 验证记录，Windows/macOS 科学验收单独列明。

**精简安装包。** 绘图脚本和网站 logo 工具保留在源码仓库，不随运行时安装。
实际 CPack 审计暴露不同 CMake 版本的递归 glob 排除差异，现通过明确的开发目录
排除规则，使 Python 与 CMake 均选出 505 个运行时文件。论文复刻所需脚本继续保留。

---

## 验证结果

| 检查 | 结果 |
| --- | --- |
| Python 全量测试 | 1,571 项：1,566 通过、5 跳过；最终运行 80.17 秒 |
| 真实 Slicer，隔离配置 | 异步依赖检查、算法选择、紧凑 UI、Agent 安装四项通过 |
| Agent 安装细项 | 临时启用、持久启用、重复启用幂等、保留其他路径、拒绝安装冲突均通过 |
| 网站 | 131 项浏览器检查及引导 bot 桌面/移动端用例通过；14 项静态检查通过 |
| 论文材料清单 | 197 个文件、33 个栅格源素材，清单校验通过 |
| 真实 Linux SDK | 配置、构建、180/180 CTest 入口和 CPack 通过；505 个运行时文件哈希匹配 |
| 真实 CPack 安装包 | Extension Manager 安装通过，20.34 秒；最终暂存资源的 Agent 激活通过，12.43 秒 |
| 官方扩散示例 | 导入与 DTI 完成；独立几何、体素、梯度及标量完整性审计通过 |

示例尺寸为 128 × 128 × 94 × 43，包含 42 个 b=1,000 方向和一个 b0。
本机导入耗时 15.48 秒，验证及掩膜准备 10.66 秒，SlicerDMRI 原生 DTI 任务
9.46 秒。这些是已配置 Linux 主机的步骤耗时，不用于推算首次安装时间或整流程加速。

[示例审计](benchmarks/slicer_sample_dti_20261028.json) 保存源文件 SHA256、
重定向后体素精确相等、仿射误差为零、梯度校验以及 AD/MD/RD 的关系检查。
原始 Trace 中十个截断边界体素保留并记录；自动 DTI QC 通过，人工审核仍待完成。

完整日志、失败尝试、隔离配置和安装包位于
`ignore/validation/product_polish_20261028/` 与
`ignore/validation/slicer_sample_20261028/`。
没有重启现有 Slicer 或 MRI Agent，也没有使用 GitHub Actions。

SDK 构建使用已有真实 Slicer 构建树。本机缺少默认 OpenGL 头文件及 X11 开发库
搜索路径，通过进程级 `CMAKE_INCLUDE_PATH` 和 `CMAKE_LIBRARY_PATH` 指向已有
开发环境补齐，没有修改系统包或用户的科学运行环境。
SDK 的本地修订号为 3838，安装版应用修订号为 34045；本地安装测试提供目标版本
元数据，不包含官方目录服务器的版本匹配或安装包上传。

精简结果及受测源码哈希见[本轮验证记录](benchmarks/product_polish_20261028.json)。

## 发布边界

安装激活验证不包含全部科学后端的安装及运行。Windows/macOS 全流程、空白机器
所有可选环境安装、人工解剖审核仍需分别验收。仓库保持私有。
