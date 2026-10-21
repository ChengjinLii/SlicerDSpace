<div align="center">

# 算法多选与简化设置

**2026 年 10 月 21 日 · 原生 Slicer 界面与工作流衔接**

[项目](../../README.zh-CN.md) | [快速开始](../setup/QUICKSTART.zh-CN.md) | [环境安装](../setup/MANAGED_SETUP.zh-CN.md) | [English](ALGORITHM_SELECTION_20261021.md)

</div>

---

## 操作入口

主界面的微结构、纤维追踪、束分析旁均有 **选择…** 按钮，可勾选一种或多种算法。
应用后立即更新；取消不改变配置，不接受空选择。算法名称自动换行，不强行撑宽侧栏。
选择保存在 MRML 与共享用户设置中。

| 产品 | 可选算法 | 默认 |
| --- | --- | --- |
| 微结构 | DTI、Free-water、NODDI、DKI | DTI；保留为基础步骤 |
| 纤维追踪 | MRtrix3 CSD/ACT、官方 UKF、DTI deterministic、CSD + SAF | CSD/ACT |
| 束分析 | WMQL、WMA、TractCloud，支持任意非空组合 | WMQL |

高级设置按 **预处理与掩膜、模型参数、运行与性能、脑区与输入导入** 分类，
每次只显示当前分类；相关参数仍按所选方法显示。旧的绑定控件隐藏保留，以兼容历史配置。
**环境与安装**、**结果与 QC** 是独立区域，不再嵌套于高级设置。

---

## 运行与安全

多个追踪方法顺序运行，结果以 `<run>__<backend>` 分开保存。
共用的所选解剖与微结构阶段只调度一次；束方法和连接组对每种追踪结果分别计算，
不混合不同追踪方法的流线。这是工作流多选，不是新增追踪算法；多选会增加依赖、耗时及存储。

UKF 仍调用官方扩展、使用自身作者参数；CSD 目标流线数不控制 UKF 播种密度。
依赖不足、数据条件不符及 QC 失败仍会阻断相应任务，不降低验收门槛。
任何分支失败都不能把整次比较标成全部成功。

每个分支保留独立运行记录，同时生成总记录。自动显示只读取实际启动且新鲜的分支记录，
批处理也遵守此规则；不扫描输出目录，不加载旧运行或仅计划的结果。
束分析 QC 能识别带算法后缀的任务名，不能通过后缀绕过失败门禁。

CLI 计划示例，不执行算法：

```bash
python3 run_subject_pipeline.py --subject-root /path/to/subject \
  --targets validation,microstructure,tractography,bundles,connectome \
  --microstructure-stages dti,noddi \
  --tractography-backend csd_act,ukf --bundle-backend wmql,tractcloud --plan
```

---

## 验证范围

完整 Python 回归运行 1,267 项：1,264 通过，3 项跳过。
真实 Slicer 5.10 检查覆盖多选弹窗、应用与取消、共享设置保存、算法提示、依赖准备、
脑区分析，以及 440/540 像素中英文紧凑布局。
独立脑掩膜 GUI 双进程测试通过 109 项选择检查和 59 项重启恢复检查。
运行资源包审计、活动文档及扩展元数据检查通过。

本机证据目录为 `ignore/validation/algorithm_picker_20261021/`，包括
`tests-complete.log`、`gui-final/`、`brain-mask/` 和 CLI 计划日志。
这些是工程验收，不代表重新完成所有算法全脑多选科学验收或跨平台 GUI 实测。
原有采集要求、有效性掩膜、人工解剖复核义务及平台限制保持不变。
