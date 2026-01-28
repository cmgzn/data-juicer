# Tracing

## Overview

Data-Juicer provides a **Tracer** feature that allows you to track and visualize changes made to datasets during the data processing pipeline. This is particularly useful for debugging, understanding the effects of different operators, and ensuring data quality.

When enabled, the tracer records sample-level changes before and after each operator processes them, helping you understand:
- What text modifications the Mapper operators made
- Which samples the Filter operators filtered out
- Which duplicate sample pairs the Deduplicator operator detected
- The overall impact of Data-Juicer on your data

> **Operator Support Note**: The tracer currently supports Mapper, Filter, and Deduplicator operators. Tracing is not yet supported for Selector, Grouper, Aggregator, and Pipeline type operators.

## Quick Start

### Quick Enable via Command Line

If you already have a configuration file, using command-line parameters is the fastest way to enable tracing without modifying the YAML file:

```shell
# Enable tracer with default settings
dj-process --config your_config.yaml --open_tracer true
```

### Enable in Configuration File

You can also configure the tracer directly in your YAML configuration file:

```yaml
# Basic tracer configuration
project_name: 'demo-with-tracer'
dataset_path: './data/demo-dataset.jsonl'
export_path: './outputs/demo-processed.jsonl'

open_tracer: true  # Enable tracer

process:
  - chinese_convert_mapper:
      mode: 's2t'
  - text_length_filter:
      min_len: 2
      max_len: 50
  - language_id_score_filter:
      lang: 'en'
```

Run processing:

```shell
dj-process --config your_config.yaml
```

## Configuration Parameters

The tracer can be configured through the following parameters in YAML configuration files or command-line arguments:

| Parameter          | Type | Default | Description                                                                                                                                                                                                                                                                 |
| ------------------ | ---- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `open_tracer`      | bool | `false` | Whether to enable the tracer to track changes during processing. Enabling the tracer adds some processing overhead.                                                                                                                                                        |
| `op_list_to_trace` | list | `[]`    | List of operator names to trace. If empty, all operators are traced. Only available when the tracer is enabled.                                                                                                                                                            |
| `trace_num`        | int  | `10`    | Maximum number of samples recorded per operator. After reaching this number, the operator stops collecting tracing information. Only available when the tracer is enabled.                                                                                                    |
| `trace_keys`       | list | `[]`    | List of sample field names to include in Mapper tracing output (e.g., `['meta', 'source_file']`). These fields will be extracted from the original sample and included in the tracing output to help identify modified samples. For Filter operators, complete samples are automatically saved without this parameter. For Deduplicator operators, complete duplicate pairs are saved without this parameter. Only available when the tracer is enabled. |

## How It Works

### Mapper Operators

When a Mapper operator modifies samples, the tracer records:
- The original text before processing
- The processed text after processing
- Values of fields specified in `trace_keys` from the original sample (for sample identification)

By default, only modified fields are recorded. To include additional fields for sample identification, use the `trace_keys` parameter (see [Advanced Usage Examples](#including-specified-fields-in-mapper-tracing)).

For example, with the `chinese_convert_mapper` operator, the trace file (`sample_trace-chinese_convert_mapper.jsonl`) contains modified samples:

```json
{"original_text":"你好，请问你是谁","processed_text":"你好，請問你是誰"}
{"original_text":"欢迎来到阿里巴巴！","processed_text":"歡迎來到阿里巴巴！"}
```

### Filter Operators

When a Filter operator filters out samples, the tracer records:
- Complete filtered samples (including all fields and statistical information)

The tracing output includes a `__dj__stats__` field that records statistical metric values for the sample (such as text length, proportion of special characters, etc.), facilitating analysis of why the sample was filtered.

For example, with the `text_length_filter` operator, the trace file (`sample_trace-text_length_filter.jsonl`) shows complete filtered samples:

```json
{"text":"Sur la plateforme MT4, plusieurs manières d'accéder à ces fonctionnalités sont conçues simultanément.","meta":{"src":"Oscar","date":null,"version":"2.0","author":null},"__dj__stats__":{"text_len":101}}
{"text":"This paper proposed a novel method on LLM pretraining.","meta":{"src":"customized","date":null,"version":null,"author":"xxx"},"__dj__stats__":{"text_len":54}}
```

### Deduplicator Operators

When a Deduplicator operator detects duplicate samples, the tracer records:
- Duplicate sample pairs (`dup1` and `dup2`), including complete sample information and `__dj__hash` hash values
- The number of recorded sample pairs is controlled by `trace_num`

This helps you understand which samples are considered duplicates and validate the deduplication logic. The hash value field shows the specific characteristic values used to determine duplicates.

> **Important Limitation**: Deduplicator tracing is only available in the default (non-Ray) execution mode. In Ray distributed mode, the Deduplicator does not support tracing.

For example, with the `document_deduplicator` operator, the trace file (`duplicate-document_deduplicator.jsonl`) shows duplicate sample pairs:

```json
{"dup1":{"text":"This is a repeated sample text.","meta":{"src":"customized","date":null,"version":"0.1","author":"xxx"},"__dj__hash":"db2ac18521d0adb4b0b89259612ff1d7"},"dup2":{"text":"This is a repeated sample text.","meta":{"src":"customized","date":null,"version":"0.1","author":"xxx"},"__dj__hash":"db2ac18521d0adb4b0b89259612ff1d7"}}
```

## Output Results

Tracing results are stored in a `trace/` subdirectory under the output directory. Each operator generates a separate JSONL file:
- Mapper and Filter operators: `sample_trace-{operator_name}.jsonl`
- Deduplicator operators: `duplicate-{operator_name}.jsonl`

For example:
```
outputs_dir/
└── trace/
    ├── sample_trace-chinese_convert_mapper.jsonl
    ├── sample_trace-text_length_filter.jsonl
    └── duplicate-document_simhash_deduplicator.jsonl
```

Each trace file contains up to `trace_num` samples, displaying changes made by that specific operator in JSONL format.

> **Note**: Existing files in the `trace/` directory are automatically cleared when starting a processing task to avoid confusion with results from previous runs.

## Advanced Usage Examples

### Tracing Specific Operators

If you only want to trace specific operators, use the `op_list_to_trace` parameter:

```yaml
project_name: 'demo-selective-trace'
dataset_path: './data/demo-dataset.jsonl'
export_path: './outputs/demo-processed.jsonl'

open_tracer: true
op_list_to_trace:
  - chinese_convert_mapper
  - text_length_filter

process:
  - chinese_convert_mapper:
      mode: 's2t'
  - text_length_filter:
      min_len: 2
      max_len: 50
  - language_id_score_filter:
      lang: 'en'
```

In this example, only `chinese_convert_mapper` and `text_length_filter` generate trace files, while `language_id_score_filter` is not traced.

### Including Specified Fields in Mapper Tracing

Use `trace_keys` to include specified fields in Mapper tracing output for better sample localization:

```yaml
project_name: 'demo-trace-with-keys'
dataset_path: './data/demo-dataset.jsonl'
export_path: './outputs/demo-processed.jsonl'

open_tracer: true
trace_num: 20  # Record at most 20 samples per operator
trace_keys:
  - meta

process:
  - chinese_convert_mapper:
      mode: 's2t'
  - text_length_filter:
      min_len: 2
      max_len: 50
  - language_id_score_filter:
      lang: 'en'
```

For Mapper operators, the tracing output will include the values of specified fields at the beginning of each entry (extracted from the original sample), making it easy to identify which sample was modified:

```json
{"meta":{"src":"customized","date":null,"version":null,"author":"xxx"},"original_text":"你好，请问你是谁","processed_text":"你好，請問你是誰"}
```

For Filter and Deduplicator operators, complete samples are automatically saved and are not affected by the `trace_keys` configuration.

### Increasing the Number of Traced Samples

By default, each operator records changes for only 10 samples. To view more samples, adjust `trace_num`:

```yaml
project_name: 'demo-large-trace'
dataset_path: './data/demo-dataset.jsonl'
export_path: './outputs/demo-processed.jsonl'

open_tracer: true
trace_num: 100  # Record at most 100 samples per operator

process:
  - chinese_convert_mapper:
      mode: 's2t'
  - text_length_filter:
      min_len: 2
      max_len: 50
```

## Performance Considerations

- **Processing Time**: Enabling the tracer adds some overhead to the processing pipeline. For large-scale production runs, consider disabling it or limiting the operators to trace.
- **Storage Space**: Each operator generates a separate trace file. Total storage usage depends on `trace_num` and sample size.
- **Memory**: The tracer uses efficient sample-level collection, storing at most `trace_num` samples per operator.

## Best Practices

1. **Development and Debugging**: Enable the tracer during development to understand how operators affect your data.
2. **Selective Tracing**: Use `op_list_to_trace` to focus on specific operators of interest.
3. **Sample Identification**: Use `trace_keys` to include fields that help identify samples (e.g., IDs, source files).
4. **Production Runs**: Disable the tracer during production runs to maximize performance.

## Related Features

- [Operator List](Operators.md): Learn about the available operators in Data-Juicer.
- [Developer Guide](DeveloperGuide.md): Learn how to develop custom operators.