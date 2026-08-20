# Quickstart

This guide walks you through a complete Data-Juicer workflow: run your first processing job, build a custom recipe, analyze your dataset, and tune filter thresholds interactively. You will have clean, filtered output data in under five minutes.

> **Note:** Some operators download model weights on first use (for example, `language_id_score_filter` downloads a fastText language identification model). The initial run may take a few extra minutes while these assets are fetched. Subsequent runs use the local cache and start immediately.

## Prerequisites

- Data-Juicer installed — see [Installation](Installation.md).
- A Python environment with the extras needed for the operators in your recipe.

---

## 1. Run your first processing job

Data-Juicer processes datasets according to a **recipe** — a YAML config file that specifies the input dataset, the output path, and the operators to apply.

Start with the built-in demo recipe [`demos/process_simple/process.yaml`](https://github.com/datajuicer/data-juicer/blob/main/demos/process_simple/process.yaml), which keeps only Chinese samples with high language confidence:

```yaml
# global parameters
project_name: 'demo-process'
dataset_path: './demos/data/demo-dataset.jsonl'
np: 4

export_path: './outputs/demo-process/demo-processed.jsonl'

# operators to apply
process:
  - language_id_score_filter:
      lang: 'zh'
      min_score: 0.8
```

Run `dj-process` or `process_data.py` with the config file path as argument to process the dataset:

```shell
# command line tool
dj-process --config demos/process_simple/process.yaml

# from source only
python tools/process_data.py --config demos/process_simple/process.yaml
```

This will produce the following output in the work directory (`export_path`):

```
outputs/demo-process/
├── demo-processed.jsonl    # the processed dataset
├── *.yaml                  # a backup of the full parsed config
└── logs/                   # run logs
```

That's it — you have processed your first dataset.

> **Note:** Operators that use third-party models or resources not saved locally may be slow on first run, because they need to download the corresponding resources to the cache directory. The default cache directory is `~/.cache/data_juicer`. You can change the cache directory location by setting the shell environment variable `DATA_JUICER_CACHE_HOME`. You can also change `DATA_JUICER_MODELS_CACHE` or `DATA_JUICER_ASSETS_CACHE` in the same way to modify the model cache or asset cache directories respectively:
>
> ```shell
> export DATA_JUICER_CACHE_HOME="/path/to/another/directory"
> export DATA_JUICER_MODELS_CACHE="/path/to/another/directory/models"
> export DATA_JUICER_ASSETS_CACHE="/path/to/another/directory/assets"
> ```

> **Note:** For operators that use third-party models, you need to declare the corresponding `memory` in the config file (refer to the settings in [`config_all.yaml`](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/config/config_all.yaml)). Data-Juicer will control the number of processes based on memory availability and the memory required by the operator's model, to achieve better data processing performance. When running in a CUDA environment, incorrect `memory` declarations may lead to CUDA Out of Memory errors.

---

## 2. Build your own recipe

A config file contains a series of global parameters and an operator list for data processing. You need to set:

- **Global arguments**: input/output dataset paths, number of worker processes, etc.
- **Operator list**: the operators and their arguments for processing the dataset.

You can build your own config file in the following ways:

| Approach | How |
| --- | --- |
| **➖ Subtract** | Modify the sample config file [`config_all.yaml`](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/config/config_all.yaml). This file includes **all** operators with their default parameters. You only need to **remove** operators you don't need and adjust parameters as needed. |
| **➕ Add** | Build your own config file from scratch. You can refer to [`config_all.yaml`](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/config/config_all.yaml), the [Operator Zoo](../Operators.md), and the [Developer Guide](../DeveloperGuide.md#2-build-your-own-data-recipes-and-configs). |

In addition to using yaml files, you can also specify one or more parameters on the command line, which will override values in the yaml file:

```shell
dj-process --config demos/process_simple/process.yaml --language_id_score_filter.lang=en
```

> **Tip:** The basic config format and definition is shown below:
>
> ![Basic config example of format and definition](https://img.alicdn.com/imgextra/i1/O1CN01uXgjgj1khWKOigYww_!!6000000004715-0-tps-1745-871.jpg "Basic config file example")

---

## 3. Configure your input dataset

Data-Juicer supports various dataset input types, including local files, remote datasets (e.g., Hugging Face); it also supports data validation and data mixture.

Two methods for configuring input files:

- **Simple scenario** — single path for a local or HF file:

```yaml
dataset_path: '/path/to/your/dataset'   # path to the dataset directory or file
```

- **Advanced method** — sub-configuration items with more features:

```yaml
dataset:
  configs:
    - type: 'local'
      path: 'path/to/your/dataset'   # path to the dataset directory or file
```

For more details, see the [Dataset Configuration Guide](../DatasetCfg.md).

---

## 4. Analyze your dataset

Before deciding on filter thresholds, it is usually helpful to look at the statistical profile of your dataset. The analyzer computes distributions and correlations for all stats produced by your operators.

```shell
# command line tool
dj-analyze --config demos/analyze_simple/analyzer.yaml

# from source only
python tools/analyze_data.py --config demos/analyze_simple/analyzer.yaml

# You can also use "auto" mode to avoid writing a new data recipe. It will use all
# stat-producing Filters to analyze a small portion of your dataset (e.g., 1000 samples,
# configurable via the `auto_num` parameter)
dj-analyze --auto --dataset_path xx.jsonl [--auto_num 1000]
```

> **Note:** The Analyzer only works with Filter operators that produce statistics in the stats field, and other operators that produce tags or category labels in the meta field. All other operators are ignored during analysis. We use the following two registries to decorate the relevant operators:
> - `NON_STATS_FILTERS`: decorates Filter operators that **cannot** produce any statistics.
> - `TAGGING_OPS`: decorates operators that produce tags or category labels in the meta field.

> **Tip:** Sometimes "Glyph missing" warnings are produced and some garbled characters appear in the analysis result figures. You can use the environment variable `ANALYZER_FONT` to specify an appropriate font. For example:
>
> ```shell
> export ANALYZER_FONT="Heiti TC"  # use Heiti to support CJK characters; this is the Analyzer default
> ```

**Distributed analysis with Ray:** `dj-analyze` also supports Ray mode for large-scale distributed data analysis. Set `executor_type: ray` in your config, and the analyzer will automatically use `RayAnalyzer`, which computes overall statistics (count/mean/std/min/max) via Ray native aggregation operators without pandas materialization. Note that RayAnalyzer does not produce per-column distribution charts or correlation analysis. See [Distributed Processing](../Distributed.md) for more details.

```shell
dj-analyze --config demos/analyze_simple/ray_analyzer.yaml
```

---

## 5. Interactive visualization and recipe tuning (Web Playground)

Run `app.py` in the project root directory to visualize your dataset in the browser.

> **Note:** Only available for installation from source.

```shell
# run in the project root directory
streamlit run app.py
```

Typical workflow:

1. **Parse Cfg** — point it at a recipe (a demo example is pre-filled), upload your own YAML, or override arguments. The playground shows the parsed config and raw YAML side by side.
2. **Analyze original data** — runs the [Analyzer](#4-analyze-your-dataset) and displays overall stats with per-stat distribution charts.
3. **Process data** — runs the full recipe and shows original vs. processed stats side by side.
4. **Tune Filter OPs** — drag sliders to adjust each filter's threshold. The page instantly reports the **discard ratio**, draws the stat histogram with your cutoff marked, and lists **retained vs. discarded samples**. You can also view a stacked bar of each filter's effect, inspect lexical diversity, and **download retained/discarded splits as JSONL**.

Once you are happy with the thresholds, copy them back into your recipe YAML. This analyze → process → tune → export loop is the core of building a good data recipe.

---

## 6. Use Data-Juicer in Python

Besides the CLI tools, Data-Juicer provides simple programming interfaces:

```python
# ... init op & dataset ...

# Chain-call style — single operator or operator list
dataset = dataset.process(op)
dataset = dataset.process([op1, op2])

# Functional style — for quick integration or script prototyping
dataset = op(dataset)
dataset = op.run(dataset)
```

---

## 7. Scale out: distributed processing

Data-Juicer supports multi-machine distributed processing via [Ray](https://www.ray.io/):

```shell
# text data
python tools/process_data.py --config ./demos/process_on_ray/configs/demo.yaml

# video data
python tools/process_data.py --config ./demos/process_video_on_ray/configs/demo.yaml
```

- To use RAY for multi-machine data processing, you need to ensure all nodes can access the corresponding data paths, i.e., mount the data paths on a shared file system (such as NAS).
- Deduplication operators in RAY mode differ from the single-machine versions. All RAY-mode deduplication operators are prefixed with `ray`, e.g., `ray_video_deduplicator` and `ray_document_deduplicator`.
- See [Distributed Processing](../Distributed.md) for more details.

> **Note:** You can also skip Ray and split the dataset to run on a cluster with [Slurm](https://slurm.schedmd.com/). In this case, use the default Data-Juicer without Ray. [Aliyun PAI-DLC](https://www.aliyun.com/activity/bigdata/pai-dlc) supports both Ray and Slurm frameworks.

---

## 8. Sandbox (optional)

The data sandbox laboratory (DJ-Sandbox) provides best practices for continuously producing data recipes, with low overhead, portability, and guidance.

- Experiment, iterate, and refine recipes on small-scale datasets before scaling up.
- In addition to basic data optimization and recipe refinement, the sandbox offers configurable components: data probe and analysis, model training and evaluation, and data/model feedback-based recipe refinement — forming a complete data-model R&D pipeline.

For more details, see the [sandbox documentation](https://datajuicer.github.io/data-juicer-sandbox/en/main/index.html).

---

## 9. Preprocess raw data (optional)

Data-Juicer's formatters support common input formats out of the box:

| Format | Samples per file |
| --- | --- |
| jsonl/json, parquet, csv/tsv | Multiple |
| txt, code, docx, pdf | Single |

However, real-world data from different sources can be complex:

- [Raw arXiv data from S3](https://info.arxiv.org/help/bulk_data_s3.html) includes thousands of tar/gzip files with embedded tex files that are hard to access directly.
- Crawled data may contain mixed file types (pdf, html, docx) with tables and charts that are hard to extract.

We provide **common preprocessing tools** in [`tools/preprocess`](../../tools/preprocess/README.md) to handle these cases. Contributions for new data types are welcome. We **highly recommend** preprocessing complex data to jsonl or parquet before feeding it to Data-Juicer.

---

## 10. For Docker users

If you build or pull the `data-juicer` Docker image, you can use it to run all the commands and tools mentioned above.

**Run directly:**

```shell
docker run --rm \
  --privileged \
  --shm-size 256g \
  --network host \
  --gpus all \
  --name dj \
  -v <host_data_path>:<image_data_path> \
  -v ~/.cache/:/root/.cache/ \
  datajuicer/data-juicer:<version_tag> \
  dj-process --config /path/to/config.yaml
```

**Or you can enter a running container and run commands in editable mode:**

```shell
# start the container
docker run -dit \
  --privileged \
  --shm-size 256g \
  --network host \
  --gpus all \
  --rm \
  --name dj \
  -v <host_data_path>:<image_data_path> \
  -v ~/.cache/:/root/.cache/ \
  datajuicer/data-juicer:latest /bin/bash

# enter the container, then you can use data-juicer in editable mode
docker exec -it <container_id> bash
```

---

## What's next

- Browse 200+ operators in the [Operator Zoo](../Operators.md) and configure inputs with the [Dataset Configuration Guide](../DatasetCfg.md).
- Understand the mental model: [Recipes](concepts/recipes.md), [Operators](concepts/operators.md), [Executor](concepts/executor.md).
- Control output with the [Export Guide](../Export.md), speed up re-runs with [Cache Management](../Cache.md), and debug sample-level changes with [Data Tracing](../Tracing.md).
- Scale to clusters with [Distributed Processing](../Distributed.md) and [Partitioning & Checkpointing](../PartitionAndCheckpoint.md).
- Build your own operators with the [Developer Guide](../DeveloperGuide.md), or reuse community recipes from the [DJ-Cookbook](DJ-Cookbook.md).
