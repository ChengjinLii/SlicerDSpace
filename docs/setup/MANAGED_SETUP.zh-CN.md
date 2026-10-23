<div align="center">

# 插件内自动配置

[项目](../../README.zh-CN.md) | [文档](../README.zh-CN.md) | [快速开始](QUICKSTART.zh-CN.md) | [GPU](GPU_EXECUTION.zh-CN.md) | [English](MANAGED_SETUP.md)

</div>

---

## 用户操作

选择分析任务后，展开独立的“环境与安装”区域，点击 **准备所选分析环境**。
环境报告的组合入口使用同一逻辑。检查与最终复核均在可取消的后台进程中进行。
只有存在待处理项目时才确认计划、下载和相关许可；已经就绪时不弹出重复确认。
离线资源、修复和手工路径位于环境区的“更多选项”，不混入算法高级设置。
只处理本次所需依赖：

1. 通过 Slicer 扩展管理器安装缺少的 SlicerDMRI/PyTorch；仅选择 UKF 时请求 UKFTractography。
2. 新安装或启用扩展后，保存工作并重启 Slicer，再点击准备继续；不会重复安装已有扩展。
3. 后台 worker 按所选解释器安装缺少的 Python 包，下载所需解剖模型，准备支持的隔离工具。
4. 校验成功后保存路径，重新检查所选依赖，明确显示就绪、仍有阻碍或需要重启。

这些自动配置路线不需要打开终端、管理员权限、激活 Conda 或手动寻找可执行文件。
如果没有 Conda，插件会从 conda-forge 官方 GitHub 下载固定版本的 Miniforge，
先校验 SHA256，再运行引导安装。环境放在用户目录，不修改 Slicer Python、系统 CUDA 或 shell 配置。
FSL 与 PNL 源码、模型、模板条款均需明确确认。
检测到 NVIDIA 工具时默认安装 GPU eddy，CUDA profile 同时保留 CPU 程序；分析设备偏好仍在高级设置调整。
实际 GPU 能否运行要在后端执行时检查，不能由“包安装成功”推断。

安装在后台执行，提供取消按钮和日志。取消或校验失败不替换已配置路径；
已成功安装的包和部分下载可能保留供重试。
已经校验且未发生变化的环境直接复用，不重复安装。

**修复所选受管工具** 在明确确认后重新安装所选的插件受管外部环境，保留修复前的就绪回执，
拒绝修改非插件管理的环境。下载或安装中断后通常直接重试“准备”；已有环境损坏时再用“修复”。
取消不回滚已经安装成功的包，可通过“打开安装日志”定位失败阶段。

Python 安装检测 `slicer.packaging.pip_ensure` 是否存在；Slicer 5.10 没有该模块，
使用可取消的后台 Python 进程。常规 pip 安装约束现有 NumPy、SciPy、VTK、SimpleITK、
PyTorch 等核心版本，不为解决冲突而静默升级基础栈。PyTorch 使用官方扩展辅助器。
已加载的包发生变更时，必须重启后再运行分析。
新版 packaging API 当前通过契约测试验证，并非已实测更新版 Slicer 二进制。
裸 VCS URL 和本地工程使用原生 `pip_install`，避免传入仅解析标准包名的
`pip_ensure`；同样应用版本约束并在最后检查实际导入。

---

## 模型与已有环境

模型使用已配置目录或默认用户数据目录，不再强制弹出目录选择器。
缺少某个产品模型时，仅下载该产品的 profile，而不是三个解剖产品全部下载。
主动选择核心资源下载时仍下载 core profile。
资源通过校验后自动保存目录；文件校验不代表授权确认或模型准确性认证。

**使用离线模型资源** 选择已有资源目录，后台按插件自带的可信 SHA256 清单验证所选产品。
不下载、不执行资源，失败保留原路径；复制资源时须保留目录结构。
导入的是模型目录，不是可移植 Conda 环境；受保护的模型下载仍需相应访问授权，不会绕过权限。

PNL 模型/模板、TractCloud 推理参考、SynthStrip 权重和 WMA ORG 图谱使用统一资源目录。
准备所选环境时，按缺少的分组获取资源、核对 SHA256 并安全解压 ORG，成功后保存路径。
仅下载数据不等于安装 WMA、TractCloud 或 FreeSurfer 的可执行后端。
详见[可选资源与离线导入](../assets/EXTERNAL_RESOURCES.zh-CN.md)。

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
| Python 科学计算包 | 所选解释器、核心版本约束、可用时使用原生 packaging API；官方 PyTorch 辅助器 |
| PNL diffusion CNN | Linux x86_64；固定官方源码、v0.3 三方向权重、IIT b0 模板、Python 3.11、TensorFlow 2.15.1/Keras 2、ANTs 2.3.0，独立环境 |
| 可选皮层后处理 | Linux x86_64；[明确同意后本机源码编译](SURFACE_COMPONENTS.zh-CN.md)七个原始 FreeSurfer 组件，需工具链及个人激活文件；完整版安装可选 |
| WMA / TractCloud / SynthStrip 非代码资源 | 所选分组下载/导入、校验、ORG 解压及自动保存路径；私有镜像仍需访问权限 |
| 完整 FreeSurfer、WMA/WMQL/TractCloud 可执行后端 | 尚未全部自动配置；保留现有适配器与缺失项指引 |
| Windows/macOS 的 MRtrix/FSL/PNL 自动配置 | 尚未实现并验收，继续使用对应平台说明与高级路径配置 |

安装校验检查命令、指定包版本、ELF 库和可执行文件哈希，并保存实际环境的显式锁定文件。
PNL 在反序列化前核对固定源码、模型与模板哈希，并执行三方向模型有限值前向检查，保存 pip 包清单。
CUDA wheel 的库和工具仅对该 Python 子进程可见，不修改全局 PATH、LD_LIBRARY_PATH 或驱动。
默认优先可用 CUDA，不统一禁用 GPU；固定作者兼容框架首次运行时可能需编译 GPU 内核。
这些检查不能代替科学正确性验证、真实干净安装、SDK 打包和跨平台验收。
实际 GPU 证据见[核查记录](../release/GPU_POLICY_20261013.md)。

---

## 重启后继续

经过用户确认但尚未完成的准备操作会跨重启保留。现有按钮显示为“继续准备所选分析环境”，
点击后重新检查当前选择，必要时再次确认；不会重放保存的命令、把旧许可确认用于不同计划，
或自动启动科学计算。已有的合格资源与环境会复用，最终就绪检查成功后才清除待续接标记。

---

## 维护者接口

`scripts/setup_managed_runtime.py` 默认只生成计划；`--execute` 才执行安装，
FSL 另需 `--accept-fsl-license`，PNL 另需 `--accept-pnl-terms`，
`--repair` 显式重装所选受管环境。
`--root` 或 `SLICERDDSURFER_RUNTIME_ROOT` 用于隔离测试。
后台 worker 成功后返回经过校验的设置，GUI 再保存路径。
不修改用户 shell、GPU 驱动或非插件管理的 Conda 目录。
