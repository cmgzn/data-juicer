# 算子插件

Data-Juicer 可以发现并加载位于核心 `data_juicer` 包**之外**的算子。借此你可以把算子作为独立的 Python 包来发布、版本化和安装（例如发到 PyPI 或私有索引），它们会像内置算子一样出现在全局 `OPERATORS` 注册表中——在任意 recipe 中直接按名字引用，无需改动 Data-Juicer 本身。

- [English](OperatorPlugins.md) | 中文

## 工作原理

在 `import data_juicer.ops` 时，Data-Juicer 会调用 `load_op_plugins()`，扫描所有已安装发行包中声明在 `data_juicer.ops` 分组下的 entry points，并导入其指向的模块。导入插件模块会执行其模块级的 `@OPERATORS.register_module(...)` 装饰器，因此这些算子在 `init_configs()` 读取注册表之前就已就绪。

关键特性：

- **零配置发现**：插件包一经 `pip install`，其算子即自动可用，无需配置任何路径。
- **故障隔离**：若某个插件导入失败（例如缺少依赖），只会记录 warning 并跳过，绝不影响其余流程。
- **向后兼容**：未安装任何插件时，行为与原来完全一致。

## 插件 vs. `custom_operator_paths`

Data-Juicer 提供两种使用库外算子的方式，二者互补：

| | 算子插件（entry points） | `custom_operator_paths` |
|---|---|---|
| 分发方式 | 可安装的包（PyPI / 私有索引） | 本地 `.py` 文件或包目录 |
| 发现方式 | `pip install` 后自动 | 在 CLI / YAML 中显式指定路径 |
| 适用场景 | 可复用、可版本化、共享的算子 | 快速的本地 / 一次性算子 |
| 配置 | 无 | `--custom-operator-paths` 或 YAML 中的 `custom_operator_paths:` |

## 开发一个算子插件

### 1. 包结构

```
my-dj-ops/
├── pyproject.toml
└── my_dj_ops/
    └── __init__.py        # 定义并注册你的算子
```

### 2. 实现并注册算子

算子的写法与内置算子完全一致：继承基类（`Mapper`、`Filter`、`Deduplicator` 等），并用 `@OPERATORS.register_module(<op_name>)` 装饰器注册。重型依赖应通过 `LazyLoader` 延迟加载（切勿在模块导入时直接 import）。

```python
# my_dj_ops/__init__.py
from data_juicer.ops.base_op import OPERATORS, Mapper


@OPERATORS.register_module("my_upper_mapper")
class MyUpperMapper(Mapper):
    """将每个样本的文本转为大写。"""

    _batched_op = True

    def process_batched(self, samples):
        samples[self.text_key] = [t.upper() for t in samples[self.text_key]]
        return samples
```

### 3. 声明 entry point

在 `pyproject.toml` 中，将模块暴露到 `data_juicer.ops` 分组下。entry point 的**取值**必须指向一个模块（或对象），其导入会触发你的 `@OPERATORS.register_module` 调用——指向包的 `__init__` 是最简单的做法。

```toml
[project]
name = "my-dj-ops"
version = "0.1.0"
dependencies = ["py-data-juicer"]

[project.entry-points."data_juicer.ops"]
my_dj_ops = "my_dj_ops"
```

### 4. 安装并使用

```bash
pip install -e .        # 或：pip install my-dj-ops
```

然后即可在任意 recipe 中按名字引用该算子，在 default 和 Ray 两种执行器下均可用：

```yaml
process:
  - my_upper_mapper: {}
```

## 注意事项与最佳实践

- **算子名唯一性**：注册的算子名（如 `my_upper_mapper`）不得与内置算子或其他插件冲突。
- **依赖 `py-data-juicer`**：在插件的 `dependencies` 中声明它，以便获得基类与注册表。
- **重型依赖保持懒加载**：将重型 ML 库写入插件的 `dependencies`，但在运行时通过 `LazyLoader` 加载，与核心算子的约定保持一致。
- **GPU / 不可 fork 算子**同样可作为插件：照常设置 `_accelerator = "cuda"` / `use_cuda()`，执行器会据此选择多进程上下文。
