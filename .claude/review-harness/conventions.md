# Data-Juicer Architectural Conventions & Experience Library

This document captures lessons learned from maintaining the data-juicer project.
It is read by the review harness to inform judgment on PRs. Each convention
includes context on WHY it exists, so the reviewer can exercise flexible judgment
on edge cases rather than blindly enforcing rigid rules.

---

## Convention 1: Dependency Import Discipline

**What:** Any import of a package NOT listed in `pyproject.toml` core dependencies
must use `LazyLoader` (from `data_juicer.utils.lazy_loader`) rather than a
top-level `import` or `from X import Y` statement.

**Why:** data-juicer is designed for lightweight installation. A user who runs
`pip install py-data-juicer` (without extras like `[vision]` or `[audio]`) should
be able to `import data_juicer` and use text-only operators without crashing.
In v1.5.3, the HumanVBench PR introduced `from scipy.interpolate import interp1d`
at module top-level — scipy was not a declared dependency, so a clean install would
crash with `ModuleNotFoundError` on any `import data_juicer` call. This took 4 days
and 6 fix commits to fully resolve.

**Flexibility:**
- Packages in core dependencies (numpy, datasets, jsonargparse, loguru, etc.) can
  be imported normally at top level.
- Imports inside method bodies are acceptable for infrequently-called code paths,
  but LazyLoader at module level is preferred for consistency.
- Test files (`tests/`) are exempt from this convention.

**How to check:** For each new/modified `.py` file under `data_juicer/ops/`,
compare top-level imports against the core dependency list in `pyproject.toml`.
Flag any import of a package only listed under optional extras (vision, audio,
sandbox, etc.) or not listed at all.

**Severity:** Blocker — causes hard crash on import.

---

## Convention 2: Dependency Declaration Completeness

**What:** Every third-party package actually imported (even via LazyLoader) must be
declared in `pyproject.toml` under the appropriate optional group (`[vision]`,
`[audio]`, `[sandbox]`, `[tools]`).

**Why:** The HumanVBench PR used `deepface`, `tf-keras`, `imageio`, `funasr`, and
`modelscope` without declaring any of them. Users who installed
`pip install py-data-juicer[vision]` still got `ModuleNotFoundError` at runtime.

**Flexibility:**
- Packages vendored in `thirdparty/` directory don't need pyproject declaration.
- If a package is only used in a demo or script (not in `data_juicer/`), it
  does not need declaration but should be documented in the demo's README.

**How to check:** Extract all import targets from new/modified op files, cross-reference
against `pyproject.toml` dependency groups.

**Severity:** Blocker — runtime crash for users who installed the correct extras.

---

## Convention 3: Dependency Version Compatibility

**What:** When adding or bumping a dependency version, check for transitive conflicts
with existing pinned packages — particularly in the protobuf/wandb/transformers/
tensorflow ecosystem.

**Why:** Adding `tf-keras==2.21.0` (needed by deepface) pulled TensorFlow 2.21 which
requires `protobuf>=6.31`, but the existing `wandb<=0.19.0` pin forced `protobuf<6`.
This created an unsolvable pip resolution. Three attempts (pin protobuf low → revert
→ bump wandb) were needed. Similarly, adding `modelscope` caused it to monkey-patch
`transformers.from_pretrained`, making unrelated operators download 14GB models.

**Flexibility:**
- If the new dependency has no known conflicts, this is informational only.
- If the PR touches pyproject.toml dependency specs, it warrants closer examination.

**How to check:** Look for version pins or bounds in pyproject.toml changes. Flag
known conflict-prone packages: protobuf, wandb, transformers, modelscope, tf-keras,
tensorflow, torch, numpy.

**Severity:** Blocker if conflict is provable; Warning otherwise.

---

## Convention 4: get_init_configs Internal Attribute Hygiene

**What:** Any new attribute set on the config Namespace during runtime (not parsed
from CLI/YAML by jsonargparse) must be added to the `internal_attrs` list in
`get_init_configs()` (in `data_juicer/config/config.py`, around line 1837).

**Why:** `get_init_configs()` serializes the config Namespace to a temp JSON file,
then re-parses it with jsonargparse. If runtime-only attributes (like
`_resume_requested`, `_same_yaml_config`) are left in the dict, jsonargparse raises
a validation error because these attributes are not registered in the parser schema.
This broke after PR #1022 when `_resume_requested` was added but not stripped.

**Flexibility:**
- Only applies to attributes set AFTER `init_configs()` returns (i.e., in
  `resolve_job_id()` or executor initialization code).
- Attributes added to the argument parser (via `parser.add_argument`) do NOT
  need to be in `internal_attrs` — they are already known to jsonargparse.

**How to check:** If the diff adds any `cfg.xxx = ...` or `setattr(cfg, ...)` in
config resolution code, verify `xxx` is either a parser argument or in `internal_attrs`.

**Severity:** Blocker — breaks any code path using `get_init_configs()`.

---

## Convention 5: Null and Edge-Case Data Handling

**What:** Operators must handle None/empty/missing fields gracefully, particularly
for `text`, `image_key`, `video_key`, and `Fields.meta` (`__dj__meta__`).

**Why:** Real-world datasets are dirty. Operators developed against "golden path"
test data silently assume all fields are populated. In production:
- `clean_html_mapper` crashed on null text values
- `image_diffusion_mapper` crashed on missing captions
- `vggt_mapper` accessed `__dj__meta__` before initialization
- `video_face_ratio_filter` returned wrong type for empty video lists, causing
  Arrow type-cast errors in downstream dataset operations

**Flexibility:**
- Not every operator needs to handle every conceivable null case — focus on the
  fields the operator actually accesses.
- For operators that legitimately require a field (e.g., a text filter needs text),
  a clear error message is acceptable; a silent crash or wrong-type return is not.

**How to check:** Examine the operator's `process_single`/`compute_stats_single` —
does it access sample fields without None checks? Do the tests include a case
with missing/empty fields?

**Severity:** Warning — may not manifest in testing but will crash in production.

---

## Convention 6: Path Resolution for Distributed Execution

**What:** Any file path used in operator logic should be resolved to an absolute
path during `__init__`, not left as relative. URL scheme detection must be
case-insensitive.

**Why:** When running under Ray, workers may have different working directories
than the driver process. Relative paths that work in single-node testing break
silently in distributed mode. Additionally, scheme detection was case-sensitive
(`S3://` vs `s3://`), causing HDFS/S3 paths to be treated as local paths.

**Flexibility:**
- Paths that are only used in the driver process (not serialized to workers)
  are fine as relative.
- Output paths configured by the user in YAML are typically resolved by the
  config system, not the operator.

**How to check:** If an operator uses file paths (model weights, output dirs,
reference files), check whether they're resolved in `__init__` or left relative.

**Severity:** Warning — only manifests in distributed mode.

---

## Convention 7: Mutable Class Attributes

**What:** Class-level attributes that are mutable containers (list, dict, set)
must not be used as instance state. Use instance attributes set in `__init__`.

**Why:** A class attribute like `extra_kwargs = {}` is shared across ALL instances.
If one operator instance mutates it (e.g., `self.extra_kwargs['key'] = value`),
all other instances see the mutation. This caused silent data corruption in
concurrent/fused execution scenarios.

**Flexibility:**
- Immutable class attributes (strings, ints, tuples, frozensets) are fine.
- Class attributes used as true class-level constants (never mutated) are fine.
- The existing pattern of `_batched_op = True` / `_accelerator = "cuda"` is
  correct because these are never mutated after class definition.

**How to check:** AST check for class-level assignments to `[]`, `{}`, `set()`,
or `defaultdict(...)` that are later accessed via `self.xxx` in methods.

**Severity:** Blocker — causes silent data corruption.

---

## Convention 8: Operator Naming Consistency

**What:** Operator names follow `{action}_{target}_{op_type}` pattern. The
registration name must exactly match the filename (minus `.py`). Parameters
should reuse established names where applicable.

**Why:** Consistency enables discoverability and reduces cognitive load. Users
configure operators in YAML by name — predictable naming means they can guess
operator names without checking documentation.

**Established parameter names to reuse:**
- `min_*` / `max_*` — range bounds (not `threshold`, `lower_bound`, etc.)
- `any_or_all` — strategy for multi-element samples
- `lang` — language code
- `hf_scorer_model` / `model_key` — HuggingFace model specification
- `pattern` / `repl` — regex pattern and replacement
- `text_key`, `image_key`, `video_key`, `audio_key` — field keys (inherited from base)

**Flexibility:**
- If an operator genuinely needs a parameter that has no existing analogue,
  a new name is fine — just ensure it's snake_case and self-explanatory.
- Legacy operators may not follow this perfectly; new ops should.

**How to check:** Compare new parameter names against existing ops in the same
category. Flag parameters that duplicate an existing concept under a different name.

**Severity:** Suggestion — does not break anything but harms API coherence.

---

## Convention 9: Filter Two-Phase Design

**What:** Filter operators MUST implement `compute_stats_single` (or `_batched`)
to store computed metrics in `sample[Fields.stats][StatsKeys.xxx]`, and
`process_single` to read from stats and return a boolean via
`self.get_keep_boolean()`.

**Why:** This separation enables:
1. OP fusion — multiple filters sharing intermediate computations
2. Analysis mode — computing stats without filtering
3. Caching — stats computed once, filtering threshold adjusted without recompute

A filter that computes and decides in one step breaks all three capabilities.

**Flexibility:**
- Complex filters that cannot meaningfully decompose (e.g., dedup-like filters)
  may deviate, but should document why.
- The metaclass enforces that you cannot override `process` directly, so this
  is partially enforced at the language level.

**How to check:** Verify new Filter subclasses implement both phases and store
stats under a proper StatsKeys entry.

**Severity:** Blocker — breaks OP fusion and analysis mode.

---

## Convention 10: Test Structure and Robustness

**What:** Every new operator must have a corresponding test file at
`tests/ops/{type}/test_{op_name}.py` inheriting `DataJuicerTestCaseBase`.
Tests should cover at minimum: normal case, edge case (empty/null input),
and boundary conditions.

**Why:** Tests that only cover the "golden path" give false confidence. Multiple
production bugs (v1.5.3–v1.5.5) were caused by null inputs, empty lists, or
boundary values that no test exercised.

**Additional test guidelines:**
- LLM-dependent tests must set `temperature=0.1` or lower to reduce flakiness
- Do not hardcode `/tmp` paths — use `tempfile.mkdtemp()` or test fixtures
- Do not depend on specific model names that may be deprecated
- Tests should be isolated — no state leakage between test methods

**Flexibility:**
- Operators that require expensive models or GPU can mark tests with
  `@unittest.skipUnless` — but the test file must still exist.
- Integration tests (Ray, multi-worker) are not required per-op.

**How to check:** Verify test file exists. Check test content for edge cases.

**Severity:** Blocker (missing test file) / Warning (insufficient coverage).

---

## Convention 11: OP Registration and __init__ Pattern

**What:** Every operator must:
1. Use `@OPERATORS.register_module('op_name')` decorator
2. Accept `*args, **kwargs` in `__init__` and forward to `super().__init__(*args, **kwargs)`
3. Have docstring starting with "Initialization method."
4. Use Sphinx `:param name:` style for parameter documentation
5. Store all parameters as `self.param = param` immediately after super().__init__

**Why:** The `*args, **kwargs` forwarding is essential because the base OP class
injects global parameters (text_key, image_key, etc.) via `update_op_attr()`.
Without forwarding, these injections silently fail and the operator uses wrong
field keys. The docstring format is consumed by the auto-documentation build
hook (`build-op-doc`) which generates operator reference documentation.

**Flexibility:**
- Operators that need to transform parameters before storing them may do
  processing between super().__init__ and self.xxx assignments.
- The "Initialization method." opener is a legacy convention — if someone writes
  a more descriptive first line, it's not a blocker, just a style note.

**How to check:** AST analysis of __init__ method signature and body.

**Severity:** Blocker (*args/**kwargs missing) / Suggestion (docstring style).
