# Recipes

A **recipe** is a YAML configuration file that fully describes a data processing pipeline. It is the single source of truth for what operators to run, in what order, and with what parameters.

Recipes are interchangeable across executors — the same recipe runs on your laptop with the default executor or on a Ray cluster, with zero changes. You version them, share them, and reproduce results months later by pointing at the same file.

## Minimal example

```yaml
# global arguments
dataset_path: './demos/data/demo-dataset.jsonl'
export_path: './outputs/demo-process/demo-processed.jsonl'
np: 4

# the process list: an ordered list of operators
process:
  - language_id_score_filter:
      lang: 'zh'
      min_score: 0.8
```

This recipe loads `demo-dataset.jsonl`, keeps only samples whose Chinese language score is at least 0.8, and writes the result to `demo-processed.jsonl` using 4 worker processes.

## Global arguments

These settings control the pipeline as a whole, not any single operator:

| Argument | Description |
| --- | --- |
| `dataset_path` | Path to the input dataset (JSONL, Parquet, CSV, TSV, or text). |
| `export_path` | Path where processed data will be written. |
| `np` | Number of parallel worker processes. |
| `executor_type` | Which executor to use: `default`, `ray`, or `ray_partitioned`. See [Executor](executor.md). |
| `op_fusion` | Enable operator fusion for the default executor (`true` / `false`). |

For the full list of global arguments and their defaults, see the [configuration reference](https://datajuicer.github.io/data-juicer-hub/en/main/docs/RecipeGallery.html).

## The `process` list

The `process` key holds an ordered list of operators. Each entry is an operator name followed by its parameters. Operators execute top-to-bottom; each one receives the output of the previous step.

```yaml
process:
  # Step 1: keep only Chinese text
  - language_id_score_filter:
      lang: 'zh'
      min_score: 0.8

  # Step 2: filter by text length
  - text_length_filter:
      min_len: 10
      max_len: 50000

  # Step 3: clean HTML tags
  - clean_html_mapper: {}

  # Step 4: remove near-duplicates
  - document_minhash_deduplicator:
      tokenization: 'space'
      window_size: 5
```

> **Tip:** Operator order matters. Put cheap filters (text length, language ID) before expensive ones (model-based scoring) to reduce the number of samples that reach costly operators.

## Running a recipe

```bash
dj-process --config my_recipe.yaml
```

That is the entire command. Data-Juicer reads the recipe, resolves operator dependencies, installs any missing packages if needed, and runs the pipeline.

## Where to go next

- [Operators](operators.md) — understand the operator types you can use in a recipe.
- [Executor](executor.md) — choose how to run your recipe (local or distributed).
- [Dataset Configuration](../DatasetCfg.md) — configure input data formats and paths.
- [Operator Zoo](../Operators.md) — browse every available operator with parameters and examples.
- [Recipe Gallery](https://datajuicer.github.io/data-juicer-hub/en/main/docs/RecipeGallery.html) — real-world recipes contributed by the community.
