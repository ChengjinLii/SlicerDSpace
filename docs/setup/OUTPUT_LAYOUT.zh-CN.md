<div align="center">

# 输出目录

[首页](../../README.zh-CN.md) | [快速开始](QUICKSTART.zh-CN.md) | [插图](../figures/README.md) | [English](OUTPUT_LAYOUT.md)

</div>

---

## 当前目录

```text
outputs/
  00_run_metadata/
  01_preproc/
  02_microstructure/
  03_anatomy/
    ddseg/
    ddparcel/
    ddsurfer/
      postprocess/
  04_tractography/
  05_statistics/
  06_slicer_scene_report/
```

新解剖结果统一使用 `03_anatomy`，组织分割、脑区分区和表面重建仍分别存储。
目录名称不表示固定执行顺序，也不代表所有产品均已选择或通过 QC。

---

## 兼容已有结果

旧 `03_structural` 目录继续支持读取，以及满足原有门禁时的缓存复用。
不会仅为改名就搬迁、复制或重写已有文件、manifest 和科学来源记录。
显式指定的输出路径仍受尊重。Python 接口 `SubjectIOLayout.structural`
保留为新 `anatomy` 规范路径的别名。

按产品目录选择：新目录存在时优先使用新目录，否则再考虑旧目录。
不从旧文件补齐一个不完整的新产品。原有 QC、输入签名和版本检查不变；
发现旧目录不等于科学结果已验收。报告保留实际路径，并能解释两种目录名称。

历史验收报告和已冻结的插图来源记录保留当时的路径，避免改写实验事实。
它们不是新输出写入旧目录的指引。用户显式选择的第三方旧后端可能仍返回旧路径，
封装层会兼容读取其实际结果。

---

## 本地验证

GitHub Actions 仅保留手动触发。使用 `make test-fast` 在本地运行目录兼容与回归测试；
数据处理不依赖 Actions。
