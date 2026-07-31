# Operator Plugins

Data-Juicer can discover and load operators that live **outside** the core
`data_juicer` package. This lets you ship, version and install operators as
independent Python packages (e.g. on PyPI or a private index) and have them
show up in the global `OPERATORS` registry exactly like the built-in ones —
usable in any recipe by name, with no code change to Data-Juicer.

- English | [中文](OperatorPlugins_ZH.md)

## How it works

At `import data_juicer.ops` time, Data-Juicer calls `load_op_plugins()`, which
scans all installed distributions for entry points under the
`data_juicer.ops` group and imports the referenced modules. Importing a plugin
module runs its module-level `@OPERATORS.register_module(...)` decorators, so
its operators become available before `init_configs()` reads the registry.

Key properties:

- **Zero-config discovery**: once a plugin package is `pip install`ed, its
  operators are available automatically; no path needs to be configured.
- **Fault isolation**: if a plugin fails to import (e.g. a missing dependency),
  it is skipped with a warning and never breaks the rest of the pipeline.
- **Backward compatible**: when no plugin is installed, behavior is unchanged.

## Plugins vs. `custom_operator_paths`

Data-Juicer offers two ways to use out-of-tree operators; they are
complementary:

| | Operator plugins (entry points) | `custom_operator_paths` |
|---|---|---|
| Distribution | Installable package (PyPI / private index) | Local `.py` file or package directory |
| Discovery | Automatic on `pip install` | Explicit path in CLI / YAML |
| Best for | Reusable, versioned, shared operators | Quick local / one-off operators |
| Config | none | `--custom-operator-paths` or `custom_operator_paths:` in YAML |

## Writing an operator plugin

### 1. Package layout

```
my-dj-ops/
├── pyproject.toml
└── my_dj_ops/
    └── __init__.py        # defines & registers your operators
```

### 2. Implement & register operators

Operators are written exactly as built-in ones: inherit from a base class
(`Mapper`, `Filter`, `Deduplicator`, ...) and register with the
`@OPERATORS.register_module(<op_name>)` decorator. Heavy dependencies should be
loaded lazily via `LazyLoader` (never imported at module import time).

```python
# my_dj_ops/__init__.py
from data_juicer.ops.base_op import OPERATORS, Mapper


@OPERATORS.register_module("my_upper_mapper")
class MyUpperMapper(Mapper):
    """Uppercases the text of each sample."""

    _batched_op = True

    def process_batched(self, samples):
        samples[self.text_key] = [t.upper() for t in samples[self.text_key]]
        return samples
```

### 3. Declare the entry point

In `pyproject.toml`, expose the module under the `data_juicer.ops` group. The
entry point **value** must point at a module (or object) whose import triggers
your `@OPERATORS.register_module` calls — pointing at the package `__init__`
is the simplest choice.

```toml
[project]
name = "my-dj-ops"
version = "0.1.0"
dependencies = ["py-data-juicer"]

[project.entry-points."data_juicer.ops"]
my_dj_ops = "my_dj_ops"
```

### 4. Install & use

```bash
pip install -e .        # or: pip install my-dj-ops
```

Then reference the operator by name in any recipe, in both the default and Ray
executors:

```yaml
process:
  - my_upper_mapper: {}
```

## Notes & best practices

- **Operator name uniqueness**: the registered op name (e.g. `my_upper_mapper`)
  must not collide with a built-in operator or another plugin.
- **Depend on `py-data-juicer`**: list it in your plugin's `dependencies` so the
  base classes and registry are available.
- **Keep heavy deps lazy**: declare heavy ML libraries in your plugin's
  `dependencies`, but load them at runtime via `LazyLoader`, matching the core
  operator convention.
- **GPU / unforkable operators** work as plugins too: set `_accelerator =
  "cuda"` / `use_cuda()` as usual; the executor handles the multiprocessing
  context based on these attributes.
