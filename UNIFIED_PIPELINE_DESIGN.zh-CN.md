# SlicerDDSurfer 统一输入与共享前处理设计

## 1. 目标

本设计的目标是把 `DDSurfer`、`DDParcel`、`DDSeg` 三条流程统一到同一个用户入口，并尽可能复用中间产物，避免重复计算。

目标行为如下：

1. 用户无论想跑哪个任务，输入要求都一致。
2. 用户只需要提供一套原始输入：
   - `data.nii.gz`
   - `bvals`
   - `bvecs`
   - `nodif_brain_mask.nii.gz`
3. 系统自动判断哪些中间产物已经存在且可复用。
4. 如果某个任务已经生成过共享前处理结果，后续任务直接复用，不再重复运行。
5. 目录组织对用户尽量简单，对程序尽量稳定，对缓存失效判断尽量明确。

---

## 2. 设计结论

结论分三条：

1. `DDSurfer` 应该改成“对用户暴露原始 DWI 输入”，但内部继续消费共享前处理生成的 `registered DTI bundle`。
2. `DDParcel` 和 `DDSurfer` 应共享同一套注册后 DTI 中间产物。
3. `DDSeg` 也应使用同一套用户入口，但它更适合复用“原始 DWI -> native DTI features”这一层，而不是直接复用 `Reg + tfm`。

因此，推荐做成：

- 用户入口统一
- 中间缓存分层
- 每个任务按需消费不同层

而不是把三条任务强行塞进完全相同的内部输入格式。

---

## 3. 用户侧统一目录结构

最方便用户使用的结构是“一个 subject 一个自包含目录”。推荐如下：

```text
<subject_root>/
  input/
    data.nii.gz
    bvals
    bvecs
    nodif_brain_mask.nii.gz

  cache/
    native_dti/
    registered_dti/

  outputs/
    ddparcel/
    ddsurfer/
    ddseg/
    postprocess/

  manifests/
    subject.json
```

其中：

- `<subject_root>` 是用户在 UI 里选择的唯一主目录。
- `subject_id` 默认取 `<subject_root>` 的目录名。
- 如果需要，也允许 UI 中手工覆盖 `subject_id`，但默认不要求用户再额外填一次。

这个结构的优点是：

1. 输入和缓存、输出都在一个目录下，用户不容易选错路径。
2. 不需要分别管理“输入目录”和“输出目录”。
3. 后续多次运行不同任务时，缓存天然共享。
4. 更适合在 Slicer 插件里做“自动检测已完成阶段”。

---

## 4. 统一输入约定

所有任务对外统一要求：

```text
<subject_root>/input/
  data.nii.gz
  bvals
  bvecs
  nodif_brain_mask.nii.gz
```

不再要求用户手动提供：

- `*-dti-*-Reg.nii.gz`
- `*-mask-Reg.nii.gz`
- `*-b0ToAtlasT2.tfm`
- `DTI_FA.nrrd`
- `DTI_MD.nrrd`

这些都应变成系统生成并缓存的内部中间产物。

---

## 5. 共享前处理的分层设计

推荐把共享前处理拆成两层缓存。

### 5.1 Layer A: Native DTI Bundle

输入：

- `data.nii.gz`
- `bvals`
- `bvecs`

输出建议放在：

```text
<subject_root>/cache/native_dti/<fit_key>/
  DWI.nrrd
  DTI.nrrd
  b0.nrrd
  DTI_FA.nrrd
  DTI_MD.nrrd
  DTI_E1.nrrd
  DTI_E2.nrrd
  DTI_E3.nrrd
  manifest.json
```

其中 `<fit_key>` 不是固定写死，建议使用：

- `ls`
- `wls`

原因：

- `DDSeg` 当前使用 `LS`
- `DDParcel` 当前使用 `WLS`

现阶段不应假设这两者可以无差别共用，否则会把数值差异引入下游结果。

### 5.2 Layer B: Registered DTI Bundle

输入：

- `Layer A` 的 native DTI features
- `nodif_brain_mask.nii.gz`
- atlas T2

输出建议放在：

```text
<subject_root>/cache/registered_dti/<atlas_key>__<fit_key>/
  <subject_id>-dti-FractionalAnisotropy-Reg.nii.gz
  <subject_id>-dti-Trace-Reg.nii.gz
  <subject_id>-dti-MinEigenvalue-Reg.nii.gz
  <subject_id>-dti-MidEigenvalue-Reg.nii.gz
  <subject_id>-dti-MaxEigenvalue-Reg.nii.gz
  <subject_id>-dti-MeanDiffusivity-Reg.nii.gz
  <subject_id>-mask-Reg.nii.gz
  <subject_id>-b0ToAtlasT2.tfm
  <subject_id>-b0ToAtlasT2_Inverse.h5
  manifest.json
```

这里保留当前代码兼容的文件命名，原因是：

1. 现有 `DDSurfer` 主逻辑直接吃这套文件名。
2. 现有 `DDParcel` 也生成并依赖这套文件名。
3. 先统一流程，再逐步减少历史命名包袱，风险更低。

---

## 6. 三条任务各自依赖哪一层

### 6.1 DDSurfer

`DDSurfer` 对外应该只要求原始 DWI 输入，但内部依赖：

- `Registered DTI Bundle`

推荐默认策略：

- `DDSurfer` 使用 `fit_key = wls`
- atlas 与 `DDParcel` 保持一致

理由：

1. 现有 `DDSurfer` 主逻辑消费的是 `*-Reg.nii.gz + mask-Reg + tfm`
2. `DDParcel` 正好产生这套结果
3. 让 `DDSurfer` 默认与 `DDParcel` 对齐，能实现最大复用

也就是说，后续 `DDSurfer` 的公共入口应是：

```text
run_ddsurfer_from_subject_root(subject_root, subject_id, ...)
```

而不再是“让用户手动准备 Reg 文件目录”。

### 6.2 DDParcel

`DDParcel` 对外也只要求原始 DWI 输入，但内部依赖：

- `Registered DTI Bundle`
- 自己专属的 `Reg-NormMasked` 后续步骤

因此建议把 `DDParcel` 拆成：

1. `ensure_native_dti_bundle(...)`
2. `ensure_registered_dti_bundle(...)`
3. `run_ddparcel_from_registered_bundle(...)`

### 6.3 DDSeg

`DDSeg` 对外同样只要求原始 DWI 输入，但内部更适合依赖：

- `Native DTI Bundle`

原因：

1. 它当前不使用 `tfm`
2. 它不要求 atlas 配准后的 `Reg` 文件
3. 它自己后续做的是 native-space 的 masking、clipping、normalization、padding

因此建议把 `DDSeg` 拆成：

1. `ensure_native_dti_bundle(...)`
2. `run_ddseg_from_native_bundle(...)`

不建议在第一阶段强行让 `DDSeg` 直接消费 `Registered DTI Bundle`。

---

## 7. 推荐的默认任务依赖表

| 任务 | 用户输入 | 共享缓存层 | 推荐 fit | 是否依赖 atlas |
|---|---|---|---|---|
| DDSurfer | 原始 DWI + bval + bvec + mask | Registered DTI Bundle | WLS | 是 |
| DDParcel | 原始 DWI + bval + bvec + mask | Registered DTI Bundle | WLS | 是 |
| DDSeg | 原始 DWI + bval + bvec + mask | Native DTI Bundle | LS | 否 |

这个表反映的是“默认安全策略”，不是永久不变的科学结论。

如果后续经过验证发现：

- `DDSeg` 可以安全改用 `WLS`
- 或 `DDSurfer`/`DDParcel` 可以共用 `LS`

再进一步合并缓存即可。

在没有验证前，不应为了省一次计算而混用不同拟合方法的缓存。

---

## 8. 缓存复用规则

缓存不能只靠“文件存在”判断。必须使用 `manifest.json` 做完整校验。

每个 bundle 的 `manifest.json` 至少应记录：

```json
{
  "subject_id": "100307",
  "pipeline_version": "v1",
  "fit_method": "wls",
  "atlas_path": "/abs/path/to/atlas.nii.gz",
  "source_files": {
    "data.nii.gz": {"size": 123, "mtime": 1700000000},
    "bvals": {"size": 456, "mtime": 1700000001},
    "bvecs": {"size": 789, "mtime": 1700000002},
    "nodif_brain_mask.nii.gz": {"size": 1011, "mtime": 1700000003}
  },
  "outputs": {
    "DTI_FA.nrrd": "DTI_FA.nrrd"
  }
}
```

推荐校验规则：

1. 原始输入文件路径存在且大小、时间戳匹配。
2. `fit_method` 匹配。
3. atlas 路径或 atlas 指纹匹配。
4. pipeline version 匹配。
5. 必需输出文件全部存在。

只有全部满足，才允许复用。

---

## 9. 最方便用户的 UI 方案

推荐把主 UI 统一成一个公共输入区，然后下方是任务按钮。

### 9.1 公共输入区

- `Subject directory`
- `Subject ID`
  - 默认自动从目录名推断
  - 允许手动覆盖
- `Atlas`
  - 默认给出内置 atlas
- `Reuse cache`
  - 默认开启
- `Force recompute`
  - 高级选项，默认关闭

### 9.2 任务区

- `Run DDSurfer`
- `Run DDParcel`
- `Run DDSeg`
- `Run Selected Tasks`

### 9.3 运行时反馈

状态日志应明确显示：

- `Reusing native DTI bundle: ...`
- `Reusing registered DTI bundle: ...`
- `Native DTI bundle not found, computing...`
- `Registered bundle invalid due to atlas mismatch, recomputing...`

这样用户就能理解为什么某一步快，为什么某一步慢。

---

## 10. 推荐的内部 API 拆分

建议新增共享模块，例如：

```text
sharedpipeline/
  __init__.py
  contracts.py
  cache_manager.py
  native_dti.py
  registered_dti.py
  manifests.py
```

推荐 API：

```python
ensure_raw_inputs(subject_root: Path, subject_id: str) -> RawInputBundle

ensure_native_dti_bundle(
    subject_root: Path,
    subject_id: str,
    fit_method: str,
    reuse: bool = True,
) -> NativeDTIBundle

ensure_registered_dti_bundle(
    subject_root: Path,
    subject_id: str,
    fit_method: str,
    atlas_path: Path,
    reuse: bool = True,
) -> RegisteredDTIBundle

run_ddsurfer_from_registered_bundle(bundle: RegisteredDTIBundle, ...)
run_ddparcel_from_registered_bundle(bundle: RegisteredDTIBundle, ...)
run_ddseg_from_native_bundle(bundle: NativeDTIBundle, ...)
```

这样可以把“生成共享中间产物”和“运行具体任务”彻底解耦。

---

## 11. 对现有代码的重构建议

### 11.1 DDSurfer

当前 `SlicerDDSurferLogic.process()` 直接要求用户目录里已有：

- `*-Reg.nii.gz`
- `*-mask-Reg.nii.gz`
- `*.tfm`

这部分应改成：

1. 从 `<subject_root>/input` 读取原始输入
2. 调 `ensure_registered_dti_bundle(...)`
3. 再把返回的 bundle 喂给 `ddsurferpipeline`

建议新增函数：

```python
run_ddsurfer_from_registered_bundle(bundle, output_dir, ...)
```

而不是继续暴露 `Reg` 文件路径给用户。

### 11.2 DDParcel

当前 `run_ddparcel()` 把前处理和后处理都写在一起。

应拆成：

1. 原始 DWI -> native DTI
2. native DTI -> registered DTI
3. registered DTI -> Reg-NormMasked
4. Reg-NormMasked -> parcel prediction

### 11.3 DDSeg

当前 `run_ddseg()` 只能从原始 DWI 开始。

应改成允许两种入口：

1. 原始 DWI 输入
2. 已存在的 `NativeDTIBundle`

推荐接口：

```python
run_ddseg(
    cfg,
    native_bundle: NativeDTIBundle | None = None,
)
```

如果 `native_bundle` 已提供，就跳过 `run_dti_feature_extraction()`。

---

## 12. 推荐的缓存命名策略

建议不要把缓存目录直接写成“latest”或“temp”，否则后续很难判断可复用性。

推荐：

```text
cache/
  native_dti/
    ls/
    wls/
  registered_dti/
    hcp_t2__wls/
    hcp_t2__ls/
```

如果未来支持多个 atlas，`atlas_key` 可以来自：

- atlas 文件名
- atlas 内容 hash
- 或手工配置的逻辑名字

推荐优先使用“逻辑名字 + manifest 中保存真实路径”的做法，便于阅读。

---

## 13. 示例工作流

### 场景 A：先跑 DDParcel，再跑 DDSurfer

1. 用户选择 `<subject_root>`
2. 运行 `DDParcel`
3. 系统生成：
   - `cache/native_dti/wls/`
   - `cache/registered_dti/hcp_t2__wls/`
   - `outputs/ddparcel/`
4. 第二次运行 `DDSurfer`
5. 系统检测到 `registered_dti/hcp_t2__wls/` 完整且 manifest 匹配
6. 直接复用，不再做 DTI 拟合和注册
7. 只运行 `DDSurfer` 自己的下游

### 场景 B：先跑 DDSeg，再跑 DDParcel

1. 用户选择 `<subject_root>`
2. 运行 `DDSeg`
3. 系统生成：
   - `cache/native_dti/ls/`
   - `outputs/ddseg/`
4. 后续运行 `DDParcel`
5. 系统发现没有 `wls` 版本 native DTI
6. 重新计算 `cache/native_dti/wls/`
7. 再计算 `registered_dti/hcp_t2__wls/`
8. 最终输出 `outputs/ddparcel/`

这个行为是合理的，因为 `LS` 与 `WLS` 当前不应默认混用。

---

## 14. 推荐的第一阶段实现策略

为了降低改造风险，建议分两步实现。

### Phase 1: 先统一入口，不强行统一全部内部数值流程

先实现：

1. 统一 `<subject_root>/input`
2. 统一 `cache/`
3. `DDSurfer` 复用 `DDParcel` 的注册后中间产物
4. `DDSeg` 复用自己的 native DTI 缓存

这一步已经能显著提升用户体验。

### Phase 2: 再做科学与数值层面的统一

后续验证：

1. `DDSeg` 是否可改用 `WLS`
2. `Trace` 与 `MD` 的命名是否应统一
3. `E1/E2/E3` 与 `Min/Mid/MaxEigenvalue` 的命名映射是否应标准化

这一步需要结果验证，不建议在第一阶段一起做。

---

## 15. 最终推荐方案

综合“最方便用户使用”和“工程上最合理”，推荐采用以下最终方案：

1. 用户唯一输入目录为 `<subject_root>`
2. 原始输入固定放在 `<subject_root>/input/`
3. 所有任务都从相同的原始输入入口进入
4. 系统自动生成并缓存：
   - `Native DTI Bundle`
   - `Registered DTI Bundle`
5. `DDSurfer` 与 `DDParcel` 共用 `Registered DTI Bundle`
6. `DDSeg` 共用 `Native DTI Bundle`
7. 所有缓存复用都通过 `manifest.json` 校验，不靠“文件存在”硬判断

这是当前代码基础上最稳、最清晰、也最容易让用户理解的一种结构。
