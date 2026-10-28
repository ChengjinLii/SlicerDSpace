<div align="center">

# 轻量依赖与 GUI 批量实验验证

[首页](../../README.zh-CN.md) | [使用说明](../setup/EXPERIMENTS.zh-CN.md) | [English](LIGHTWEIGHT_EXPERIMENTS_20261028.md)

</div>

---

## 改动

可选的 Slicer 原生轻量预设复用 Slicer Python、SlicerDMRI、Python WMQL
和 Python 连接组。新增 DIPY median-Otsu 掩膜，不需要 TensorFlow、ANTs、
外部掩膜程序或权重。PNL/CSD 默认选择不自动修改；解剖产品及 GPU 偏好不关闭，
相应 Python 包、模型和可选后处理组件仍按需准备。原有 PNL/MRtrix/FSL 方法
保留其自身依赖，算法不会静默替换。

高级设置新增主动启用的“实验与批处理”页，支持 CLI 参数覆盖、JSON 命名组合、
当前被试或已准备队列。参数组合与 CLI 共用校验函数。被试间可以并发，同一被试
的组合依次执行，保护共享输入和缓存；输出目录、状态、耗时及日志分开记录。
支持预览、导出、实时进度、取消和运行记录浏览，完成时仅自动显示一个成功实验。

复用参数解析器，每个组合跨被试只校验一次，限制 GUI 预览长度。每次最多
64 个组合、4,096 个任务，禁止 shell 命令、安装选项和绕过依赖检查的参数。

---

## 验证

| 检查 | 结果 |
| --- | --- |
| Python 全量回归 | 1,583 项：1,578 通过、5 跳过；83.82 秒 |
| 真实隔离 Slicer | 实验页、算法选择、紧凑 UI、异步依赖检查通过 |
| GUI 实验细项 | 双语控件、显式轻量预设、无 Subject ID 的队列预览、危险参数拦截、依赖失败记录及取消通过 |
| Linux SDK | 配置、构建、182/182 CTest、CPack 通过 |
| 真实 CPack 包 | 510 个运行时文件匹配；Extension Manager 安装通过 |
| DIPY 掩膜 | 测试输入上与直接调用上游函数逐体素一致，保留原仿射，不调用外部程序 |
| 真实 DTI 实验 | 四个 WLS/LS 任务完成，自动 DTI QC 通过 |

真实影像测试使用 **同一官方 Slicer DWIVolume 数据的两个独立目录副本**，
不将其算作两个独立受试者。两个副本并发，各自的 WLS/LS 组合依次运行。
首次总耗时 66.38 秒，复用掩膜及原生 DTI 缓存的再次运行耗时 14.73 秒。
这些时间不用于宣称算法加速。同一拟合方法在两个副本上的 FA 数组完全一致；
人工解剖审核仍待完成。

[机器记录](benchmarks/lightweight_experiments_20261028.json) 保留源码哈希、任务、
QC 和计时。完整日志、截图、失败尝试及安装包位于
`ignore/validation/native_experiments_20261028/`。测试采用隔离配置，未改动现有
Slicer/MRI Agent 会话，未使用 GitHub Actions。
Windows/macOS 原生科学流程及空白机器全部可选后端安装仍需分别验收。
