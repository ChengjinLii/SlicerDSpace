<div align="center">

# 快速开始

**一条最小、便于检查的工作流**

[项目](../../README.zh-CN.md) | [文档](../README.zh-CN.md) | [平台](SUPPORT_MATRIX.zh-CN.md) | [QC](GUI_RESULT_REVIEW.md) | [English](QUICKSTART.md)

</div>

先按 README 完成源码安装。默认界面不显示首次向导；
当前项目尚未进入官方 Extensions Catalog。

---

## 准备输入

使用获授权、去标识化的 DWI、匹配的 bval/bvec，以及同一网格上的脑掩膜。
按 README 的规范目录存放。DICOM/NRRD 转换位于 **高级设置 > 输入导入 /
转换**，先预览后写入。Slicer DTI 准备路线需要 SlicerDMRI。

在 **高级设置 > 环境与模型** 检查环境。仅尝试 DTI 不必安装 MRtrix3、FSL 或
FreeSurfer。依赖不足会报告阻碍，不会悄悄换成另一种科学算法。

---

## 仅运行 DTI

1. 填写被试 ID、Subject root 和新的 Output directory。
2. 只勾选 **Microstructure**，取消其他产品及预处理。
3. 在 **高级设置 > 分析参数** 仅选择 DTI 微结构阶段。
4. 检查环境后点击 **Run SlicerDDSurfer**，查看日志。
5. 在 **高级设置 > 结果与 QC** 选择本次运行，用 **Load / reuse** 查看 FA/MD 与原始解剖影像的叠加。
6. 检查脑掩膜、数值有限性、空间对齐和 QC 摘要，再接受结果。

只生成计划、不执行算法：

~~~bash
python3 run_subject_pipeline.py --subject-root /path/to/sub-01 \
  --targets validation,microstructure --microstructure-stages dti --plan
~~~

MD 使用灰度；显示设置不修改真实参数。执行完成、自动 QC 和人审是不同状态。

---

## 合成安装测试

在具备 NumPy/nibabel 的环境、从仓库根目录执行：

~~~bash
python3 -c "from pathlib import Path; from shared.demo_data import create_synthetic_demo_subject; print(create_synthetic_demo_subject(Path('ignore/demo')))"
~~~

使用生成的 <code>ignore/demo/slicerdsurfer-demo</code> 作为 Subject root。
这是七个测量的小型恒定张量场，**不是人体脑数据**，只检查安装与 DTI 链路，
不能验证表面精度、NODDI 或临床有效性。

旧 Demo 回调保留给测试，不是公开按钮。可再分发的真实数据教程与 Sample Data
注册仍是后续工作，不标记为完成。

---

## 失败处理

缺字段时 waiting 提示变红。依赖不足应先到高级设置配置。
取消不会回滚已安装的包；模型部分下载可续传。共享日志前删除私人路径和被试信息。
