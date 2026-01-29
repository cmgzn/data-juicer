# 缓存管理

## 概览

Data-Juicer 提供了基于 [HuggingFace Datasets](https://github.com/huggingface/datasets) 的缓存管理机制，用于加速数据处理流程中的重复计算。

LLM 数据处理经常需要频繁重新执行，原因包括算子超参数的调整、处理失败（如超出可用内存、磁盘或预定义时间限制）等，尤其是对于大规模数据集。为此，Data-Juicer 提供了内置的缓存管理来支持弹性和可靠的数据处理。基于精心组织的目录结构，Data-Juicer 自动监控每个运行进程的配置变化，当相同配置重新运行时，可以直接复用之前的计算结果，避免重复计算。

此外，针对原始 HuggingFace Datasets 库中缓存管理协议的不足，特别是在处理某些算子中不可序列化的第三方模型和函数时，Data-Juicer 设计了专用的哈希方法来绕过这些不可序列化对象的序列化过程，确保每个算子都能成功缓存。

更多细节请参考我们的论文：[Data-Juicer: A One-Stop Data Processing System for Large Language Models](https://arxiv.org/abs/2309.02033) 。

## 实现与优化

### 缓存机制

每个算子根据以下内容生成具有唯一 **fingerprint（指纹）** 的缓存文件：
- 输入数据的指纹
- 算子名称和参数
- 处理函数的哈希值

即：相同输入 + 相同算子配置 = 相同指纹 = 缓存命中。

### 空间复杂度分析

对于大小为 **S** 的数据集，包含 **M** 个 Mapper、**F** 个 Filter 和 **D** 个 Deduplicator，其峰值空间占用可能为：

```
Space[cache_mode] = (1 + M + F + I(F > 0) + D) × S
```

其中：
- 原始数据集加载后占用 **1×S**
- 每个算子生成一份缓存，共 **(M + F + D)×S**
- `I(F > 0)` 表示当存在 Filter 时，第一个 Filter 添加统计列会额外生成一份缓存

**示例**：10GB 数据集 + 3 Mapper + 4 Filter + 1 Deduplicator：

```
Space = (1 + 3 + 4 + 1 + 1) × 10GB = 100GB
```

这意味着理论峰值可能出现 10 倍的磁盘放大。

> 详见[论文](https://arxiv.org/abs/2309.02033) Section 4.1.1 和 Appendix A.2。

### 缓存压缩

为了解决磁盘空间问题，Data-Juicer 集成了多种压缩技术，如 [Zstandard (zstd)](https://github.com/facebook/zstd) 和 [LZ4](https://github.com/lz4/lz4)。启用后，系统会在每个算子完成后自动压缩缓存文件，并在相同配置重新运行该算子时解压这些压缩文件。

与处理时间相比，压缩/解压时间相对可以忽略不计，这得益于上述压缩技术的高效性。此功能大幅减少了缓存数据存储量，使得在不影响速度或稳定性的情况下处理更大的数据集成为可能。

| 算法 | 压缩率 | 速度 | 推荐场景 |
|-----|-------|------|---------|
| `zstd` | 最高 | 快 | 综合最佳 |
| `lz4` | 中等 | 最快 | 速度优先 |
| `gzip` | 高 | 较慢 | 兼容性优先 |

压缩发生在**算子之间**，而不是处理过程中，所以不会减慢实际的数据处理速度：

```
INFO - Compressing cache file to cache-*_of_*.arrow.zstd
INFO - Decompressing cache file to cache-*_of_*.arrow
```

### 与 Checkpoint 的关系

缓存和 Checkpoint 是**互斥的**两种机制：

| 方面 | Cache 模式 | Checkpoint 模式 |
|-----|-----------|----------------|
| **目的** | 加速相同配置的重复运行 | 故障恢复和断点续跑 |
| **空间使用** | `(1 + M + F + D) × S`（累积） | `3 × S`（恒定） |
| **最适合** | 迭代开发、参数调优 | 长时间运行的生产任务 |

当启用 `use_checkpoint: true` 时，缓存会自动禁用。

## 快速开始

### 基本配置

在配置文件中启用缓存（默认已启用）：

```yaml
project_name: 'demo-cache'
dataset_path: './data/demo-dataset.jsonl'
export_path: './outputs/demo-processed.jsonl'

use_cache: true  # 默认值，可省略

process:
  - text_length_filter:
      min_len: 100
  - language_id_score_filter:
      lang: 'en'
      min_score: 0.8
```

### 启用缓存压缩

对于大数据集，建议启用压缩：

```yaml
project_name: 'demo-cache-compress'
dataset_path: './data/large-dataset.jsonl'
export_path: './outputs/large-processed.jsonl'

use_cache: true
cache_compress: 'zstd'  # 推荐
ds_cache_dir: '/data/large_disk/dj_cache'  # 可选：使用空间更大的磁盘

process:
  - text_length_filter:
      min_len: 100
  - language_id_score_filter:
      lang: 'en'
      min_score: 0.8
```

### 禁用缓存

对于一次性处理或调试场景：

```yaml
project_name: 'demo-no-cache'
dataset_path: './data/demo-dataset.jsonl'
export_path: './outputs/demo-processed.jsonl'

use_cache: false
temp_dir: '/tmp/dj_temp'  # 可选：指定临时文件位置

process:
  - my_custom_mapper:
      param: value
```

### 命令行使用

```shell
# 使用默认缓存设置
dj-process --config your_config.yaml

# 启用缓存压缩
dj-process --config your_config.yaml --cache_compress zstd

# 禁用缓存
dj-process --config your_config.yaml --use_cache false
```

## 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| `use_cache` | bool | `true` | 是否启用 HuggingFace Datasets 缓存 |
| `cache_compress` | string | `null` | 压缩算法：`gzip`、`zstd` 或 `lz4` |
| `ds_cache_dir` | string | `null` | 自定义缓存目录（默认：`~/.cache/huggingface/datasets`） |

## 缓存管理

### 检查缓存大小

```bash
du -sh ~/.cache/huggingface/datasets
```

### 清理缓存

```bash
# 清理所有 HuggingFace datasets 缓存
rm -rf ~/.cache/huggingface/datasets/*

# 或清理特定项目缓存（如果使用了自定义 ds_cache_dir）
rm -rf /path/to/your/ds_cache_dir/*
```

> [!Warning]
> 清理缓存意味着下次运行将重新计算所有内容。

## 故障排除

### 处理过程中出现"磁盘已满"错误

1. 启用压缩：`cache_compress: 'zstd'`
2. 使用更大的磁盘：`ds_cache_dir: '/path/to/large/disk'`
3. 如果是一次性运行，禁用缓存：`use_cache: false`

### 即使有缓存，处理似乎仍然很慢

检查缓存是否真正被使用：
- 验证指纹没有改变（相同输入 + 相同算子配置）
- 检查是否在某处设置了 `use_cache: false`