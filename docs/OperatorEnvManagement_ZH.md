# 算子环境管理

本文档描述 Data-Juicer 的算子环境管理功能：如何将每个算子的依赖与当前环境进行判定，哪些算子留在主进程、哪些被隔离到独立环境中运行。环境合并、冲突策略等进阶配置与 Ray 模式的用法见[进阶用法](#进阶环境合并与管理)。

## 概述

Data-Juicer 的部分算子依赖核心安装之外的第三方包（如 `ftfy`、`simhash-pybind`、`vllm`、`opencv-contrib-python` 等）。当同一条流水线中的算子需要冲突版本的包，或某个算子的依赖并不属于 Data-Juicer 自身的环境时，把所有依赖塞进同一个共享环境要么直接失败，要么悄悄破坏用户的环境。

算子环境管理让这些算子在独立的环境中安装依赖并运行，从而避开依赖冲突。在**本地模式**下，其行为很直接：

- 算子默认都在**主进程**运行。
- 只有当某个算子的依赖在主环境里**缺失或版本不兼容**时，它才会被拆到一个独立的 `venv` + 子进程中运行；依赖已满足的算子照常在主进程运行。
- 需要隔离的依赖装在各自独立的 `venv` 里。

> Ray 模式下的环境管理与本地模式不同——算子本来就在各自的 Ray worker 中执行，Data-Juicer 只负责为每个算子生成合适的 `runtime_env`，让同一分组的算子复用同一个虚拟环境。Ray 相关用法见[Ray 模式](#ray-模式下的环境管理)。

## 配置

### 基本设置

本地隔离由一个顶层开关控制，默认开启：

```yaml
# 本地模式隔离的顶层开关，默认开启。
# 为 true 时，依赖缺失或版本冲突的算子会被隔离到独立环境。
# 为 false 时，所有本地算子都在主进程运行，不做任何隔离。
local_op_isolation: true
```

### 命令行

```bash
# 完全关闭本地隔离（所有本地算子在主进程运行）
dj-process --config config.yaml --local_op_isolation false
```

> 还有用于控制分组合并与版本冲突的进阶配置项（`min_common_dep_num_to_combine`、`conflict_resolve_strategy`），见[进阶：环境合并与分组](#进阶环境合并与管理)。

## 依赖分析

每个算子可以通过两种方式声明其 pip 依赖，两者会被自动合并。

### 显式声明

在算子类上设置 `_requirements` 类属性，可以是 pip 依赖字符串列表或指向 requirements 文件的路径：

```python
class MyMapper(Mapper):
    _requirements = ["some-package>=1.0", "another-package==2.3.0"]
```

也支持指向 requirements 文件的路径：

```python
class MyMapper(Mapper):
    _requirements = "/path/to/requirements.txt"
```

### 自动静态分析

如果算子通过 `LazyLoader` 加载依赖：

```python
from data_juicer.utils.lazy_loader import LazyLoader

cv2 = LazyLoader("cv2", "opencv-contrib-python")
simhash = LazyLoader("simhash", "simhash-pybind")
```

Data-Juicer 会静态扫描算子源码文件中的 `LazyLoader(...)` 与 `LazyLoader.check_packages([...])` 调用，自动推导出对应的 pip 包名（如 `opencv-contrib-python`、`simhash-pybind`），**无需实例化算子**。这一机制使得本地模式能够在任何算子被构造之前就完成隔离判定。

`LazyLoader` 的构造函数签名为：

```python
LazyLoader(module_name, package_name=None, package_url=None, ...)
```

- `module_name`：模块名（如 `"cv2"`、`"scipy.interpolate"`）
- `package_name`：pip 包名（如 `"opencv-contrib-python"`）；为 `None` 时自动取 `module_name` 的基础部分
- `package_url`：安装来源 URL（如 `git+https://...`）

当 `module_name` 与 pip 包名不同时（如 `cv2` → `opencv-contrib-python`），需要显式指定 `package_name`。

### 合并结果

两种来源的依赖信息会被合并为每个算子的单一 `OPEnvSpec`（见 [`op_requirements_to_op_env_spec`](/data_juicer/ops/op_env.py)）。合并时显式声明的依赖优先，自动分析出的额外依赖会被补充进去。

## 主环境判定（本地模式）

在任何算子被实例化之前，`load_ops` 基于算子**类**（`_requirements` + 静态 LazyLoader 分析）计算每个算子的 `OPEnvSpec`，并通过 [`resolve_local_env_spec`](/data_juicer/ops/op_env.py) 与当前环境进行判定。

对算子声明的每个依赖 `(name, 版本约束)`，Data-Juicer 只看它在主环境里是否已经装好：

1. **已安装且版本满足约束** → 该依赖可在**主进程**满足。
2. **其他情况** → 触发隔离，包括：
   - 该包**未安装**；
   - **已安装但版本不满足约束**；
   - URL / VCS / 本地路径依赖（无法与已安装的包直接比对）。

对当前平台不适用的环境 marker 会被跳过。

几个例子：

- 主环境里没装的包 → 隔离。
- 通过 `git+URL` 声明的依赖 → 隔离。
- 已装但版本与算子要求不兼容 → 隔离。
- 所有依赖都已按兼容版本装好 → 在主进程运行，不创建 venv。

## 本地模式的环境管理

在本地（非 Ray）模式下，隔离既决定算子声明什么环境，也改变了算子的执行方式。

### 加载流程

1. `load_ops` 计算并判定每个算子的 spec（见[主环境判定](#主环境判定本地模式)）。需隔离的依赖会装到各自的 venv 里，而不是装进主环境。
2. 判定为留在主进程的算子正常实例化。
3. 必须隔离的算子被记录到 `OPEnvManager`，合并后由 `IsolatedOpProxy` 代替 —— 一个只持有算子类和构造参数、不实例化算子的轻量占位对象。

### 分段合并

处理列表中连续属于同一分组的算子会被合并为一个「段」（segment）：

- 只有该段的第一个代理（**leader**）真正发起一次子进程调用，在该子进程中按顺序执行整段算子序列。
- 其余代理（**follower**）的 `run()` 是一个空操作，直接透传它收到的数据集 —— 因为 leader 的子进程调用已经把整段（包括 follower 对应的算子）都执行完了，最终结果已经由 leader 返回。

这减少了子进程创建和数据序列化的次数。

### 子进程执行

当段 leader 执行时：

1. **获取虚拟环境** — 使用 `<cache-dir>/<python-cache-tag>/<spec-hash>/` 下的独立 `venv`。不使用 `--system-site-packages`；Data-Juicer 向子 venv 的 site-packages 写入受管 `.pth` 文件（`_data_juicer_parent_env.pth`），列出项目根目录与父环境的 site-packages。见 [venv 缓存生命周期](#venv-缓存生命周期)。
2. **安装依赖** — 使用配置的后端（`uv` 或 `pip`）安装该 venv 的 `pip_pkgs`。
3. **环境变量注入** — `OPEnvSpec.env_vars` 中的变量被叠加到子进程环境（对应 Ray 的 `runtime_env["env_vars"]`）。
4. **数据传递** — 输入数据集通过 `save_to_disk` 序列化，子进程（`data_juicer.ops._isolated_worker`）反序列化后按顺序执行整段，再把结果保存回磁盘。
5. **结果加载** — leader 通过 `NestedDataset.load_from_disk(..., keep_in_memory=True)` 加载结果。`keep_in_memory=True` 是必须的：普通内存映射（mmap）加载不是 fork 安全的，后续主进程调用 `datasets.map(num_proc>=1)` 时，多进程池 fork 会继承 mmap 的 Arrow 缓冲区并崩溃。
6. **副作用转发** — Exporter/Tracer 配置被序列化并转发给子进程，逐算子日志写入 `<work_dir>/isolated_logs/`，确保 tracing/导出副作用依然正确发生。

### 执行路径示意

> 下图仅为**示意**。实际分组完全取决于各算子判定后的依赖情况和 `min_common_dep_num_to_combine`（见[进阶：环境合并与分组](#进阶环境合并与管理)）。例如在 `min_common_dep_num_to_combine: 0` 且无版本冲突时，下面的 B、C、D 可能被合并进**同一个**分组。本例假设：A、E 判定为主进程；B、C 在同一环境组；D 在另一个分组。

```
主进程
├── 算子 A（主进程）  → 在主进程中实例化并执行
├── 算子 B（隔离）    → IsolatedOpProxy (leader) ──→ 子进程 1
│   └── 算子 C（同分组）→ IsolatedOpProxy (follower)   └─ 执行 B, C
├── 算子 D（隔离）    → IsolatedOpProxy (leader) ──→ 子进程 2
│   └──                                              └─ 执行 D
└── 算子 E（主进程）  → 在主进程中实例化并执行
```

### venv 缓存生命周期

- **位置** — `<cache-dir>/<python-cache-tag>/<spec-hash>/`，其中 `<cache-dir>` 默认为 `<tempdir>/dj_venvs`（通常是 `/tmp/dj_venvs`）。Python cache tag（如 `cpython-312`）作为一级目录，确保不同解释器的 venv 不会互相冲突。
- **按 spec 哈希复用** — 键是*整份*合并 spec 的 SHA-1 哈希（不做子集/增量匹配，与 Ray 一致）。哈希命中即原样复用该 venv，不重装任何包。
- **完成标记与健康检查** — 创建与安装受每个 spec 独立的文件锁保护。缓存项只有在写入 `.complete` 标记**且** venv 的 `bin/python` 存在后才可复用。不完整或失败的目录会被删除重建。
- **父环境同步** — 受管 `.pth` 文件在每次获取时重写，使继承路径与当前父环境保持同步。

> **注意：** 缓存的 venv 不会被自动回收，会随不同 spec 的累积而占用磁盘。如需释放空间，请手动清理缓存目录（如 `rm -rf /tmp/dj_venvs/`）。

## 运行时验证

关注以下日志行，可确认算子的判定/分组是否符合预期：

```
Try to combine OP Environments with at least N common dependencies
Creating isolated venv at /tmp/dj_venvs/cpython-312/<spec-hash> ...
Installing packages in isolated venv (backend=uv): [...]
Running ops [opA, opB, ...] in isolated subprocess ...
```

`Running ops [...]` 这一行列出了本次子进程调用中被合并执行的具体算子，是判断分组是否符合预期的依据。

## 故障排除

**隔离子进程失败：**

```
# 子进程会继承父进程的 stdout/stderr 以实时输出，
# 同时在 <work_dir>/isolated_logs/ 下为每次调用写一个日志文件。
# 例如：Isolated ops [opA, opB] failed (rc=1). Log: <work_dir>/isolated_logs/...
```

**venv 创建或包安装失败：**

```bash
# 检查 venv 缓存目录（默认在 /tmp 下）
ls -la /tmp/dj_venvs/

# 清理缓存重新创建
rm -rf /tmp/dj_venvs/
```

不完整的缓存项（缺少 `.complete` 标记或 `bin/python`）会在下次运行时被自动删除并重建。

**子进程缺少父环境依赖：**

父环境路径通过写入子 venv site-packages 的受管 `.pth` 文件（`_data_juicer_parent_env.pth`）继承，**不再**通过 `PYTHONPATH`。如果子进程仍报 `ModuleNotFoundError`，请确认：

- 主环境的 `site.getsitepackages()` 返回正确路径；
- 项目根目录可被导入（editable 安装，或位于父环境的 `sys.path` 中）。

**分组结果不符合预期：**

```python
from data_juicer.ops.op_env import OPEnvManager
manager.print_the_current_states()
```

## 进阶：环境合并与管理

默认情况下，每个被隔离的算子各自使用独立环境，你无需关心分组。本节介绍用于控制**如何把多个算子合并到同一个环境**以及合并时**版本冲突**如何处理的配置项。这套分组逻辑由 `OPEnvManager` 实现，本地模式与 Ray 模式共用。

### 合并与冲突控制

```yaml
# 控制环境合并（产生多少个隔离分组），不负责启用/关闭本地隔离。
#   -1（默认）：隔离分组之间不合并，每个分组保留自己的环境；venv 稳定、可复用。
#   >= 0：      将共享依赖数达到该阈值的算子环境合并为一组。
min_common_dep_num_to_combine: -1

# 当两个算子声明了同一个包但版本约束「完全不兼容」时，如何解决冲突。
#   - split：     （默认）不合并，两个算子保持独立分组
#   - overwrite： 使用后声明算子的版本
#   - latest：    使用两个版本约束中较新的一个
conflict_resolve_strategy: split
```

命令行示例：

```bash
# 尽可能激进地合并隔离分组
dj-process --config config.yaml --min_common_dep_num_to_combine 0

# 仅在共享至少 2 个共同依赖时才合并
dj-process --config config.yaml --min_common_dep_num_to_combine 2

# 激进合并并用 overwrite 解决不兼容的版本冲突
dj-process --config config.yaml --min_common_dep_num_to_combine 0 --conflict_resolve_strategy overwrite
```

### 合并阈值说明

| 值 | 行为 | 适用场景 |
|----|------|----------|
| `-1`（默认） | 隔离分组之间不合并 | 稳定、可复用的逐 spec venv；跨次运行复用更好 |
| `0` | 尽可能合并，即使没有任何共同依赖 | 最小化子进程数量；更少、更大的 venv |
| `N`（N > 0） | 仅在共享至少 `N` 个共同依赖时才合并 | 保持分组精细、有针对性 |

默认值 `-1`（不合并）能让每个隔离环境保持稳定、不受流水线形状影响，从而尽可能复用已创建的 venv。如果你希望减少子进程/venv 的数量，可以调高该阈值来合并分组。

### 合并逻辑

`OPEnvManager.merge_op_env_specs` 是两种模式共用的核心合并逻辑：

1. 按声明顺序依次注册每个算子的 `OPEnvSpec`。
2. 对新注册的 spec，`OPEnvManager` 遍历已有分组，将其合并进**第一个**满足 `can_combine_op_env_specs` 的分组：
   - 共同依赖名称数量 ≥ `min_common_dep_num_to_combine`，**且**
   - 若双方都指定了 `working_dir`，则必须相同。
3. 若没有可合并的分组，则新建一个分组。
4. 若同一依赖名称在两个 spec 中出现但版本约束不同，由 `conflict_resolve_strategy` 决定处理方式。

**空 spec 永不合并。** 判定为留在主进程的算子拥有空 spec，它既不会吸收其他隔离分组，也不会被吸收进隔离分组 —— 即使 `min_common_dep_num_to_combine` 为 `0`。

### 冲突解决策略

只有当同一依赖在两个 spec 中出现**且版本约束不同**时，才涉及冲突解决。

**只要两个约束存在交集（相互兼容），无论采用哪种策略都会直接合并为交集，策略并不介入。** 只有当两个约束**完全无交集**时，`conflict_resolve_strategy` 才决定结果：

| 策略 | 无交集时的行为 |
|------|----------------|
| `split`（默认） | 合并失败，两个算子保持独立分组 |
| `overwrite` | 使用后声明算子的版本约束覆盖已有版本 |
| `latest` | 取两个约束中较新的一个；无法判定时回退为不固定版本并打印告警 |

此外还有一个**与策略无关**的特例 —— PEP 440 的「任意等号」约束 `===`（三个等号，与普通 `==` 是不同的运算符）：

- 当两个约束**都是** `===` 且取值不同时（如 `numpy===2.0` 与 `numpy===1.23.0`），无法合并，两个算子保持独立分组；
- 当**只有一个**是 `===` 时，直接采用该精确版本。

### 查看分组结果

通过 `OPEnvManager.print_the_current_states()` 可打印每个分组包含的算子及合并后的 `pip_pkgs` 列表：

```python
from data_juicer.ops.op_env import OPEnvManager

manager = OPEnvManager(min_common_dep_num_to_combine=0)
# ... 注册算子环境规格后 ...
manager.print_the_current_states()
```

## Ray 模式下的环境管理

Ray 模式下，算子本来就在各自的 Ray worker 中执行，Data-Juicer 负责为每个算子生成合适的 Ray `runtime_env`，让同一分组的算子复用同一个虚拟环境/容器。

`load_ops` 会立即实例化所有算子，然后执行两轮遍历：

1. **第一轮** — 通过 `op.get_env_spec()` 获取每个算子的 `OPEnvSpec`，记录到 `OPEnvManager`。
2. **第二轮** — 将每个算子合并后的 spec 转换为 Ray `runtime_env` 字典（`OPEnvSpec.to_dict()`），赋值给 `op.runtime_env`（仅当用户没有显式设置时）。

同一分组内的算子共享同一个 `runtime_env`，Ray 会为整组复用同一个虚拟环境/容器。Ray 模式仅在 `min_common_dep_num_to_combine >= 0` 时启用分组管理；顶层开关 `local_op_isolation` 与本地模式的主环境判定都不适用于 Ray。

## 性能考虑

### 开销来源

| 开销类型 | 频率 | 说明 |
|----------|------|------|
| venv 创建 | 首次使用每个 spec 时一次性 | 缓存目录存活期间可跨次运行复用 |
| 包安装 | 首次使用每个 spec 时一次性 | 按 spec 哈希缓存 |
| 数据序列化/反序列化 | 每次子进程调用 | 与数据集大小成正比 |
| 子进程启动 | 每次子进程调用 | 固定开销 |

### 合并阈值影响

- `min_common_dep_num_to_combine: 0` — 最大化共享：更少、更大的分组和更少的子进程调用，但每个共享 venv 需安装所有依赖的并集，其哈希对流水线形状更敏感（跨次运行复用变差）。
- `-1`（默认）或更大阈值 — 更多、更小、更精细的分组：子进程调用更多，但每个 venv 稳定、跨次运行复用好。

### 适用场景

| 场景 | 建议 |
|------|------|
| 小数据集 | 隔离开销可能占主导；但隔离只在真冲突时触发，通常无妨 |
| 大数据集 | 子进程执行时间远大于启动开销 |
| 依赖冲突频繁 | 保持默认 `split` 策略，让冲突算子相互独立 |
| 想减少子进程数 | 设 `min_common_dep_num_to_combine: 0`；可选 `overwrite`/`latest` 以跨小版本冲突合并 |

## API 参考

### OPEnvSpec

算子环境规格，封装算子的依赖信息：

```python
from data_juicer.ops.op_env import OPEnvSpec

spec = OPEnvSpec(
    pip_pkgs=["numpy>=1.20.0", "pandas>=1.3.0"],  # pip 依赖列表或 requirements 文件路径
    env_vars={"CUDA_VISIBLE_DEVICES": "0"},          # 环境变量
    working_dir="/path/to/working_dir",              # 工作目录
    backend="uv",                                    # 包管理后端："uv" 或 "pip"
    extra_env_params={},                             # 额外传递给 Ray runtime_env 的参数
)
```

| 属性 | 类型 | 描述 |
|------|------|------|
| `pip_pkgs` | `List[str]` | pip 依赖字符串列表 |
| `env_vars` | `Dict[str, str]` | 环境变量 |
| `working_dir` | `Optional[str]` | 工作目录 |
| `backend` | `str` | 包管理后端，`"uv"` 或 `"pip"` |
| `extra_env_params` | `Dict` | 额外 Ray runtime_env 参数 |

主要方法：

- `to_dict()` — 转换为 Ray `runtime_env` 字典
- `get_hash()` — 返回规格的 SHA-1 哈希值（用于 venv 缓存键）
- `get_requirement_name_list()` — 返回已解析的依赖名称排序列表

### resolve_local_env_spec

`resolve_local_env_spec(env_spec) -> OPEnvSpec` 实现了[主环境判定](#主环境判定本地模式)。它返回单个 spec：`pip_pkgs` 为空表示该算子可在主进程运行（每个适用依赖都已按兼容版本安装）；否则返回完整原始 spec，该算子将在独立的隔离 venv 运行。

### OPEnvManager

负责记录、合并和查询算子环境规格：

```python
from data_juicer.ops.op_env import OPEnvManager

manager = OPEnvManager(
    min_common_dep_num_to_combine=0,
    conflict_resolve_strategy="split",  # "split", "overwrite", 或 "latest"
)

manager.record_op_env_spec("my_op", op_env_spec)   # 注册
merged_spec = manager.get_op_env_spec("my_op")      # 获取合并后的 spec
manager.print_the_current_states()                  # 查看分组
```

### IsolatedOpProxy

本地模式下必须隔离的算子的轻量占位对象。持有算子类引用和构造参数，不实际实例化算子。其 `run` 方法在 `wrap_ops_with_isolation` 调用后被替换为子进程执行逻辑。

### VenvManager

管理隔离算子使用的虚拟环境。每个唯一的 `OPEnvSpec` 对应一个 venv，在 Python cache tag 目录下按完整 spec 哈希缓存，配有每个 spec 独立的文件锁、`.complete` 标记和 `bin/python` 健康检查。venv 通过受管 `.pth` 文件继承基础环境，而非 `--system-site-packages`。

## 模式对比

| | 本地模式 | Ray 模式 |
|---|---|---|
| 启用开关 | `local_op_isolation`（默认 `true`） | `min_common_dep_num_to_combine >= 0` |
| 主环境判定 | 基于已安装集合的满足性；冲突/缺失则隔离 | 不适用 |
| 隔离单元 | 每个分组一个独立 `venv` + 子进程 | 每个分组一个 `runtime_env` |
| 分组逻辑 | `OPEnvManager`（共用） | `OPEnvManager`（共用） |
| 无需隔离的算子 | 在主进程中正常运行 | 得到一个（实际为空的）`runtime_env` |
| 连续同组算子 | 合并为一次子进程调用（leader/follower） | 每个仍是独立的 Ray task |
| 算子实例化时机 | 隔离算子在子进程中延迟实例化 | 加载时立即实例化 |
| 缓存机制 | `<cache-dir>/<python-cache-tag>/` 按 spec 哈希缓存 | Ray 内部 runtime_env 缓存 |
