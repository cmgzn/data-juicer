# Operator Environment Management

This document describes Data-Juicer's operator environment management feature: how each operator's dependencies are resolved against the current environment, and which operators stay in the main process versus being isolated into a dedicated environment. Advanced configuration such as environment merging and conflict strategies, along with Ray mode usage, are covered in [Advanced Usage](#advanced-environment-merging-and-management).

## Overview

Some Data-Juicer operators depend on third-party packages outside the core installation (e.g., `ftfy`, `simhash-pybind`, `vllm`, `opencv-contrib-python`). When two operators in the same pipeline require conflicting package versions, or when an operator's dependency is not part of Data-Juicer's own environment, running everything in a single shared environment either fails or silently disturbs the user's environment.

Operator environment management lets these operators install their dependencies and run in a separate environment, avoiding dependency conflicts. In **local mode**, the behavior is straightforward:

- Operators run in the **main process** by default.
- An operator is moved into a dedicated `venv` + subprocess only when its dependencies are **missing from, or version-incompatible with**, the main environment; operators whose dependencies are already satisfied keep running in the main process.
- Dependencies that need isolation are installed into their own dedicated `venv`.

> In Ray mode, operators already execute in their own Ray workers; Data-Juicer is responsible for generating an appropriate Ray `runtime_env` for each operator and letting operators in the same group share one virtualenv/container. Ray usage is covered in [Ray Mode](#ray-mode-environment-management).

## Configuration

### Basic settings

Local isolation is controlled by a single top-level switch, enabled by default:

```yaml
# Top-level switch for LOCAL-mode isolation. Enabled by default.
# When true, operators with missing or version-conflicting dependencies are
# isolated into a dedicated environment.
# When false, every local operator runs in the main process with no isolation.
local_op_isolation: true
```

### Command line

```bash
# Disable local isolation entirely (all local ops run in the main process)
dj-process --config config.yaml --local_op_isolation false
```

> Two advanced configuration options (`min_common_dep_num_to_combine`, `conflict_resolve_strategy`) control group merging and version conflicts. See [Advanced: Environment Merging and Grouping](#advanced-environment-merging-and-management).

## Dependency Analysis

Each operator can declare its pip requirements in two ways, which are combined automatically.

### Explicit declaration

Set the class attribute `_requirements` on the operator class, as a list of pip specifiers or a path to a requirements file:

```python
class MyMapper(Mapper):
    _requirements = ["some-package>=1.0", "another-package==2.3.0"]
```

A path to a requirements file is also supported:

```python
class MyMapper(Mapper):
    _requirements = "/path/to/requirements.txt"
```

### Automatic static analysis

If an operator loads a dependency via `LazyLoader`:

```python
from data_juicer.utils.lazy_loader import LazyLoader

cv2 = LazyLoader("cv2", "opencv-contrib-python")
simhash = LazyLoader("simhash", "simhash-pybind")
```

Data-Juicer statically scans the operator's source file for `LazyLoader(...)` and `LazyLoader.check_packages([...])` calls and infers the pip package names (e.g., `opencv-contrib-python`, `simhash-pybind`) **without instantiating the operator**. This is what allows isolation decisions to be made *before* any operator is constructed in local mode.

The `LazyLoader` constructor signature is:

```python
LazyLoader(module_name, package_name=None, package_url=None, ...)
```

- `module_name`: the module to import (e.g., `"cv2"`, `"scipy.interpolate"`)
- `package_name`: the pip package name (e.g., `"opencv-contrib-python"`); when `None`, defaults to the base module name
- `package_url`: installation source URL (e.g., `git+https://...`)

When the module name differs from the pip package name (e.g., `cv2` → `opencv-contrib-python`), `package_name` must be specified explicitly.

### Merging result

Both sources are merged into a single `OPEnvSpec` per operator (see [`op_requirements_to_op_env_spec`](/data_juicer/ops/op_env.py)). Explicitly declared dependencies take precedence; auto-analyzed extras are added on top.

## Main-Environment Resolution (Local Mode)

Before any operator is instantiated, `load_ops` computes each operator's `OPEnvSpec` from its **class** (`_requirements` + static LazyLoader analysis) and resolves it against the current environment via [`resolve_local_env_spec`](/data_juicer/ops/op_env.py).

For each dependency `(name, version_specifier)` the operator declares, Data-Juicer only checks whether it is already installed in the main environment:

1. **Installed and the version satisfies the specifier** → this requirement is satisfied in the **main process**.
2. **Anything else** → triggers isolation, including:
   - the package is **not installed**,
   - **installed but the version does not satisfy the specifier**,
   - URL / VCS / local-path requirements (cannot be compared against installed packages directly).

Environment markers that do not apply to the current platform are skipped.

A few examples:

- A package not installed in the main environment → isolated.
- A dependency declared via `git+URL` → isolated.
- A package installed at a version incompatible with the operator's requirement → isolated.
- All requirements already installed at compatible versions → runs in the main process, no venv created.

## Local Mode Environment Management

In local (non-Ray) mode, isolation changes both *what* environment an operator declares and *how* it is executed.

### Loading process

1. `load_ops` computes and resolves each operator's spec (see [Main-Environment Resolution](#main-environment-resolution-local-mode)). Isolated dependencies are installed into their own venvs, not the main environment.
2. Operators resolved to the main process are instantiated normally.
3. Operators that must be isolated are recorded with `OPEnvManager` and, after merging, represented by an `IsolatedOpProxy` — a lightweight placeholder that holds the operator class and constructor kwargs without instantiating it.

### Segment grouping

Consecutive operators in the process list that belong to the same env group are merged into one "segment":

- Only the segment's first proxy (the **leader**) actually spawns a subprocess, which executes the entire segment's operator sequence in order.
- The remaining proxies (**followers**) have a no-op `run()` that simply passes through whatever dataset it receives — because the leader's subprocess call has already executed the whole segment (including the operators corresponding to each follower), and the final result has already been returned by the leader.

This reduces the number of subprocess invocations and dataset serialization rounds.

### Subprocess execution

When a segment leader runs:

1. **Virtualenv acquisition** — A dedicated `venv` is used under `<cache-dir>/<python-cache-tag>/<spec-hash>/`. It does **not** use `--system-site-packages`; instead Data-Juicer writes a managed `.pth` file (`_data_juicer_parent_env.pth`) into the child venv's site-packages, listing the project root and the parent environment's site-packages. See [venv Cache Lifecycle](#venv-cache-lifecycle).
2. **Package installation** — The venv's `pip_pkgs` are installed with the configured backend (`uv` or `pip`).
3. **Environment variable injection** — Variables from `OPEnvSpec.env_vars` are overlaid onto the subprocess environment (mirroring Ray's `runtime_env["env_vars"]`).
4. **Data transfer** — The input dataset is serialized via `save_to_disk`. The subprocess (`data_juicer.ops._isolated_worker`) deserializes it, runs the whole segment in order, and saves the result back.
5. **Result loading** — The leader loads the result with `NestedDataset.load_from_disk(..., keep_in_memory=True)`. `keep_in_memory=True` is required: a plain memory-mapped load is not fork-safe, and a subsequent `datasets.map(num_proc>=1)` call in the main process would crash when the multiprocessing pool forks the mmap'd Arrow buffer.
6. **Side-effect forwarding** — Exporter/Tracer configuration is serialized and forwarded to the subprocess, and per-operator logs are written under `<work_dir>/isolated_logs/`, so tracing/export side effects still occur correctly.

### Execution path diagram

> The diagram is **illustrative only**. The actual grouping depends entirely on each operator's resolved dependencies and `min_common_dep_num_to_combine` (see [Advanced: Environment Merging and Grouping](#advanced-environment-merging-and-management)). For example, with `min_common_dep_num_to_combine: 0` and no version conflicts, B, C, and D below could all merge into a **single** group. This example assumes: A and E resolve to the main process; B and C are in the same env group; D is in a separate group.

```
Main process
├── Op A (main process) → instantiated and run in main process
├── Op B (isolated)     → IsolatedOpProxy (leader) ──→ Subprocess 1
│   └── Op C (same group) → IsolatedOpProxy (follower)   └─ runs B, C
├── Op D (isolated)     → IsolatedOpProxy (leader) ──→ Subprocess 2
│   └──                                                   └─ runs D
└── Op E (main process) → instantiated and run in main process
```

### venv Cache Lifecycle

- **Location** — `<cache-dir>/<python-cache-tag>/<spec-hash>/`, where `<cache-dir>` defaults to `<tempdir>/dj_venvs` (typically `/tmp/dj_venvs`). The Python cache tag (e.g., `cpython-312`) forms a first-level directory so venvs from different interpreters never collide.
- **Reuse by spec hash** — the key is the SHA-1 hash of the *entire* merged spec (no subset/incremental matching, mirroring Ray). A hash hit means the venv is reused as-is; nothing is reinstalled.
- **Completion & health** — creation and installation are protected by a per-spec file lock. A cache entry is reusable only after a `.complete` marker is written **and** the venv's `bin/python` exists. Incomplete or failed entries are removed and rebuilt.
- **Parent-env sync** — the managed `.pth` file is rewritten on every acquisition, keeping inherited paths in sync with the current parent environment.

> **Note:** Cached venvs are not reclaimed automatically and will accumulate on disk as more specs are used. To free space, clean up the cache directory manually (e.g., `rm -rf /tmp/dj_venvs/`).

## Runtime Verification

Look for these log lines to confirm operators were resolved/grouped as expected:

```
Try to combine OP Environments with at least N common dependencies
Creating isolated venv at /tmp/dj_venvs/cpython-312/<spec-hash> ...
Installing packages in isolated venv (backend=uv): [...]
Running ops [opA, opB, ...] in isolated subprocess ...
```

The `Running ops [...]` line lists exactly which operators were merged into that subprocess call — the ground truth for whether grouping behaved as intended.

## Troubleshooting

**Isolated subprocess failure:**

```
# The subprocess inherits the parent's stdout/stderr for real-time output,
# and also writes a per-invocation log under <work_dir>/isolated_logs/.
# e.g.: Isolated ops [opA, opB] failed (rc=1). Log: <work_dir>/isolated_logs/...
```

**venv creation or package installation failure:**

```bash
# Inspect the venv cache directory (default under /tmp)
ls -la /tmp/dj_venvs/

# Clear the cache and let it rebuild
rm -rf /tmp/dj_venvs/
```

Incomplete entries (no `.complete` marker or missing `bin/python`) are removed and rebuilt automatically on the next run.

**Subprocess missing parent-environment dependencies:**

Parent paths are inherited via the managed `.pth` file (`_data_juicer_parent_env.pth`) written into the child venv's site-packages — **not** via `PYTHONPATH`. If the subprocess still reports `ModuleNotFoundError`, verify that:

- `site.getsitepackages()` returns correct paths in the main environment,
- the project root is importable (editable install, or on the parent's `sys.path`).

**Grouping results not as expected:**

```python
from data_juicer.ops.op_env import OPEnvManager
manager.print_the_current_states()
```

## Advanced: Environment Merging and Management

By default, each isolated operator uses its own environment and you don't need to think about grouping. This section covers the configuration options that control **how multiple operators are merged into one environment** and how **version conflicts** are handled during merging. This grouping logic is implemented by `OPEnvManager` and shared by both local and Ray modes.

### Merge and conflict management

```yaml
# Controls environment merging (how many isolated groups are produced).
# It does NOT enable/disable local isolation.
#   -1 (default): do not merge isolated groups; each group keeps its own
#                 environment. Stable, reusable per-spec venvs.
#   >= 0:         merge environments that share at least this many common
#                 dependencies into one group.
min_common_dep_num_to_combine: -1

# How to resolve a version conflict when merging two operators that declare
# the SAME package with COMPLETELY incompatible version specifiers.
#   - split:     (default) do not merge; keep the operators in separate groups
#   - overwrite: use the version required by the later-declared operator
#   - latest:    use the newer of the two version specifiers
conflict_resolve_strategy: split
```

Command-line examples:

```bash
# Merge isolated groups as aggressively as possible
dj-process --config config.yaml --min_common_dep_num_to_combine 0

# Only merge when at least 2 common dependencies are shared
dj-process --config config.yaml --min_common_dep_num_to_combine 2

# Merge aggressively and use overwrite to resolve incompatible version conflicts
dj-process --config config.yaml --min_common_dep_num_to_combine 0 --conflict_resolve_strategy overwrite
```

### Merge threshold guide

| Value | Behavior | Use case |
|-------|----------|----------|
| `-1` (default) | Isolated groups are not merged | Stable, reusable per-spec venvs; better cross-run venv reuse |
| `0` | Merge as aggressively as possible, even with zero common dependencies | Minimize subprocess count; fewer, larger venvs |
| `N` (N > 0) | Only merge when at least `N` common dependencies are shared | Keep groups small and targeted |

The default `-1` (no merging) keeps each isolated environment stable and independent of pipeline shape, so previously created venvs can be reused across runs. If you want to reduce the number of subprocesses/venvs, raise the threshold to merge groups.

### Merging logic

`OPEnvManager.merge_op_env_specs` is the shared core logic for both modes:

1. Each operator's `OPEnvSpec` is registered in declaration order.
2. For a newly registered spec, `OPEnvManager` scans existing groups and merges into the **first** one that satisfies `can_combine_op_env_specs`:
   - number of common dependency names ≥ `min_common_dep_num_to_combine`, **and**
   - if both specs specify `working_dir`, they are the same.
3. If no group can be merged with, a new group is created.
4. If a dependency name exists in both specs with different version specifiers, `conflict_resolve_strategy` decides the outcome.

**Empty specs never merge.** An operator that resolved to the main process has an empty spec; it never absorbs, or is absorbed into, an isolated group — even when `min_common_dep_num_to_combine` is `0`.

### Conflict resolution strategies

Conflict resolution applies only when the same dependency appears in two specs **with different version specifiers**.

**If the two specifiers have a non-empty intersection (they are compatible), they are always merged into the intersection regardless of strategy — the strategy is not consulted.** The `conflict_resolve_strategy` only takes effect when the two specifiers are **completely incompatible** (empty intersection):

| Strategy | Behavior on incompatibility |
|----------|-----------------------------|
| `split` (default) | Merge fails; the two operators stay in separate groups |
| `overwrite` | The later-declared operator's version overrides the existing one |
| `latest` | Picks the newer of the two specifiers; falls back to an unpinned version with a warning when it cannot decide |

There is also a **strategy-independent** special case — PEP 440's "arbitrary equality" specifier `===` (three equals signs; a different operator from ordinary `==`):

- when **both** specifiers use `===` with different values (e.g., `numpy===2.0` vs `numpy===1.23.0`), they cannot be merged and the operators stay separate;
- when **only one** uses `===`, that exact version is used directly.

### Inspecting grouping results

Use `OPEnvManager.print_the_current_states()` to print each group's member operators and the resulting merged `pip_pkgs` list:

```python
from data_juicer.ops.op_env import OPEnvManager

manager = OPEnvManager(min_common_dep_num_to_combine=0)
# ... after registering operator env specs ...
manager.print_the_current_states()
```

## Ray Mode Environment Management

In Ray mode, operators already execute in their own Ray workers; Data-Juicer is responsible for generating an appropriate Ray `runtime_env` for each operator and letting operators in the same group share one virtualenv/container.

`load_ops` eagerly instantiates every operator, then performs two passes:

1. **First pass** — each operator's `OPEnvSpec` (via `op.get_env_spec()`) is recorded with `OPEnvManager`.
2. **Second pass** — the merged spec for each operator is converted to a Ray `runtime_env` dict (`OPEnvSpec.to_dict()`) and assigned to `op.runtime_env` (only if the user hasn't already set one).

Operators in the same group share the same `runtime_env`, so Ray reuses one virtualenv/container for all of them. Ray mode enables group management only when `min_common_dep_num_to_combine >= 0`; neither the top-level `local_op_isolation` switch nor the local-mode main-environment resolution applies to Ray.

## Performance Considerations

### Overhead sources

| Overhead type | Frequency | Description |
|---------------|-----------|-------------|
| venv creation | Once per unique spec | Reused across runs while the cache directory survives |
| Package installation | Once per unique spec | Cached by spec hash |
| Dataset serialization | Per subprocess call | Proportional to dataset size |
| Subprocess startup | Per subprocess call | Fixed overhead |

### Merge threshold impact

- `min_common_dep_num_to_combine: 0` — maximizes sharing: fewer, larger groups and fewer subprocess calls, but each shared venv installs the union of all dependencies and its hash is more sensitive to pipeline shape (worse cross-run reuse).
- `-1` (default) or a larger threshold — more, smaller, targeted groups: more subprocess invocations, but each venv is stable and reused well across runs.

### Recommended scenarios

| Scenario | Recommendation |
|----------|----------------|
| Small datasets | Overhead may dominate; isolation only kicks in for real conflicts, so this is usually fine |
| Large datasets | Subprocess execution outweighs startup overhead |
| Frequent dependency conflicts | Keep the default `split` strategy so conflicting operators stay separate |
| Want fewer subprocesses | Set `min_common_dep_num_to_combine: 0`; optionally `overwrite`/`latest` to merge across minor version conflicts |

## API Reference

### OPEnvSpec

Operator environment specification, encapsulating dependency information:

```python
from data_juicer.ops.op_env import OPEnvSpec

spec = OPEnvSpec(
    pip_pkgs=["numpy>=1.20.0", "pandas>=1.3.0"],  # pip specifiers or requirements file path
    env_vars={"CUDA_VISIBLE_DEVICES": "0"},          # environment variables
    working_dir="/path/to/working_dir",              # working directory
    backend="uv",                                    # package management backend: "uv" or "pip"
    extra_env_params={},                             # extra params for Ray runtime_env
)
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `pip_pkgs` | `List[str]` | List of pip specifier strings |
| `env_vars` | `Dict[str, str]` | Environment variables |
| `working_dir` | `Optional[str]` | Working directory |
| `backend` | `str` | Package management backend, `"uv"` or `"pip"` |
| `extra_env_params` | `Dict` | Extra Ray runtime_env parameters |

Key methods:

- `to_dict()` — converts to a Ray `runtime_env` dict
- `get_hash()` — returns the SHA-1 hash of the spec (used as venv cache key)
- `get_requirement_name_list()` — returns a sorted list of parsed dependency names

### resolve_local_env_spec

`resolve_local_env_spec(env_spec) -> OPEnvSpec` implements the [main-environment resolution](#main-environment-resolution-local-mode). It returns a single spec: an empty `pip_pkgs` means the operator can run in the main process (every applicable requirement is already installed at a compatible version); otherwise the complete original spec is returned so the operator runs in a dedicated isolated venv.

### OPEnvManager

Records, merges, and queries operator environment specs:

```python
from data_juicer.ops.op_env import OPEnvManager

manager = OPEnvManager(
    min_common_dep_num_to_combine=0,
    conflict_resolve_strategy="split",  # "split", "overwrite", or "latest"
)

manager.record_op_env_spec("my_op", op_env_spec)   # register
merged_spec = manager.get_op_env_spec("my_op")      # retrieve merged spec
manager.print_the_current_states()                  # inspect grouping
```

### IsolatedOpProxy

A lightweight placeholder for a local-mode operator that must be isolated. It holds the operator class reference and constructor kwargs without instantiating the operator. Its `run` is replaced by subprocess execution after `wrap_ops_with_isolation` is called.

### VenvManager

Manages virtual environments for isolated operators. Each unique `OPEnvSpec` gets its own venv, cached by full spec hash below a Python cache-tag directory, with a per-spec file lock, a `.complete` marker, and a `bin/python` health check. Venvs inherit the base environment through a managed `.pth` file rather than `--system-site-packages`.

## Mode Comparison

| | Local mode | Ray mode |
|---|---|---|
| Enabling switch | `local_op_isolation` (default `true`) | `min_common_dep_num_to_combine >= 0` |
| Main-env resolution | Installed-set satisfiability; conflicts/missing isolated | Not applied |
| Isolation unit | Dedicated `venv` + subprocess per group | `runtime_env` per group |
| Grouping logic | `OPEnvManager` (shared) | `OPEnvManager` (shared) |
| Operators with no isolation | Run normally in the main process | Get an (effectively empty) `runtime_env` |
| Consecutive same-group operators | Merged into one subprocess call (leader/follower) | Each still a separate Ray task |
| Operator instantiation | Deferred to subprocess for isolated ops | Eagerly instantiated at load time |
| Caching | `<cache-dir>/<python-cache-tag>/` keyed by spec hash | Ray internal runtime_env cache |
