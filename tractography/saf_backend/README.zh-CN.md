<div align="center">

# SAF Python 后端

**原生扩散空间短程联合纤维筛选**

[项目](../../README.zh-CN.md) | [实现来源](../../docs/architecture/IMPLEMENTATION_PROVENANCE.zh-CN.md) | [核验](../../docs/release/SAF_PYTHON_20261013.md) | [English](README.md)

</div>

本目录为 [Dmitri Shastin 原版 MATLAB SAF](https://github.com/dmitrishastin/SAF/tree/7e2a9d152caf1cf3e6bface64e7e176faac0c14f)
的**非官方 Python 移植**，保留原 [MIT 许可证](LICENSE.md)。运行不需要 MATLAB，
需要 NumPy、SciPy、scikit-learn、NiBabel 和所选路线的 MRtrix 命令。
建议通过 [`../saf.py`](../saf.py) 的输入检查、运行记录和 QC 接口执行。

---

## 支持范围

保留 GG/HH 皮层端点与半球条件、可选 PG、初始长度上限、GWG 穿行/裁剪
及表面投影。表面与纤维必须**已经处于同一原生扩散物理空间**，
此接口不执行原版可选 ANTs 配准，也不从 T1 图像启动 recon-all。

结果是 SAF 追踪**候选**，不是独立证实的相邻脑回 U-fibres。
原版 soft GWG 保留最外侧交点之间的链，不保证内部每一点都在白质。
默认 90 mm 不是通用解剖学短纤维定义；研究中需记录实际长度阈值及选项。

---

## 移植差异

`python-native-20261013` 修正端点坐标与三角面配对、极短纤维原始索引、
hard-split 权重映射。complete 求交保留边/顶点交点并处理共享点重复；
公开 MATLAB 原码在返回前清零这些标志。固定种子的 scikit-learn
k-means 不保证与 MATLAB 聚类一致，因此不宣称全流程逐位等价。

旧表面密度、长度和标量投影需要重新计算。复制到拆段后的权重不是
重新估计的 SIFT2 权重。[核验报告](../../docs/release/SAF_PYTHON_20261013.md)
区分原码核心对照、解析几何案例、真实产品检查和人工复核。
继承的 [`doc/`](doc/README.md) 描述**原版 MATLAB**，不是当前 Python
接口和依赖的完整使用说明。

---

## 引用

Shastin 等，*Surface-based tracking for short association fibre tractography*，
NeuroImage (2022)，[doi:10.1016/j.neuroimage.2022.119423](https://doi.org/10.1016/j.neuroimage.2022.119423)。
