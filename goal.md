# SlicerDDSurfer Release Candidate Goal

更新日期：2026-06-08

## 当前定位

SlicerDDSurfer 当前进入 Release Candidate 验证阶段。下一步不继续新增算法，而是证明现有 unified pipeline 可以：

- 作为正式 Slicer extension 被安装或模拟安装。
- 只暴露 `SlicerDDSurfer` 一个 Slicer scripted module，不误扫描仓库里的其他 `.py`。
- 从一个干净 `subject_root` 用一条命令跑出约定的 outputs 文件树。
- 在 Slicer UI 中完成依赖检查、partial run、结果自动加载和报告打开。

## 当前已完成基线

- 代码目录已按产品域收拢：`shared/`、`preprocessing/`、`surface/`、`parcellation/`、`segmentation/`、`microstructure/`、`tractography/`、`connectome/`。
- 主模块入口 `SlicerDDSurfer.py` 已保持为薄入口，UI/logic glue 拆到产品域和 `shared/`。
- 统一命令入口保留为 `run_subject_pipeline.py`，真实实现移动到 `shared/run_subject_pipeline_cli.py`，避免正式 extension 顶层误扫描 CLI 脚本。
- `CMakeLists.txt` 只把 `${MODULE_NAME}.py` 放入 `MODULE_PYTHON_SCRIPTS`，其他 Python 支撑代码走 resources/package 目录。
- 已新增 `SlicerDDSurfer.s4ext`，声明 Slicer extension metadata 和推荐依赖 `SlicerDMRI`、`PyTorch`。
- 已新增 `scripts/release_audit.py`，检查 `.gitignore`、Git LFS、大文件、`third_party/`、测试输出、`.s4ext`、CMake module entry。
- 依赖检查已产品化：Slicer UI 显示 Python 包安装目标、外部依赖缺失项、auto-installable Python 包、manual setup 外部工具，并支持依赖路径配置导入/导出。
- 外部工具策略已明确：MRtrix3、FSL、FreeSurfer、WMA、TractCloud 不静默安装，只生成平台化安装说明和路径配置。
- pipeline 结束后自动生成 `report.html`、`provenance.json`、`qc_summary.json`，输出到 `outputs/06_slicer_scene_report/`。
- Slicer UI 已支持根据 manifest 自动加载关键结果：FA/MD/DTI scalars、Free Water、NODDI、connectome table；FiberBundle 加载会在 SlicerDMRI loader 不可用时明确跳过。
- Slicer UI 已增加 `Open latest report`，可直接打开最新 HTML 报告。
- Free Water / NODDI long regression 已在 `100307-release-candidate` 上完成：Free Water joblib/8 workers 处理 740916 voxels，NODDI 完成并生成 NDI/ODI/IsoVF；同一命令 resume 为 0 run / 3 skipped / 0 blocked。
- SAF 已完成一键闭环验证：使用 RC CSD/FOD、ACT `.tck`、显式 FastSurfer `--saf-fs-dir` 生成 `SAF.tck`、`SAF.vtk`、`saf_qc.json`，streamline count 为 1316；同一命令 resume 为 0 run / 1 skipped / 0 blocked。
- WMA / TractCloud 已有真实 completed 证据汇总：`bundle_backend_closure.json` 记录 WMA 800 clusters / 74 anatomical tracts，TractCloud 17 bundles / 5 categories；它们仍是显式外部后端，依赖外部 checkout、atlas/model 和 Python/Slicer runtime。
- 100307 既有样例已证明 unified command resume、report、QC、输出树审计和 Slicer UI smoke 可运行。
- 已新增 extension-like staging 验证：`scripts/stage_slicer_extension.py` 会生成只含 `SlicerDDSurfer.py` 的 `qt-scripted-modules/` 目录，并排除 `third_party/`、测试目录和非模块脚本。
- 真实 Slicer staged install smoke 已通过：Slicer 只注册 `SlicerDDSurfer`，不误注册 `workflow_catalog`、`run_subject_pipeline`、`release_audit` 等 helper。
- 干净 subject `/data/chengjin/SlicerDDSurfer-test/100307-release-candidate` 已用统一命令跑通 DTI-only release gate：DDSeg、DDParcel、DDSurfer、DTI microstructure、MRtrix CSD/FOD/ACT、SIFT2、WMQL AF/CST、connectome、report/QC/provenance。
- 同一 RC 命令第二次运行已验证 resume：只重新运行 validation，其余完成结果被 `skipped/reused`。
- 已修复 `PythonSlicer` 调 MRtrix Python 脚本的环境污染问题：CSD/ACT backend 会清理 Slicer `PYTHONHOME` / `PYTHONPATH` 并优先使用用户配置的 MRtrix `bin`。
- 真实 Slicer UI report/auto-load smoke 已通过：run panel 能读取 RC manifest，report 按钮可用，并自动加载 DTI maps、DDParcel/DDSeg volumes、DDSurfer surfaces。
- 已新增 [RELEASE_CANDIDATE_VALIDATION.md](RELEASE_CANDIDATE_VALIDATION.md)，记录 staging、真实 Slicer smoke、一条命令、resume、输出审计和 UI smoke 命令。
- 最新验证记录见 [RELEASE_CANDIDATE_VALIDATION.md](RELEASE_CANDIDATE_VALIDATION.md)。

## Release Candidate 当前任务

### 1. 正式安装或模拟安装验证

目标：不再使用临时 symlink module dir，改用 extension-like staging 目录模拟 Slicer extension 安装。

验收标准：

- staging 目录中 `qt-scripted-modules/` 顶层只有 `SlicerDDSurfer.py`。
- `shared/`、`surface/`、`microstructure/`、`tractography/` 等支撑包在 staging 目录内可 import。
- Slicer 使用 staging 目录启动后，只能发现 `SlicerDDSurfer` 模块，不能发现 `workflow_catalog`、`run_subject_pipeline`、`release_audit` 等非模块脚本。
- Slicer UI 能成功打开模块并初始化参数面板。

状态：已完成可落地部分。hardlink staging 和 copy-mode staging 均通过真实 Slicer smoke；本机 `cmake` 不存在，二进制 Slicer 未提供 `SlicerConfig.cmake`，因此完整 CMake/Extension Manager 构建在当前环境阻塞。

### 2. 干净 subject 一键全流程验证

目标：从一个只包含标准输入的干净 subject root 重新跑一遍 Release Candidate 命令。

候选目录：

```text
/data/chengjin/SlicerDDSurfer-test/100307-release-candidate
```

验收标准：

- 只复制标准输入到 `input/`：`data.nii.gz`、`bvals`、`bvecs`、`nodif_brain_mask.nii.gz`。
- 用一条 `/path/to/Slicer --launch PythonSlicer run_subject_pipeline.py ... --execute` 命令跑出 outputs。
- 第二次运行同一命令应 resume/skip 已完成步骤。
- 输出树包含：
  - `00_run_metadata/`
  - `01_preproc/`
  - `02_microstructure/`
  - `03_structural/`
  - `04_tractography/`
  - `05_statistics/`
  - `06_slicer_scene_report/`
- `report.html`、`provenance.json`、`qc_summary.json` 存在。
- `output_tree_audit.json` 状态为 passed 或明确列出可接受的 blocked/partial reason。
- Slicer UI 可以从该 subject 的 manifest 自动加载已有结果并启用 `Open latest report`。

状态：已完成。DTI-only release gate 已完成；Free Water / NODDI 作为单独 long regression 完成并通过 resume/report/数值审计。

### 3. 用户安装/配置/运行文档收口

目标：把用户真正需要执行的安装、检查、运行、排错步骤写成最终文档。

需要覆盖：

- Slicer 内如何加载/运行插件。
- 终端如何调用一条命令跑 pipeline。
- `--targets`、`--skip-targets`、`--microstructure-stages`、`--tractography-backend`、`--bundle-backend` 等核心参数。
- 缺 MRtrix3、FSL、FreeSurfer、WMA、TractCloud 时会如何显示。
- 哪些目标会 blocked，哪些目标仍可 partial run。
- 外部路径配置 JSON 如何导入/导出。
- Python 包安装到 Slicer Python 还是 shell Python 的区别。

## 建议执行顺序

1. 提交并推送 RC 验证文档和 LFS 归一化修复。
2. 若要做真正 Extension Manager 发布，在具备 `cmake` 和 Slicer extension build tree / `SlicerConfig.cmake` 的机器上重复 CMake configure/build。
3. 若要把 WMA/TractCloud 变为普通用户开箱即用，需要提供可再分发 atlas/model 获取策略和明确的 runtime installer；当前仅作为外部后端交付。

## 当前风险

- 本机 `/data/chengjin/software/Slicer-5.10.0-linux-amd64` 是二进制 Slicer，未发现 `SlicerConfig.cmake`，且当前 shell 没有 `cmake`，因此无法做完整 CMake configure/build。当前 release 验证采用 hardlink/copy-mode extension-like staging 加真实 Slicer smoke。
- 完整 subject run 不能依赖普通 shell `python3`；需要通过 Slicer `--launch PythonSlicer`，否则 Slicer CLI 模块解析不完整。
- Free Water / NODDI 已完成 long regression，但耗时仍显著高于 quick gate；快速 RC gate 继续使用 `--microstructure-stages dti`。
- WMA / TractCloud 的真实执行依赖外部 checkout、atlas、模型和 Python 环境。Release Candidate 验证可以复用已完成证据，但不能宣称这些后端在任意用户机器上无需配置即可执行。
- SlicerDMRI 不可用时 FiberBundle 自动加载会跳过 tractogram/bundle，但 volumes/tables/report 应仍可加载。
- 当前 STL surface 加载时 Slicer 会提示缺 coordinate-system metadata 并默认 LPS；不阻塞加载，但后续应作为 metadata/QC 优化项处理。
