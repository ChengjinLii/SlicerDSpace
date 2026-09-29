# AGENTS.md

本文件记录 `SlicerDDSurfer` 当前阶段的关键信息，供后续 agent / 开发者接手时快速建立上下文。

## 项目目标

`SlicerDDSurfer` 当前不再只是单一 `DDSurfer` 插件，而是在向一个以 diffusion MRI 为核心的统一分析平台演进。

当前已纳入或明确规划中的一级功能包括：

- `DDSurfer`
- `DDParcel`
- `DDSeg`
- Microstructure
- Tractography
- Connectome

功能范围的草图整理文档见：

- [SlicerDDSurfer_feature_scope_from_sketch.md](/data/chengjin/SlicerDDSurfer/SlicerDDSurfer_feature_scope_from_sketch.md:1)
- [UNIFIED_PIPELINE_DESIGN.zh-CN.md](/data/chengjin/SlicerDDSurfer/UNIFIED_PIPELINE_DESIGN.zh-CN.md:1)

## 统一输入约定

推荐所有任务共用同一个 `subject_root`：

```text
<subject_root>/
  input/
    data.nii.gz
    bvals
    bvecs
    nodif_brain_mask.nii.gz
```

当前代码已支持：

- `DDSurfer` 从 `subject_root` 直接运行
- `DDParcel` 从 `subject_root` 直接运行
- `DDSeg` 从 `subject_root` 直接运行

同时保留兼容：

- `DDSurfer` 旧的 `*-Reg.nii.gz + mask-Reg + tfm` 输入布局
- `DDSeg` 旧的显式 `mask + dwi + bval + bvec` 输入模式

## 共享缓存设计

当前共享缓存已经落地，目录约定如下：

```text
<subject_root>/
  cache/
    native_dti/
      ls/
      wls/
    registered_dti/
      <atlas>__wls/
  outputs/
    ddsurfer/
    ddparcel/
    ddseg/
```

语义分层：

- `cache/native_dti/ls`
  - 面向 `DDSeg`
- `cache/native_dti/wls`
  - 面向 `DDParcel` / `DDSurfer` 上游
- `cache/registered_dti/<atlas>__wls`
  - 面向 `DDSurfer` / `DDParcel`

缓存复用策略：

- `DDSeg` 优先复用 `native_dti/ls`
- `DDSurfer` 优先复用 `registered_dti/...`
- `DDParcel` 优先复用 `registered_dti/...`

每个 bundle 都带有 `manifest.json`，用于校验输入文件和参数是否匹配。

## 当前代码结构

关键入口和模块：

- 主模块入口：
  - [SlicerDDSurfer.py](/data/chengjin/SlicerDDSurfer/SlicerDDSurfer.py:1)
- 共享 pipeline：
  - [sharedpipeline/pipeline.py](/data/chengjin/SlicerDDSurfer/sharedpipeline/pipeline.py:1)
- DDSurfer 主流程：
  - [ddsurferpipeline/](/data/chengjin/SlicerDDSurfer/ddsurferpipeline:1)
- DDParcel：
  - [ddparcpipeline/pipeline.py](/data/chengjin/SlicerDDSurfer/ddparcpipeline/pipeline.py:1)
- DDSeg：
  - [ddsegpipeline/src/ddseg/pipeline.py](/data/chengjin/SlicerDDSurfer/ddsegpipeline/src/ddseg/pipeline.py:1)
- DDSeg 子进程入口：
  - [ddsegpipeline/src/run_ddseg.py](/data/chengjin/SlicerDDSurfer/ddsegpipeline/src/run_ddseg.py:1)
- UI：
  - [Resources/UI/SlicerDDSurfer.ui](/data/chengjin/SlicerDDSurfer/Resources/UI/SlicerDDSurfer.ui:1)

## 已完成的重要重构

1. 把用户入口统一到了原始 diffusion 输入：
   - `data.nii.gz`
   - `bvals`
   - `bvecs`
   - `nodif_brain_mask.nii.gz`

2. 抽出了共享缓存层：
   - `ensure_native_dti_bundle(...)`
   - `ensure_registered_dti_bundle(...)`

3. `DDSurfer` 已能直接从 `subject_root` 启动，并自动复用 `registered_dti`

4. `DDParcel` 已能直接从 `subject_root` 启动，并自动复用 `registered_dti`

5. `DDSeg` 已能直接从 `subject_root` 启动，并自动复用 `native_dti/ls`

6. 修复了多处旧脚本式包导入问题：
   - `ddparcpipeline` 中一批绝对导入已改为相对导入
   - `conversion/` 子包已改为 lazy export，避免无关依赖拖死导入

7. 修复了 `DDParcel` 输出命名 bug：
   - `DDSurfer_Pred.py` 现在优先使用显式传入的 `subject_id`

8. 为 repo 增加了基础 `.gitignore`

## Slicer / 运行环境

当前已验证的本机 Slicer：

- `/data/chengjin/software/Slicer-5.10.0-linux-amd64`

当前运行方式要点：

- 直接启动 `Slicer` 时依赖本机包装脚本：
  - `/data/chengjin/software/run-slicer.sh`
- headless 测试使用：
  - `/data/chengjin/software/xvfb/usr/bin/xvfb-run`
- `SlicerDMRI` 扩展已安装
- `PyTorch` 扩展已安装

PyTorch 说明：

- `PyTorch` 是 Slicer 扩展
- `torch` 是该扩展管理并安装到 Slicer 内置 Python 环境中的包

当前已确认：

- `torch 2.11.0+cu129`
- `torchvision 0.26.0+cu129`

当前已补齐并验证存在于 Slicer Python 环境中的依赖：

- `nibabel`
- `pynrrd`
- `SimpleITK`
- `networkx`
- `trimesh`
- `tqdm`
- `scikit-image`
- `h5py`
- `plumbum`

## 关键兼容性处理

当前代码里有几项专门为这台机器和 Slicer 5.10 做的兼容：

- `launcherExecutableFilePath` 在该版本中是属性，不是函数
- `SlicerDMRI` 的 CLI 在 headless 下不会稳定注册到 `slicer.modules`
- 因此 `sharedpipeline` 增加了 CLI 磁盘扫描回退
- 扩展 CLI 缺少动态库路径时会报 `libvtkDMRI.so`，因此执行 CLI 时会显式补 `LD_LIBRARY_PATH`

额外说明：

- `DDSeg` 在 `SlicerApp-real` 进程内直接运行时会异常退出
- 同一代码在 `PythonSlicer` 内稳定
- 因此 `runDDSegPipeline()` 现改为调用 `PythonSlicer` 子进程执行

## 已验证的测试 subject

测试 subject 路径：

- [/data/chengjin/SlicerDDSurfer-test/100307](/data/chengjin/SlicerDDSurfer-test/100307:1)

来源：

- `/dataset/nfs_share01/HCP/HCP-YA/3T/Diffusion_Preprocessed/100307`

当前已存在的测试结构：

- `input/`
- `cache/native_dti/ls`
- `cache/native_dti/wls`
- `cache/registered_dti/100HCP-population-mean-T2__wls`
- `outputs/ddsurfer`
- `outputs/ddparcel`
- `outputs/ddseg`

## 已完成的真实联调结果

### DDSurfer

已从同一个 `subject_root` 跑通完整流程，输出位于：

- [/data/chengjin/SlicerDDSurfer-test/100307/outputs/ddsurfer](/data/chengjin/SlicerDDSurfer-test/100307/outputs/ddsurfer:1)

已生成：

- `100307_predicted_wm_lh.stl`
- `100307_predicted_wm_rh.stl`
- `100307_predicted_pial_lh.stl`
- `100307_predicted_pial_rh.stl`

说明：

- headless 测试时曾临时短路 `_load_model_node()`，避免 MRML scene 加载影响算法验证
- 算法链路和文件输出已确认成功

### DDParcel

已从同一个 `subject_root` 跑通，并验证缓存复用，输出位于：

- [/data/chengjin/SlicerDDSurfer-test/100307/outputs/ddparcel](/data/chengjin/SlicerDDSurfer-test/100307/outputs/ddparcel:1)

关键输出包括：

- `100307-DDSurfer-wmparc-Reg.mgz`
- `100307-DDSurfer-wmparc.nii.gz`

已确认：

- 首次运行会复用 `registered_dti`
- 二次运行几乎瞬时完成，说明缓存与产物复用正常

### DDSeg

已从同一个 `subject_root` 跑通，输出位于：

- [/data/chengjin/SlicerDDSurfer-test/100307/outputs/ddseg](/data/chengjin/SlicerDDSurfer-test/100307/outputs/ddseg:1)

关键输出包括：

- `SegmentationMap_GMWMCSF.nii.gz`
- `ProbabilisticMap_GM.nii.gz`
- `ProbabilisticMap_WM.nii.gz`
- `ProbabilisticMap_CSF.nii.gz`

已确认：

- 复用 `cache/native_dti/ls`
- 通过 `PythonSlicer` 子进程稳定运行

## 当前 UI 状态

当前 UI 已经开始向统一入口迁移：

- 顶部说明已强调三条任务共享同一个 `subject_root`
- `DDSurfer` 面板支持新的统一输入
- `DDParcel` 面板支持新的统一输入
- `DDSeg` 面板已补入 UI
  - 推荐模式：直接提供 `subject_root`
  - 兼容模式：手动提供 `mask + dwi + bval + bvec`

默认填充值：

- `DDParcel` atlas 会自动填默认 T2 atlas
- `DDSeg` weights 目录会自动填 `ddsegpipeline/weights`
- `DDSeg` 的 `Slicer base` 和 `SlicerDMRI extension` 会尽量自动填

## 当前已知后续方向

根据手写需求草图，项目后续还应继续覆盖：

- Microstructure
  - `ROI-wise FA`
  - `FA / MD`
  - `Free Water`
  - `NODDI`
- Tractography
  - `DTI`
  - `CSD`
  - `ACT`
  - 以及待确认的 `SAT/SAF`、`DDTracking`
- Connectome
  - 目标是尽量消除对 `T1w` 的依赖

详见：

- [SlicerDDSurfer_feature_scope_from_sketch.md](/data/chengjin/SlicerDDSurfer/SlicerDDSurfer_feature_scope_from_sketch.md:1)

## 当前仓库状态

当前仓库存在未提交改动，主要集中在：

- `SlicerDDSurfer.py`
- `sharedpipeline/`
- `ddparcpipeline/`
- `ddsegpipeline/`
- `Resources/UI/SlicerDDSurfer.ui`
- 文档文件

开始任何新的大改之前，应先注意：

- 工作树不是干净的
- 不要回退现有修改
- 新功能应继续围绕统一 `subject_root` 和共享缓存结构展开
