<div align="center">

# 用 Slicer 示例完成首次 DTI

[快速开始](QUICKSTART.zh-CN.md) | [环境准备](MANAGED_SETUP.zh-CN.md) | [实测记录](../release/benchmarks/slicer_sample_dti_20261028.json) | [English](SLICER_SAMPLE_DTI.md)

</div>

直接使用 Slicer 自带的 **DWIVolume** 示例练习输入转换和 DTI。
该数据为 128 × 128 × 94 体素、1.5 mm 分辨率、43 个测量：1 个 b0 和
42 个 b = 1,000 s/mm² 方向。它是单壳 DTI 示例，不用于验证多壳 NODDI/DKI
或解剖重建精度。

---

## GUI 操作

1. 安装 SlicerDDSurfer 和 SlicerDMRI。在 **Sample Data** 下载 **DWIVolume**。
   若当前版本没有显示该按钮，可在 Python 控制台执行
   `import SampleData; SampleData.downloadSample('DWIVolume')`。
2. 通过 Slicer 的 **Save** 对话框，把下载的 DWI 节点保存为扩散 NRRD。
   使用新的工作目录，保留原下载文件。
3. 打开 SlicerDDSurfer 的 **高级设置 > 脑区与输入导入 > 输入导入/转换**，
   选择该 NRRD 和新的被试目录。先预览计划，再取消 Dry run 并准备输入。
4. Subject root 指向准备好的被试目录。只勾选 **Microstructure**，在旁边的
   **...** 中只保留 **DTI**；本例取消预处理及其他产品。
5. 准备所选环境。默认 PNL 掩膜需要相应模型及运行时；明确改选 MRtrix 掩膜时
   则需要 MRtrix。在 **高级设置 > 预处理与掩膜** 选择已准备好的方法。
   本次记录使用 MRtrix；出错不会自动更换算法。
6. 点击 **Run SlicerDDSurfer**。FA/MD 成功后自动加载。检查脑掩膜、方向、
   参数图及 **结果与 QC**。没有脑区标签时不生成区域统计表。

---

## 预期结果

标准输入为 `input/data.nii.gz`、`input/bvals` 和 `input/bvecs`。
DTI 图保存在 `outputs/02_microstructure/dti/`，运行记录位于
`outputs/00_run_metadata/`。NRRD 与 NIfTI 可能使用不同的存储顺序，
需要按实际空间位置核对，不应只比较未经方向变换的数组索引。

Linux/Slicer 5.10 实测核对了上游文件哈希、方向变换后的体素逐值一致性、
空间与梯度一致性以及记录的 DTI 输出 QC。已配置参考工作站上的 DTI 任务耗时
9.46 秒，不包含下载、导入、掩膜准备、依赖检查及 Slicer 启动。人工解剖审核仍独立进行。

DWIConvert 拒绝无符号 16 位 NRRD 时，导入器会先确认所有数值均能无损表示为
int16，再生成保留空间及梯度信息的临时文件。超范围时拒绝转换，不启用
`--allowLossyConversion`，也不修改原始文件。

---

## 来源

示例直接取自 [Slicer SampleData](https://github.com/Slicer/Slicer/blob/main/Modules/Scripted/SampleData/SampleData.py)
和 [SlicerTestingData](https://github.com/Slicer/SlicerTestingData)，本仓库不镜像原始数据。
使用及再次分发需遵循上游条款。来源哈希与本次验证范围保存在页面上方的 JSON 中。
