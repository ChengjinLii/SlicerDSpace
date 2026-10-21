<div align="center">

# 依赖准备验证记录

[项目](../../README.zh-CN.md) | [自动配置](../setup/MANAGED_SETUP.zh-CN.md) | [平台](../setup/SUPPORT_MATRIX.zh-CN.md) | [English](DEPENDENCY_SETUP_20261021.md)

</div>

---

## 已实现

高级设置提供“准备所选分析环境”统一入口，以及显式受管工具修复、离线模型目录校验。
已有 Slicer 扩展继续由原生扩展管理器处理；Python 包和模型使用可取消的后台 worker；
Linux x86_64 的 MRtrix/FSL/PNL 放在独立用户目录。
已完成的受管环境复验后复用，不重复安装；修复须确认，拒绝修改非插件管理环境。
不改算法选择、系统驱动或 shell 配置。

按需请求 SlicerDMRI/PyTorch，UKFTractography 仍为可选扩展。
新装/启用扩展，或已加载包发生变更时要求重启；最终重新检查依赖决定是否就绪，
不能仅凭安装进程退出成功就显示全部就绪。
主界面三行同时显示当前算法，随高级设置更新，但不把运行配置当成科学 QC 状态。

---

## 实测结果

| 项目 | 实际结果 | 边界 |
| --- | --- | --- |
| Python 回归 | 1,256 项：1,253 通过、3 跳过 | 主机科学环境，不代表三平台完整运行 |
| Slicer 5.10 GUI | 统一准备、FSL/PNL 独立许可确认、算法提示、依赖路径、安装进程树取消通过 | 隔离设置和临时容器；部分依赖响应受控，不影响用户会话 |
| PNL 新隔离环境 | 固定官方源码、三方向权重、模板下载并校验；安装 TF 2.15.1/Keras 2.15.0、ANTs 2.3.0 | 新 prefix；使用已有 Conda 创建，不是空白机器引导 Miniforge 实测 |
| PNL 模型检查 | 三方向加载及有限值前向通过，H100 CUDA | 不证明解剖准确性 |
| PNL 环境复用 | 命令、资源哈希与前向复验通过，无重装 | 刚创建的受管环境 |
| 100307 真实掩膜 | 102.73 秒、697,375 脑体素；二值、有限值、原生几何检查通过 | 含哈希、b0、推理、自动 QC，不含下载与环境探测；人工解剖复核待完成 |
| 离线 DDSeg 资源 | 3 个权重、3 项 SHA256 匹配，无下载 | 校验可信清单，不代表再分发授权 |
| 新 Python 环境 worker | 在仅含 pip 的新 venv 安装 packaging 24.2 | 兼容安装路径，不修改生产 Slicer 包 |
| 打包与来源检查 | 暂存安装包资源、文档链接/样式、第三方说明检查通过 | 不代替官方 SDK/CPack 或法律认证 |

日志、回执、截图、掩膜验收 JSON 与单元测试记录位于
`ignore/validation/selected_setup_20261021/`。权重、隔离环境和患者图像不进入 Git。

---

## 复现与限制

在开发环境执行 `python3 -m unittest discover -s Testing/Python -p 'test_*.py'`。
原生界面检查使用
`scripts/slicer_acceptance.py --tests selected_setup algorithm_labels dependency_workflow setup_tree`。
`Testing/Python/pnl_managed_acceptance.py` 为主动运行的真实掩膜验收：
需要已获准使用的 PNL 环境、原始 DWI/bval/bvec 和独立报告目录，不写入源输入目录。

本机 Slicer 5.10 没有 `slicer.packaging`，已实测兼容 worker；
新版 `pip_ensure` 目前采用能力检测与契约测试，未实测更新版 Slicer 二进制。
此次未在完全空白机器重复扩展下载/重启或完整 MRtrix/FSL 安装。
完整 FreeSurfer 以及 WMA/WMQL/TractCloud 的全部资源尚未自动配置，
Windows/macOS 的 MRtrix/FSL/PNL 自动环境仍未开放。
受保护模型源可能需要访问授权；环境就绪不等于科学 QC、SDK 验收或再分发许可。

设计参考 Slicer [扩展管理](https://slicer.readthedocs.io/en/latest/user_guide/extensions.html)、
官方 [packaging API](https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/packaging.py)
与 [PNL 作者运行说明](https://github.com/pnlbwh/CNN-Diffusion-MRIBrain-Segmentation/blob/d7fe0fd4976c2d5a3489526f75d2a00dae3e1fe1/docs/README.md)。
