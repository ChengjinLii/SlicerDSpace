<div align="center">

# 项目网站

**公开网站素材与私有软件文档分开发布**

[项目](../../README.zh-CN.md) | [网站](https://chengjinlii.github.io/SlicerDSpace/) | [原始记录](UPSTREAM_README.md) | [English](README.md)

</div>

---

## 来源与贡献者

网站由 [xiaji](https://github.com/xiaji) 贡献，原 Git 作者为
`x1aji <jwjwei@gmail.com>`。通过普通 merge 保留 `935a5d9`、`444d8db`、
`5b09bc2` 三条原始提交，不做 squash/rebase，也不改写作者、提交者、时间及
共同作者记录。这样原贡献记录仍属于贡献者，不会被替换成维护者的新提交。

网站 HTML、样式、脚本、字体、图片、字幕和 47,838,648 字节宣传片放在
`docs/site/`。合并仅调整存放位置与测试/部署配置，不重新设计网页或转码视频。
[FACTS.md](FACTS.md)、[SPEC.md](SPEC.md)、[原 README](UPSTREAM_README.md)
保留贡献者的历史依据、设计及审核记录；它们不是当前安装指南，也不会公开部署。

---

## 性能部分

性能证据已并入主页的 `#performance` 部分：位于 `#runtime` 图之后、页尾参考文献之前，是一个
默认关闭的折叠块“Performance evidence”。页脚链接使用主页内导航。
运行时间、优化图表和详细证据均留在主页，不另设子页；旧跳转页已删除。
证据分别展示等价计算实现、原生多线程、工作流调度及 Python 移植版对照，注明基线、
测量范围、输出一致性和限制，不宣称整条工作流的加速率。

`python3 scripts/build_performance_site.py` 从既有证据生成表格，写入 `index.html` 中
`measured-evidence` 标记之间；`--check` 核对来源哈希并拦截过期 HTML／JSON。只有筛选后的
`assets/data/performance.json` 进入公开网站，不复制原始快照、私有文件路径、被试数据或内部报告；
网页与生成工具不进入插件运行包。

目录共保留 13 条分范围记录；优化图选取十项有通用价值的实现、移植版、继承上游与 I/O
优化，上方展示计时、下方通过相同编号解释方法及一致性。线程数、设备切换、调度和仅与
插件旧版比较的 API 接入优化不进入该图。目录在 10 月 25 日补齐，源码新鲜度核验仍是
10 月 22 日，不将旧测速改称当天复测。

---

## 首页、方法表与参考文献

首页 `#skills` 区域和导航介绍安装与使用 Agent Skill，提供 Skill、使用指南、CLI 模板
链接，以及可复制的安装、分析两个 Prompt。中英文根 README 及论文的安装与使用
部分也提供对应示例；Skill 仅保留面向 Agent 的操作规范。下载前由用户
确认存储路径，分析前确认执行计划。Skill 文件留在仓库中，
私有预发布阶段需要仓库访问权限。Skill 由用户自己的 Agent 执行，与网页本地导览分开。

悬浮项目助手按个人主页 `d30286f` 的 Chengjin Bot 复刻头像、光晕、眨眼、眼动、
节日帽和对话框：眼动每 150 ms 采样、每帧按 0.05 平滑，最大偏移 5 px。使用
`docs/site/assets/js/guide-bot.js` 中的中英文预设资料在本地回答，不访问在线模型、
不发送或持久化用户问题。安装步骤或产品功能变化时，应同步更新答案。可运行
`node Testing/Website/guide_bot_check.mjs` 检查拖动、键盘、响应式布局及无脚本回退。
正文外侧留白不足或窗口较矮时，头像自动缩小并停靠到页眉预留的 36 px 位置，
不再覆盖正文；宽屏保留悬浮效果及用户上次拖动的位置。打开助手时自动收起已展开的
导航菜单，桌面端点击对话框外即可收起助手。浏览器测试覆盖 320--1440 px 窗口、
滚动时的位置、页眉元素避让及两种模式之间的切换。

首页主标题为“SlicerDSpace”，论文题目的说明部分作为下方副标题。移除独立的
The idea、Workflows 和 Status 部分，结果简介不再反复强调被试编号，来源记录继续保留。
“What is integrated” 紧邻最后的 References 之前。方法总图继续保留，六种产品组合示例
及独立 In Slicer 区块不再展示。页眉、页脚和浏览器图标改用 `paper-latex:docs/figures/logo-ref.svg`
导出的透明 PNG；`python3 scripts/check_website_assets.py --check` 检查矢量源及导出资源。
Get started 提供安装路径、输入准备、
按需环境安装、方法选择及 CLI 示例。

- `assets/img/fig-product-map.png`（`#choose`），以及 `#runtime` 中独立的
  `assets/img/fig-runtime-resources.png` 和 `assets/img/fig-runtime-optimizations.png`
  由 `paper-latex:docs/figures/` 中可编辑的 SVG 生成，SVG 不公开发布，重建方法见 `paper-latex:docs/figures/README.md`。
  每个 `<img>` 的宽高与文件像素一致，并链接到原图。
- WMQL 卡片改用 `assets/img/res-wmql-ukf.jpg`，与 Results 图的官方多束规则 UKF
  素材逐字节一致，来源及哈希见 `paper-latex:docs/figures/src/results/wmql_sources.json`。
  `python3 scripts/check_website_assets.py --check` 校验已发布文件；更新时从独立论文仓库重新生成并导入。
  完整侧位图按比例显示，不裁切边缘；旧 CSD/ACT AF/CST 缩略图不再发布。
- 独立的 `#integrated` 部分用“What is integrated”表列出 35 项具体方法及分析工具，
  覆盖去噪、脑掩膜、解剖、微结构、追踪、束分析、连接组和选区分析，每项均有来源引用。
  表格逐项说明实现、运行依赖和调用入口，
  不再用某次测试的橙色状态标签概括整种方法。WMA 的推荐 UKF 输入、部分连接组权重的
  Python API 入口及所需外部组件继续明确列出；具体测试与科学审核记录保留在原有链接中。
- `#cite` 放在主页最后，直接展开 [1]–[53] 的完整参考文献，保留原有编号。
  `docs/website/references.json` 保存已核对的论文、作者软件或官方文档链接；新增 DOI
  的出版者元数据保存在 `reference_verification_20261026.json`。
  `python3 scripts/build_website_catalog.py` 统一生成方法表和文献表，`--check` 检查
  HTML 是否过期、源码入口是否存在、方法是否缺引用。文献链接由该审核目录加入允许列表；
  其他外部链接仍须加入 `Testing/Website/check_site.py` 的 `ALLOWED_URLS`。

---

## 发布方式

`Website` 工作流从 `main` 验证并发布**仅 `docs/site/`**，不会上传仓库根目录或
其余 `docs/` 中的科学验证、发布审核材料。网站文件也不进入 Slicer 运行包。

仓库所有者需先在 [Settings > Pages](https://github.com/ChengjinLii/SlicerDSpace/settings/pages)
将 **Source 设为 GitHub Actions**。私有仓库需要支持 Pages 的付费计划。
发布后网站公开，但仓库继续保持私有。当前连接可读写代码，未开放 Pages 管理
接口；合并代码不等于已经启用 Pages。

`Website` 仅保留手动触发，推送或拉取请求均不会自动验证或部署。
手动运行时，Pages 未启用或仍采用分支发布，则只执行验证并明确跳过部署，
不会假报已上线。启用 Pages 后，需要发布时再在 Actions 中手动运行 `Website`。
以部署任务成功和公网地址可访问作为上线依据。

预期地址为 `https://chengjinlii.github.io/SlicerDSpace/`。分享标签、canonical
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

可编辑插图、原始素材与生成脚本由独立的 [paper-latex 仓库](https://github.com/ChengjinLii/paper-latex) 管理。本软件仓库保留网站展示图片及 SHA256 凭据。
