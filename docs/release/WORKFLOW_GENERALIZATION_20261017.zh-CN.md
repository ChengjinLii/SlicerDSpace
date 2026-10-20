<div align="center">

# 工作流泛化验收

[文档](../README.zh-CN.md) | [前次审计](QC_FOLLOWUP_20261016.zh-CN.md) | [English](WORKFLOW_GENERALIZATION_20261017.md)

</div>

本记录不代表全流程 QC 已通过，也不代表临床适用性。历史失败记录不覆盖，仓库可见性不变。

---

## 根因和修正

| 路线 | 已确认的问题 | 修正 | 尚未解决的边界 |
| --- | --- | --- | --- |
| WMQL | 旧 CST 示例要求脑干终止；后续改用完整作者预设时，也意外将 AF 候选改成区域穿行规则，损失端点候选。 | 默认采用明确命名的 `ddparcel_act`：保留原 DDParcel AF 端点表达式，导入未改动的作者 CST。保留 `author` 和 `published_endpoints`，记录递归哈希及不可变查询快照。 | 不是完整官方 AF/CST 复现，也不代表旧实验已修复；数量合格不证明解剖正确。不按被试换规则，不降低采样门槛。 |
| WMA | 五条主要束通过，不代表全部 74 条图谱束适合定量。 | 新增逐束采样、排除列表和警告；整体自动 QC 还须每条输出束采样合格，缓存重新解码核查。 | 五条小束没有被救活；不关闭作者离群剔除、不复制流线，也不把数量门槛当作统计效能证明。 |
| MK-Curve | RK/AK 不合格会连带排除同位置原本合格的 MK/FA。 | Python 移植版版本 2 输出逐指标有效性掩膜，区域统计使用对应指标掩膜。保留原联合掩膜和作者无约束拟合。 | 真实超范围值仍不合格；不填洞、不截断为有效。 |

当前实现验证：**1098 项测试全部通过**，包含真实 DDSeg 世界坐标夹具；另对
100206、149741、877168 分别运行真实夹具测试，均通过。这不等于所有科学结果正确。
v11 Linux 构建通过 132 项 CTest 和 470 项 CPack 资源核查；其实际安装包的四项隔离
Slicer 检查通过：Extension Manager 安装、WMQL 控件、紧凑中英文 UI 和完整 WMA 束加载。
证据为 `ignore/validation/sdk_current_20261017_v11/sdk_build_report.json` 及
`ignore/validation/sdk_package_gui_20261017_v8/acceptance.json`。

WMQL 默认导入锁定作者提交 `5c69c594d489859e08485110678dca7f6f4cba40` 的完整
`freesurfer_queries.qry`，只用原 DDParcel 端点候选覆盖 AF。AST 测试核对 AF 与
`AF_CST.qry` 原表达式一致，CST 没有覆盖。这是明确的兼容性适配，不是 AF 解剖认证。
GUI、单被试及批处理 CLI 均有 `ddparcel_act`、`author`、`published_endpoints` 三项，
没有失败后的自动替代。

参考：[作者查询源码](https://github.com/demianw/tract_querier/blob/5c69c594d489859e08485110678dca7f6f4cba40/tract_querier/data/freesurfer_queries.qry)、[不同的严格端点示例](https://tract-querier.readthedocs.io/en/latest/example_script.html)、[ACT 组织先验](https://mrtrix.readthedocs.io/en/latest/quantitative_structural_connectivity/act.html)。

---

## 实测证据

100307 的 ACT-v3 原始流线没有改变。此前完整作者 WMQL 用时 55.02 秒，AF 左/右 70/28 条，CST 左/右 154/311 条，最低 20 条门槛未改。这是不同协议，不能宣称与旧端点定义等价；旧 13/18 条仍失败。

WMA 五条小束的中间结果已逐阶段核对：逆变换、左右半球分离、按作者图谱簇拼接均守恒。EC 双侧候选由 75 条在离群剔除后剩 15 条，再分成左 8、右 7 条；Intra-CBLM-PaT 双侧候选由 697 条剩 45 条，再分成左 40、右 5 条。这更支持输入与图谱匹配/采样方面的限制，而不是转换或拼接丢线，但尚不能解释每条被剔除流线的具体原因，仍需验证追踪算法域与配准。

MK-Curve 原始系数、曲线和残差均有限，原始掩膜和体素顺序核对通过。逐指标范围失败的并集恰好还原原记录的 4622 个联合排除体素：

| 指标 | 自身不合格体素 | 被联合掩膜连带排除的原本合格体素 |
| --- | ---: | ---: |
| FA | 0 | 4622 |
| MD | 81 | 4541 |
| AD | 643 | 3979 |
| RD | 24 | 4598 |
| MK | 683 | 3939 |
| AK | 591 | 4031 |
| RK | 3508 | 1114 |

各行有重叠，不可相加。RK 包括 219 个负值和 3289 个大于 3 的值。门槛没有改变；逐指标合格也不代表拟合准确、可重复，或在 CSF/部分容积区有可靠组织解释。审计没有改动原图或旧 QC。

本地证据：

- `ignore/validation/wmql_author_default_20261017/`
- `ignore/validation/scientific_roots_20261017/wma_sampling.json`
- `ignore/validation/scientific_roots_20261017/mkcurve_validity.json`
- `ignore/validation/gui_wmql_preset_20261017_v3/`：真实 Slicer Qt/MRML 高级预设绑定通过。

---

## 多被试一次运行验收

新增 `scripts/validate_pipeline_cohort.py`：先核对不同真实 DWI 的哈希及原生网格，复制冻结运行时代码和作者后端，为每个被试建立空输出目录；所有被试使用相同参数，强制 `--no-resume`、`--no-user-config`，每个被试仅运行一次。选定任务出现跳过、缺失、阻塞或失败均不算通过；另做独立输出审计，复核输入与快照没有变化。

首轮被试为 **100206、149741、877168**，均为真实 HCP，形状均为 `145 × 174 × 145 × 288`。测试全新 DDSeg、DDParcel、DDSurfer、DTI、百万条 CSD/ACT、固定作者 WMQL、数量及 SIFT2 连接矩阵。HCP 已预处理且自带掩膜，此轮不验证从零预处理或 PNL 掩膜生成。

**状态：已结束，失败。** 记录为 `ignore/validation/cohort_onepass_20261017/acceptance.json`。启动成功、局部输出或以前被试的成功均不能代替本轮结果。此核心队列不覆盖可选 WMA、FW、NODDI、MK-Curve、SAF 或人工解剖审核，也不能凭三个 HCP 个体证明所有设备、疾病和采集协议都能一遍通过。

100206 已在首次且唯一一次运行中完成全部选定核心任务，耗时 **3473.56 秒**，独立审计通过、输入哈希未变。固定 WMQL 协议得到 AF 左／右 **63／27**、CST **159／136** 条。

149741 首次且唯一一次运行在 **3404.39 秒**结束，仅 WMQL 失败，输入哈希未变。AF
为 **52／16**、CST **373／239** 条，右 AF 低于原有 20 条门槛，保留在 `.failed_products`
而非发布成合格输出。877168 首次且唯一一次运行耗时 **3576.14 秒**，独立审计通过。
输入、运行时及作者后端哈希未变。**该队列保留失败状态，不能宣布整个队列通过。**
没有按个体更换定义、降低阈值或调整追踪预算来挽救本轮记录。

149741 的只读逐谓词核查确认：AF 左／右额颞交集仅 **53／16** 条，原排除规则之后
为 **52／16**，AF/CST 保存结果与作者应选源流线一一对应，没有导出丢失。该 DDParcel
输出没有 DK 区域白质标签；源码执行 `map_label2aparc_aseg`。新 QC 显式描述皮层、
普通白质和区域白质标签，不能因历史文件名含 `wmparc` 就认定等价于完整 FreeSurfer
`wmparc`；这项说明不改变通过标准。

控制对照只将输入分区替换为 HCP T1 来源的官方 `wmparc`，按原生世界坐标最近邻
重采样，保留相同流线与作者规则。右 AF 仍很少：100206 **1** 条、149741 **4** 条。
因此不能将缺少区域白质标签认定为唯一根因，也没有将未经验证的投影／膨胀作为默认
修复。T1 来源结果仅供诊断，不替代正式 T1w-free 输出，不算挽救了原队列。预先声明的
脑掩膜重叠检查通过（Dice >= 0.85），但不等于区域配准或解剖金标准。

证据为队列内 `subjects/149741/af_cst_predicate_parity/predicate_trace.json` 及
`ignore/validation/wmql_atlas_reference_20261017/acceptance.json`。
参考：[WMQL 输入说明](https://tract-querier.readthedocs.io/en/latest/example_script.html)、
[FreeSurfer 白质分区](https://surfer.nmr.mgh.harvard.edu/fswiki/wmparc)。

追加的只读逐谓词审计重现了作者 CST 的 159／136 条选择集合，保存几何与应选源流线一一对应、输入未变。证据为队列内的 `subjects/100206/cst_predicate_parity/predicate_trace.json`；这证明实现符合所选规则，不等于解剖金标准。

### 明确的 DDParcel／ACT 兼容协议

独立端点／穿行对照发现，100206 的原 AF 端点候选为 **143／128**，149741 为
**83／48**；完整作者 AF 规则则为 **63／27**、**52／16**。149741 右 AF 在最初
额颞区域穿行交集就只有 16 条，后续 AF 排除没有再删线。因此定位到的是不必要的
AF 定义切换，而不是导出丢失，不能宣称两种解剖定义等价。
证据：`ignore/validation/wmql_af_endpoint_20261017/acceptance.json`。

`ddparcel_act` 将原 AF 候选与未改动的作者 CST 组合。束提取重放逐条对比 AF 与原 AF
新提取结果、CST 与原作者结果的几何多重集；这不是完整冷启动。
记录为 `ignore/validation/wmql_ddparcel_act_20261017/acceptance.json`。

两人重放均通过：100206 的 AF **143／128**、CST **159／136**；149741 的 AF
**83／48**、CST **373／239**。每人四个输出均与相应原 AF／CST 定义逐条几何一致，
坐标差为零，输入哈希未变。每人的 `current_independent_endpoint_audit.json` 也通过：
AF 端点违规为零，CST 明确不做端点规则认证。这些是完整性和采样检查，不是 AF 解剖认证。

另在全新目录启动预先固定的新队列：100206、149741，以及新增个体 **100408**。
所有被试使用同一冻结版本、百万条流线及 `ddparcel_act`，不重试、不按被试换配置、
不恢复旧输出。记录为 `ignore/validation/cohort_ddparcel_act_20261017/acceptance.json`，
不能与失败的作者队列混淆。新队列仍在运行，重放或启动成功不表示全流程验收通过。
AF 端点独立审计；CST 穿行规则不被误认证为端点规则。作者逐谓词诊断脚本也会拒绝
改写或不同定义的查询快照，避免应用错误的 AF 诊断。

运行方法见[英文说明](WORKFLOW_GENERALIZATION_20261017.md)。报告目录必须不存在，失败记录不能在原位置恢复或覆盖成通过。

---

## 全脑 MK-Curve 队列

三名新增真实被试使用相同 Python 移植版 v2：原脑掩膜、完整壳层 `b <= 2500`、校正阈值 0.5、batched WLLS、16 个进程。没有引入参数截断或拟合后平滑，三者均已完成：

| 被试 | 脑内体素 | 联合不合格体素 | MK 自身不合格体素 | 拟合及审计耗时（秒） |
| --- | ---: | ---: | ---: | ---: |
| 100206 | 936256 | 7353 | 505 | 1221.18 |
| 149741 | 825145 | 5828 | 891 | 1045.96 |
| 877168 | 699932 | 6367 | 565 | 886.92 |

原联合掩膜／范围复算均通过。新增只读审计继续检查保存的全部十项逐指标掩膜：原生网格、二值性、脑外为零、与重算结果逐体素一致、与覆盖率记录一致。合成损坏测试会拒绝错误、缺失、非二值、脑外非零或计数错误的掩膜。RK 失败不再连带删除原本合格的 MK；真实 MK 异常仍被排除。**这些结果均不能称为全体素拟合有效。**

证据：`ignore/validation/mkcurve_cohort_20261017/acceptance.json` 及各被试的 `independent_saved_masks_v2.json`。这是独立微结构验收，不代替核心队列、人工解剖复核或临床有效性。

另外对每人 128 个正信号异常／对照体素，共 384 个，完整执行参考 QR 重拟合。最终校正系数、七项参数、作者异常／特殊判定及校正 b0 均一致。但**原始合成曲线不是全部数值一致**：149741 和 877168 各有一个巨大负峰未通过误差比较，对应方向 ADC 接近零且张量有负特征值。在两条曲线绝对值均不超过 5 的范围内，没有比较失败，最大绝对误差为 1.56e-9；抽样中的校正决策未改变。原始曲线对照失败记录保留，不改写成通过；这也不能认证所有合成曲线，更不表示异常拟合被救活。
证据为 `ignore/validation/` 下的 `mkcurve_outlier_parity_20261017/acceptance.json` 与 `mkcurve_curve_stability_20261017/acceptance.json`。

WMA 的输入域对照也单独保留。锁定作者源码的双张量 UKF 已完成 `b0 + b=3000` 参考追踪，
耗时 **1830.84 秒**；后续原版 ORG 配准／分类耗时 **16033.89 秒**。严格逐束采样仍失败：
右 Intra-CBLM-PaT 只有 **2 条**。只读阶段审计确认双侧初始 1524 条，作者离群剔除后
939 条，再分成左 937、右 2 条，变换／分侧／拼接均守恒，没有导出丢失。UKF 执行
成功或更换追踪协议都不保证所有小束合格。此失败对照保留，不替换成成功结果；
耗时也不是受控的缓存提速对照。
证据：`ignore/validation/ukf_domain_20261017/reference_100307_v2/acceptance.json`。

---

## WMA 输入域复核

此前独立的 100307 双张量 UKF 输出已按当前严格合同重新解码：源流线 **277875 条**，分配到解剖束的流线 **95755 条**；**74 条束全部通过采样门槛，最少 60 条**，有限坐标、正长度及来源归属检查通过。AF 为 287／602 条，CST 为 446／520 条。此前五条 CSD 小束对比如下：

| 束 | CSD 路线 | 独立 UKF 路线 |
| --- | ---: | ---: |
| 左 CR-P | 5 | 110 |
| 左 EC | 8 | 169 |
| 右 EC | 7 | 239 |
| 右 EmC | 7 | 218 |
| 右 Intra-CBLM-PaT | 5 | 1249 |

这份 UKF 使用旧 Slicer 5.2 作者二进制、双张量及每体素一个种子，不是上面的新版
5.10／b=3000／五种子对照。两者与 CSD 的输入及追踪协议不同，因此只能说明结果
具有路线依赖，不能作为单因素因果证明，也不等于 CSD 已被修复。独立审计后，仅更新
这份成功 UKF 结果的 QC 元数据至 v2，旧记录归档，流线文件不改；仍保留
`quantification_eligible=false`、`human_review=pending`。

证据为 `ignore/validation/scientific_roots_20261017/wma_ukf_alltract_current.json` 和 `wma_ukf_alltract_revalidated.json`。失败的 CSD 记录未变。

---

## 审计及资源控制

### WMA 配准性能

配准图谱含 1989106 条流线。作者实现每轮迭代都会重复相同的长度筛选与点复制。
原生 POSIX 封装新增有界的进程内缓存，只保留筛选后的图谱和被试，核对 VTK 修改时间
与长度参数，不缓存随机采样、目标函数、变换或分类。请求属性、索引或其他筛选时绕过
缓存。只有已经核对的上游筛选及配准源码哈希匹配才启用，其他版本保持原版运行。
Windows WSL 暂时不启用这项 POSIX shim 优化，原路线保持不变。
保留的 VTK 数据还限制为当前可用内存的四分之一，最高 4 GiB；若没有可选内存检查库，
采用保守的 256 MiB 预算。超过预算的筛选结果正常返回，但不缓存。

每次调用单独写入 `registration_cache_*.json`，记录源码哈希、兼容性、命中次数和
筛选实测时间；重跑的 manifest 不会混入历史缓存报告。诊断时可将
`WMAOrgAtlasConfig.registration_preprocess_cache` 设为 `False`。不修改上游源码、
原始流线或图谱。

真实全量输入对照已通过：同一份 1989106 条图谱流线和 277875 条被试流线、三个固定
种子，原版筛选及采样合计 533.77 秒，缓存版 180.55 秒，提速 2.96 倍。采样索引、坐标、
配准输入数组和随机状态逐位相同，原始输入哈希未变。带内存预算的新版也与保存的
作者原版三个种子签名一致，峰值保留 3374317568 字节，未超过 4 GiB，实际两次筛选、
四次命中。记录为 `ignore/validation/wma_cache_benchmark_20261017/acceptance.json`
及 `ignore/validation/wma_cache_memory_20261017/acceptance.json`。

最初缓存快照的完整 WMA 配准在 **560.87 秒**完成，实际筛选两次、命中十八次；
完整配准和分类耗时 **4664.83 秒**，74 条束全部通过严格采样及独立来源几何审计，
人工解剖审核仍待完成。这份快照早于内存预算改动，后者的数值一致性另行验证。
记录为 `ignore/validation/wma_cache_full_20261017/acceptance.json`。历史 WMA
6506.94 秒只是参考，不作为受控的整条流程提速比。

同时修正 WMA 内层缓存判断：`--no-resume` 不再因为已有成功结果而跳过本次执行。
后续队列脚本在超时后清理其所属进程组及后代、保留失败尝试，并实时刷新日志。
已经运行的旧队列没有热修改或重启。

### 已有验证

- 独立端点审计显式识别 `published_endpoints`，默认查询切换后，违反旧端点条件的结果不能被漏检；作者穿行规则不会被错误认证为端点规则。
- 后续一次运行验收会拒绝重复任务记录，防止先失败再重试的记录被最后一次成功覆盖。正在运行的队列继续使用原冻结版本，没有热改输出或实验参数。
- CLI 环境将显式 OMP 预算传给 ITK，保留用户显式 ITK 设置，不额外添加默认上限，不改变 CUDA。**这不能限制 SlicerDMRI 中的 VTK 张量估计器**，耗时记录明确保留此边界。真实 `48 × 48 × 32 × 288` 裁块的 ITK 环境值 1／4／8／未设置共八次运行，张量逐位一致；不能据此推断 VTK 线程上限或全脑提速。
- 耗时表保留真实被试编号，不再把新被试都写成 100307，或把所有 WMA 输入都写成 10 万条 UKF。

线程证据：`ignore/validation/native_dti_thread_20261017_v2/acceptance.json`。

100307 全脑对照也得到逐位相同的张量：ITK 环境值设为四时耗时 155.32 秒，未设置时 129.49 秒。这不是 VTK 四核与无限制的对照，**既没有证明提速，也没有证明限制了张量估计器的线程**；不包含标量导出及后续任务。证据为 `ignore/validation/native_dti_fullbrain_thread_20261017/acceptance.json`。
源码边界：[SlicerDMRI 张量 CLI](https://github.com/SlicerDMRI/SlicerDMRI/blob/master/Modules/CLI/DWIToDTIEstimation/DWIToDTIEstimation.cxx) 使用 VTK／Teem 估计器，不是 ITK 张量拟合滤波器。

当前 Linux SDK 的 131 项 CTest（129 项后端套件、两项原生 Slicer 测试）通过，CPack 的 466 项资源核验通过。实际 CPack 归档已通过 Extension Manager 安装到空的私有目录，再分别启动 Slicer 验证 WMQL 高级预设绑定及紧凑中英文 UI。首版测试驱动缺少一项必需的输入夹具环境变量，失败记录保留，补全夹具后通过。这些测试共享已有 Slicer 二进制与 Python 依赖，不是空白机器、跨平台或完整科学流程验收。
证据为 `ignore/validation/sdk_current_20261017_v7/sdk_build_report.json` 和 `ignore/validation/sdk_package_gui_20261017_v2/acceptance.json`。

修正 ITK／VTK 控制范围的表述后，v8 SDK 再次通过全部 131 项 CTest 及 466 项 CPack 资源核验。该归档自己的四项隔离 Slicer 检查全部通过：安装、WMQL 控件、紧凑 UI、束加载及 QC 节点归属。74 个 UKF 来源 WMA 文件共 95755 条流线，加载坐标差为零，原生加载耗时 36.34 秒，不含提取／启动。失败 CSD 结果仍被拦截，后来发生 QC 失败时，40 个用户手动加载节点被保留。
这轮证据为 `ignore/validation/sdk_current_20261017_v8/sdk_build_report.json` 与 `ignore/validation/sdk_package_gui_20261017_v5/acceptance.json`。

---

## 计时账本和后续对照

新版[32 项操作耗时表](MODULE_RUNTIMES_20261017.zh-CN.md)保存 129 条限定范围记录，
包含失败尝试。新增 `--one-pass-cohort`、`--wma-acceptance`：必须有独立验收且来源未变，
才能进入成功主表；来源／manifest 不符、QC 缺失、重试、未完成均被拒绝。
JSON 保留生成参数和来源哈希。READY 仅表示有计时，不代表科学结果获认证。

新版 CSD 在 `phase_timings` 逐步保存真实命令、TRK 转换及输出检查的时间和失败位置。
不修改算法、随机数环境、线程数或输出合同。历史组合耗时不反推子步骤；冷启动队列
继续使用其原冻结版本。

全新缓存 WMA 完整耗时 **4664.83 秒**。与此前成功 UKF 结果的只读对照显示：
**95755 条分配完全相同，标签变化为零，双方均无独有流线**。记录为
`ignore/validation/wma_cache_full_20261017/repeat_geometry_audit.json`。

失败的新版高壳层 UKF 对照通过当前来源／几何检查，但逐束采样失败。
`current_independent_audit.json` 和 `sparse_stage_diagnosis.json` 保留不同层次的结论。
新增控制固定此前成功的 b0+b1000 文件及显式 UKF CLI 参数，只更换上游／构建版本，
另记录隐式默认值。记录为 `ignore/validation/ukf_matched_protocol_20261017_v3/acceptance.json`。
两次追踪前的驱动失败保留：主机缺少旧运行库，以及不支持 `--xml` 探测。当前驱动读取
两版自带的参数 XML；没有重试科学拟合或更改门槛。

冻结的后续审计器等待新冷启动队列结束，再对三人 WMQL 执行当前端点／来源规则核查，
生成本地耗时账本，不重跑工作流或修改结果。记录为
`ignore/validation/cohort_ddparcel_act_20261017_followup/acceptance.json`。
计时／账本更新后的最终打包记录在
`ignore/validation/sdk_current_20261017_v12/sdk_build_report.json` 与
`ignore/validation/sdk_package_gui_20261017_v9/acceptance.json`；以实际状态为准，不暗示通过。
未完成／失败、拟合无效体素、人工解剖审核及未测试的平台，不能改写成全部通过。
