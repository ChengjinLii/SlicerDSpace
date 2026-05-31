# SlicerDDSurfer Goal

更新日期：2026-05-31

## 当前定位

SlicerDDSurfer 的长期目标是从单一 DDSurfer Slicer 模块，扩展为一个以 diffusion MRI 为核心的统一分析平台。平台应尽量复用同一个 `subject_root` 输入、共享 DTI/cache 结果，并覆盖以下产品域：

- `Surface`
- `Parcellation`
- `Segmentation`
- `Microstructure`
- `Tractography`
- `Connectome`

当前仓库已经完成产品目录收拢和主入口拆分。`SlicerDDSurfer.py` 现在是薄入口，UI/logic glue 已经按产品域拆到 `shared/`、`surface/`、`parcellation/`、`segmentation/`、`microstructure/`。

## 已完成基线

- `Surface / DDSurfer`：支持从统一 `subject_root` 或 legacy registered 输入运行，复用 `registered_dti` cache，输出 native-space STL mesh。已新增 `surface.pipeline` headless facade，输出 `surface_manifest.json` / `surface_qc.json`，并可在资源齐备时由统一 product orchestrator 执行；Slicer 面板仍负责把生成模型加载到 scene。
- `Parcellation / DDParcel`：支持从统一 `subject_root` 运行，复用 `registered_dti` cache，输出 `DDSurfer-wmparc`。
- `Segmentation / DDSeg`：支持 subject-root 模式和 legacy 显式输入模式，复用 `native_dti/ls` cache，通过 `PythonSlicer` 子进程运行。
- `Microstructure`：已实现 FA/MD、ROI-wise stats、DIPY Free Water、AMICO NODDI，并支持 Free Water / NODDI 分阶段 cache 复用。
- `Testing`：已有 `test_product_facades.py` 和 `run_microstructure_regression.py`，100307 个体可用于 Microstructure 回归验证。
- `Product Architecture`：顶层目录已经收成 `shared/ surface/ parcellation/ segmentation/ microstructure/ tractography/ connectome/`。
- `Input Validation / QC`：已增加 `shared.validation`，覆盖必需文件检查、BIDS 相位编码/读出时间检查、bval/bvec 合理性检查、依赖环境检查和 QC JSON 报告；主 GUI `Validate` 按钮已接入 subject-root shared validation。
- `Tractography / WMA scaffold`：已将 WMA ORG atlas clustering 包装为 SlicerDDSurfer Tractography 内的可选外部后端，支持显式 `wma_root`、环境变量或 PATH 发现，提供 dry-run wrapper、backend 可用性检查、ORG atlas 结构检查、manifest、QC JSON 和轻量测试。已从 `/dataset/nfs_share01` 复制 `149741_wma_act` 最小测试子集，包含 downsampled VTK tractography、WMA VTP/CSV、DWI 梯度、mask 和 parcellation。
- `Tractography / DTI scaffold`：已增加 DTI tracking config/result、dry-run manifest、QC JSON、native DTI cache 复用扫描、Slicer logic glue 和轻量测试。
- `Tractography / ACT`：已增加 ACT config/result、MRtrix3 后端可用性检查、DDParcel/parcellation 依赖检查、5TT/GMWMI 标准 ACT readiness 检查、manifest、QC JSON 和轻量测试；已构造 MRtrix3 ACT 命令链，并支持在后端和标准 ACT 输入齐备时 `execute=True`。`third_party/act_mrtrix_reference` 仅作为本地参考脚本，不作为运行时默认依赖；`third_party/mrtrix3_reference` 已浅拷贝 MRtrix3 官方源码作为 ACT/tckgen/tcksift2/tck2connectome 参考实现，同样不作为运行时默认依赖。
- `Tractography / SAF`：已将 MATLAB-to-Python SAF 转写版收进 `tractography/saf_backend`，不再运行时依赖 `third_party/SAF-Python`；新增 `tractography.saf` facade，支持依赖检查、dry-run manifest/QC、`SlicerDDSurferLogic.runSAFPipeline(...)` 和 `execute=True` 调用入口，默认输出到 `outputs/04_tractography/saf`，执行后会尝试把 `SAF.tck` 作为 FiberBundle 加载到 Slicer scene。
- `Tractography / TractCloud`：wrapper 已支持外部 TractCloud source root，不要求包必须安装到当前 Python；可通过 `tractcloud_root`、`SLICERDDSURFER_TRACTCLOUD_ROOT` 或 `TRACTCLOUD_ROOT` 指向 checkout，执行时把 `src/` 注入 `PYTHONPATH`，manifest/QC 会记录 source root、pythonpath、backend packages 和输出 bundle summary。本机 `/data/chengjin/SlicerDDSurfer/third_party/TractCloud` 只读 probe 结果为 `tractcloud=true`、`torch=false`，说明源码可发现但真实模型执行仍缺运行环境依赖。
- `Connectome / Phase 1`：已增加 `connectome.pipeline`，显式依赖 tractography 输出和 DDParcel/parcellation 节点，输出 matrix/nodes、manifest、QC JSON 和轻量测试；`.tck` 可走 MRtrix3 `tck2connectome`，`.trk`/`.tck` 和 legacy `.vtk` 可走 Python endpoint-label fallback。已用 `149741_wma_act` 的 downsampled VTK + wmparc 做过真实 `execute=True` 验证，得到 100000 条 streamlines、61708 条 assigned、5535 条边。MRtrix dense matrix 现在支持可选 `compress_mrtrix_dense=True`：先保留 raw dense CSV，再按 parcellation 中实际存在的非零 ROI label 压缩为稀疏 edge-list，并在 manifest/QC 记录 dense path、remap mode、dense node count 和 remapped label count。
- `Real subject minimal closure`：已新增 `Testing/Python/run_real_subject_minimal_closure.py`，并用 `/data/chengjin/SlicerDDSurfer-test/100307` 跑通真实最小闭环：DTI FA/MD/AD/RD/L1/L2/L3、ROI-wise DTI stats、DIPY DTI `.trk`、WMQL execute、connectome matrix。当前回归参数 `--max-seed-voxels 5000 --min-fa 0.15 --wmql-execute` 生成 4944 条合法 streamlines，connectome assigned 4208 条、205 条边；WMQL 后端执行成功，但受限于稀疏 DTI tractogram，AF/CST bundle 命中数为 0。
- `Tractography / CSD-FOD-ACT`：已新增外部 MRtrix3 backend `tractography/csd.py`，覆盖 response function estimation、MSMT-CSD FOD、mtnormalise、ACT `tckgen`、可选 `tcksift2`、TCK-to-TRK 导出、manifest/QC 和测试。MRtrix3 已作为外部环境安装在 `/data/chengjin/software/mrtrix3_env`，插件不打包 MRtrix3；`CSDActConfig.mrtrix_bin_dir` 可显式指定后端路径。
- `Real subject CSD/ACT closure`：已新增 `Testing/Python/run_csd_act_real_subject_smoke.py`，并用 `/data/chengjin/SlicerDDSurfer-test/100307` 跑通真实 MRtrix CSD/FOD/ACT/SIFT2 -> TRK export -> WMQL -> connectome 闭环。1000 条 smoke 可快速验证；100k 长测试已用 `--run-name csd_act_100k --select-streamlines 100000` 跑通，输出独立目录，不覆盖 1000 条结果。100k connectome 为 101 个节点、625 条边、95121 条 assigned streamlines；SIFT2 assigned weight 为 76872.7276；`mean_fa`、`mean_md`、`mean_length_mm`、`total_length_mm` 均完成真实 100307 输出。
- `WMQL / AF-CST bundles`：已修复默认 `query_selection`。原先选择 `AF,CST` 无法命中 `AF.side/CST.side` 展开的 `af.left/af.right/cst.left/cst.right`；现在默认选择 side-aware bundle 名称，并在 QC 中记录每个 bundle 文件和 streamline count。100307 的 100k ACT tractogram 当前命中 4 个 bundles：`af.left=9`、`af.right=2`、`cst.left=12`、`cst.right=6`。
- `Real subject audit summary`：已新增 `Testing/Python/summarize_csd_act_real_subject.py`，用于只读汇总既有真实长测试 QC，避免引用过期 smoke summary。100307 `csd_act_100k` 审计输出为 `/data/chengjin/SlicerDDSurfer-test/100307/outputs/00_run_metadata/csd_act_100k_real_subject_audit.json`，状态 `completed`；记录 CSD/ACT runtime 121.93 秒、CSD/FOD 输出目录约 5.60GB、tractogram 目录约 64MB、WMQL runtime 3.96 秒、connectome root 约 8.54MB、6 类 connectome 均完成。
- `UI / Product targets`：主 UI 已按“Subject root + Output directory + optional preprocessing + target products”继续收口，目标产品增加 `Tractography`、`Bundles`、`Connectome` checkbox；复杂依赖由后端 manifest/QC 报告。`runSelectedButton` 现在会把 DDSeg / DDParcel / Microstructure / Tractography / Bundles / Connectome 交给统一 product orchestrator；Surface 暂时仍走原 Surface 面板执行，直到拆出不依赖 Slicer scene loading 的 headless facade。统一入口已暴露高级运行参数：`run_name`、ACT `select_streamlines`、Connectome backend（python/mrtrix）和 MRtrix dense compression；`Output directory` 现在作为 orchestrator 的可选 output root，留空则继续使用 `<subject_root>/outputs`。
- `DAG / Resume runner`：已新增轻量 `shared.orchestrator`，支持 subject-root、output-root、target products、`run_name`、`execute`、`resume`、MRtrix bin、TractQuerier root、Connectome backend 和 dense compression。当前覆盖 `segmentation.ddseg -> parcellation.ddparcel -> surface.ddsurfer -> microstructure.dti -> tractography.csd_act -> bundles.wmql -> connectome.streamline_count/sift2`，会读取各步骤 QC 或核心输出，已完成则 skip，依赖缺失则 blocked，并写 `<output_root|subject_root/outputs>/00_run_metadata/<run_name>_orchestration_manifest.json`。Surface 已从 resume/block 升级为 headless execute facade：资源齐全时运行 DDSurfer preprocessing / prediction / native-space postprocessing，资源缺失时写明 blocked reason。已用 100307 的 `csd_act_100k` 结果验证全产品 resume：DDSeg、DDParcel、DDSurfer surfaces、Microstructure、CSD/ACT、WMQL、streamline connectome、SIFT2 connectome 全部跳过，不重跑 MRtrix 或 Slicer CLI。
- `Slicer GUI smoke`：已用 `/data/chengjin/software/run-slicer.sh`、`DISPLAY=:99` 和临时模块目录完成真实 Slicer GUI 启动、模块切换和截图。截图路径：`/data/chengjin/SlicerDDSurfer-test/gui_smoke/SlicerDDSurfer_gui_fixed_choice_20260531_170837.png`。本轮修复了 Slicer 5.10 `parameterNodeWrapper` 对 `QComboBox` 字段要求 `Choice` annotation 的问题。

## 下一步建议

我建议下一步先做 **提交前收口 + Slicer launcher / GUI smoke 验证**。

原因很直接：产品目录、Microstructure、WMA scaffold、DTI scaffold 都已经进入可导入/可轻测状态。继续做新算法前，应该先确认 Slicer 主模块在真实 launcher 里可加载，避免后续 GUI 控件和逻辑入口堆在一个无法启动的集成层上。

推荐顺序：

1. **提交前收口**
   - 执行 `git add -A` 后复查目录迁移是否被识别为 rename/new path。
   - 复查 `git lfs ls-files`，确认 `parcellation/weights/*.pkl`、`segmentation/weights/*.pt`、`Resources/Data/ckpts/*.pt` 走新路径。
   - 跑快速测试：`test_input_validation.py`、`test_product_facades.py`、`test_repository_structure.py`、`test_tractography_dti.py`、`test_tractography_wma.py`。
   - 不跑 Microstructure `--validate-stage-reuse`，不跑 WMA 真实 clustering。

2. **Slicer launcher / GUI smoke**
   - 用 `/data/chengjin/software/run-slicer.sh` 或已确认可用的 Slicer launcher 加载扩展目录。
   - 验证 `SlicerDDSurfer.py` 可导入，顶部导航和现有核心面板仍可显示。
   - 只做启动和 import 级 smoke，不跑长算法。

3. **WMA 真实运行前置准备**
   - 明确 100307 是否已有可用于 WMA 的 VTK/VTP tractography。
   - 明确 ORG atlas 存放路径和是否需要下载。
   - 明确 Slicer/SlicerDMRI `FiberTractMeasurements` CLI 路径。
   - 准备好这些后再把 `execute=True` 的 WMA 回归作为单独长测试。

4. **ACT / Connectome 下一步**
   - ACT 下一阶段应实现 5TT/GMWMI 生成策略，并在安装真实 MRtrix3 后做小数据 `execute=True`。
   - Connectome 下一阶段应把当前 endpoint-label matrix 扩展为可选 dense matrix、length/FA/MD weighted matrix。

## 未完成目标

### Workflow 图对照：仍未完整实现

- `DAG pipeline runner`：已完成第一版轻量 runner，覆盖 DDSeg / DDParcel / DDSurfer Surface / Microstructure DTI / Tractography / Bundles / Connectome 的依赖顺序、resume skip、blocked 状态、可选 output root 和统一 run manifest。DDSeg、DDParcel、Surface、Microstructure DTI、CSD/ACT、WMQL、Connectome 均已有 headless execute 入口；高级失败恢复和并行调度尚未实现。
- `Tool adapter layer`：已有 Slicer CLI、Python logic、WMA shell wrapper、Docker postprocess 的局部适配，但还没有统一 adapter interface 和任务规范。
- `DWI Preprocessing`：已新增可选 `preprocessing/` 阶段，支持 skip / dry-run / execute。默认 `backend=dipy` 提供插件内轻量预处理（denoise、Gibbs removal、between-volume motion correction）；`backend=mrtrix_fsl` 保留完整外部路线（MRtrix3 `dwidenoise`、`mrdegibbs`、`dwifslpreproc` + FSL eddy/topup）。DIPY 后端不声明完整 susceptibility distortion / eddy-current 建模，真实高质量畸变校正仍建议用 MRtrix/FSL。
- `Registration chain`：已有 DWI 到 atlas 的注册 cache；尚未完整实现 DWI ↔ T1w ↔ MNI 的通用链路和 transform provenance。
- `T1w branch / ACT`：ACT 命令链和可执行入口已有；新增简化 ACT prep，可从 WM/GM/CSF label map 生成 5TT/GMWMI 近似输入。完整 FreeSurfer/MRtrix `5ttgen` 级组织模型和真实 MRtrix3 小数据验证仍未完成。
- `FOD / CSD / SIFT2`：DIPY DTI tractography 已支持 `execute=True`，可生成第一版 `.trk/.tck`；MRtrix3 CSD/FOD/ACT/SIFT2 外部 backend 已完成真实 `execute=True` 验证，并自动导出 WMQL 可读的 `.trk`。100k streamlines 长测试已跑通，后续可继续评估更大规模 tractogram 的稳定性和 runtime。
- `WMQL / pyAFQ bundle segmentation`：WMQL 已作为正式 bundle backend 接入，包含默认 AF/CST 查询、backend 检查、dry-run manifest/QC、execute 入口和 Slicer logic glue；已在 100307 上执行 Tract Querier，但当前稀疏 DTI tractogram 未命中 AF/CST。pyAFQ 路线尚未实现。
- `Connectome`：connectome 执行入口已有；支持 streamline count、SIFT2 weighted streamline count、`mean_length_mm`、`total_length_mm`，以及基于 scalar map 的 `mean_fa` / `mean_md` / `mean_odi` / `mean_scalar` Python endpoint connectome；已在 100307 DTI 最小闭环和 MRtrix CSD/ACT 闭环中生成真实 matrix。节点表现在会自动使用 `parcellation/conversion/data/FreeSurferColorLUT.txt` 或显式 `lut_path` 输出真实 ROI 名称，并在 QC 记录 named/unnamed node count。`tck2connectome` dense CSV 现在会回填 node_count、edge_count 和 assigned streamlines；若启用 `compress_mrtrix_dense=True`，会把 sparse label 造成的超大 dense matrix 压缩为 ROI-label edge-list。100307 `csd_act_100k` 真实验证中，raw dense matrix 为 2035 个 dense nodes，压缩后得到 101 个 ROI labels、650 条边、99974 条 assigned streamlines。
- `Export package`：已有各分支输出和部分 manifest；尚未统一导出 MRB、provenance.json、QC report bundle、group-analysis CSV/TSV。

### P0: 代码库收口与可维护性

- `AGENTS.md` 中的旧路径引用已更新为当前产品目录。
- `workflow_catalog.py` 顶部说明已更新为产品目录承载真实实现。
- `.gitignore` 已覆盖 Python cache、Slicer 测试临时目录、coverage、常见临时文件和 `third_party/`；本轮已清理运行产生的 `__pycache__/` / `.pyc`。
- 已检查 Git LFS 规则：`.gitattributes` 对 `*.pt`、`*.pkl`、`*.nii.gz`、`*.mgz`、`*.tck`、`*.trk`、`*.vtk`、`*.vtp`、`*.obj`、`*.stl` 启用 LFS。新规则会保护后续新增影像、tractogram、surface mesh 和模型文件；当前历史里已有的 atlas/template `.nii.gz/.obj` 不是 LFS pointer，若要彻底迁移需要单独做 Git LFS history migration，不应混在普通功能提交里。
- 已补仓库级 smoke test，验证产品代码不再引用旧根目录包名、`third_party` 被 ignore、大文件扩展名具备 LFS filter、未跟踪文件中没有大运行产物。
- 当前未跟踪文件审计结果：都是源码、测试脚本和小型查询文件，未发现超过 5MB 的新增运行产物。

### P0: Slicer 集成验证

- 真实 Slicer GUI smoke 已完成：`DISPLAY=:99` 下启动 Slicer，使用临时 module path 加载 `SlicerDDSurfer.py`，成功切换到 `SlicerDDSurfer` 模块并保存截图。
- 验证命令模式：

```bash
rm -rf /tmp/SlicerDDSurfer_slicer_module
mkdir -p /tmp/SlicerDDSurfer_slicer_module
ln -s /data/chengjin/SlicerDDSurfer/SlicerDDSurfer.py /tmp/SlicerDDSurfer_slicer_module/SlicerDDSurfer.py
ln -s /data/chengjin/SlicerDDSurfer/Resources /tmp/SlicerDDSurfer_slicer_module/Resources
DISPLAY=:99 PYTHONPATH=/data/chengjin/SlicerDDSurfer \
  SLICERDDSURFER_GUI_CAPTURE=/data/chengjin/SlicerDDSurfer-test/gui_smoke/SlicerDDSurfer_gui_fixed_choice_20260531_170837.png \
  /data/chengjin/software/run-slicer.sh --no-splash \
  --additional-module-paths /tmp/SlicerDDSurfer_slicer_module \
  --python-script /data/chengjin/SlicerDDSurfer/Testing/Python/slicer_gui_capture.py
```

- 注意：不要把仓库根目录直接作为 Slicer `--additional-module-paths`。Slicer 会扫描根目录所有 `.py`，误把 `workflow_catalog.py` 和 `run_postprocess_docker.py` 当模块/CLI 加载。开发 smoke 应使用临时 module dir；正式安装路径应由 Slicer extension packaging 只暴露模块入口和 Resources。
- `PythonSlicer` 不能替代 GUI import，因为 `parameterNodeWrapper` 会使用 GUI Qt 类型，例如 `qt.QColor`。

### P1: Microstructure 收口

- `microstructure.dti` 已纳入 `shared.orchestrator`，统一入口可从 `subject_root/input` 复用 `cache/native_dti`，输出 FA/MD/AD/RD/L1/L2/L3/Trace 和 ROI-wise stats；100307 `csd_act_100k` resume 已验证会正确跳过已有 DTI 输出。
- Free Water / NODDI 暂时仍保留在 Microstructure 专用面板和 pipeline 配置里，不作为 orchestrator 默认步骤，避免用户选择 Microstructure 时默认触发高耗时或额外依赖阶段。
- 跑完较慢的三段阶段复用回归：

```bash
cd /data/chengjin/SlicerDDSurfer
python3 Testing/Python/run_microstructure_regression.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307 \
  --subject-id 100307 \
  --output-dir /data/chengjin/SlicerDDSurfer-test/100307/outputs/microstructure \
  --fit-method wls \
  --expected-roi-count 101 \
  --validate-stage-reuse
```

- 在 Slicer 内实际运行一次 Microstructure，确认 FA/MD、Free Water、NODDI map 和 ROI-wise table 都自动加载到 scene。
- 明确 NODDI 后端策略：当前代码走 AMICO，文档中应固定说明 NODDI 不依赖 Free Water 结果，但会扫描并复用已有 stage output。
- 为 Microstructure 增加更小的单元测试覆盖：manifest 匹配/不匹配、stage disabled 但 cache 缺失、ROI label map 缺失。
- 评估 AMICO `nthreads=1` 的性能瓶颈，确认是否能通过环境变量或配置项开放线程数。

### P1: Tractography Phase 1

- SAF Python backend 已作为插件内部 backend 接入：`tractography/saf_backend` 保存算法实现，`tractography/saf.py` 保存 SlicerDDSurfer wrapper、manifest/QC 和执行入口。
- SAF 当前已完成 dry-run 单元测试、import/compile 验证，以及基于 `/data/chengjin/SlicerDDSurfer-test/100307-FastSurfer` 的 Python 版和 Slicer 插件 logic 版 `execute=True` smoke。测试使用 `noregister + pregenerated_tractogram + maxlen=None`，生成 `SAF.tck`、`saf_manifest.json`、`saf_qc.json` 和 `surf_data/`。
- SAF 输出树已固定为 `outputs/04_tractography/saf/`，核心文件为 `SAF.tck`、`saf_manifest.json`、`saf_qc.json`、`log.txt` 和 `surf_data/`。
- SAF FastSurfer 回归命令已补：`python3 Testing/Python/run_saf_fastsurfer_smoke.py --subject-root /data/chengjin/SlicerDDSurfer-test/100307 --subject-id 100307 --fs-dir /data/chengjin/SlicerDDSurfer-test/100307-FastSurfer --execute`；Slicer 版可用 `xvfb-run` 加 `--use-slicer-logic`。
- SAF / MRtrix3 适配层已补：MRtrix3 不打包进插件，可通过 `mrtrix_bin_dir`、`SLICERDDSURFER_MRTRIX_BIN` / `MRTRIX_BIN` 或 `PATH` 发现；也支持 `mrtrix_prefix` 的 container/shell wrapper 模式。manifest 会记录 discovery、resolved commands、effective prefix 和 `initial_tractogram_source`。使用已有 `.tck` 时不强制 `tckgen`，关闭 `maxlen` 时不强制 `tckstats`。
- WMA ORG atlas clustering scaffold 已完成：`tractography/wma.py` 可构造 WMA 命令、写 manifest、dry-run，`tractography/pipeline.py` 和 `SlicerDDSurferLogic.runWMAOrgAtlasPipeline(...)` 已作为 pipeline glue 接入。
- WMA Phase 2 小收口已完成：`inspect_wma_backend(...)` 检查 WMA shell 和依赖脚本，`inspect_wma_org_atlas(...)` 检查 `ORG-RegAtlas-100HCP` / `ORG-800FC-100HCP`，`run_wma_org_atlas(...)` 同时写 `wma_org_atlas_manifest.json` 和 `wma_org_atlas_qc.json`。
- fake backend 的 `execute=True` 已由 `test_tractography_wma.py` 覆盖；真实 WMA 数据测试尚未完成，因为当前机器未发现 ORG atlas 目录，也未在 100307 测试个体中发现 `.vtk/.vtp` tractography。
- 后续真实测试命令模板：`python3 Testing/Python/run_wma_org_atlas_smoke.py --subject-id 100307 --input-tractography <subject.vtk|subject.vtp> --atlas-dir <ORG-Atlases> --output-dir <out> --slicer-executable /data/chengjin/software/Slicer-5.10.0-linux-amd64/Slicer --wma-root <whitematteranalysis> --execute`。
- DTI tractography scaffold 已完成：输入复用 `subject_root/input` 和 `shared/native_dti`，输出 `.trk` 或 `.tck` 计划路径、manifest 和 QC JSON。
- 初始后端仍建议优先 DIPY deterministic / probabilistic tracking，但真实 streamlines 生成应作为下一阶段单独实现。
- `tractography/pipeline.py` 与 `tractography/module_logic.py` 已建立；后续如需要 GUI 暴露，再补 `tractography/module_widget.py` 和 `.ui` 控件。
- 输出至少包含：streamlines 文件、tracking manifest、基础 QC 指标（streamline count、length stats、mask coverage）。
- 100307 回归命令已补：`python3 Testing/Python/run_tractography_dti_smoke.py --subject-root /data/chengjin/SlicerDDSurfer-test/100307 --subject-id 100307 --require-native-cache`。

### P1: Connectome Phase 1

- 节点来源已明确：默认复用 DDParcel/parcellation label map。
- 边来源已明确：默认使用 Tractography 输出的 streamlines。
- `connectome/pipeline.py` 已建立，输出 matrix CSV、nodes TSV、manifest 和 QC JSON。
- 已支持 `.tck` 的 MRtrix3 `tck2connectome` 后端，以及 `.trk`/`.tck`/legacy `.vtk` 的 Python endpoint-label fallback；已支持 length、FA/MD 和 SIFT2 weighted connectome。
- 增加 connectome 与 tractography 的 cache/manifest 一致性检查。

### P2: 去 T1w 依赖路线

- 梳理仍含 `T1w` 假设的位置。当前 `parcellation/pipeline.py` legacy 模式仍使用 `<input_root>/<subject>/T1w/Diffusion` 布局，这是兼容路径，应在文档中明确“legacy only”。
- Tractography 的 ACT 已按标准概念收口：标准 ACT 需要 5TT/GMWMI；DDParcel 可作为节点和派生组织模型来源，但不能直接等同于完整 ACT tissue model。如果目标是去 T1w，需要设计 diffusion-only ACT-like 策略或明确 fallback 置信度。
- Connectome 默认应以 diffusion-space parcellation 和 tractography 为主，避免把 T1w 作为必需输入。

## 值得优化的代码点

- `shared/module_widget.py` 的 `_checkCanApply` 仍然集中同步所有产品 UI 字段。后续可以拆成每个 product mixin 提供 `_sync_<product>_parameters()`，公共层只调度，避免这个文件重新膨胀。
- `MicrostructureLogicMixin.runMicrostructurePipeline()` 默认加载所有 map 到 Slicer。后续可加 UI 选项控制加载哪些 map，减少大数据场景下的 scene 压力。
- `setup*Requirements()` 会在 GUI 操作中触发安装依赖。建议增加 dependency status 检查面板，把“检查”和“安装”显式分开。
- `Testing/Python/CMakeLists.txt` 目前注册了轻量 smoke tests。Microstructure 回归是独立脚本，建议增加可选 CTest label，默认不跑长任务。
- `AGENTS.md` 与 README 内容有重叠且部分过期。建议把长期架构放 README / PRODUCT_ARCHITECTURE，机器环境和临时验证状态放 AGENTS。
- `workflow_catalog.py` 目前只服务导航元数据。后续可以扩展 `status`、`default_enabled`、`requires_slicer`、`requires_docker`、`estimated_runtime`，供 UI 显示和测试选择复用。

## 当前推荐执行顺序

1. 评估是否需要继续跑 500k/1M streamlines；100k 已有完整审计证据，但 AF/CST 命中数仍偏少。
2. 改进 WMQL bundle 质量：当前 100k 已能命中 AF/CST，但数量较少，应继续评估查询定义、ACT tissue model 和 parcellation 端点策略。
3. 扩展 product orchestrator：Surface headless facade 已纳入；下一步应定义 Free Water / NODDI 是否进入默认 DAG 的 gating。DDSeg、DDParcel、Surface、Microstructure DTI、CSD/ACT、WMQL、Connectome 已纳入，output root、100k streamlines、Connectome MRtrix backend 和 dense compression 已可从统一 UI 传入。
4. WMA 真实运行准备：已有 149741 downsampled VTK 测试输入；全盘扫描未发现 ORG atlas，仍需 ORG atlas 和 SlicerDMRI CLI 路径。
5. Connectome Phase 1.5：节点 LUT 名称映射、length、FA/MD、SIFT2 weighted connectome 和 MRtrix dense matrix 到 ROI-label edge-list 的可选压缩已完成真实 100307 审计；后续可继续做 UI 暴露和 group-analysis 汇总格式。
6. Microstructure 长回归和 WMA 真实 clustering 放到后台或夜间测试。

## 当前风险

- 工作树当前不是干净状态，目录迁移表现为大量旧文件删除和新产品目录新增；在继续大改前应避免回退已有改动。
- `.gitattributes` 已新增更多 LFS 规则，但不会自动改写历史中已经作为普通 Git blob 存在的 atlas/template 大文件；如需完全去除历史大文件，需要单独规划 `git lfs migrate`，会改写历史，不建议在当前功能提交里直接做。
- Slicer launcher 动态库问题已由 `/data/chengjin/software/run-slicer.sh` 补充库路径缓解；真实 GUI smoke 已可在 `DISPLAY=:99` 的 Xvfb/VNC 环境下完成。剩余风险是正式 extension packaging 不能直接暴露仓库根目录，否则 Slicer 会误扫描非模块 `.py` 文件。
- NODDI 全量重算耗时长，长回归应作为可选验证，适合后台或夜间运行。
- 输入验证第一版只读取 BIDS sidecar，不做 DICOM/BIDS 自动索引，也不验证相位编码和图像轴向的一致性。
- Tractography 已有 WMA、TractCloud、DTI、ACT/CSD pipeline、manifest 和轻量测试；DTI 与 MRtrix CSD/ACT 已完成真实 streamlines smoke。真实 WMA clustering 和 TractCloud 模型执行仍未完成；Connectome 已有真实 streamline-count、SIFT2 weighted、length、FA/MD endpoint-label matrix 和 MRtrix dense matrix QC。
