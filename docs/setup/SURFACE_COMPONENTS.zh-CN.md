<div align="center">

# 表面后处理组件

**可选本机源码编译，不再强制安装完整 FreeSurfer**

[项目](../../README.zh-CN.md) | [入门](QUICKSTART.zh-CN.md) | [平台](SUPPORT_MATRIX.zh-CN.md) | [English](SURFACE_COMPONENTS.md)

</div>

已同步 DDSurfer `8a8699c0fda32be7e0a3cbca2903680b9f0c950b`：皮层后处理可调用
本机编译的七个原始 FreeSurfer 命令。不是 Python 重写、新算法或完整 FreeSurfer 的
等功能替代；后处理仍为可选任务。

---

## 路线选择

| 配置 | 实际行为 |
| --- | --- |
| 填写表面组件目录 | 使用该源码编译运行包，不再搜索完整 FreeSurfer |
| 未填组件目录，检测到已有 FreeSurfer | 复用已有安装 |
| 两者都没有 | 查找与上游构建配方匹配的用户缓存 |

在 **环境与安装 > 更多选项 > 高级路径** 中填写可选组件目录及个人激活文件。
要沿用已有 FreeSurfer，可清空组件目录。环境变量 `SLICERDDSURFER_SURFACE_RUNTIME`
也可选择本机组件；`FS_LICENSE` 指向个人激活文件。显式选择的组件不完整或损坏时
明确报错，不静默换用其他算法或安装。

支持当前保留顶点对应关系的原生 `lh/rh.white.obj`、`lh/rh.pial.obj`。
历史 STL／外部 shell 路线还有其他依赖，不会强行改成七组件流程。

---

## 首次准备

**“检查”不下载或编译，“运行分析”也不会暗中准备编译器。**
检查所选任务后，点击“准备所选分析环境”。若缺少本机组件，确认弹窗会说明
源码／数据条款及首次编译成本；用户同意后才在后台执行，可取消，成功后自动保存路径。
缺少个人激活文件单独提示，不会因此重复编译组件。

需要 Git、C/C++ 编译器、系统开发库（本次 Linux 包括 crypt）和 **CMake >=3.24,<4**。
插件不自动安装系统编译器、不修改 Slicer Python、驱动或 shell。
如果缺少工具，应先准备工具链，也可以直接指定已编译的组件目录或已有 FreeSurfer。
首次下载源码与保存构建缓存需要额外磁盘空间，可能耗时数分钟或更久。

命令行显式接受相关源码／数据许可后准备：

```bash
python scripts/setup_surface_runtime.py --execute --accept-terms --jobs 4
```

CMake 不在 PATH 时可加 `--cmake /path/to/cmake`。另支持 `--work-dir`、`--prefix`、
`--source-root` 和 `--offline`；离线模式要求已有图谱、固定 Git 源码及已校验依赖压缩包。
不加 `--execute` 只打印计划。损坏或配方不同的已有安装不会被覆盖。

保持上游构建器原样，编译固定 FreeSurfer 版本、ITK Common/VNL 和 zlib。
Slicer 适配层仅调整图谱的数据存放位置：29,657,074 字节的压缩包从固定 DDSurfer 提交
按需下载并校验 SHA256，不放进扩展安装包；本次也没有声称它已上传模型资源仓库。
组件默认保存到上游按构建配方区分的用户缓存，也可指定独立目录。

---

## 运行与检查

```bash
python run_subject_pipeline.py --subject-root /data/sub-01 --subject-id sub-01 \
  --targets surface_postprocess --postprocess-runtime /data/local-components \
  --postprocess-license-file /data/private/freesurfer-license.txt --execute
```

使用已保存原生 OBJ 的同一被试目录，也可指定 `--postprocess-native-dir`。
完整安装仍可通过 `--postprocess-freesurfer-home` 使用。SynthStrip 及其模型单独配置，
不包含在这七个表面组件中。

独立工作进程检查组件清单、源码版本、动态库和校验和。激活文件预检查仅确认文件
存在，不代表取得授权；原生命令仍执行其激活检查。几何、标量和分区完整性 QC 独立进行，
不代替人工解剖审核。清单及缓存签名记录运行环境身份；切换显式组件目录时不会沿用
上一运行环境的“已完成”状态。

自动源码准备目前仅验证 **Linux x86_64**；未认证 macOS 编译或原生 Windows，
WSL 也不等于原生 Windows 支持。支持的平台上仍可使用已有原生 FreeSurfer。
不宣称核心算法或完整计算流程因此提速。

---

## 来源与许可

原始命令、图谱及第三方库保留 [FreeSurfer 协议](../../licenses/FreeSurfer.txt)
和[图谱许可声明](../../anatomy/surface/ddsurfer_backend/postprocessing/assets/LICENSE.txt)，
不改为项目 MIT 许可。个人激活文件不会进入扩展包、模型镜像或自动下载。
见[实现来源说明](../architecture/IMPLEMENTATION_PROVENANCE.zh-CN.md)。
