<div align="center">

# 项目网站

**公开网站素材与私有软件文档分开发布**

[项目](../../README.zh-CN.md) | [网站](https://chengjinlii.github.io/SlicerDDSurfer/) | [原始记录](UPSTREAM_README.md) | [English](README.md)

</div>

---

## 来源与贡献者

网站由 [xiaji](https://github.com/xiaji) 贡献，原 Git 作者为
`x1aji <jwjwei@gmail.com>`。通过普通 merge 保留 `935a5d9`、`444d8db`、
`5b09bc2` 三条原始提交，不做 squash/rebase，也不改写作者、提交者、时间及
共同作者记录。这样原贡献记录仍属于贡献者，不会被替换成维护者的新提交。

网站 HTML、样式、脚本、字体、图片、字幕和 41,070,370 字节宣传片放在
`docs/site/`。合并仅调整存放位置与测试/部署配置，不重新设计网页或转码视频。
[FACTS.md](FACTS.md)、[SPEC.md](SPEC.md)、[原 README](UPSTREAM_README.md)
保留贡献者的历史依据、设计及审核记录；它们不是当前安装指南，也不会公开部署。

---

## 发布方式

`Website` 工作流从 `main` 验证并发布**仅 `docs/site/`**，不会上传仓库根目录或
其余 `docs/` 中的科学验证、发布审核材料。网站文件也不进入 Slicer 运行包。

仓库所有者需先在 [Settings > Pages](https://github.com/ChengjinLii/SlicerDDSurfer/settings/pages)
将 **Source 设为 GitHub Actions**。私有仓库需要支持 Pages 的付费计划。
发布后网站公开，但仓库继续保持私有。当前连接可读写代码，未开放 Pages 管理
接口；合并代码不等于已经启用 Pages。

Pages 未启用或仍采用分支发布时，网页验证照常执行，部署任务会明确跳过并显示
配置提示，不会假报已上线。启用后，在 Actions 中重新运行 `Website`，或推送网站
更新。以部署任务成功和公网地址可访问作为上线依据。

预期地址为 `https://chengjinlii.github.io/SlicerDDSurfer/`。分享标签、canonical
URL 与 404 返回链接沿用该地址。不要设置 `main /docs`，否则会公开发布不属于
网站的内部文档。更换域名时按原始记录同步更新这些地址。

宣传片保留为普通 Git 文件，便于静态播放。仓库大文件检查仅对这一公开路径、
精确字节数和 SHA256 提供例外，不放行其他大视频或模型文件；替换视频须另行审核。

---

## 本地测试

```bash
python scripts/audit_pages_site.py
python -I Testing/Website/check_site.py
npm ci --prefix Testing/Website
node Testing/Website/browser_check.mjs
```

浏览器测试默认调用已安装的 Google Chrome，也可通过 `CHROME_EXECUTABLE`
指定兼容的 Chrome for Testing。可选 `PLAYWRIGHT_CORE` 指向已有模块；不设置时
使用本地锁定版本。仍须通过视频编解码与播放检查；没有 ffprobe 时，相关可选
检查明确记录为 SKIP，不冒充已通过。

截图与浏览器结果保存在忽略的 `Testing/Website/out/`。浏览器依赖仅用于测试，
不进入网站或插件包。发布文件白名单拒绝内部文档和符号链接。

---

## 证据边界

页面介绍已展示的工作流与审核证据，不表示所有算法在每个被试、平台都通过。
正式发布前保留科学与发布状态说明。自动字幕/时间检查不等于已经人工听过视频
混音；贡献者明确记录了人工听审仍待完成。
