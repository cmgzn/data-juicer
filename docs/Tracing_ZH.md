# 追踪

## 概览

Data-Juicer 提供了 **Tracer（追踪器）** 功能，允许你追踪和可视化数据处理流水线中对数据集所做的更改。这对于调试、理解不同算子的效果以及确保数据质量特别有用。

启用后，追踪器将记录每个算子处理前后的样本级别变化，帮助你了解：
- Mapper 算子对文本做了哪些修改
- Filter 算子过滤掉了哪些样本
- Deduplicator 算子检测到了哪些重复样本对
- Data-Juicer 对数据的整体影响

> **算子支持说明**：追踪器目前支持 Mapper、Filter 和 Deduplicator 算子。Selector、Grouper、Aggregator 和 Pipeline 类型的算子暂不支持追踪功能。

## 快速开始

### 命令行快速启用

如果你已经有一份配置文件，使用命令行参数是最快的启用方式，无需修改 YAML 文件：

```shell
# 使用默认设置启用追踪器
dj-process --config your_config.yaml --open_tracer true
```

### 在配置文件中启用

你也可以在 YAML 配置文件中直接配置追踪器：

```yaml
# 基本追踪器配置
project_name: 'demo-with-tracer'
dataset_path: './data/demo-dataset.jsonl'
export_path: './outputs/demo-processed.jsonl'

open_tracer: true  # 启用追踪器

process:
  - chinese_convert_mapper:
      mode: 's2t'
  - text_length_filter:
      min_len: 2
      max_len: 50
  - language_id_score_filter:
      lang: 'en'
```

运行处理：

```shell
dj-process --config your_config.yaml
```

## 配置参数

追踪器可以通过以下参数在 YAML 配置文件或命令行参数中进行配置：

| 参数               | 类型 | 默认值  | 说明                                                                                                                                                                                                                                                                                   |
| ------------------ | ---- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `open_tracer`      | bool | `false` | 是否启用追踪器来追踪处理过程中的变化。启用追踪器会增加一定的处理时间。                                                                                                                                                                                                                 |
| `op_list_to_trace` | list | `[]`    | 要追踪的算子名称列表。如果为空，则追踪所有算子。仅在追踪器启用时可用。                                                                                                                                                                                                                 |
| `trace_num`        | int  | `10`    | 每个算子记录的最大样本数量。达到此数量后，该算子将停止收集追踪信息。仅在追踪器启用时可用。                                                                                                                                                                                             |
| `trace_keys`       | list | `[]`    | 在 Mapper 追踪输出中包含的样本字段名列表（例如 `['meta', 'source_file']`）。这些字段将从原始样本中提取并包含在追踪输出中，便于识别被修改的样本。对于 Filter 算子，会自动保存完整样本，无需此参数。对于 Deduplicator 算子，会保存完整的重复样本对，也无需此参数。仅在追踪器启用时可用。 |

## 工作原理

### Mapper 算子

当 Mapper 算子修改样本时，追踪器会记录：
- 处理前的原始文本
- 处理后的文本
- `trace_keys` 中指定字段在原始样本中的值（用于识别样本）

默认只记录发生变化的字段，如需包含更多字段用于识别样本，请使用 `trace_keys` 参数（参见[高级用法示例](#在-mapper-追踪中包含指定字段)）。

以 `chinese_convert_mapper` 算子为例，追踪文件（`sample_trace-chinese_convert_mapper.jsonl`）包含被修改的样本：

```json
{"original_text":"你好，请问你是谁","processed_text":"你好，請問你是誰"}
{"original_text":"欢迎来到阿里巴巴！","processed_text":"歡迎來到阿里巴巴！"}
```

### Filter 算子

当 Filter 算子过滤样本时，追踪器会记录：
- 被过滤掉的完整样本（包含所有字段和统计信息）

追踪输出会包含 `__dj__stats__` 字段，其中记录了该样本的统计指标值（如文本长度、特殊字符占比等），便于分析样本被过滤的具体原因。

以 `text_length_filter` 算子为例，追踪文件（`sample_trace-text_length_filter.jsonl`）会显示被过滤的完整样本：

```json
{"text":"Sur la plateforme MT4, plusieurs manières d'accéder à ces fonctionnalités sont conçues simultanément.","meta":{"src":"Oscar","date":null,"version":"2.0","author":null},"__dj__stats__":{"text_len":101}}
{"text":"This paper proposed a novel method on LLM pretraining.","meta":{"src":"customized","date":null,"version":null,"author":"xxx"},"__dj__stats__":{"text_len":54}}
```

### Deduplicator 算子

当 Deduplicator 算子检测到重复样本时，追踪器会记录：
- 重复样本对（`dup1` 和 `dup2`），包含完整样本信息和 `__dj__hash` 哈希值
- 记录的样本对数量由 `trace_num` 控制

这有助于你了解哪些样本被认为是重复的，并验证去重逻辑。哈希值字段展示了用于判断重复的具体特征值。

> **重要限制**：Deduplicator 追踪仅在默认（非 Ray）执行模式下可用。在 Ray 分布式模式下，Deduplicator 不支持追踪功能。

以 `document_deduplicator` 算子为例，追踪文件（`duplicate-document_deduplicator.jsonl`）会显示重复样本对：

```json
{"dup1":{"text":"这是一段重复出现的示例文本。","meta":{"src":"customized","date":null,"version":"0.1","author":"xxx"},"__dj__hash":"18e72ba46f7e4ada6a9956df898488af"},"dup2":{"text":"这是一段重复出现的示例文本。","meta":{"src":"customized","date":null,"version":"0.1","author":"xxx"},"__dj__hash":"18e72ba46f7e4ada6a9956df898488af"}}
```

## 输出结果

追踪结果存储在输出目录下的 `trace/` 子目录中。每个算子生成一个单独的 JSONL 文件：
- Mapper 和 Filter 算子：`sample_trace-{算子名称}.jsonl`
- Deduplicator 算子：`duplicate-{算子名称}.jsonl`

例如：
```
outputs_dir/
└── trace/
    ├── sample_trace-chinese_convert_mapper.jsonl
    ├── sample_trace-text_length_filter.jsonl
    └── duplicate-document_simhash_deduplicator.jsonl
```

每个追踪文件包含最多 `trace_num` 个样本，以 JSONL 格式展示该特定算子所做的更改。

> **注意**：启动处理任务时，`trace/` 目录中的现有文件会被自动清除，以避免与上次运行的结果混淆。

## 高级用法示例

### 追踪特定算子

如果你只想追踪特定算子，使用 `op_list_to_trace` 参数：

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

在这个示例中，只有 `chinese_convert_mapper` 和 `text_length_filter` 会生成追踪文件，`language_id_score_filter` 不会被追踪。

### 在 Mapper 追踪中包含指定字段

使用 `trace_keys` 在 Mapper 追踪输出中包含指定字段，以便定位具体样本：

```yaml
project_name: 'demo-trace-with-keys'
dataset_path: './data/demo-dataset.jsonl'
export_path: './outputs/demo-processed.jsonl'

open_tracer: true
trace_num: 20  # 每个算子最多记录 20 个样本
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

对于 Mapper 算子，追踪输出将在每个条目的开头包含指定字段的值（从原始样本中提取），便于识别是哪个样本被修改：

```json
{"meta":{"src":"customized","date":null,"version":null,"author":"xxx"},"original_text":"你好，请问你是谁","processed_text":"你好，請問你是誰"}
```

而对于 Filter 和 Deduplicator 算子，会自动保存完整样本，不受 `trace_keys` 配置影响。

### 增加追踪样本数量

默认情况下，每个算子只记录 10 个样本的变化。如果需要查看更多样本，可以调整 `trace_num`：

```yaml
project_name: 'demo-large-trace'
dataset_path: './data/demo-dataset.jsonl'
export_path: './outputs/demo-processed.jsonl'

open_tracer: true
trace_num: 100  # 每个算子记录最多 100 个样本

process:
  - chinese_convert_mapper:
      mode: 's2t'
  - text_length_filter:
      min_len: 2
      max_len: 50
```

## 性能考虑

- **处理时间**：启用追踪器会给处理流水线增加一些开销。对于大规模生产运行，考虑禁用它或限制要追踪的算子。
- **存储空间**：每个算子生成一个单独的追踪文件。总存储使用量取决于 `trace_num` 和样本的大小。
- **内存**：追踪器使用高效的样本级别收集，每个算子只存储最多 `trace_num` 个样本。

## 最佳实践

1. **开发和调试**：在开发过程中启用追踪器，以了解算子如何影响数据。
2. **选择性追踪**：使用 `op_list_to_trace` 专注于感兴趣的特定算子。
3. **样本识别**：使用 `trace_keys` 包含有助于识别样本的字段（例如 ID、源文件）。
4. **生产运行**：在生产运行时禁用追踪器以最大化性能。

## 相关功能

- [算子列表](Operators.md)：了解 Data-Juicer 中可用的算子。
- [开发者指南](DeveloperGuide_ZH.md)：了解如何开发自定义算子。
