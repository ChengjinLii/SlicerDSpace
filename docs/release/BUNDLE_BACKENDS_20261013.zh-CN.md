<div align="center">

# 白质束后端核查

**2026 年 10 月 13 日 · 源码、真实输出与重复性**

[项目](../../README.zh-CN.md) | [文档](../README.zh-CN.md) | [运行时间](MODULE_RUNTIMES_20261013.zh-CN.md) | [English](BUNDLE_BACKENDS_20261013.md)

</div>

**确认的封装缺陷已修复，但不能宣称所有历史结果都正确或 QC 全部通过。**
几何完整性、源流线对应、规则执行正确和解剖分类正确是不同层级的证据。

---

## 真实结果

| 后端 / 输入 | 输出 | 自动检查 | 科学边界 |
| --- | --- | --- | --- |
| WMQL：100307，50,000 条 CSD/ACT 流线，真实重跑 | 左 AF 1；右 AF 1；左 CST 11；右 CST 14 | 27 条全部对应输入；独立检查全部满足端点标签规则；与旧结果的集合完全一致 | **PARTIAL**：AF 各仅 1 条，不能当作可靠束定量。默认查询是 DDParcel 适配端点规则，不是完整经典 AF 解剖判据 |
| TractCloud：同一输入，种子 0 独立运行两次 | 两次均为 **39 条非空束、21,432 条已分配流线** | 有限坐标、正长度、源对应、类别互斥通过；同硬件同配置的流线集合及标签 **100% 一致** | 待人工解剖核验；未出现的类别、未输出的 Other 需单独解释 |
| WMA：149741，100,000 条 UKF，已有官方 rigid 路线 | **74 条可读、非空束；40,338 条流线** | 当前输出契约、完整解码、源对应和 Slicer 加载通过 | 审计已有输出，**本轮没有重新运行完整 WMA 算法**；待人工核验 |
| WMA：100307，1,000,000 条，`qc_verified_20260916` | 74 个可读文件，但仅 **45 条非空束**；51,674 条流线 | 几何和源对应通过；**当前覆盖 QC 不通过** | 检查覆盖、流线长度与配准，不放宽阈值强行通过 |
| WMA：100307，旧 `linux_acceptance_20260813_full` | 74 个可读文件，仅 **34 条非空束** | 旧 completed 不符合当前契约 | 不能沿用旧绿色状态作为验收证据 |

WMA 的至少 73 个可读文件、55 条非空束是本项目的保守工程契约，**不是上游规定的
解剖准确率阈值**。WMA/WMQL 可有规则重叠；TractCloud 输出类别必须互斥。

---

## 已修复的问题

| 范围 | 修复 |
| --- | --- |
| WMA 重跑 | 上游 shell 会跳过已有阶段目录。现在独立暂存运行，完整解码并通过契约才发布；旧结果归档，失败证据保留；记录显式配准变换 |
| WMQL 输出判断 | 从只读 VTK 头部改成完整几何解码，拒绝截断/非有限坐标/无效连接；检查被试与查询身份；重跑不直接删除旧结果；阈值必须合法；单流线候选明确警告 |
| TractCloud 旧结果混入 | 上游只写当前非空类别、不删除旧类别。现在只验收本次暂存产品，旧类别归档，不参与扫描 |
| Python 环境 | 保留 virtualenv 的符号链接身份；外部 Python 不继承 Slicer 的 PYTHONHOME/库路径；Slicer 自身解释器保留启动器环境 |
| TractCloud 重复性 | 固定并记录 Python/NumPy/PyTorch 种子，默认 0；记录模型、参数、质心文件 SHA256；旧未固定种子缓存以及资源/种子/批大小/路径/指定设备变化不能直接复用 |
| 上游异常处理 | CUDA 异常转 CPU 分支使用未导入的 logging。兼容启动器只补这个全局量并进入官方 CLI，不修改作者源码、架构、权重、标签映射或推理方法 |
| SlicerDMRI CLI 发现 | 同时搜索 Slicer 当前额外模块路径，解决新安装副本找不到 CLI 的问题；全新全脑 WLS DTI 和六指标转换已实测通过 |

作者源码：[WMA](https://github.com/SlicerDMRI/whitematteranalysis)、
[Tract Querier](https://github.com/demianw/tract_querier)、
[TractCloud](https://github.com/SlicerDMRI/TractCloud)。参考快照分别为
`4532b911386d2d1bc7ebba63fdd13e65b1660623`、
`5c69c594d489859e08485110678dca7f6f4cba40`、
`94de6275d07d7b5eeb50e4cd4d6e85fde29d5fb0`。
三者是 **外部作者代码的适配封装**，不是本项目重新编写算法。

结果对象也向编排器传递实际 QC 状态：TractCloud 返回码为 0，但新输出缺失或损坏时，
不能再被上层默认记成 completed。

---

## 重复性与 Slicer

未固定种子的两次 TractCloud，在“已输出流线并集”上的同标签比例仅 **63.19%**，
因此旧结果不能声称严格可复现。该比例不是全输入的分类准确率，也不是临床指标。
固定种子后两次的 21,432 条流线和标签完全一致。跨设备/跨库版本逐位一致性和所有可选分支
仍未验证；logging 兼容处理有单元回归，不声称真实测过不兼容 GPU 的回退分支。

隔离 Slicer 5.10/SlicerDMRI 中加载 **117 个真实文件**：WMQL 4、固定种子 TractCloud 39、
WMA 74。全部为 FiberBundle 节点；TRK 世界坐标转换/float32 精度以 **0.001 mm** 容差核查，
最大偏差小于 0.00001 mm，不虚称逐位一致；VTP 坐标完全一致。私有 settings、运行目录和
X display 不影响用户的 Slicer/MRI Agent。全新全脑 DTI 拟合/转换实测 **135.999 秒**，
与启动、脑区统计分开。

完整 Python 回归 **902 项：899 通过，3 跳过**。合成夹具只验证工程分支，不作为科研结果。

---

## 证据位置

`ignore/validation/bundles_runtime_20261013/` 保存源码核查对应的重跑、日志和逐束统计。

| 文件 | 内容 |
| --- | --- |
| `wmql_endpoint_verified_audit.json` | 27 条源对应、独立端点规则、重复集合 |
| `tractcloud_seed0_repeat_audit.json` | 固定种子重复性、互斥类别、源坐标 |
| `wma_149741_previous.json` | 全部 74 条 WMA 束 |
| `wma_100307_failed_audit.json` | 几何有效、覆盖不合格的失败证据 |
| `native_cli_fixed/gui_acceptance.json` | Slicer 加载和全新全脑 DTI |
| `native_seeded/gui_acceptance.json` | 最终安装副本与固定种子束输出 |
| `unittest_completion.log` | 最终完整回归 |
| `timings/module_runtimes.json` | 成功/失败/复用计时及来源哈希 |

原科研结果没有覆盖；新输出单独保存在证据目录，旧未固定种子的 TractCloud 结果没有被
重新标成已验证。专家解剖核验、失败 WMA 的覆盖/配准排查、全脑 DKI/MK-Curve 计时仍需继续。
