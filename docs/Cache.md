# Cache Management

## Overview

Data-Juicer provides a cache management mechanism based on [HuggingFace Datasets](https://github.com/huggingface/datasets) to accelerate repetitive computations in data processing workflows.

LLM data processing often requires frequent re-execution due to reasons such as operator hyperparameter tuning, processing failures (e.g., exceeding available memory, disk space, or predefined time limits), especially for large-scale datasets. To address this, Data-Juicer provides built-in cache management to support elastic and reliable data processing. Based on a carefully organized directory structure, Data-Juicer automatically monitors configuration changes for each running process. When the same configuration is re-run, it can directly reuse previous computation results, avoiding redundant calculations.

Furthermore, to address deficiencies in the cache management protocol of the original HuggingFace Datasets library, particularly when handling non-serializable third-party models and functions in certain operators, Data-Juicer has designed dedicated hashing methods to bypass the serialization process of these non-serializable objects, ensuring successful caching for every operator.

For more details, please refer to our paper: [Data-Juicer: A One-Stop Data Processing System for Large Language Models](https://arxiv.org/abs/2309.02033).

## Implementation and Optimization

### Cache Mechanism

Each operator generates a cache file with a unique **fingerprint** based on the following:
- Fingerprint of input data
- Operator name and parameters
- Hash value of the processing function

That is: Same input + Same operator configuration = Same fingerprint = Cache hit.

Cache files are stored in the following directory structure:

### Space Complexity Analysis

For a dataset of size **S**, containing **M** Mappers, **F** Filters, and **D** Deduplicators, the peak space usage may be:

```
Space[cache_mode] = (1 + M + F + I(F > 0) + D) × S
```

Where:
- Original dataset occupies **1×S** after loading
- Each operator generates one cache copy, totaling **(M + F + D)×S**
- `I(F > 0)` indicates that when Filters exist, the first Filter adding statistical columns generates an additional cache copy

**Example**: 10GB dataset + 3 Mappers + 4 Filters + 1 Deduplicator:

```
Space = (1 + 3 + 4 + 1 + 1) × 10GB = 100GB
```

This means the theoretical peak may result in a 10x disk amplification.

> See [paper](https://arxiv.org/abs/2309.02033) Section 4.1.1 and Appendix A.2 for details.

### Cache Compression

To address disk space issues, Data-Juicer integrates multiple compression technologies, such as [Zstandard (zstd)](https://github.com/facebook/zstd) and [LZ4](https://github.com/lz4/lz4). When enabled, the system automatically compresses cache files after each operator completes, and decompresses these compressed files when the same configuration re-runs that operator.

Compared to processing time, compression/decompression time is relatively negligible, thanks to the high efficiency of the aforementioned compression technologies. This feature significantly reduces cache data storage, making it possible to process larger datasets without affecting speed or stability.

| Algorithm | Compression Ratio | Speed | Recommended Scenario |
|-----------|------------------|-------|---------------------|
| `zstd` | Highest | Fast | Best overall |
| `lz4` | Medium | Fastest | Speed priority |
| `gzip` | High | Slower | Compatibility priority |

Compression occurs **between operators**, not during processing, so it doesn't slow down actual data processing speed:

```
INFO - Compressing cache file to cache-*_of_*.arrow.zstd
INFO - Decompressing cache file to cache-*_of_*.arrow
```

### Relationship with Checkpoints

Cache and Checkpoint are **mutually exclusive** mechanisms:

| Aspect | Cache Mode | Checkpoint Mode |
|--------|-----------|----------------|
| **Purpose** | Accelerate repeated runs with same configuration | Fault recovery and resumption |
| **Space Usage** | `(1 + M + F + D) × S` (cumulative) | `3 × S` (constant) |
| **Best For** | Iterative development, parameter tuning | Long-running production tasks |

When `use_checkpoint: true` is enabled, cache is automatically disabled.

## Quick Start

### Basic Configuration

Enable cache in configuration file (enabled by default):

```yaml
project_name: 'demo-cache'
dataset_path: './data/demo-dataset.jsonl'
export_path: './outputs/demo-processed.jsonl'

use_cache: true  # Default value, can be omitted

process:
  - text_length_filter:
      min_len: 100
  - language_id_score_filter:
      lang: 'en'
      min_score: 0.8
```

### Enable Cache Compression

For large datasets, enabling compression is recommended:

```yaml
project_name: 'demo-cache-compress'
dataset_path: './data/large-dataset.jsonl'
export_path: './outputs/large-processed.jsonl'

use_cache: true
cache_compress: 'zstd'  # Recommended
ds_cache_dir: '/data/large_disk/dj_cache'  # Optional: use disk with more space

process:
  - text_length_filter:
      min_len: 100
  - language_id_score_filter:
      lang: 'en'
      min_score: 0.8
```

### Disable Cache

For one-time processing or debugging scenarios:

```yaml
project_name: 'demo-no-cache'
dataset_path: './data/demo-dataset.jsonl'
export_path: './outputs/demo-processed.jsonl'

use_cache: false
temp_dir: '/tmp/dj_temp'  # Optional: specify temporary file location

process:
  - my_custom_mapper:
      param: value
```

### Command Line Usage

```shell
# Use default cache settings
dj-process --config your_config.yaml

# Enable cache compression
dj-process --config your_config.yaml --cache_compress zstd

# Disable cache
dj-process --config your_config.yaml --use_cache false
```

## Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_cache` | bool | `true` | Whether to enable HuggingFace Datasets cache |
| `cache_compress` | string | `null` | Compression algorithm: `gzip`, `zstd`, or `lz4` |
| `ds_cache_dir` | string | `null` | Custom cache directory (default: `~/.cache/huggingface/datasets`) |

## Cache Management

### Check Cache Size

```bash
du -sh ~/.cache/huggingface/datasets
```

### Clean Cache

```bash
# Clean all HuggingFace datasets cache
rm -rf ~/.cache/huggingface/datasets/*

# Or clean specific project cache (if custom ds_cache_dir is used)
rm -rf /path/to/your/ds_cache_dir/*
```

> [!Warning]
> Cleaning cache means the next run will recompute everything.

## Troubleshooting

### "Disk Full" Error During Processing

1. Enable compression: `cache_compress: 'zstd'`
2. Use a larger disk: `ds_cache_dir: '/path/to/large/disk'`
3. If it's a one-time run, disable cache: `use_cache: false`

### Processing Still Seems Slow Despite Having Cache

Check if cache is actually being used:
- Verify the fingerprint hasn't changed (same input + same operator configuration)
- Check if `use_cache: false` is set somewhere