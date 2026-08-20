# Executor

An **executor** is the runtime engine that drives a Data-Juicer pipeline. Executors are interchangeable — you write the same [recipe](recipes.md) regardless of which one you use, and swap between them by changing a single line. This lets you develop and test locally, then scale to a full distributed cluster without rewriting any configuration.

## The three executor types

### 1. `default` — Local multiprocessing

The default executor runs entirely on your local machine using Python multiprocessing. It is the right choice for development, small-to-medium datasets, and environments where a Ray cluster is not available.

```yaml
executor_type: 'default'
np: 4          # spin up 4 worker processes
```

| Parameter | Description |
| --- | --- |
| `np` | Number of parallel worker processes. Set this to the number of CPU cores you want to dedicate to processing. |

**Operator fusion** is available with this executor. When enabled, Data-Juicer fuses compatible operators so that each sample passes through multiple operators in a single read pass — delivering a 2–10x throughput improvement on typical pipelines. See [Operator fusion](#operator-fusion) below.

### 2. `ray` — Distributed cluster

The `ray` executor distributes processing across a [Ray](https://www.ray.io/) cluster. Use it when your dataset is too large for a single machine or when you need to meet a tight processing deadline.

```yaml
executor_type: 'ray'
ray_address: 'auto'     # connect to a running Ray cluster
np: 4                   # workers per Ray node
```

| Parameter | Description |
| --- | --- |
| `ray_address` | Address of the Ray cluster head node. Use `'auto'` to auto-discover a locally running cluster, or provide an explicit address such as `'ray://192.168.1.100:10001'`. |
| `np` | Number of parallel tasks per node. |

> **Note:** You must have a Ray cluster running before launching a job with `executor_type: 'ray'`. Start a local single-node cluster with `ray start --head`, or provision a multi-node cluster on your infrastructure. See [Distributed Processing](../Distributed.md) for a full setup walkthrough.

### 3. `ray_partitioned` — Partitioned distributed processing

The `ray_partitioned` executor extends the `ray` executor with **partition-level checkpointing**. It divides the dataset into independent partitions and processes each partition as an isolated unit. Completed partitions are checkpointed to disk, so a job that fails mid-way can resume from the last completed partition rather than restarting from scratch.

```yaml
executor_type: 'ray_partitioned'
ray_address: 'auto'
np: 4
```

Use `ray_partitioned` for very large datasets where a full restart would be prohibitively expensive, or in environments with unreliable cluster availability (preemptible nodes, spot instances).

## Selecting an executor

Use this decision guide to choose the right executor for your workload:

| Scenario | Recommended executor |
| --- | --- |
| Development and testing on a laptop | `default` |
| Single-machine production workload (~100 GB) | `default` |
| Multi-machine cluster, dataset fits in cluster memory | `ray` |
| Very large dataset, or cluster uses preemptible nodes | `ray_partitioned` |

> **Tip:** Start with `default` even for large datasets. The operator fusion optimizations often make local processing faster than you expect. Move to `ray` only when wall-clock time or memory constraints make local processing impractical.

## Performance at scale

Data-Juicer's distributed executor has been validated at extreme scale:

> **70 billion samples processed in ~2 hours** on a 50-node cluster with 6,400 CPU cores.

This throughput is achievable thanks to the combination of Ray's task scheduling, Data-Juicer's zero-copy data passing, and operator fusion.

## Operator fusion

When running with the `default` executor, you can enable **operator fusion** to let Data-Juicer identify fusible operator groups — sequences of operators that can share a single data-read pass. Instead of reading each sample from disk once per operator, fused groups process a sample through multiple operators in one pass, dramatically reducing I/O overhead.

Enable fusion by adding `op_fusion: true` to your recipe:

```yaml
op_fusion: true   # disabled by default; enable for throughput gains

process:
  # These three operators can be fused into a single pass:
  - text_length_filter:
      min_len: 10
      max_len: 50000
  - alphanumeric_filter:
      min_ratio: 0.5
  - clean_html_mapper: {}

  # Deduplicators require global state — they run in a separate pass
  - document_minhash_deduplicator:
      tokenization: 'space'
      window_size: 5
```

To maximize fusion opportunities, group operators that work on the same field consecutively in your `process` list.

> **Note:** Operator fusion applies to the `default` executor. Ray-based executors benefit from distributed parallelism instead.

## Configuration quick reference

```yaml
# ── Local multiprocessing (default) ──────────────────────────────
executor_type: 'default'
np: 8
op_fusion: false    # set to true to enable operator fusion

# ── Ray distributed ──────────────────────────────────────────────
executor_type: 'ray'
ray_address: 'auto'
np: 4

# ── Ray with partition checkpointing ─────────────────────────────
executor_type: 'ray_partitioned'
ray_address: 'ray://cluster-head:10001'
np: 4
```

## Where to go next

- [Recipes](recipes.md) — learn how to configure your pipeline.
- [Distributed Processing](../Distributed.md) — set up a Ray cluster.
- [Partition and Checkpoint](../PartitionAndCheckpoint.md) — details on partition-level checkpointing.
- [Operators](operators.md) — understand operator types and fusion behavior.
