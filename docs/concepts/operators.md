# Operators

An **operator** is a single, composable processing step. Data-Juicer ships 200+ production-tested operators for text, image, audio, video, and multimodal data. You select operators, set their parameters, and chain them together in your recipe's `process` list.

## Operator types

Every operator belongs to one of eight types, grouped by what it does to the data:

| Type | What it does | Example |
| --- | --- | --- |
| **formatter** | Discovers, loads, and canonicalizes source data into the DJ format. | `json_formatter`, `parquet_formatter` |
| **mapper** | Edits and transforms individual samples. | `clean_html_mapper`, `fix_unicode_mapper` |
| **filter** | Computes per-sample stats and keeps or drops samples by threshold. | `language_id_score_filter`, `text_length_filter` |
| **deduplicator** | Detects and removes duplicate samples. | `document_minhash_deduplicator` |
| **selector** | Selects a subset of top samples based on ranking. | `topk_specified_field_selector` |
| **grouper** | Groups samples into batched samples. | `naive_grouper` |
| **aggregator** | Aggregates a batch of samples into a summary or conclusion. | `simple_aggregator` |
| **pipeline** | Applies dataset-level processing; both input and output are full datasets. | `dataset_process_pipeline` |

The most common workflow uses **mapper**, **filter**, and **deduplicator** in sequence. The other types handle specialized scenarios.

## Composing operators

Operators compose like building blocks. Each operator's output feeds into the next one's input:

```yaml
process:
  - language_id_score_filter:    # Step 1: keep Chinese text
      lang: 'zh'
      min_score: 0.8
  - text_length_filter:          # Step 2: filter by length
      min_len: 10
      max_len: 50000
  - clean_html_mapper: {}        # Step 3: strip HTML
```

> **Tip:** Order matters. Put cheap, high-impact filters first (language ID, text length) to reduce the sample count before reaching expensive model-based operators.

## Capability tags

Every operator in the [Operator Zoo](../Operators.md) carries tags that tell you at a glance what it needs and how mature it is:

| Tag | Values | Meaning |
| --- | --- | --- |
| **Modality** | Text, Image, Audio, Video, Multimodal | The data type the operator processes. |
| **Resource** | CPU, GPU | Whether the operator needs a GPU or runs on CPU alone. |
| **Usability** | Alpha, Beta, Stable | Alpha = basic implementation; Beta = tested; Stable = DJ-optimized. |
| **Model** | API, vLLM, HuggingFace | Whether the operator downloads or calls an external model. |

Use these tags to filter the Operator Zoo when searching for the right operator for your data.

## Stats and metadata

While processing, operators attach intermediate fields to each sample:

- **Stats** (`__dj__stats__`): numeric measures computed by filters — text length, language score, perplexity, and so on. Filters decide what to keep by comparing stats against your thresholds.
- **Meta** (`__dj__meta__`): labels and categories produced by tagging operators — language label, detected entities, etc.

These fields power two other features:

1. The [Analyzer](../tutorial/QuickStart.md#4-analyze-your-dataset) reads stats to produce the distribution and correlation profile of your dataset — this is how you pick good filter thresholds.
2. By default, stats and meta fields are stripped from the final output. To keep them, set `keep_stats_in_res_ds: true` or `keep_hashes_in_res_ds: true` in your recipe. See the [Export Guide](../Export.md).

## Where to go next

- [Operator Zoo](../Operators.md) — browse every operator with full parameter lists and examples.
- [Recipes](recipes.md) — learn how to chain operators in a YAML recipe.
- [Dataset Configuration](../DatasetCfg.md) — configure input data for your operators.
- [Developer Guide](../DeveloperGuide.md) — build your own custom operator.
