<div align="center">

# 能力与平台

**只安装当前路线需要的依赖**

[项目](../../README.zh-CN.md) | [文档](../README.zh-CN.md) | [快速开始](QUICKSTART.zh-CN.md) | [发布](../release/EXTENSION_READINESS.zh-CN.md) | [English](SUPPORT_MATRIX.md)

</div>

能力检查检测包、程序和资源是否可用，不认证每种采集、每个平台的数值正确性。

---

## 依赖层级

| 层级 | 产品 | 前提 |
| --- | --- | --- |
| 检查与计划 | 导入预览、输入检查、计划 | 基础影像环境；格式转换需要对应工具 |
| 最小 DTI | 张量参数、可选确定性流线 | SlicerDMRI 或支持的 DTI 路线及 Python 包 |
| 解剖模型 | DDSurfer/DDSeg/DDParcel | PyTorch、匹配资源及对应准备过程 |
| 微结构 | Free-water/NODDI | 配置的 DIPY/AMICO 与适合的采集 |
| 高级通路 | CSD/ACT/SIFT2/SAF/白质束 | 仅配置所选外部后端 |
| 连接组 | 区域矩阵与场景 QC | 流线/分区；加权路线才需权重 |

不强制一次安装所有依赖，资源授权与环境可用性分别检查。

---

## 平台证据

| 检查 | Linux | Windows | macOS |
| --- | --- | --- | --- |
| 资源/CMake 合同 | 有本地证据；已配置 CI | 已配置 CI，仍需运行证据 | 已配置 CI，仍需运行证据 |
| 真实 Slicer GUI/源码安装 | 有带日期记录 | 未认证 | 未认证 |
| 真实 SDK/CTest/CPack | 待真实 SDK 验收 | 待真实 SDK 验收 | 待真实 SDK 验收 |
| 科学路线 | 仅报告所列路线/数据 | 原生未认证；WSL 设置不等于原生验收 | 未认证 |
| 高级后端 | 仅报告所列路线 | 受工具/WSL 限制 | 受工具限制 |

资源检查不等于三平台 Slicer 构建。手动 SDK workflow 需要另行部署真实构建
环境的 runner，未运行不能标记成功。详见[发布门禁](../release/EXTENSION_READINESS.zh-CN.md)。
