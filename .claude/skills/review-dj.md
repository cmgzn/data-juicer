---
name: review-dj
description: >
  Review a PR or branch for data-juicer, checking mechanical conventions (Lens 1),
  regression risk (Lens 2), robustness (Lens 3), and interface quality (Lens 4).
  Outputs a structured report with prioritized findings.
trigger: /review-dj
arguments:
  - name: target
    description: "Branch name, PR number, or commit range to review (e.g., 'feat/xxx', '#1038', 'main...HEAD')"
    required: false
---

# Review-DJ: Data-Juicer PR Review Harness

You are acting as the review harness for the data-juicer project. Your role is to
systematically review code changes through four lenses, outputting a structured
report that helps the maintainer make merge decisions quickly.

## Step 0: Determine the diff target

If a target argument is provided, use it. Otherwise:
- If on a non-main branch, diff against `main` (or `origin/main`)
- Ask the user what to review

Obtain the diff:
```bash
git diff --stat <base>...<head>
git diff <base>...<head>
```

## Step 1: Run Lens 1 (Mechanical Convention Check)

Run the automated checker:
```bash
python .claude/review-harness/lens1_checks.py <base_ref>
```

Include its output verbatim in the report. If there are blockers, flag them prominently.

## Step 2: Lens 2 — Regression Risk Assessment

Read the conventions library at `.claude/review-harness/conventions.md`, particularly
conventions 3, 4, 5, 6 which are about regression risks.

Analyze the diff looking for:

1. **Core module modifications**: Does the diff touch any of these high-risk files?
   - `data_juicer/config/config.py`
   - `data_juicer/ops/base_op.py`
   - `data_juicer/core/` (any file)
   - `data_juicer/ops/load.py`
   - `data_juicer/ops/op_fusion.py`
   - `pyproject.toml` (dependency changes)

2. **Default value changes**: Does the diff modify any default parameter values
   in existing operators or config?

3. **Config parameter additions**: If new config parameters are added, check:
   - Are they runtime-internal (set programmatically)? → must be in `internal_attrs`
   - Or are they user-facing (parsed from YAML)? → must be in config_all.yaml

4. **Type changes in interfaces**: Does the diff change return types, parameter
   types, or stored data structures that downstream code depends on?

For each risk found, assess:
- What could break?
- What's the blast radius (one op? all filters? the whole pipeline?)
- Is there a test that would catch this?

## Step 3: Lens 3 — Robustness Analysis

For new/modified operators, check:

1. **Null/edge handling**: Does the operator handle:
   - `sample[key]` being None?
   - Empty lists for multi-modal fields (images=[], videos=[])?
   - Missing `__dj__meta__` field?

2. **Return type consistency**: Under all code paths (including early returns,
   exception handlers), does the operator return the expected type?
   - Mapper: always returns dict (sample)
   - Filter compute_stats: always returns sample with stats populated
   - Filter process: always returns bool
   - Inconsistent returns cause Arrow type errors in batch processing

3. **Test coverage**: Do the tests cover:
   - Normal case?
   - Empty/null input?
   - Boundary values for any thresholds?

4. **Path handling**: Are file paths resolved to absolute in __init__?

## Step 4: Lens 4 — Interface Quality

This lens requires pure judgment. Consider:

1. **Naming consistency**: Do new parameter names match established conventions?
   - `min_*/max_*` for ranges (not `threshold`, `lower_bound`)
   - `any_or_all` for multi-element strategy
   - `hf_scorer_model` for HF model spec
   - `lang` for language codes

2. **YAML config naturalness**: If you were a user writing a data processing
   config in YAML, would this operator's configuration feel intuitive?
   ```yaml
   process:
     - new_operator_name:
         param1: value1
         param2: value2
   ```
   Does this read naturally? Are parameter names self-explanatory?

3. **Unnecessary complexity**: Is there logic that duplicates what the base class
   already provides? (e.g., reimplementing `get_keep_boolean`, manual stats key
   management instead of using StatsKeys)

4. **API coherence**: Does this operator fit naturally alongside existing operators
   of the same type? Would a user familiar with similar operators immediately
   understand how to use this one?

## Output Format

Structure your report exactly as follows:

```markdown
## Review Report: <branch/PR description>

**Files changed:** <N> | **New ops:** <list> | **Modified core:** <yes/no>

---

### BLOCKERS (must fix before merge)
<numbered list, each with: [Lens N] file:line — description>

### WARNINGS (should fix, discuss if disagreed)
<numbered list, same format>

### SUGGESTIONS (nice-to-have, non-blocking)
<numbered list, same format>

### RISK SUMMARY
<1-2 sentence assessment: what could realistically break if merged as-is?>

---
Lens 1 raw output:
<paste the mechanical checker output>
```

## Important Guidelines

- **Be specific**: Always include file paths and line numbers.
- **Be calibrated**: Only mark as BLOCKER if it will actually cause breakage
  (import crash, test failure, data corruption). Design taste issues are SUGGESTIONS.
- **Reference conventions by ID**: When citing a convention, reference it
  (e.g., "Convention dep-001") so the maintainer can look up the full context.
- **State uncertainty**: If you're unsure whether something is a real issue,
  say so explicitly rather than presenting speculation as fact.
- **Consider the contributor**: Note any patterns that suggest the contributor
  may be unfamiliar with the project's conventions — this informs the tone
  of review feedback.
