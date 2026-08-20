# 执行引擎（Executor）

**执行引擎**是驱动 Data-Juicer 流水线的运行时引擎。执行引擎之间可以互换——无论使用哪种引擎，你编写的[菜谱](recipes_ZH.md)都是一样的，只需改一行配置即可切换。这让你可以在本地开发和测试，然后扩展到完整的分布式集群，而无需重写任何配置。

## 三种执行引擎

### 1. `default` — 本地多进程

默认执行引擎完全在你的本地机器上运行，使用 Python 多进程。它适用于开发、中小规模数据集，以及没有 Ray 集群的环境。

```yaml
executor_type: 'default'
np: 4          # 启动 4 个 worker 进程
```

| 参数 | 说明 |
|------|------|
| `np` | 并行 worker 进程数。设置为你想用于处理的 CPU 核心数。 |

此引擎支持**算子融合**。启用后，Data-Juicer 将兼容的算子融合在一起，使每个样本在一次读取中经过多个算子处理——在典型流水线上可带来 **2–10 倍的吞吐提升**。详见下方的[算子融合](#算子融合)章节。

### 2. `ray` — 分布式集群

`ray` 执行引擎将处理分布到 [Ray](https://www.ray.io/) 集群上。当数据集太大无法在单机上处理，或需要在紧迫的时间内完成处理时，使用它。

```yaml
executor_type: 'ray'
ray_address: 'auto'     # 连接到运行中的 Ray 集群
np: 4                   # 每个 Ray 节点的 worker 数
```

| 参数 | 说明 |
|------|------|
| `ray_address` | Ray 集群头节点地址。使用 `'auto'` 自动发现本地运行的集群，或提供显式地址如 `'ray://192.168.1.100:10001'`。 |
| `np` | 每个节点的并行任务数。 |

> **注意：** 在使用 `executor_type: 'ray'` 启动任务之前，必须有一个运行中的 Ray 集群。使用 `ray start --head` 启动本地单节点集群，或在你的基础设施上配置多节点集群。详见[分布式处理](../Distributed_ZH.md)。

### 3. `ray_partitioned` — 分区分布式处理

`ray_partitioned` 执行引擎在 `ray` 执行引擎的基础上增加了**分区级检查点**。它将数据集划分为独立的分区，并将每个分区作为独立单元处理。已完成的分区会被检查点到磁盘，因此中途失败的任务可以从最后完成的分区恢复，而无需从头重新开始。

```yaml
executor_type: 'ray_partitioned'
ray_address: 'auto'
np: 4
```

对超大数据集使用 `ray_partitioned`——完全重启代价过高的场景，或集群可用性不可靠的环境（抢占式节点、竞价实例）。

## 如何选择执行引擎

用这个决策指南为你的工作负载选择合适的执行引擎：

| 场景 | 推荐执行引擎 |
|------|-------------|
| 笔记本上的开发和测试 | `default` |
| 单机生产负载（~100 GB） | `default` |
| 多机集群，数据集可放入集群内存 | `ray` |
| 超大数据集，或集群使用抢占式节点 | `ray_partitioned` |

> **提示：** 即使是大数据集也先用 `default`。算子融合优化通常使本地处理比你预期的更快。只有当处理时间或内存限制使本地处理不可行时，才转向 `ray`。

## 大规模性能

Data-Juicer 的分布式执行引擎已在极端规模下得到验证：

> **约 2 小时内处理 700 亿样本**，使用 50 节点集群、6,400 个 CPU 核心。

这一吞吐量得益于 Ray 的任务调度、Data-Juicer 的零拷贝数据传递和算子融合的组合。

## 算子融合

使用 `default` 执行引擎时，你可以启用**算子融合**，让 Data-Juicer 识别可融合的算子组——即可以共享单次数据读取的算子序列。融合组中的算子在一次读取中处理每个样本，而不是每个算子各读一次，大幅减少 I/O 开销。

在菜谱中添加 `op_fusion: true` 即可启用融合：

```yaml
op_fusion: true   # 默认关闭；启用以提升吞吐

process:
  # 这三个算子可以融合为一次读取：
  - text_length_filter:
      min_len: 10
      max_len: 50000
  - alphanumeric_filter:
      min_ratio: 0.5
  - clean_html_mapper: {}

  # 去重算子需要全局状态——在单独的读取中运行
  - document_minhash_deduplicator:
      tokenization: 'space'
      window_size: 5
```

为了最大化融合机会，在 `process` 列表中将处理同一字段的算子连续排列。

> **注意：** 算子融合适用于 `default` 执行引擎。基于 Ray 的执行引擎通过分布式并行获得性能提升。

## 配置速查

```yaml
# ── 本地多进程（默认） ───────────────────────────────────────────
executor_type: 'default'
np: 8
op_fusion: false    # 设为 true 启用算子融合

# ── Ray 分布式 ───────────────────────────────────────────────────
executor_type: 'ray'
ray_address: 'auto'
np: 4

# ── Ray + 分区检查点 ─────────────────────────────────────────────
executor_type: 'ray_partitioned'
ray_address: 'ray://cluster-head:10001'
np: 4
```

## 下一步去哪

- [数据菜谱](recipes_ZH.md)——学习如何配置流水线。
- [分布式处理](../Distributed_ZH.md)——搭建 Ray 集群。
- [分区与检查点](../PartitionAndCheckpoint_ZH.md)——分区级检查点的详细说明。
- [算子](operators_ZH.md)——了解算子类型和融合行为。
