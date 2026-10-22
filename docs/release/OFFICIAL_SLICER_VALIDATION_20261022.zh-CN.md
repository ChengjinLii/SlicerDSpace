<div align="center">

# Slicer 官方集成规范与实测

**2026 年 10 月 22 日 | Linux x86-64 | Slicer 5.10.0**

[项目](../../README.zh-CN.md) | [文档](../README.zh-CN.md) | [发布门禁](EXTENSION_READINESS.zh-CN.md) | [机器记录](benchmarks/official_slicer_20261022.json) | [English](OFFICIAL_SLICER_VALIDATION_20261022.md)

</div>

当前工作区候选版本已通过真实 SDK 生成的模块测试、原生参数测试、全部注册的
CTest、CPack，以及真实 Extension Manager 的本地安装验证。**这不等于官方批准上架、
全平台验收或科学结果正确性认证。** 仓库仍保持私有，没有提交官方目录或公开发布。

---

## 测试结果

官方提供测试框架和自动生成的模块契约检查，并没有一个能够统一认证所有 dMRI
算法正确性的官方测试包。以下明确区分官方生成测试与本项目编写的测试。

| 检查 | 实测结果 | 范围 |
| --- | --- | --- |
| 官方 SDK 生成的 GenericTest | 12/12 通过 | 应用、元数据、逻辑/控件访问、MRML 场景绑定 |
| 本模块原生参数契约 | 3/3 通过 | 默认值、非法参数拒绝、私有场景 XML 保存恢复 |
| SDK CTest | 161/161 测试入口通过 | 2 个原生入口与 159 个本项目后端测试文件 |
| CTest 内的后端用例 | 1,317 通过、3 跳过 | 共发现 1,320 项；并非 1,320 项官方编写的测试 |
| 扩展 configure/build/CPack | 通过 | 使用已有真实 Slicer SDK，不是重新编译 Slicer 核心 |
| 安装包资源审计 | 469/469 文件匹配 | 无缺失、变更、多余或不安全路径 |
| 真实 CPack 包安装 | 通过，14.04 秒 | 私有配置的 Extension Manager，无开发模块路径 |
| 安装副本的 Self Tests | 通过 | 调用注册的官方入口，测试前后场景节点数量一致 |
| 额外 GUI 场景 | 7/7 通过 | 真实 Qt/Slicer 进程，隔离配置，禁用网络 |
| 元数据与第三方声明审计 | 通过 | 仅本地一致性/完整性，不代表公开可访问或法律认证 |

原生 unittest 加载器报告 4 项，是因为还发现了继承自基类的入口；实际新增/维护的
参数契约是 3 项，不能将其说成 4 个独立科学测试。Self Tests 回调会运行这 3 项。
本次没有另外手动点击 Reload & Test 按钮。

3 个后端跳过项分别是：1 项需显式启用的真实被试 DDSeg 世界坐标 QC，以及
2 项需要 PowerShell 的安装器测试。没有把跳过项算作通过。

7 个 GUI 场景覆盖：安装副本加载和中英文设置、紧凑布局、场景结果复用/替换/清除及
可移植 MRB 保存恢复、算法多选、异步环境检查与过期结果拒绝、任务取消、后台工作
期间退出。部分场景使用合成输入或替代科学执行逻辑，不代表模型推理或束解剖已验收。

---

## 发现与修复

原来的原生测试只检查少量默认值。本次补充了官方 `parameterNodeWrapper` 的非法值
校验、失败写入不改变旧值，以及私有 MRML 场景中的 XML 保存恢复。Self Tests 不会
清空用户的场景。

逐测试文件启动独立进程后，复现了原先合并运行掩盖的 VTK 导入崩溃。
`fiber_conversion_support` 在 WMA 作者源码缺失或版本未匹配时也先加载 VTK；模拟
分发测试恢复 `sys.modules` 后，这些新加载的原生模块被移除，再次导入可能崩溃。
现改为先核对作者源码，再加载可选 VTK，与已有 transform 防护一致。不匹配时保留
作者实现，已验证版本的数值转换逻辑未改动。新增了独立进程 CI 回归和禁止提前导入
VTK 的检查。

同时修正两个测试夹具假设：合成 FreeSurfer 几何头使用固定标记，不再依赖系统
用户名和时间；本地安装发现测试不再误选宿主的 `/opt/freesurfer` 或 PATH。
隔离测试环境缺少的 Pillow 仅安装到测试虚拟环境，没有修改 Slicer Python 或用户后端。

CMake 按官方建议在 `project()` 前读取 `ConfigurePrerequisites`，用于继承 macOS SDK
架构与 sysroot。本次仅在 Linux 配置验证，不能因此声称 macOS 已实测。

GUI 验收工具新增 `--extension-archive`，记录包来源和 SHA256。Extension Manager
测试现在可以安装指定的真实 CPack 包，不再用手工 staging 包替代。其他 GUI 场景
仍明确属于 staging 副本测试。

---

## 证据与复现

[机器记录](benchmarks/official_slicer_20261022.json)保存用例数、测试文件哈希与步骤耗时。
完整日志、测试快照、截图、私有设置和安装包保存在
`ignore/validation/official_slicer_20261022/`；中断/失败尝试与最终 `release/` 结果均保留。

候选版本是 `7808a0c8391d` 加记录中的工作区补丁，不是该提交的未修改快照。
SDK 和安装版应用均对应 Slicer 源码
`a2b6d082be04274a849884fbb1e85634a9df90fb`。本地 SDK 数字修订号为 3838，
安装版为 34045；本地文件安装测试提供了目标元数据，因此不是官方服务器的修订匹配
或插件商店在线安装验收。

扩展 configure/build/CTest/CPack 分别用时 3.22/0.77/143.65/1.18 秒。
这是已配置共享主机上的工程测试时间，不是模型耗时，也不是从零安装基准。

```bash
xvfb-run -a python3 scripts/build_slicer_sdk.py \
  --slicer-dir /path/to/Slicer-build \
  --build-dir ignore/official-check-new \
  --unit-test-python /path/to/test-env/bin/python

python3 scripts/slicer_acceptance.py \
  --report ignore/official-package-install \
  --slicer /path/to/Slicer/Slicer --xvfb /usr/bin/xvfb-run \
  --assets /path/to/authorized/model-assets --subject /path/to/subject \
  --extension-archive /path/to/the-cpack-package.tar.gz \
  --tests extension_manager_install
```

每次使用新的构建目录和隔离配置。本次容器禁用网络，没有重启现有 DDSurfer 或
MRI Agent 会话。

---

## 尚未完成

日志保留 SDK/CTK 的 CMP0148/CMP0177 CMake 警告，以及未找到可选 SlicerDMRI/PyTorch
CMake 配置文件的警告，没有通过删除依赖或隐藏日志消除它们。官方无主窗口、禁用 CLI
的 GenericTest 还会报告 CropVolume/工具栏警告，但模块契约测试通过。

尚未验证原生 Windows/macOS、其他 Slicer 版本、空白机器的全后端安装和全科学流程。
人工解剖审核独立保留。公开资源链接、GitHub topic、已授权的 Sample Data 教程、
专利披露和模型/模板再分发审核，不会因自动测试通过而自动完成。本次没有核对本地
修改对应的远端 Actions 状态。

代码采用原生模块基类、类型化 MRML 参数、UI/逻辑分离、场景生命周期观察和可取消
进程。本次是针对这些集成契约的复核，并非穷尽全部代码的风格认证。Tier 3 规范还
建议避免不必要的自定义样式，仍需保留外观人工检查和平台特定布局验证。

---

## 官方依据

- [扩展开发、构建与分发](https://slicer.readthedocs.io/en/latest/developer_guide/extensions.html)
- [Self Tests 发现与执行](https://slicer.readthedocs.io/en/latest/developer_guide/modules/selftests.html)
- [类型化参数节点与持久化](https://slicer.readthedocs.io/en/latest/developer_guide/parameter_nodes/overview.html)
- [当前 Extensions Index 清单](https://github.com/Slicer/ExtensionsIndex/blob/main/.github/PULL_REQUEST_TEMPLATE.md)
