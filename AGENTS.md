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

- [SlicerDDSurfer_target.md](/data/chengjin/SlicerDDSurfer/SlicerDDSurfer_target.md:1)
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
  - [shared/pipeline.py](/data/chengjin/SlicerDDSurfer/shared/pipeline.py:1)
- Surface / DDSurfer：
  - [surface/](/data/chengjin/SlicerDDSurfer/surface:1)
- Parcellation / DDParcel：
  - [parcellation/pipeline.py](/data/chengjin/SlicerDDSurfer/parcellation/pipeline.py:1)
- Segmentation / DDSeg：
  - [segmentation/pipeline.py](/data/chengjin/SlicerDDSurfer/segmentation/pipeline.py:1)
- DDSeg 子进程入口：
  - [segmentation/run_ddseg.py](/data/chengjin/SlicerDDSurfer/segmentation/run_ddseg.py:1)
- Microstructure：
  - [microstructure/pipeline.py](/data/chengjin/SlicerDDSurfer/microstructure/pipeline.py:1)
- Tractography / WMA scaffold：
  - [tractography/wma.py](/data/chengjin/SlicerDDSurfer/tractography/wma.py:1)
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

6. 产品代码已从旧根目录包迁移到：
   - `shared/`
   - `surface/`
   - `parcellation/`
   - `segmentation/`
   - `microstructure/`
   - `tractography/`
   - `connectome/`

7. 修复了 `DDParcel` 输出命名 bug：
   - `DDSurfer_Pred.py` 现在优先使用显式传入的 `subject_id`

8. 为 repo 增加了基础 `.gitignore`

9. 已将 WhiteMatterAnalysis 作为可选外部后端接入：
   - 来源：`https://github.com/SlicerDMRI/whitematteranalysis`
   - 接入点：`tractography/wma.py`
   - 发现方式：显式 `wma_root`、`SLICERDDSURFER_WMA_ROOT`、`WMA_ROOT` 或 PATH
   - 当前只做 dry-run command/manifest scaffold，不跑真实 WMA 数据任务

## Slicer / 运行环境

当前已验证的本机 Slicer：

- `/data/chengjin/software/Slicer-5.10.0-linux-amd64`

## Slicer UI 部署教训

这部分是后续 agent 必须遵守的经验结论，避免再次把 `SlicerDDSurfer` 和其他 Slicer 会话混在一起。

### 1. 不要复用现有 `:99 / 5900 / 6081` 链路

历史上这条链路经常已经被别的会话占用，尤其是：

- 旧的 `DMRIAgentSlicer`
- 旧版容器内 `Slicer 5.2.2`
- 其他用户或先前实验残留的 `Xvfb/x11vnc/websockify`

如果直接复用：

- `6081` 可能仍然桥接到 `DMRIAgent`
- 浏览器打开后看起来“能连上”，但实际显示的是错误应用
- 很难从 noVNC 链接表面判断背后到底是哪一个 Slicer 进程

结论：

- 不要默认使用既有 `6081`
- 优先起独立 viewer 端口，例如 `5903/6083`
- 端口和容器名必须显式区分

### 2. 不要把源码根目录直接作为 Slicer module path

`SlicerDDSurfer` 不是“把仓库根目录扔给 `--additional-module-path` 就能稳定加载”的模块。

直接这样做会导致两类问题：

- Slicer 误扫描非模块脚本
- `GetModuleHomeDirectory` / runtime import 计算失败

已验证稳定的方法是：

- 先运行 [scripts/stage_slicer_extension.py](/data/chengjin/SlicerDDSurfer/scripts/stage_slicer_extension.py:1)
- 使用它生成的 extension-like 安装目录：
  - `.../SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules`
- 然后把这个 `qt-scripted-modules` 目录传给 `--additional-module-path`

### 3. 不要把宿主机断链 symlink 直接挂进容器

之前踩过的错误是：

- 在宿主机创建一个指向 `/data/chengjin/SlicerDDSurfer/...` 的 symlink 目录
- 再把这个 symlink 目录 mount 到容器

结果：

- 容器内 symlink 目标路径不存在
- `SlicerDDSurfer.py` 在容器里变成断链
- Slicer 表面上拿到了 module path，实际无法 import

结论：

- 挂到容器里的必须是实体 staging 目录
- 最稳妥的做法是使用 `stage_slicer_extension.py --link-mode copy`

### 4. `--python-script/--python-code` 只有在“独立新实例”里才可信

在宿主机已有旧 Slicer 实例时：

- 新命令有可能只激活旧窗口
- `--python-script` / `--python-code` 可能根本不会重新执行

所以如果要自动切换到 `SlicerDDSurfer`：

- 优先在独立容器里起一个全新的 `Xvfb + Slicer`
- 再通过 `--python-script` 定时切换模块

### 5. 推荐的稳定方案

后续默认采用下面这条链路：

1. 用 `scripts/stage_slicer_extension.py` 生成最新 extension staging
2. 起独立容器
3. 容器内自己运行：
   - `Xvfb`
   - `x11vnc`
   - `websockify`
   - 本地 `Slicer 5.10`
4. `Slicer` 使用 staged `qt-scripted-modules/`
5. 用独立 noVNC 端口暴露，例如 `6083`

已经验证通过的关键判据：

- `SLICERDDSURFER_GUI_READY=1`
- 日志里出现 `Switch to module:  "SlicerDDSurfer"`

### 6. 已验证可复用脚本

后续不要再手工拼一长串 `docker run + Xvfb + noVNC + Slicer` 命令。

统一用：

- [scripts/start_isolated_slicerdsurfer_viewer.sh](/data/chengjin/SlicerDDSurfer/scripts/start_isolated_slicerdsurfer_viewer.sh:1)

这个脚本会：

- 重新 stage 最新 extension-like 安装目录
- 起独立容器 viewer
- 自动切到 `SlicerDDSurfer`
- 输出最终 noVNC 链接

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
- 因此 `shared` 增加了 CLI 磁盘扫描回退
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
- `DDSeg` weights 目录会自动填 `segmentation/weights`
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
  - `WMA ORG atlas clustering`
  - 以及待确认的 `SAT/SAF`、`DDTracking`
- Connectome
  - 目标是尽量消除对 `T1w` 的依赖

详见：

- [SlicerDDSurfer_target.md](/data/chengjin/SlicerDDSurfer/SlicerDDSurfer_target.md:1)

## 当前仓库状态

当前仓库存在未提交改动，主要集中在：

- `SlicerDDSurfer.py`
- `shared/`
- `surface/`
- `parcellation/`
- `segmentation/`
- `microstructure/`
- `tractography/`
- `Resources/UI/SlicerDDSurfer.ui`
- 文档文件

开始任何新的大改之前，应先注意：

- 工作树不是干净的
- 不要回退现有修改
- 新功能应继续围绕统一 `subject_root` 和共享缓存结构展开
