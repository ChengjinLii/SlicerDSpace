<div align="center">

# 插件内自动配置

[项目](../../README.zh-CN.md) | [文档](../README.zh-CN.md) | [快速开始](QUICKSTART.zh-CN.md) | [GPU](GPU_EXECUTION.zh-CN.md) | [English](MANAGED_SETUP.md)

</div>

---

## 用户操作

选择分析任务后，展开“高级设置 > 环境与模型”，点击“自动配置所选计算工具”。
插件只安装所选 MRtrix/FSL 路线需要的工具，校验成功后自动填写并保存路径。
环境检查报告中缺少 MRtrix/FSL 的条目也提供自动安装入口。
报告中的组合安装操作按顺序处理缺少的 Python 包、所需模型和支持自动安装的外部工具，
不是要求一次装齐所有后端。

这些自动配置路线不需要打开终端、管理员权限、激活 Conda 或手动寻找可执行文件。
如果没有 Conda，插件会从 conda-forge 官方 GitHub 下载固定版本的 Miniforge，
先校验 SHA256，再运行引导安装。环境放在用户目录，不修改 Slicer Python、系统 CUDA 或 shell 配置。
FSL 需要明确确认许可；检测到 NVIDIA 工具时默认安装 GPU eddy，也可选择 CPU 安装。
实际 GPU 能否运行要在后端执行时检查，不能由“包安装成功”推断。

安装在后台执行，提供取消按钮和日志。取消或校验失败不替换已配置路径；
已成功安装的包和部分下载可能保留供重试。
已经校验且未发生变化的环境直接复用，不重复安装。

---

## 模型与已有环境

模型使用已配置目录或默认用户数据目录，不再强制弹出目录选择器。
缺少某个产品模型时，仅下载该产品的 profile，而不是三个解剖产品全部下载。
主动选择核心资源下载时仍下载 core profile。
资源通过校验后自动保存目录；文件校验不代表授权确认或模型准确性认证。

已有软件、离线部署或集群管理员管理的环境仍可在高级路径设置中配置。
自动安装是明确发起的操作，不会在科学分析过程中静默替换已有环境。
默认环境目录位于模型资源旁的 `SlicerDDSurfer/runtimes`。

---

## 当前覆盖范围

| 工具 | 自动配置范围 |
| --- | --- |
| MRtrix3 3.0.8 | Linux x86_64，官方 MRtrix3 Conda 源 |
| FSL eddy 2602.0 / topup 2203.5 | Linux x86_64，官方 FSL 源，安装前确认许可 |
| CUDA eddy 2602.0 | 可选 FSL profile，需要 NVIDIA 驱动，不要求安装完整 CUDA Toolkit |
| DDSurfer / DDSeg / DDParcel 资源 | 已有后台下载，改为按产品选择并使用默认目录 |
| Python 科学计算包 | 已有依赖安装入口；PyTorch 继续由 Slicer PyTorch 扩展管理 |
| PNL CNN、完整 FreeSurfer、WMA/WMQL/TractCloud 资源 | 本自动安装器尚未完整覆盖，保留现有显式配置路线 |
| Windows/macOS 的 MRtrix/FSL 自动配置 | 尚未实现并验收，继续使用对应平台说明与高级路径配置 |

安装校验检查命令、指定包版本、ELF 库和可执行文件哈希，并保存实际环境的显式锁定文件。
这些检查不能代替科学正确性验证、真实干净安装、SDK 打包和跨平台验收。
实际 GPU 证据见[核查记录](../release/GPU_POLICY_20261013.md)。

---

## 维护者接口

`scripts/setup_managed_runtime.py` 默认只生成计划；`--execute` 才执行安装，
FSL 另需 `--accept-fsl-license`。
`--root` 或 `SLICERDDSURFER_RUNTIME_ROOT` 用于隔离测试。
后台 worker 成功后返回经过校验的设置，GUI 再保存路径。
不修改用户 shell、GPU 驱动或非插件管理的 Conda 目录。
