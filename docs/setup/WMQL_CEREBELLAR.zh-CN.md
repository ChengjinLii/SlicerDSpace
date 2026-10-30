<div align="center">

# 小脑区域查询

[配置](../README.zh-CN.md) | [CLI 模板](CLI_TEMPLATES.zh-CN.md) | [作者 WMQL 文档](https://tract-querier.readthedocs.io/en/latest/example_script.html) | [English](WMQL_CEREBELLAR.md)

</div>

---

## 选择预设

| 预设 | 输出数 | 范围 |
| --- | --- | --- |
| `official`（默认） | 48 | 原作者规则，保持不变 |
| `official_cerebellar` | 51 | 原有 48 条加 3 条 SlicerDSpace 小脑区域查询 |
| `cerebellar` | 3 | 仅小脑区域查询 |

GUI 入口：**高级设置 > 模型参数 > WMQL 解剖查询定义**。不需要新增模型或运行环境。
CLI 使用相同参数：

```bash
"$SLICER" --launch PythonSlicer run_subject_pipeline.py --no-user-config \
  --subject-root /path/to/subject --subject-id SUBJECT --output-root /path/to/results \
  --targets validation,parcellation,tractography,bundles --tractography-backend ukf \
  --bundle-tractography-backend ukf --bundle-backend wmql \
  --wmql-query-preset official_cerebellar --plan
```

确认计划后将 `--plan` 改为 `--execute`。只取新增结果可使用
`--wmql-query-selection cerebellar_brainstem,cerebellar_bilateral`。
不同预设使用独立运行名或输出目录。

## 查询定义

输入为原始全脑流线及同一原生空间内的 FreeSurfer 兼容标签：左小脑白质/皮层 `7/8`、
右侧 `46/47`、脑干 `16`。直接调用作者 Tract Querier，不移动流线、不重采样标签，
也不掺入其他算法的流线。

| 输出 | 主要条件 |
| --- | --- |
| `cerebellar_brainstem.left` | 至少一个左小脑端点；两端限于左小脑或脑干；经过左小脑白质及脑干；排除右小脑、幕上端点或经过区域 |
| `cerebellar_brainstem.right` | 对应的右侧条件 |
| `cerebellar_bilateral` | 两端分别位于左右小脑；经过双侧小脑白质与脑干；排除幕上端点或经过区域 |

这三组是较宽泛的区域候选流线，不直接赋予小脑上、中、下脚的标签，也不据此判断突触连接。
精细小脑脚分析需额外的解剖路标与相应审核。

经过区域仍沿用作者默认阈值 `2.0`，即每个标签内的采样点比例，而非毫米长度。
端点排除独立判断。规则及导入文件均记录快照与哈希；组合预设先读取原有规则，再读取
新增定义，不重复导入标签，以保持原有 CST 和半球集合不变。

## 本次实测

官方规则与 DDParcel 的白质及胼胝体编号不同；解释空束前请参阅
[标签兼容性说明](DDPARCEL_WMQL_COMPATIBILITY.zh-CN.md)。

已有 UKF 输入共 277,875 条流线。组合运行耗时 19.57 秒，得到 44 个非空输出，
其中新增左小脑—脑干 315 条、右侧 436 条、双侧小脑 432 条，均超过未修改的 20 条采样下限。

检查包括：原有 48 项与历史官方预设结果逐流线一致；全部 51 项与直接调用作者引擎一致；
三项新增结果与独立计算的完整输入期望集合一致；原始输入归属、几何、哈希及规则快照检查。
原有 7 项空输出和 10 项采样不足仍保留，组合运行不被标为全部束 QC 通过。

见[独立区域检查](../release/benchmarks/wmql_cerebellar_20261030.json)；原预设范围见
[覆盖核查](../release/benchmarks/wmql_coverage_20261030.json)。可复核工具为
`scripts/audit_wmql_cerebellar.py`、`scripts/validate_wmql_official.py`。

---

Results 图展示实际提取的三组新增结果，并通过独立色键和图注明确其区域查询身份。
执行、规则一致性及采样检查与人工解剖审核分别记录。
