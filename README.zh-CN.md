# SlicerDDSurfer（中文版）

SlicerDDSurfer 是一个 3D Slicer scripted module，用于扩散 MRI 的解剖重建和连接组分析。它整合了输入准备、环境检查、分割、分区、表面重建、微结构指标、纤维追踪、束分析、connectome 生成和 Slicer 内结果检查。

本项目面向研究流程，重点是生成可追踪的输出、QC 文件和 provenance 记录，而不是替代下游统计分析或专家解释。

**English README:** [README.md](README.md)

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

`git clone` 只下载源码、脚本、文档、配置、`models/assets_manifest.json` 和 Git LFS pointer。大模型权重和模板需要通过 downloader 单独拉取，并用文件大小和 SHA256 校验。

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
python3 run_subject_pipeline.py \
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

在 3D Slicer 中打开 `SlicerDDSurfer` 模块后，可以完成：

- subject-root 选择；
- 依赖 preflight 和外部路径覆盖；
- 运行前 run-plan 检查；
- 后台执行和取消；
- output tree、report、manifest、QC 文件检查。

详细依赖配置见
[docs/setup/EXTERNAL_DEPENDENCIES.md](docs/setup/EXTERNAL_DEPENDENCIES.md)。

## 模型资源

推荐默认下载：

```bash
scripts/download_model_assets.sh --profile core
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

## 验证

常用本地检查：

```bash
make test-fast
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

## 文档入口

- [docs/assets/MODEL_ASSETS.md](docs/assets/MODEL_ASSETS.md)：模型权重、模板和 mirror。
- [docs/setup/EXTERNAL_DEPENDENCIES.md](docs/setup/EXTERNAL_DEPENDENCIES.md)：Python 包和外部工具配置。
- [docs/architecture/PRODUCT_ARCHITECTURE.md](docs/architecture/PRODUCT_ARCHITECTURE.md)：流程和输出结构。
- [docs/release/RELEASE.md](docs/release/RELEASE.md)：发布流程。
- [docs/release/DOI_ARCHIVE_PREP.md](docs/release/DOI_ARCHIVE_PREP.md)：代码归档和模型资产边界。

## License 和引用

见 [LICENSE](LICENSE)、[CITATION.cff](CITATION.cff) 和
[docs/assets/MODEL_ASSET_TERMS.md](docs/assets/MODEL_ASSET_TERMS.md)。
