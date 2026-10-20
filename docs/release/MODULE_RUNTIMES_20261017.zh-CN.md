<div align="center">

# 模块运行时间

**2026-10-17 · Measured, scoped, traceable**

[Project](../../README.md) | [QC](BUNDLE_BACKENDS_20261013.zh-CN.md) | [GPU verification](GPU_POLICY_20261013.md) | [CSV](benchmarks/module_runtimes_20261017.csv) | [JSON](benchmarks/module_runtimes_20261017.json) | [Other language](MODULE_RUNTIMES_20261017.md)

</div>

汇总真实历史记录与本轮补测，共 32 项操作。READY 仅表示有明确范围的实测计时，不表示解剖准确性获认证。缺失不填 0，失败/跳过/缓存复用不充作成功计算。完整账本和来源哈希见下方 CSV/JSON。

新增计时包括三种输入导入、MRtrix/SynthStrip 掩膜、全新全脑 DTI、六指标 ROI 统计和三类束的 Slicer 加载。WMQL/TractCloud 使用真实重跑；WMA 仅在新运行完成独立验收后替换原 149741 范围记录。PNL/SynthStrip 和 MRtrix/FSL 已纳入本轮真实 GPU 验收，CPU 对照、重复运行和失败记录在下方单独展示。

---

| 模块 | 被试 | 设备 | 秒 | 分钟 | 状态 | 输入 / 范围 |
| --- | --- | --- | ---: | ---: | --- | --- |
| NIfTI 导入 | sub-dicom | 未记录 | 2.880 | 0.048 | READY | [104, 104, 60, 31] |
| DICOM 导入 | sub-dicom | 未记录 | 0.271 | 0.005 | READY | [104, 104, 60, 31] |
| NRRD 导入 | sub-dicom | 未记录 | 2.296 | 0.038 | READY | [104, 104, 60, 31] |
| 输入校验 | 877168 | 未记录 | 0.268 | 0.004 | READY | Subject 877168 / cohort_onepass_20261017; see frozen protocol |
| PNL CNN 掩膜 | 100307 | cuda | 84.437 | 1.407 | READY | 288-volume real HCP DWI |
| MRtrix 掩膜 | sub-dicom | 未记录 | 2.455 | 0.041 | READY | [104, 104, 60, 31] |
| SynthStrip 掩膜 | sub-dicom | cuda | 9.494 | 0.158 | READY | 31-volume real DWI |
| DIPY 预处理 | sub-dicom | 未记录 | 657.224 | 10.954 | READY | 31-volume real DWI |
| MRtrix/FSL 预处理 | sub-dicom | cuda | 719.476 | 11.991 | READY | 31-volume real DWI / reverse-PE b0 |
| 全新原生 DTI 拟合 | 100307 | 未记录 | 135.999 | 2.267 | READY | [145, 174, 145, 288] |
| DDSeg | 877168 | 未记录 | 46.707 | 0.778 | READY | Subject 877168 / cohort_onepass_20261017; see frozen protocol |
| DDSeg 世界坐标 QC | 877168 | 未记录 | 0.539 | 0.009 | READY | Subject 877168 / cohort_onepass_20261017; see frozen protocol |
| DDParcel | 877168 | 未记录 | 277.823 | 4.630 | READY | Subject 877168 / cohort_onepass_20261017; see frozen protocol |
| DDSurfer 原生表面 | 877168 | 未记录 | 213.753 | 3.563 | READY | Subject 877168 / cohort_onepass_20261017; see frozen protocol |
| 表面后处理 | 100307 | cpu | 726.217 | 12.104 | READY | Fresh full bilateral current-snapshot surface postprocessing; independent geometry/morphometry/annotation checks |
| DTI 参数导出 / ROI | 877168 | 未记录 | 7.630 | 0.127 | READY | Subject 877168 / cohort_onepass_20261017; see frozen protocol |
| Free-water | 100307 | 未记录 | 1288.584 | 21.476 | READY | Subject 100307 / task-specific inputs; see source manifest |
| AMICO NODDI | 100307 | 未记录 | 1784.280 | 29.738 | READY | Subject 100307 / task-specific inputs; see source manifest |
| DIPY DKI WLS | 100307 | cpu | 5496.222 | 91.604 | READY | Full supplied brain mask: 740916 voxels; 681770 valid; read-only full-grid and direct-DIPY sample parity passed |
| Python MK-Curve | 100307 | cpu | 989.384 | 16.490 | READY | 740916 mask voxels / 736294 corrected-valid; not all voxels valid |
| DTI 确定性追踪 | 100307 | 未记录 | 67.922 | 1.132 | READY | Subject 100307 / task-specific inputs; see source manifest |
| CSD / ACT / SIFT2 路线 | 877168 | 未记录 | 2670.909 | 44.515 | READY | Subject 877168 / cohort_onepass_20261017; see frozen protocol |
| SAF 重新筛选 | 100307 | 未记录 | 209.474 | 3.491 | READY | 100k tracks -> 13043 SAF candidates |
| WMQL | 877168 | 未记录 | 67.850 | 1.131 | READY | Subject 877168 / cohort_onepass_20261017; see frozen protocol |
| WMA ORG atlas | 100307 | 未记录 | 4664.826 | 77.747 | READY | 277875 source tracks / wma_cache_full_20261017 |
| TractCloud | 100307 | cuda | 18.500 | 0.308 | READY | 50k CSD/ACT tracks / batch 2048 / seed 0 |
| 流线计数连接组 | 877168 | 未记录 | 141.623 | 2.360 | READY | Subject 877168 / cohort_onepass_20261017; see frozen protocol |
| SIFT2 加权连接组 | 877168 | 未记录 | 139.081 | 2.318 | READY | Subject 877168 / cohort_onepass_20261017; see frozen protocol |
| 六指标脑区统计 | 100307 | 未记录 | 6.198 | 0.103 | READY | 101 regions |
| Slicer 加载 WMQL | 100307 | 未记录 | 0.189 | 0.003 | READY | 4 files / 27 streamlines |
| Slicer 加载 TractCloud | 100307 | 未记录 | 6.320 | 0.105 | READY | 39 files / 21432 streamlines |
| Slicer 加载 WMA | 149741 | 未记录 | 8.269 | 0.138 | READY | 74 files / 40338 streamlines |

---

## 计时边界

- DKI/MK-Curve 只有完整独立验收通过后才采用实测全脑时间；旧 64/8 体素记录保留且不外推。MK-Curve 计时不表示全部体素有效。
- DTI 参数导出行复用已经拟合的张量；全新 DTI 行包含拟合与六指标转换，两者不混淆。
- 表面后处理只有新版独立完整验收通过后才替换历史计时；范围和版本以 JSON 来源为准。
- 本表的历史 CSD/ACT/SIFT2 为组合阶段，不反推独立时间；新版运行在 manifest/QC 中逐步记录实际命令、转换和输出检查的耗时及失败位置。
- Slicer 加载时间包含独立坐标对照，排除启动和束提取。新全脑 DTI 测试进程总时间 165.7 秒，不冒充 136 秒拟合计时。
- 不同被试、输入规模、缓存、线程、版本与当时负载不可直接横比或相加；历史硬件/线程缺记录时不从当前机器反推。
- PNL 主表采用默认 Auto GPU 实测，而非最快一次；CPU 对照、显式 CUDA 重复和旧 CPU 346.7 秒记录均保留在 JSON。本轮 CPU 已约 79 秒，不能声称相对历史记录的四倍 GPU 加速。
- MRtrix/FSL 的 GPU 行约 719 秒是完整路线，包含 CPU denoise/Gibbs/topup/最终掩膜，不是 eddy 单步耗时。
- SynthStrip 旧环境 949 秒中止和 CUDA eddy 365 秒线程参数失败均不是成功计算；修正后的实测分别约 9 秒和 719 秒，解剖人工检查仍待完成。
- PNL 历史慢记录主要在 CNN 阶段（日志约 284 秒），当前 CPU 日志约 15 秒；历史负载/完整线程环境缺失，根因未能唯一确定。新生成掩膜保留分阶段计时和线程环境，实际 GPU 重跑也独立记录。
- 当前实测主机为 Xeon Platinum 8360Y、144 逻辑 CPU、约 503.5 GiB 内存、两张 H100；并非各记录都使用 GPU。
- 模型下载、可选 UKF 追踪/WMA diffusion-measurement 导出、批调度和最终场景保存不在本表范围。

---

## CPU / GPU 对照与失败记录

| 模块 | 运行 / 范围 | 请求 → 实际设备 | 秒 | 执行 / 完整性状态 |
| --- | --- | --- | ---: | --- |
| PNL CNN 掩膜 | CPU 对照 | cpu / cpu | 78.961 | pass |
| PNL CNN 掩膜 | 默认 Auto GPU 运行 | auto / cuda | 84.437 | pass / 主表采用 |
| PNL CNN 掩膜 | 显式 CUDA 重复 | cuda / cuda | 79.775 | pass |
| SynthStrip 掩膜 | 兼容环境 CPU 对照 | cpu / cpu | 14.268 | pass |
| SynthStrip 掩膜 | 兼容环境 Auto GPU 运行 | auto / cuda | 9.494 | pass / 主表采用 |
| SynthStrip 掩膜 | 不兼容环境中止；无掩膜 | 未记录 / 未记录 | 949.431 | fail |
| SynthStrip 掩膜 | 不兼容环境提前拒绝；未推理 | 未记录 / 未记录 | 1.579 | fail |
| MRtrix/FSL 预处理 | CUDA eddy 线程参数失败 | 未记录 / 未记录 | 365.179 | FAIL |
| MRtrix/FSL 预处理 | 修正 CUDA eddy 后的完整预处理 | 未记录 / cuda | 719.476 | PASS / 主表采用 |
| TractCloud | 固定种子 CUDA 推理及解码 QC | cuda / cuda | 18.500 | completed / 主表采用 |
| PNL CNN 掩膜 | 含分阶段计时的 Auto GPU 重复 | auto / cuda | 104.326 | pass |
| SynthStrip 掩膜 | 含分阶段计时的 Auto GPU 重复 | auto / cuda | 7.007 | pass |

设备缺少记录时不从日志推断；软件版本、输入哈希、来源文件和完整计时范围保留在 JSON。失败耗时仅供排障，不参与主表选取。

```bash
python scripts/collect_module_runtimes.py --output-dir /path/to/report --documentation-dir docs/release
```

本表为更新后的汇总；多数模块仍使用限定范围的历史记录，不表示全部在该日期重跑。
