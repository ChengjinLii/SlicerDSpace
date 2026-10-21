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
按 README 的规范目录存放。DICOM/NRRD 转换位于 **高级设置 > 脑区与输入导入 > 输入导入 /
转换**，先预览后写入。Slicer DTI 准备路线需要 SlicerDMRI。

在独立的 **环境与安装** 区域检查环境。仅尝试 DTI 不必安装 MRtrix3、FSL 或
FreeSurfer。依赖不足会报告阻碍，不会悄悄换成另一种科学算法。

检查在可取消的后台进程中进行，结果直接显示在环境区；无需逐次关闭详情弹窗。
点击 **准备所选分析环境**，仅在确实需要安装时确认下载与许可；已经就绪时不再确认或安装。
如提示重启，保存工作并重启后再次准备。
**更多选项（离线、修复、路径）** 中提供依赖详情、**使用离线模型资源**、
**修复所选受管工具** 和手工路径。
支持范围与平台限制见[自动配置说明](MANAGED_SETUP.zh-CN.md)。

主界面的 Microstructure、Tractography 和 Bundles 三行显示当前算法，默认分别为
**DTI**、**MRtrix3 CSD / ACT** 和 **WMQL**。修改设置后提示会同步更新；这是运行
配置，不表示结果已完成或 QC 已通过。点击每行旁的 **选择…**，可勾选一种或多种算法。
DTI 为基础步骤；FW、NODDI、DKI 可分别勾选。高级设置分四类，每次只显示当前类别参数，
环境安装独立于高级设置。

多种追踪方法顺序运行，以 `<run>__<backend>` 分别保存，共用解剖与微结构只运行一次。
束分析与连接组针对各追踪结果分别计算，不混合流线；依赖与 QC 要求不变。
多选将增加耗时和磁盘占用。

---

## 仅运行 DTI

1. 选择 Subject root；空白的被试 ID 自动取目录名，已有自定义 ID 不被覆盖。
   误选规范目录的 `input/` 子目录会自动回到其被试根目录。Output directory 留空时使用被试下的 `outputs/`。
2. 只勾选 **Microstructure**，取消其他产品及预处理。
3. 点击 Microstructure 旁的 **选择…**，仅保留 DTI。
4. 点击 **Run SlicerDDSurfer**，查看日志。必要的环境检查在后台自动完成；
   缺少依赖会停止提交并展开环境区，准备好后再运行，不会静默遗漏勾选产品。
5. 成功阶段的 FA/MD 自动加载；在独立的 **结果与 QC** 区域检查报告，或用 **Load / reuse** 再次加载而不堆积重复节点。
6. 检查脑掩膜、数值有限性、空间对齐和 QC 摘要，再接受结果。

只生成计划、不执行算法：

~~~bash
python3 run_subject_pipeline.py --subject-root /path/to/sub-01 \
  --targets validation,microstructure --microstructure-stages dti --plan
~~~

MD 使用灰度；显示设置不修改真实参数。执行完成、自动 QC 和人审是不同状态。
默认只跑 DTI；FW、NODDI、DKI 在该行的选择框分别启用。缺少掩膜时使用所选后端
（默认 PNL CNN），需要先配置其外部环境；已有掩膜不需要生成器依赖。

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

缺字段时 waiting 提示变红。依赖不足应先到“环境与安装”配置。
取消不会回滚已安装的包；模型部分下载可续传。共享日志前删除私人路径和被试信息。
