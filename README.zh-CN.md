# SlicerDDSurfer（中文版）

SlicerDDSurfer 是一个 3D Slicer scripted module，用于扩散 MRI 的解剖重建和连接组分析。它整合了输入准备、环境检查、分割、分区、表面重建、微结构指标、纤维追踪、束分析、connectome 生成和 Slicer 内结果检查。

本项目面向研究流程，重点是生成可追踪的输出、QC 文件和 provenance 记录，而不是替代下游统计分析或专家解释。

**English README:** [README.md](README.md)

**源码导航：** [仓库目录说明](docs/architecture/REPOSITORY_LAYOUT.md)。算法实现按功能放在各模块包，维护工具放在 `scripts/`，本地报告、缓存和发布产物统一放在忽略提交的 `ignore/`。根目录的旧命令入口保留兼容，但不再承载工具实现。

**DDSurfer 后端更新（2026-10-04）：** 已同步上游推理、四份 TANet 权重、变换后的初始化表面及 1 mm 图谱。迁移说明、运行环境选择与真实数据验证记录见 [同步与验证说明](docs/release/DDSURFER_SYNC_20261004.md)。

## 功能概览

- Slicer 图形界面：设置 subject-root、依赖检查、run plan、后台运行和结果查看。
- 命令行入口：支持单被试和批量运行。
- 模型权重下载器：基于 manifest 下载并校验 checksum。
- 规范输出树：每次运行写 manifest、QC、logs 和报告。
- 可选外部工具：MRtrix3、FSL、FreeSurfer、WMA、TractQuerier、TractCloud、SlicerDMRI。

## 快速开始

代码和模型权重是两个独立下载步骤：

```bash
git clone https://github.com/ChengjinLii/SlicerDDSurfer.git
cd SlicerDDSurfer

scripts/download_model_assets.sh --profile core
python3 scripts/download_model_assets.py --profile core --verify-only
```

`git clone` 只下载源码、脚本、文档、配置和 `models/assets_manifest.json`，不包含大模型权重或模板。模型资源需要通过 downloader 从独立资源仓库拉取，并用文件大小和 SHA256 校验。

默认情况下，权重不会放在 Slicer 插件/代码目录里，而是下载到用户资产目录：

- Linux: `$XDG_DATA_HOME/SlicerDDSurfer/model-assets` 或 `~/.local/share/SlicerDDSurfer/model-assets`
- macOS: `~/Library/Application Support/SlicerDDSurfer/model-assets`
- Windows: `%LOCALAPPDATA%\\SlicerDDSurfer\\model-assets`

用户可以通过 Slicer UI 里的 `Model assets root`、环境变量
`SLICERDDSURFER_MODEL_ASSETS_DIR`，或命令行 `--asset-root` 自定义路径：

```bash
python3 scripts/download_model_assets.py \
  --profile core \
  --asset-root /path/to/SlicerDDSurfer-model-assets \
  --source url \
  --source-id slicerdsurfer_models_git
```

## 最小命令行用法

准备 subject-root：

```text
sub-01/
  input/
    data.nii.gz
    bvals
    bvecs
    dwi.json                  # 可选
    nodif_brain_mask.nii.gz   # 可选
```

先做环境检查：

```bash
/path/to/Slicer --launch PythonSlicer run_subject_pipeline.py \
  --subject-root /path/to/sub-01 \
  --targets validation,preprocessing,microstructure,tractography,connectome \
  --doctor
```

只生成 run plan，不执行算法：

```bash
python3 run_subject_pipeline.py \
  --subject-root /path/to/sub-01 \
  --targets validation,preprocessing,microstructure,tractography,bundles,connectome \
  --microstructure-stages dti \
  --tractography-backend csd_act \
  --bundle-backend wmql \
  --plan
```

执行一个较小的产品组合：

```bash
python3 run_subject_pipeline.py \
  --subject-root /path/to/sub-01 \
  --subject-id sub-01 \
  --targets microstructure,tractography,connectome \
  --microstructure-stages dti \
  --tractography-backend dti_det \
  --execute
```

默认输出目录是 `<subject-root>/outputs/`。

## Slicer 图形界面

Linux Slicer 5.10 可以通过源码安装：

```bash
python3 scripts/stage_slicer_extension.py \
  --install-root ~/SlicerDDSurfer-extension --link-mode copy
```

打开 Slicer 的 **Edit > Application Settings > Modules**，在 **Additional module paths**
中添加 `~/SlicerDDSurfer-extension/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules`
对应的绝对目录，然后重启，在模块选择器中选择 **SlicerDDSurfer**。
通过 Extension Manager 安装相应流程所需的 **SlicerDMRI** 和 **PyTorch**。
这是源码安装方式，不能替代打包扩展的安装验收；更新源码后需要重新运行 staging。

在 3D Slicer 中打开 `SlicerDDSurfer` 模块后，可以完成：

- 使用有步骤状态的首次运行向导，分别选择模型目录、下载/续传模型、扫描本机依赖并查看可运行能力；
- 使用 `Demo / 我只是想试一下` 自动生成无隐私的微型 DWI，运行 validation、DTI 和确定性纤维追踪，并把关键结果加载回 Slicer 场景；
- subject-root 选择；
- 依赖 preflight 和外部路径覆盖；
- 运行前 run-plan 检查；
- 后台执行和取消；
- output tree、report、manifest、QC 文件检查。

界面中的路径示例会根据 Windows、macOS 或 Linux 自动切换。模型下载弹窗显示当前文件、字节进度和续传状态；取消时保留 `.part` 文件，再次点击即可继续。

详细依赖配置见
[docs/setup/EXTERNAL_DEPENDENCIES.md](docs/setup/EXTERNAL_DEPENDENCIES.md)。

语言、最近使用的 subject/output 路径、运行目标、后端和外部依赖路径会保存到本地 `user_config.json`，GUI 与命令行共用。路径和优先级见 [docs/setup/USER_CONFIG.md](docs/setup/USER_CONFIG.md)。

## 模型资源

推荐默认下载：

```bash
scripts/download_model_assets.sh --profile core
```

如果用户只 clone 代码仓库，希望从独立模型资源仓库下载，而不是依赖本仓库
Git LFS：

```bash
python3 scripts/download_model_assets.py \
  --profile core \
  --source url \
  --source-id slicerdsurfer_models_git
```

常用 profile：

- `core`：surface + segmentation + parcellation 资源。
- `surface`：DDSurfer 表面重建资源。
- `segmentation`：DDSeg 权重。
- `parcellation`：DDParcel 权重。
- `all`：全部 LFS 资源和测试 fixture。

详细 manifest、mirror、lockfile 和再分发边界见
[docs/assets/MODEL_ASSETS.md](docs/assets/MODEL_ASSETS.md)。

## 输入准备

用 `scripts/prepare_inputs.py` 把外部数据整理成标准 subject-root：

```bash
python3 scripts/prepare_inputs.py \
  --source /path/to/dicom_or_dwi_file \
  --subject-root /path/to/sub-01 \
  --subject-id sub-01
```

支持 DICOM 到 NIfTI、NIfTI+bval/bvec、以及通过 MRtrix3 `mrconvert` 处理 NRRD/NHDR。

也可以用 Makefile 入口：

```bash
SLICERDDSURFER_SOURCE=/path/to/dicom_or_dwi_file \
SLICERDDSURFER_SUBJECT_ROOT=/path/to/sub-01 \
SLICERDDSURFER_SUBJECT_ID=sub-01 \
make prepare-inputs
```

## 验证

常用本地检查：

```bash
make test-fast
make fresh-clone-smoke
python3 scripts/release_audit.py
python3 scripts/download_model_assets.py --profile core --verify-only
```

更完整的 release-candidate 检查：

```bash
python3 scripts/release_validation.py \
  --subject-root /path/to/sub-01 \
  --asset-mirror-dir /path/to/SlicerDDSurfer-models-core \
  --all-asset-mirror-dir /path/to/SlicerDDSurfer-models-all \
  --run-fresh-clone-smoke \
  --warn-only
```

## 依赖规划

只生成依赖报告、不修改系统：

```bash
python3 scripts/install_dependencies.py --profile core --platform Linux
python3 scripts/install_dependencies.py --profile bundles --platform Darwin
python3 scripts/install_dependencies.py --profile full --platform Windows
```

可以用 `--python-environment <conda-env-or-python-path>` 指定 Python 或 conda
环境。只有显式加 `--execute` 时，脚本才会把缺失的 Python 包安装到该环境中。
MRtrix3、FSL、FreeSurfer、WMA、TractCloud 等外部工具只生成安装说明，不会静默修改系统。

## 报告和本地清理

运行完成后生成 subject-level HTML/JSON/Markdown 报告：

```bash
SLICERDDSURFER_SUBJECT_ROOT=/path/to/sub-01 \
SLICERDDSURFER_RUN_NAME=Test1 \
make subject-report
```

清理本地缓存和被忽略的 smoke/report 临时产物：

```bash
make clean-local
```

## 文档入口

- [docs/assets/MODEL_ASSETS.md](docs/assets/MODEL_ASSETS.md)：模型权重、模板和 mirror。
- [docs/setup/EXTERNAL_DEPENDENCIES.md](docs/setup/EXTERNAL_DEPENDENCIES.md)：Python 包和外部工具配置。
- [docs/architecture/PRODUCT_ARCHITECTURE.md](docs/architecture/PRODUCT_ARCHITECTURE.md)：流程和输出结构。
- [docs/architecture/REPOSITORY_LAYOUT.md](docs/architecture/REPOSITORY_LAYOUT.md)：仓库布局和 GitHub 首屏整理规则。
- [docs/release/RELEASE.md](docs/release/RELEASE.md)：发布流程。
- [docs/release/DOI_ARCHIVE_PREP.md](docs/release/DOI_ARCHIVE_PREP.md)：代码归档和模型资产边界。

## License 和引用

见 [LICENSE](LICENSE)、[CITATION.cff](CITATION.cff) 和
[docs/assets/MODEL_ASSET_TERMS.md](docs/assets/MODEL_ASSET_TERMS.md)。
