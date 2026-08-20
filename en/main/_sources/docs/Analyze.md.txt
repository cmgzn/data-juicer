# Data Analysis

Before committing to filter thresholds, it helps to understand the statistical profile of your dataset. `dj-analyze` computes distributions and correlations for all statistics produced by operators, enabling data-driven threshold decisions.

---

## Basic usage

Run the analyzer against an existing recipe:

```bash
dj-analyze --config path/to/your-recipe.yaml
```

Or use **auto mode**—no dedicated analysis recipe needed. It runs all statistics-producing Filters on a subset of your dataset:

```bash
dj-analyze --auto --dataset_path your-dataset.jsonl [--auto_num 1000]
```

- `--auto_num`: number of samples to analyze (default 1000). Good for a quick profile.

---

## Analysis output

The analyzer produces:

- **Summary table**: count, mean, std, min, max for each statistic
- **Distribution plots**: histogram for each statistic
- **Correlation analysis**: heatmap of inter-statistic correlations

Output is saved to the directory containing `export_path` by default.

---

## Which operators participate

The analyzer processes two kinds of operators:
- **Filter operators** that produce statistics in the `stats` field (most Filters do)
- **Other operators** that produce tags or category labels in the `meta` field

Exception markers:
- `NON_STATS_FILTERS`: decorates Filters that do **not** produce statistics
- `TAGGING_OPS`: decorates operators that produce tags in meta

---

## Distributed analysis

`dj-analyze` supports Ray mode for large-scale distributed profiling. Set in your config:

```yaml
executor_type: ray
```

The analyzer uses `RayAnalyzer`, computing aggregate statistics (count/mean/std/min/max) via Ray-native aggregations without pandas materialization.

> **Note:** RayAnalyzer does not produce per-column distribution plots or correlation analysis. See [Distributed Processing](Distributed.md) for Ray details.

```bash
dj-analyze --config demos/analyze_simple/ray_analyzer.yaml
```

---

## Font configuration

If you see "Glyph missing" warnings or garbled characters in plots, set the font via environment variable:

```bash
export ANALYZER_FONT="Heiti TC"  # default; supports CJK characters
```

---

## Next steps

- Tune thresholds interactively? Use [Web Playground](Playground.md)
- Ready to run the full pipeline? See [Quickstart §4](tutorial/QuickStart.md#4-run-the-pipeline)
- Processing at scale? See [Distributed Processing](Distributed.md)
