<div align="center">

# 首次使用依赖准备核查

[项目](../../README.zh-CN.md) | [自动配置](../setup/MANAGED_SETUP.zh-CN.md) | [平台范围](../setup/SUPPORT_MATRIX.zh-CN.md)

</div>

---

## 本轮变更

| 用户需求 | 实现与边界 |
| --- | --- |
| 共享兼容环境 | 默认复用 Slicer/workflow Python 和 PyTorch；按实际解释器分组安装，保留每个算法的版本要求，不覆盖用户明确指定的解释器 |
| 冲突环境由插件管理 | 保留 PNL 的独立 TensorFlow/ANTs 环境，统一入口负责准备、校验及保存路径；不更改用户 shell、驱动或非受管环境 |
| 减少 Git、编译器要求 | WMQL/WMA/TractCloud 使用固定提交、固定 SHA256 的源码压缩包，普通 Python 依赖仅安装 wheel；GUI 不启动表面源码编译 |
| 一个准备入口 | 运行前缺少依赖时进入统一确认，依次准备源码、Python、模型、外部工具；重启后进入模块提示续接，已完成资源复用 |
| 功能自检 | 依赖导入之外，检查小型求解、影像及流线读写、PyTorch 设备计算与模型加载；DDSeg 做合成输入前向，MRtrix 做图像转换；失败不显示就绪 |

默认分析方法、精度、模型权重及 GPU 选择策略不变。用户明确配置的源码目录和外部环境保留。
重启后续接会重新检查当前选择，必要时重新确认许可，不自动启动科学分析。
模型和源码大小在确认页列出；Conda/Python 依赖由求解器确定，尚未提供精确的总下载量预估。

---

## 实际验证

证据目录为软件仓库下的 `ignore/validation/setup_delivery_20261031/`。

| 检查 | 结果与证据 |
| --- | --- |
| 单元回归 | 1,728 项，9 项按条件跳过，其余通过，86.23 秒；`unit-tests-complete.log` |
| 三个作者源码包 | 实际下载并核对 SHA256，离线解压、逐文件验证和复用通过；`backend-sources.json` |
| Slicer Python 功能检查 | NumPy/SciPy/nibabel/VTK/PyTorch 及三个作者包导入通过；NIfTI/流线读回、22 份解剖权重加载、DDSeg 三方向及 TractCloud 合成前向通过；`all-models-result.log`，该组合 41.22 秒 |
| MRtrix | 现有受管 3.0.8 环境的版本、依赖及小体积 MIF 转换读回通过 |
| PNL / ANTs | 现有受管 TensorFlow/ANTs 环境中，ImageMath 小体积恒等运算及数据、仿射读回通过；原有三方向模型自检仍保留 |
| 表面预编译包 | 独立路径安装、配方与逐文件哈希核对、七个命令 `--version` 启动通过；`prebuilt-install.json`、`prebuilt-reuse.json` |
| Slicer GUI | 正式资源清单 staging，独立 Slicer 5.10/Qt/MRML 会话，断网执行；14 项交互检查通过，含自检失败拦截、恢复及真实 Agent 计划/准备助手；`selected_setup.json`、`gui-final.log` |
| 文档、元数据、第三方声明 | 检查通过；声明检查覆盖本地文件及打包完整性，分发授权仍需独立核对 |

GUI 测试使用已有 Slicer 科学计算包，模拟缺失依赖报告以走真实后台 worker，不在断网环境安装新包。
测试容器挂载的软件目录只读，因此日志含全局设置写入告警；关闭 CLI 模块也产生 CropVolume 依赖告警。
这些不属于本次自检失败。当前用户的运行中 Slicer 会话和安装副本未被替换。
本轮未重跑完整被试流程，也未把安装自检作为解剖或纤维束定量验收。

本轮 GUI 复测修复了一个实际问题：后台检查返回 Slicer 的 `python-real` 路径时，
后续进程曾按外部 Python 清理环境，导致找不到 `libpython3.12.so`。
现在识别当前 Slicer 的原始解释器及包装器，并通过 Slicer launcher 启动；
`bin/..`、macOS 应用目录及外部虚拟环境链接分别处理，外部 venv 不会折叠到基础解释器。

独立复查还促成以下修正：按后端保留 Python 依赖归属；TractCloud 单独检查其解释器的
NumPy、VTK、PyTorch；自检失败按配置签名持久化；显式 CPU 不变为自动 CUDA 自检；
三个束分析后端的实际运行复用已校验源码；Windows WMA 不自动接收 Bash-only 源码；
macOS 14.5 要求在安装规划时就检查，而不是下载后才拒绝。

Skill 的安装详情集中到 `references/setup.md`，并提供 `prepare_in_slicer.py`：
Agent 先让用户确认资源存放路径，再通过插件本身导出计划、确认资源与许可并准备环境。
真实 Slicer 测试覆盖 `plan` 和已经具备依赖时的 `prepare`，验证没有运行患者分析或改变场景节点数量。
37 份既有算法 Shell 模板通过同步检查。安装授权不扩大为科学运行授权。

独立 Skill 走读还修正了准备失败被写成取消、旧回执被误读、资源目录只检查模块子目录
以及 ORG 解压空间漏计的问题。ORG 的 849 个已校验文件共 2,439,318,525 字节，
现在纳入空间计划及下载前检查。Agent 的 `plan` 不安装软件或处理患者数据，
但会更新 GUI 选择、常规环境检查元数据并写出报告。

---

## 原生运行包

Linux x86_64 表面包来自现有、与当前配方匹配的原生构建，没有重新实现数值算法。

| 项目 | 内容 |
| --- | --- |
| 压缩大小 | 40,994,566 字节，约 39.1 MiB |
| 解压文件 | 67 项命令、图谱及组件文件，另含 `runtime.json` |
| 文件内容大小 | 89,390,119 字节，约 85.2 MiB，不含清单 |
| SHA256 | `d1bdcb2bf307f506cfb9393a1aaeca5169674e91020ff6a42b089d9c41d835f3` |
| 激活文件 | 不包含；分析时用户单独提供 |
| 在线状态 | 尚未发布。目录与下载地址已预留，但 `published=false`，不会尝试尚不存在的下载 |

没有可下载或已导入的合格包时，确认页保留明确的待处理项，不默默编译、不显示全部就绪。
普通用户无需准备编译工具；维护者仍可显式选择 `--build-from-source`。
运行包进入公开下载前须完成组件、图谱及第三方库分发许可核对。

---

## 平台边界与后续

- Linux x86_64 保留已有 PNL、MRtrix、FSL 受管路线，本轮实测源码准备、MRtrix 小测试、表面包和 GUI。
- macOS Intel 新增官方 MRtrix 3.0.8 包及 Miniforge 安装适配，要求 macOS 14.5+；仅核对官方包信息并做规划测试，尚未 Mac 真机安装。
- macOS ARM 不自动切换到 Rosetta；本安装器未提供 ARM MRtrix、macOS FSL/PNL 或 macOS 表面运行包。
- Windows 保留现有 Windows/WSL 路线；原生 PNL、表面组件等尚不能宣称安装即用。
- 仍需发布已核对授权的运行包，并在对应平台的干净 Slicer 中完成联网首次安装及完整分析路线验收。

参考的交付方式来自
[Slicer Python 依赖规范](https://slicer.readthedocs.io/en/latest/developer_guide/python_faq.html#can-i-use-any-python-package-in-a-slicer-module)、
[SlicerTotalSegmentator](https://github.com/lassoan/SlicerTotalSegmentator#tutorial)、
[SlicerNNUnet](https://github.com/KitwareMedical/SlicerNNUnet#using-the-extension) 和
[MRtrix 官方 macOS 安装说明](https://www.mrtrix.org/download/macos-anaconda/)。
