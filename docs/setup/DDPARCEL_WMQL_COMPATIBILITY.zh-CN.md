<div align="center">

# DDParcel 与 WMQL 标签兼容性

[配置](../README.zh-CN.md) | [区域查询](WMQL_CEREBELLAR.zh-CN.md) | [English](DDPARCEL_WMQL_COMPATIBILITY.md)

</div>

---

## 标签定义

DDParcel 预测 101 个解剖区域。网络先输出 82 个合并类别，再拆分部分左右皮层区域。
其训练标签主动将区域白质合并为左右 `2/41`，将胼胝体分段合并为 `192`。
因此，没有 `3000/4000` 系列不代表模型漏预测；旧输出文件名中的 `wmparc` 也不代表
它包含完整 FreeSurfer 白质分区。

| 结构 | DDParcel | 本仓库固定的 WMQL 官方规则 |
| --- | --- | --- |
| 左右大脑白质 | `2/41` | 部分规则需要皮层对应的区域白质 `3000/4000` 系列 |
| 胼胝体 | `192` | `corpuscallosum.left/right` 引用 `1004/3004` 与 `2004/4004` |
| 半卵圆中心 / 未细分白质 | 合并为 `2/41` | 作者别名使用 `5001/5002` |

当这些别名没有对应标签时，部分官方查询会变空或过于严格。例如 `CC`、`CC_5`、
`CC_6` 中的必需胼胝体条件无法满足；`only()` 还可能排除经过通用白质的候选。
`CC_4` 使用左右中央前回端点条件，应单独检查，不能归因于同一胼胝体编号问题。

## 本次核查

- 本地标签映射、训练标签转换及矢状位映射函数与作者提交
  `257ec7c2a02209f86365dc5c0b39755458a3f776` 的语法树一致。
- 配准空间及原生空间均包含全部 101 个非背景标签，没有意外标签。
- 胼胝体 `192` 在两个空间分别包含 3,814 和 1,754 个体素；不同体素大小下不直接比较计数。
- 用记录的逆变换和 Slicer CLI 重新导出原生标签，体素与 affine 完全一致。
- UKF 与原生分区共用空间网格和掩膜。UKF 使用记录的 b0 加 b≈1000 子集，
  不是全部 288 个扩散体积；其 b0 值及向量在工作副本中显式归零。

这些检查没有发现标签映射、原生导出或两条路线坐标网格的错误。
分区的解剖精度仍通过图像复核或带参考标签的实验评价。
[核查凭据](../release/benchmarks/ddparcel_wmql_compatibility_20261030.json) 同时保留
独立 SimpleITK 实现的一处半体素边界舍入差异；实际 Slicer CLI 的复算完全一致。

## 使用与检查

WMQL QC 分别记录执行、输出完整性和逐查询采样情况，并输出标签兼容性提示。
正常的 DDParcel 输出不能自动保证所有官方 WMQL 查询都有充分采样。
本次组合示例仍保留 7 项空输出和 10 项采样不足，不修改原有 QC 门槛。

可使用在同一空间内、满足所选规则的已审核分区，或使用独立命名、经过验证的自定义查询。
不要将整个通用白质直接替换为多个区域标签，也不要仅为增加流线数量去除 `only()` 条件。
WMA 和 TractCloud 不使用这套 DDParcel 区域标签条件，其覆盖情况应独立检查。

## 实验性邻近白质分区

CLI 新增 `--wmql-atlas-mode ddparcel_wm`，默认仍为 `native`。实验路线保持作者查询
及原生 DDParcel 图像不变，在 WMQL 输出目录中独立生成派生分区：

- 仅在原来的左右大脑白质内，按物理距离寻找同侧最近的皮层区域；距皮层体素中心
  不超过 5 mm 的白质取得对应区域白质标签，更远的白质使用 `5001/5002`。
- 仅对已有胼胝体 `192`，按距原左右白质的距离拆为 `3004/4004`；等距体素保留 `192`。
- 皮层、皮层下、小脑及背景体素完全不变。
- 保存输入、输出及实现代码哈希、空间矩阵、单位与参数，输入变化或缓存损坏后重新生成。

5 mm 参考 FreeSurfer 白质分区的邻域尺度；这里使用体素中心，而 FreeSurfer 使用表面顶点，
因此两者不是同一种分区实现。`5001/5002` 表示剩余未分区白质，不当作已经验证的半卵圆中心 ROI。
即使采样达到门槛，实验路线也保留解剖审核状态，不自动判为科学 QC 通过。不扩张组织掩膜，
不生成或复制流线，不为凑齐输出而放宽查询。

```sh
"$SLICER_LAUNCHER" --launch PythonSlicer run_subject_pipeline.py \
  --subject-root /path/to/subject --subject-id sub-01 \
  --targets parcellation,tractography,bundles \
  --tractography-backend ukf --bundle-backend wmql \
  --wmql-query-preset official_cerebellar \
  --wmql-atlas-mode ddparcel_wm --run-name wmql-territories-pilot --plan
```

检查计划后，将 `--plan` 改成 `--execute`。UKF 调用已安装的 UKFTractography 扩展。
与原生标签比较时使用独立运行名称；GUI 默认设置及已审核的论文结果图保持不变。

### 配对试验

每一对使用相同流线、作者查询、阈值及输出目录清单；原采样门槛仍为每束 20 条流线。

| 被试／追踪输入 | 原生非空数／51 | 派生非空数／51 | 原生采样通过数／51 | 派生采样通过数／51 |
| --- | --- | --- | --- | --- |
| 100307／UKF | 44 | 50 | 34 | 43 |
| 100206／CSD/ACT | 39 | 51 | 32 | 48 |
| 149741／CSD/ACT | 32 | 50 | 27 | 49 |

覆盖增加不等于全部验收通过。有些查询的计数下降：100307 的右 SOFF 从 63 降到 10；
100206 的左右 AF 从 63／27 降到 15／4。区域白质标签也会触发作者原有的排除条件，
因此目前仅作为显式选择的实验路线，不替换默认路线或论文中已审核的原生分区结果。
UKF 案例另用作者引擎直接复跑，51 项查询结果完全一致，所有输出流线都来自原输入。
三个被试的独立抽样距离计算及全体非白质体素保留检查均通过。

完整逐查询前后计数见[配对凭据](../release/benchmarks/wmql_territories_20261030.json)。

---

来源：[DDParcel 论文](https://doi.org/10.1109/TMI.2023.3331691)、
[作者标签转换源码](https://github.com/zhangfanmark/DDParcel/blob/257ec7c2a02209f86365dc5c0b39755458a3f776/data_loader/load_neuroimaging_data.py)、
[WMQL 输入说明](https://tract-querier.readthedocs.io/en/latest/example_script.html)、
[FreeSurfer 白质分区源码](https://github.com/freesurfer/freesurfer/blob/dev/mri_aparc2aseg/mri_aparc2aseg.cpp)、
[FreeSurfer 标签定义](https://surfer.nmr.mgh.harvard.edu/fswiki/FsTutorial/AnatomicalROI/FreeSurferColorLUT)。
