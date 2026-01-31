# SlicerDDSurfer（中文版）

SlicerDDSurfer 是一个 3D Slicer 扩展模块，整合了多条基于扩散 MRI 的流程：

- **DDSurfer**：根据 DTI 标量图生成 WM / Pial 皮层表面。
- **DDParcel**：101 脑区分割（基于 DTI 特征）。
- **DDSeg**：WM/GM/CSF 分割（多视角 CNN）。
- **Surface post-process**：通过 Docker 调用 postprocess-release 做 FreeSurfer 级别的精细化后处理。

---

## 代码结构

```
SlicerDDSurfer.py              # Slicer ScriptedLoadableModule 入口
CMakeLists.txt
Resources/
  Icons/                        # 模块图标
  UI/                           # SlicerDDSurfer 的 .ui 文件
  Data/
    ckpts/                      # DDSurfer 模型权重（LFS）
    template/                   # DDSurfer 模板

# 三条主要流程

ddsurferpipeline/              # DDSurfer 主流程
  preprocessing.py
  prediction.py
  postprocessing.py
  networks/
  models/
  template/
  sculpting/                    # 拓扑保持的表面编辑器

# 101 脑区分割

ddparcpipeline/
  pipeline.py
  conversion/
  models/
  weights/                      # LFS

# WM/GM/CSF 分割

ddsegpipeline/
  src/ddseg/                    # DDSeg 实现
  weights/                      # LFS

run_postprocess_docker.py       # Docker 后处理辅助脚本
```

---

## Slicer 主模块（SlicerDDSurfer.py）

### UI 与导航
- 顶部 **“Choose workflow”** 导航栏可跳转：
  - DDParcel（101 脑区分割）
  - DDSeg（WM/GM/CSF 分割）
  - DDSurfer（WM & Pial Surface）
  - Surface post-process
- DDSurfer 主面板为折叠项 **“DDSurfer”**。
- 其他流程也有对应折叠区（DDParcel / DDSeg / Docker Post-process）。

### 参数节点
`SlicerDDSurferParameterNode` 保存全部 UI 状态：
- DDSurfer 输入/输出
- DDParcel 输入/输出/Atlas
- DDSeg 输入/权重/设备
- Docker Post-process 参数

### 运行逻辑
- 统一输入校验
- 自动准备 Python 依赖 / PyTorch Extension
- DDSurfer 结束后自动加载预测 mesh

---

## DDSurfer 流程（ddsurferpipeline/）

### 1) 预处理（preprocessing.py）
- 复制/标准化 DTI 指标
- mask skull-strip
- resample 到 template
- z-score 标准化
- 输出：`preprocessed/<subject>/` 等

### 2) 预测（prediction.py）
- TANet 模型推理 white/pial
- 160k 初始化模板网格
- Taubin 平滑
- 输出 STL meshes

### 3) 后处理（postprocessing.py）
- 把 mesh 从模板空间映射回原始空间
- SimpleITK + 变换

### 4) Surface Sculptor（sculpting/）
- 拓扑保持的表面编辑
- 支持 Slice 与 3D
- Smooth / Grow / Shrink / Flatten
- 可撤销、可导出

---

## DDParcel（101 脑区）

入口：`ddparcpipeline.pipeline.run_ddparcel`

主要步骤：
- NIfTI → NHDR
- DTI 特征提取
- Atlas 配准 + normalize
- DDSurfer_Pred 推理 parcellation

输入结构：
```
<T1w>/Diffusion/
  data.nii.gz
  bvals
  bvecs
  nodif_brain_mask.nii.gz
```

输出：
- Reg / Norm DTI
- DDSurfer-wmparc
- 分区图谱

---

## DDSeg（WM/GM/CSF）

入口：`ddsegpipeline/src/ddseg/pipeline.py::run_ddseg`

流程：
- Slicer CLI DTI 特征提取
- 多视角预测 + 融合
- 输出分割与概率图

输出：
- SegmentationMap_GMWMCSF.nii.gz
- ProbabilisticMap_GM/WN/CSF.nii.gz

---

## Docker Post-process

`run_postprocess_docker.py`：
- 整理 DDSurfer 输出
- 调用 postprocess-release docker/run_container.sh

必需输入：
- brain.mgz
- DDSurfer-wmparc.nii.gz
- native STL meshes

---

## 权重（Git LFS）

- `Resources/Data/ckpts/hcp/*.pt`
- `ddparcpipeline/weights/*.pkl`
- `ddsegpipeline/weights/*.pt`

获取方式：
```bash
git lfs install
git lfs pull
```

---

## 依赖

- 3D Slicer
- PyTorch Extension
- Python packages: nibabel, SimpleITK, trimesh, tqdm, networkx
- Docker + FreeSurfer license（后处理）

---

## 备注

- DDSurfer 需要 DTI 指标 + mask + 变换矩阵。
- DDParcel/DDSeg 依赖 Slicer 的 DTI 特征提取。
- Sculptor 修改仅改变顶点坐标，不改变拓扑。

