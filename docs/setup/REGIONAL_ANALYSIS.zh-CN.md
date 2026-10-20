<div align="center">

# 脑区分析

**按需复用已完成且 QC 可用的结果，不改变默认工作流**

[项目](../../README.zh-CN.md) | [文档](../README.zh-CN.md) | [结果查看](AUTOMATIC_RESULTS.md) | [English](REGIONAL_ANALYSIS.md)

</div>

---

## 操作入口

展开 **高级设置 > 脑区分析（可选）**。默认折叠，不会自动增加主工作流的任务。

1. 点击“使用最近一次运行”，或选择单被试的 `*_orchestration_manifest.json`。
2. 点击“读取脑区与可用结果”。只读取该记录明确声明、已完成或可复用、QC 可用且文件签名未过期的产品。部分失败运行中的失败产品仍排除。
3. 按名称、左右半球或标签 ID 搜索并勾选脑区，也可一次勾选当前搜索结果。
4. 选择所需的可用分析，点击“分析所选脑区”。

默认采用 DDParcel 分区与 FreeSurfer 脑区名称。也可指定自定义整数 NIfTI 分区图
及 FreeSurfer 格式的 LUT。参数图、脑掩膜和分区图必须具有一致的形状与空间仿射；
不会静默配准或重采样。连接组必须对应原运行记录的同一分区图，不能仅凭标签号相同混用。

---

## 支持的分析

| 分析 | 复用输入 | 输出 |
| --- | --- | --- |
| 微结构统计 | 已有 DTI、FW、NODDI、DKI/MK-Curve 参数图 | 各脑区均值、标准差、最小/最大值、有效/排除体素数及覆盖率 |
| 选区相关流线 | 已完成的完整流线文件，以及明确记录的配套 SIFT2 权重 | 完整筛选流线、原始索引、对应权重和独立显示预览 |
| 脑区连接分析 | 已有对称连接矩阵与节点表 | 所选脑区的诱导子矩阵，以及各选区到原矩阵其他节点的非零连接 |

可选指标由原运行已经生成的结果决定；这里**不重新拟合模型**。DTI 包括
FA/MD/AD/RD 及已有特征值、Trace。FW 组织参数、NDI/ODI 必须有明确的组织有效性
掩膜；DKI 采用原始参数图与有效性掩膜，不使用为显示截断后的值；MK-Curve
优先使用各参数自己的有效性掩膜。有限的真实零值仍参与统计；无效拟合不进入
分母。脑区没有有效值时留空/null，不填零。

流线支持四种明确的几何规则：

- **经过任一所选脑区**：各脑区相交流线的并集。
- **经过全部所选脑区**：各脑区匹配的交集；单次最多 16 个脑区。
- **至少一个端点在选区内**：至少一个端点属于所选脑区的并集。
- **两个端点都在选区内**：两端都属于并集，不要求端点位于不同脑区。

“经过”规则采用 DIPY 的 [line-based ROI targeting](https://docs.dipy.org/stable/reference/dipy.tracking.html#dipy.tracking.utils.target_line_based)，
可处理两个已保存顶点之间线段穿过脑区的情况。输出是**几何子集，不自动等于
WMQL/WMA/TractCloud 解剖束识别**；流线数量也不是轴突数量。端点规则采用明确的
体素归属，不等于原连接组可能使用的径向端点分配。

连接组保持原权重，不额外归一化、阈值化、平滑或重算。按节点表中的实际分区
标签匹配，而不是按连续行号匹配。不存在的边沿用原矩阵的零边约定；有向或不一致
的矩阵会拒绝，不会悄悄对称化。

---

## 输出与审核

分析在可取消的后台进程运行，关键结果自动进入当前 Slicer 场景，按被试、区域运行、
产品分组。重复加载复用已有结果节点，不替换主工作流的“最近一次运行”引用。

默认写入 `05_statistics/selected_regions/<原运行>/<时间戳-ID>/`，每次使用独立目录：

| 文件 | 内容 |
| --- | --- |
| `request.json` | 脑区、指标、规则和来源配置 |
| `region_analysis_manifest.json` / `region_analysis_qc.json` | 输入/输出哈希、任务状态、耗时及验证范围 |
| `selected_regions.nii.gz` / `.csv` | 保留原标签的选区图及名称、体素数、物理体积 |
| `selected_microstructure.csv` / `.json` | 所选脑区的有效参数统计 |
| `selected_streamlines.vtk` | 非空时生成的完整匹配几何 |
| `selected_streamlines_preview.vtk` | 仅用于显示的有界预览 |
| `selected_streamline_ids.csv` | 原流线索引；存在配套 SIFT2 权重时保留对应权重 |
| `selected_tractography.json` | 规则、数量、坐标系及预览策略 |
| `selected_connectome_matrix.csv` | 所选脑区的原权重子矩阵 |
| `selected_region_connections.csv` | 所选脑区到其他节点的非零连接 |
| `selected_connectome.json` | 原连接指标与导出策略 |

VTK 保存 RAS-mm 几何，不复制原文件的张量或逐点数组；可用索引回溯原文件。
完整几何以双精度写出，不裁剪、不重采样。可复现预览最多 30,000 条流线、
1,000,000 个点，**不能用于定量测量**；场景中另行记录完整定量来源。

显示时将 FreeSurfer LUT 的前景色适配为不透明，不修改原 LUT 或标签。
未提供 LUT 时使用确定性的显示配色。此处 Slicer 稠密颜色表最多支持标签 ID
1,000,000；更大的定量 ID 仍可导出，但不会为了显示而静默重编号。

没有匹配流线时如实记录 0，不补线。开始与结束均核对来源/QC 文件哈希，输入改变
即不验收；不覆盖已有结果。取消或未完成任务不能成为完成状态。
**这里的 QC 仅验证后处理一致性，不代表重新验证上游拟合，也不替代人工解剖审核。**

---

## CLI 与验证

GUI 与 CLI 共用同一后端：

```bash
python scripts/analyze_regions.py --inspect /absolute/run_orchestration_manifest.json \
  --catalog /absolute/catalog.json
python scripts/analyze_regions.py --request /absolute/request.json
python scripts/validate_region_analysis.py /absolute/region_analysis_manifest.json \
  --report /absolute/independent_check.json
```

请求包含 `source_manifest`、正整数 `selected_labels`、可用的 `metrics`，
可选来源任务键 `tractogram`、`connectome`，以及 `tract_rule`、独立 `output_dir`。
也支持分区图/LUT 覆盖与目录读取时的哈希。GUI 会自动生成该请求，无需手写。

真实 Slicer 验证覆盖后台执行、中英文、440 像素面板、1000 以上标签、自定义 LUT、
自动加载和重复加载复用。独立核对将统计值与布尔掩膜直接计算比较，逐条比较导出
流线及原索引对应几何，并与原矩阵逐项核对连接权重；这些测试不等于临床有效性验证。

[10 月 20 日验证记录](../release/benchmarks/regional_analysis_20261020.json)包含真实
HCP-YA 百万流线案例，单独标明后处理耗时，不将其当作上游算法加速对照实验。
