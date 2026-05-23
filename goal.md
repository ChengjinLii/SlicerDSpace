# SlicerDDSurfer Goal

更新日期：2026-05-23

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

- `Surface / DDSurfer`：支持从统一 `subject_root` 或 legacy registered 输入运行，复用 `registered_dti` cache，输出 native-space STL mesh。
- `Parcellation / DDParcel`：支持从统一 `subject_root` 运行，复用 `registered_dti` cache，输出 `DDSurfer-wmparc`。
- `Segmentation / DDSeg`：支持 subject-root 模式和 legacy 显式输入模式，复用 `native_dti/ls` cache，通过 `PythonSlicer` 子进程运行。
- `Microstructure`：已实现 FA/MD、ROI-wise stats、DIPY Free Water、AMICO NODDI，并支持 Free Water / NODDI 分阶段 cache 复用。
- `Testing`：已有 `test_product_facades.py` 和 `run_microstructure_regression.py`，100307 个体可用于 Microstructure 回归验证。
- `Product Architecture`：顶层目录已经收成 `shared/ surface/ parcellation/ segmentation/ microstructure/ tractography/ connectome/`。
- `Input Validation / QC`：已增加 `shared.validation`，覆盖必需文件检查、BIDS 相位编码/读出时间检查、bval/bvec 合理性检查、依赖环境检查和 QC JSON 报告；主 GUI `Validate` 按钮已接入 subject-root shared validation。
- `Tractography / WMA scaffold`：已将 WMA ORG atlas clustering 包装为 SlicerDDSurfer Tractography 内的可选外部后端，支持显式 `wma_root`、环境变量或 PATH 发现，提供 dry-run wrapper、backend 可用性检查、ORG atlas 结构检查、manifest、QC JSON 和轻量测试。已从 `/dataset/nfs_share01` 复制 `149741_wma_act` 最小测试子集，包含 downsampled VTK tractography、WMA VTP/CSV、DWI 梯度、mask 和 parcellation。
- `Tractography / DTI scaffold`：已增加 DTI tracking config/result、dry-run manifest、QC JSON、native DTI cache 复用扫描、Slicer logic glue 和轻量测试。
- `Tractography / ACT`：已增加 ACT config/result、MRtrix3 后端可用性检查、DDParcel/parcellation 依赖检查、5TT/GMWMI 标准 ACT readiness 检查、manifest、QC JSON 和轻量测试；已构造 MRtrix3 ACT 命令链，并支持在后端和标准 ACT 输入齐备时 `execute=True`。`third_party/act_mrtrix_reference` 仅作为本地参考脚本，不作为运行时默认依赖；`third_party/mrtrix3_reference` 已浅拷贝 MRtrix3 官方源码作为 ACT/tckgen/tcksift2/tck2connectome 参考实现，同样不作为运行时默认依赖。
- `Connectome / Phase 1`：已增加 `connectome.pipeline`，显式依赖 tractography 输出和 DDParcel/parcellation 节点，输出 matrix/nodes、manifest、QC JSON 和轻量测试；`.tck` 可走 MRtrix3 `tck2connectome`，`.trk`/`.tck` 和 legacy `.vtk` 可走 Python endpoint-label fallback。已用 `149741_wma_act` 的 downsampled VTK + wmparc 做过真实 `execute=True` 验证，得到 100000 条 streamlines、61708 条 assigned、5535 条边。

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

- `DAG pipeline runner`：目前各产品 pipeline 有 cache/manifest，但还没有统一 DAG runner 来表达任务依赖、resume 策略、统一日志和失败恢复。
- `Tool adapter layer`：已有 Slicer CLI、Python logic、WMA shell wrapper、Docker postprocess 的局部适配，但还没有统一 adapter interface 和任务规范。
- `DWI Preprocessing`：NIfTI/NRRD 标准化已有局部实现；去噪、Gibbs removal、motion/eddy/susceptibility correction 仍未作为统一预处理阶段实现。
- `Registration chain`：已有 DWI 到 atlas 的注册 cache；尚未完整实现 DWI ↔ T1w ↔ MNI 的通用链路和 transform provenance。
- `T1w branch / ACT`：ACT 命令链和可执行入口已有；5TT/GMWMI 生成和真实 MRtrix3 小数据验证尚未实现，因为当前环境未安装 MRtrix3 命令。
- `FOD / CSD / SIFT2`：尚未实现 MRtrix3 CSD、全脑 tractography、SIFT2。
- `WMQL / pyAFQ bundle segmentation`：WMA ORG atlas dry-run scaffold 已有，但 WMQL/pyAFQ 路线尚未实现。
- `Connectome`：connectome 执行入口已有；legacy `.vtk` 已用 149741 fixture 验证，`.vtp` 仍需要安装 `vtk` Python 模块；边权重仍只覆盖 streamline count。
- `Export package`：已有各分支输出和部分 manifest；尚未统一导出 MRB、provenance.json、QC report bundle、group-analysis CSV/TSV。

### P0: 代码库收口与可维护性

- `AGENTS.md` 中的旧路径引用已更新为当前产品目录。
- `workflow_catalog.py` 顶部说明已更新为产品目录承载真实实现。
- `.gitignore` 已覆盖 Python cache、Slicer 测试临时目录、coverage 和常见临时文件；本轮已清理运行产生的 `__pycache__/`。
- 已检查 Git LFS 规则：`.gitattributes` 对 `*.pt` 和 `*.pkl` 仍启用 LFS；新路径下权重文件存在。当前最高优先级是执行提交前索引检查：`git add -A` 后复查 `git lfs ls-files` 是否显示新路径。
- 已补仓库级 smoke test，验证产品代码不再引用旧根目录包名。

### P0: Slicer 集成验证

- 修复当前机器直接启动 Slicer / PythonSlicer 时的动态库问题：`libpcre2-16.so.0` 缺失导致 launcher 级导入测试无法完成。
- 用正确 launcher 完成一次真实 Slicer Python 导入验证：

```bash
/data/chengjin/software/run-slicer.sh --launch \
  /data/chengjin/software/Slicer-5.10.0-linux-amd64/bin/PythonSlicer \
  -c "import sys; sys.path.insert(0, '/data/chengjin/SlicerDDSurfer'); import SlicerDDSurfer; print('OK')"
```

- 做一次 GUI 级 smoke：打开模块、展开各 workflow panel、确认默认路径填充、导航按钮、运行按钮状态没有回归。
- 给 `SlicerDDSurferWidget` 的产品 mixin 组合补轻量导入测试，避免后续拆 UI 时发生循环导入。

### P1: Microstructure 收口

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
- 已支持 `.tck` 的 MRtrix3 `tck2connectome` 后端，以及 `.trk`/`.tck`/legacy `.vtk` 的 Python endpoint-label fallback；后续再扩展 length、FA/MD weighted connectome。
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

1. 提交前收口和 LFS 新路径复查。
2. Slicer launcher / GUI smoke 修复和验证。
3. 完整 Slicer GUI smoke：需要有 DISPLAY 或安装 `xvfb-run/Xvfb` 后再跑；当前无显示环境会阻断 Qt `xcb` 初始化。
4. ACT Phase 1.5：实现 5TT/GMWMI 生成策略，优先基于 DDSeg/DDParcel/T1w 可选输入的明确分支。
5. Tractography DTI tracking 真实 streamlines 后端：DIPY deterministic / probabilistic 最小实现。
6. WMA 真实运行准备：已有 149741 downsampled VTK 测试输入；全盘扫描未发现 ORG atlas，仍需 ORG atlas 和 SlicerDMRI CLI 路径。
7. Connectome Phase 1.5：增加 dense matrix 导出、节点 LUT、length/FA/MD weighted connectome。
8. Microstructure 长回归和 WMA 真实 clustering 放到后台或夜间测试。

## 当前风险

- 工作树当前不是干净状态，目录迁移表现为大量旧文件删除和新产品目录新增；在继续大改前应避免回退已有改动。
- Slicer launcher 动态库问题已由 `/data/chengjin/software/run-slicer.sh` 补充库路径缓解；当前 GUI smoke 的新阻断是无 `DISPLAY` 且无 `xvfb-run/Xvfb`，完整 Slicer 报 Qt `xcb` 初始化失败。`PythonSlicer` 不能替代 GUI import，因为其中 `qt` 模块缺少 `QColor`、`QFrame` 等 GUI 类。
- NODDI 全量重算耗时长，长回归应作为可选验证，适合后台或夜间运行。
- 输入验证第一版只读取 BIDS sidecar，不做 DICOM/BIDS 自动索引，也不验证相位编码和图像轴向的一致性。
- Tractography 已有 WMA、DTI、ACT pipeline、manifest 和轻量测试，但尚无真实 WMA clustering、DTI/CSD/ACT streamlines 生成或 GUI 控件；Connectome 已有真实 streamline-count endpoint-label matrix，但还没有 dense matrix、节点 LUT 或 weighted connectome。
