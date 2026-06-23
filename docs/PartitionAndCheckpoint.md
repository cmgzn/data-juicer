# Partitioned Processing with Checkpointing

This document describes DataJuicer's fault-tolerant processing system with partitioning, checkpointing, and event logging.

## Overview

The `ray_partitioned` executor splits datasets into partitions and processes them with configurable checkpointing. Failed jobs can resume from the last checkpoint.

**Checkpointing strategies:**
- `every_n_ops` - checkpoint every N operations (default, balanced)
- `every_op` - checkpoint after every operation (max protection, impacts performance)
- `manual` - checkpoint only after specified operations (best for known expensive ops)
- `disabled` - no checkpointing (best performance)

## Directory Structure

```
{work_dir}/{job_id}/
├── job_summary.json              # Job metadata (created on completion)
├── events_{timestamp}.jsonl      # Machine-readable event log
├── dag_execution_plan.json       # DAG execution plan
├── checkpoints/                  # Checkpoint data
├── partitions/                   # Input partitions
├── logs/                         # Human-readable logs
└── metadata/                     # Job metadata
```

## Configuration

### Partition Modes

**Auto mode** (recommended) - analyzes data and resources to determine optimal partitioning:

```yaml
executor_type: ray_partitioned

partition:
  mode: "auto"
  target_size_mb: 256    # Target partition size (128, 256, 512, or 1024)
  size: 5000             # Fallback if auto-analysis fails
  max_size_mb: 256       # Fallback max size
```

**Manual mode** - specify exact partition count:

```yaml
partition:
  mode: "manual"
  num_of_partitions: 8
```

### Checkpointing

```yaml
checkpoint:
  enabled: true
  strategy: every_n_ops  # every_n_ops (default), every_op, manual, disabled
  n_ops: 5               # Default: checkpoint every 5 operations
  op_names:              # For manual strategy - checkpoint after expensive ops
    - document_deduplicator
    - embedding_mapper
```

### Intermediate Storage

```yaml
intermediate_storage:
  format: "parquet"              # parquet, arrow, jsonl
  compression: "snappy"          # snappy, gzip, none
  preserve_intermediate_data: true
  retention_policy: "keep_all"   # keep_all, keep_failed_only, cleanup_all
```

## Usage

### Running Jobs

```bash
# Auto partition mode
dj-process --config config.yaml --partition.mode auto

# Manual partition mode
dj-process --config config.yaml --partition.mode manual --partition.num_of_partitions 4

# With custom job ID
dj-process --config config.yaml --job_id my_experiment_001
```

### Resuming Jobs

```bash
dj-process --config config.yaml --job_id my_experiment_001
```

## Python API Checkpointing

For local `NestedDataset` workflows that call `dataset.process(...)` directly,
create a `CheckpointManager` with the same operator config list used to build
the operators. Build the operators with `load_ops(...)`; this attaches the
operator config metadata that the checkpointer records after each successful
operation.

```python
from pathlib import Path

from data_juicer.core.data import NestedDataset
from data_juicer.ops import load_ops
from data_juicer.utils.ckpt_utils import CheckpointManager

process_list = [
    {"whitespace_normalization_mapper": {"num_proc": 1}},
]
ckpt_dir = Path("./outputs/python-api-checkpoint")


def main():
    dataset = NestedDataset.from_dict({
        "text": ["  A\tline  ", "B\nline"],
    })

    checkpointer = CheckpointManager(
        str(ckpt_dir),
        original_process_list=process_list,
    )

    if checkpointer.ckpt_available:
        dataset = checkpointer.load_ckpt()

    operators = load_ops(checkpointer.get_left_process_list())
    dataset = dataset.process(
        operators,
        checkpointer=checkpointer,
        open_monitor=False,
    )

    print(dataset.to_list())


if __name__ == "__main__":
    main()
```

On the first run, Data-Juicer writes the latest processed dataset and the
processed operator record under `ckpt_dir`. On a retry with the same
`process_list`, `CheckpointManager` loads that record, `load_ckpt()` restores the
latest dataset, and `get_left_process_list()` returns only the operators that
still need to run. If any operator config differs from the recorded prefix,
Data-Juicer starts from the original dataset again.

For direct Python API use, prefer this config-list pattern instead of manually
constructing operators and then attaching checkpointing. Directly constructed
operator instances do not necessarily carry the `_op_cfg` metadata that
`NestedDataset.process(checkpointer=...)` records. Keep the usual Python
`if __name__ == "__main__"` guard in runnable scripts because checkpoint writes
can start worker processes through HuggingFace Datasets.

For Ray processing, checkpoint recovery is handled by the `ray_partitioned`
executor and the `checkpoint` config block shown below. Although
`RayDataset.process` exposes a `checkpointer` keyword for interface
compatibility, direct `RayDataset.process(checkpointer=...)` is not the
documented recovery path for partitioned Ray jobs.

### Checkpoint Strategies

```bash
# Every operation
dj-process --config config.yaml --checkpoint.strategy every_op

# Every N operations
dj-process --config config.yaml --checkpoint.strategy every_n_ops --checkpoint.n_ops 3

# Manual
dj-process --config config.yaml --checkpoint.strategy manual --checkpoint.op_names op1,op2
```

## Auto-Configuration

In auto mode, the optimizer:
1. Samples the dataset to detect modality (text, image, audio, video, multimodal)
2. Measures memory usage per sample
3. Analyzes pipeline complexity
4. Calculates partition size targeting the configured `target_size_mb`

Default partition sizes by modality:

| Modality | Default Size | Max Size | Memory Multiplier |
|----------|--------------|----------|-------------------|
| Text | 10000 | 50000 | 1.0x |
| Image | 2000 | 10000 | 5.0x |
| Audio | 1000 | 4000 | 8.0x |
| Video | 400 | 2000 | 20.0x |
| Multimodal | 1600 | 6000 | 10.0x |

## Job Management Utilities

### Monitor

```bash
# Show progress
python -m data_juicer.utils.job.monitor {job_id}

# Detailed view
python -m data_juicer.utils.job.monitor {job_id} --detailed

# Watch mode
python -m data_juicer.utils.job.monitor {job_id} --watch --interval 10
```

```python
from data_juicer.utils.job.monitor import show_job_progress

data = show_job_progress("job_id", detailed=True)
```

### Stopper

```bash
# Graceful stop
python -m data_juicer.utils.job.stopper {job_id}

# Force stop
python -m data_juicer.utils.job.stopper {job_id} --force

# List running jobs
python -m data_juicer.utils.job.stopper --list
```

```python
from data_juicer.utils.job.stopper import stop_job

stop_job("job_id", force=True, timeout=60)
```

### Common Utilities

```python
from data_juicer.utils.job.common import JobUtils, list_running_jobs

running_jobs = list_running_jobs()

job_utils = JobUtils("job_id")
summary = job_utils.load_job_summary()
events = job_utils.load_event_logs()
```

## Event Types

- `job_start`, `job_complete`, `job_failed`
- `partition_start`, `partition_complete`, `partition_failed`
- `op_start`, `op_complete`, `op_failed`
- `checkpoint_save`, `checkpoint_load`

## Performance Considerations

### Checkpoint vs Ray Optimization Trade-off

**Key insight: Checkpointing interferes with Ray's automatic optimization.**

Ray optimizes execution by fusing operations together and pipelining data. Each checkpoint forces materialization, which breaks the optimization window:

```
Without checkpoints:     op1 → op2 → op3 → op4 → op5
                         |___________________________|
                              Ray optimizes entire window

With every_op:           op1 | op2 | op3 | op4 | op5
                         materialize at each | (5 barriers)

With every_n_ops(5):     op1 → op2 → op3 → op4 → op5 |
                         |_____________________________|
                              Ray optimizes all 5 ops
```

### Checkpoint Cost Analysis

| Cost Type | Typical Value |
|-----------|---------------|
| Checkpoint write | ~2-5 seconds |
| Cheap op execution | ~1-2 seconds |
| Expensive op execution | minutes to hours |

**For cheap operations, checkpointing costs MORE than re-running on failure.**

Example pipeline analysis:
```
filter(1s) → mapper(2s) → deduplicator(300s) → filter(1s)

Strategy         | Overhead  | Protection Value
-----------------|-----------|------------------
every_op         | ~20s      | Save 1-304s on failure
after dedup only | ~5s       | Save 300s on failure
disabled         | 0s        | Re-run everything
```

### Strategy Recommendations

| Job Duration | Recommended Strategy | Rationale |
|--------------|---------------------|-----------|
| < 10 min | `disabled` | Re-running is cheap |
| 10-60 min | `every_n_ops` (n=5) | Balanced protection |
| > 60 min with expensive ops | `manual` | Checkpoint after expensive ops only |
| Unstable infrastructure | `every_n_ops` (n=2-3) | Accept overhead for reliability |

### Operation Categories

**Expensive operations (checkpoint after these):**
- `*_deduplicator` - Global state, expensive computation
- `*_embedding_*` - Model inference
- `*_model_*` - Model inference
- `*_vision_*` - Image/video processing
- `*_audio_*` - Audio processing

**Cheap operations (skip checkpointing):**
- `*_filter` - Simple filtering
- `clean_*` - Text cleaning
- `remove_*` - Field removal

### Storage Recommendations

- Event logs: fast storage (SSD)
- Checkpoints: large capacity storage
- Partitions: local storage

### Partition Sizing Trade-offs

- Smaller partitions: better fault tolerance, more scheduling overhead
- Larger partitions: less overhead, coarser recovery granularity

## Troubleshooting

**Job resumption fails:**
```bash
ls -la ./outputs/{work_dir}/{job_id}/job_summary.json
ls -la ./outputs/{work_dir}/{job_id}/checkpoints/
```

**Check Ray status:**
```bash
ray status
```

**View logs:**
```bash
cat ./outputs/{work_dir}/{job_id}/events_*.jsonl
tail -f ./outputs/{work_dir}/{job_id}/logs/*.txt
```
