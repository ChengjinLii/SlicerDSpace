# SlicerDDSurfer 功能范围整理

本文根据用户提供的手写草图整理，目标是把“项目还应包含哪些功能”转成一份可执行的功能清单。

## 1. 核心定位

SlicerDDSurfer 不应只包含当前已有的：

- `DDSurfer`
- `DDParcel`
- `DDSeg`

还应扩展为一个更完整的 diffusion MRI 分析框架，覆盖：

- 微结构分析
- 纤维追踪
- Connectome

## 2. 微结构分析（Microstructure）

草图中明确提到的微结构相关功能包括：

- `ROI-wise FA`
  - 支持 ROI 层面的 FA 统计分析
- `FA / MD`
  - 支持基础 DTI 指标计算与分析
- `Free Water`
  - 支持 free-water 相关微结构建模
- `NODDI`
  - 支持 NODDI 模型分析

### 推断的实现方向

草图右侧圈出了 `Dipy`，因此可以合理理解为：

- 微结构分析模块应考虑基于 `DIPY` 实现或集成
- 至少可将 `DIPY` 作为：
  - DTI 指标计算后端
  - Free Water 建模后端
  - NODDI 建模候选后端

## 3. 纤维追踪（Tractography）

草图中将 tractography 单独列为第二大类，并指出：

- 需要支持多种 tractography 方法
- 应尽量消除对 `T1w` 的依赖

### 草图中明确写到的方法/方向

- `ACT`
  - 旁注写明：`也是消除 T1w 依赖`
- `CSD`
- `DTI`

### 草图中还提到但需要确认的手写项

以下词条在手写图中可见，但拼写存在一定歧义，需要后续确认正式命名：

- `SAT` 或 `SAF`
- `DDTracking`

因此当前应先把它们记为候选功能：

- 候选 tractography 模块 A：`SAT/SAF`（待确认）
- 候选 tractography 模块 B：`DDTracking`（待确认）

### 当前可整理出的 tractography 能力目标

- 支持多种 tractography 后端
- 至少覆盖：
  - `DTI tractography`
  - `CSD tractography`
  - `ACT-related tractography`
- 尽量减少或移除对 `T1w` 的强依赖

## 4. Connectome

草图中第三项明确写到：

- `Connectome`
- `消除 T1w`

因此可整理出的功能目标是：

- 支持 connectome 构建
- connectome 流程应尽量不依赖 `T1w`
- connectome 应与 tractography 模块形成上下游关系

## 5. 与当前项目结构的关系

根据草图，当前项目的已有三大模块：

- `DDSurfer`
- `DDParcel`
- `DDSeg`

仍然保留为基础能力，但未来项目范围应扩展为：

1. 现有结构模块
   - `DDSurfer`
   - `DDParcel`
   - `DDSeg`
2. 微结构分析模块
   - ROI-wise FA
   - FA/MD
   - Free Water
   - NODDI
3. 纤维追踪模块
   - DTI
   - CSD
   - ACT
   - 其他候选方法（`SAT/SAF`、`DDTracking` 待确认）
4. Connectome 模块
   - 尽量去除 `T1w` 依赖

## 6. 建议拆分成的一级功能包

如果后续要继续做产品和代码结构设计，可以把项目一级功能拆成：

- `Surface`
  - DDSurfer
- `Parcellation`
  - DDParcel
- `Segmentation`
  - DDSeg
- `Microstructure`
  - ROI-wise FA
  - FA / MD
  - Free Water
  - NODDI
- `Tractography`
  - DTI
  - CSD
  - ACT
  - 其他候选方法
- `Connectome`
  - 基于 tractography 的连接组分析

## 7. 需要进一步确认的点

从草图中还需要你后续明确的地方有：

- `SAT` 是否应为 `SAF`
- `DDTracking` 的正式名称、具体算法含义
- `ACT` 在这里指的是标准 ACT，还是一个去 `T1w` 依赖的变体
- `Connectome` 的节点来源是否默认复用 `DDParcel`
- 微结构分析后端约定：`Free Water` 使用 `DIPY`，`NODDI` 使用 `AMICO`（当前稳定配置 `nthreads=1`）

## 8. 当前结论

从这张图看，`SlicerDDSurfer` 的目标已经不只是一个 surface/parcellation/segmentation 插件，而是一个：

- 以 diffusion MRI 为中心
- 尽量去除 `T1w` 依赖
- 同时覆盖微结构、tractography、connectome 的统一分析平台

## 9. Microstructure 回归命令（100307）

当前仓库可直接使用 Python 回归脚本验证 `FA/MD + Free Water + NODDI + ROI-wise stats`：

```bash
cd /data/chengjin/SlicerDDSurfer
python3 Testing/Python/run_microstructure_regression.py \
  --subject-root /data/chengjin/SlicerDDSurfer-test/100307 \
  --subject-id 100307 \
  --output-dir /data/chengjin/SlicerDDSurfer-test/100307/outputs/microstructure \
  --fit-method wls \
  --expected-roi-count 101
```

阶段复用三段验证（较慢，包含两次强制重算）：

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
