## 2026-10-20：当前 checkpoint 设计的实测、恢复验证与代码核查

代码：[当前实现 ae2e99a6](https://github.com/cmgzn/data-juicer/commit/ae2e99a6e48f74b0a35223aa691f1f71b90cb927)，对应 Draft PR #212。本次保留现有设计，不实现“计算与保存彻底独立”的新架构。

### 结论

- 20 万行图片记录四组各 1 轮预热＋1 轮正式，**8/8 通过**。所有组保留 157,762 行，全部统计值与基线完全一致。
- 当前设计正式耗时 **552.0 秒**，旧版四分区 **833.0 秒**，main **818.6 秒**，不开 checkpoint **569.8 秒**。相对旧版/main 耗时减少 **33.7% / 32.6%**；与不开接近，不能解释成“写 checkpoint 本身能加速”。
- 当前版本两次 GPU 故障恢复均正确：完整输出、全部统计值一致，重复/缺失均为 0，故障前已经发布的 manifest 哈希不变。
- 旧版半成品 checkpoint 缺陷重新复现：20,000 行保存到第 8 个文件时杀进程，旧恢复逻辑把目录识别为最新 checkpoint，只读出 **4,000 行且不报错**。
- 当前设计尚未解决超大规模碎文件问题，也不是计算、保存完全独立：仍然先持久化并提交，再向下游交付。

### 1. 版本、环境和测量口径

| 组别 | 代码版本 | 配置特点 |
|---|---|---|
| 旧 checkpoint | `276f7784`，执行组引入前的基线 | 图片大实验用 4 分区并发，GPU 算子全局 `num_proc=16`，分摊到各分区；每 actor `num_gpus=0.5` |
| main checkpoint | `cb196ae2`，本轮冻结的 main 快照 | 1 分区，GPU 算子 `num_proc=16`、`num_gpus=0.5` |
| 不开 checkpoint | 与当前新设计相同代码快照 | 1 分区，三个 GPU 阶段各 14 actors、每 actor `num_gpus=0.18` |
| 当前新设计 | `8142c677`＋本轮整块提交/重试/并行读取改动 | 与不开相同 GPU 配置，显式 `partition.size=1024` |

“main”在这里是冻结版本，不指发布报告当天最新的 main。代码快照的 SHA-256 及三个改动文件校验值保存在 [source-snapshot.json](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/source-snapshot.json)。提交前只有导入格式整理，不改变所测执行逻辑。

- H20 命名实验机：8 张 PPU-ZW810，Ray **2.56.1**、Python **3.12.3**、PyArrow **25.0.1**、PPU Torch **2.11.0+v0.1.0.ppu2.1.1**。模型、版本和文件校验值见 [environment.json](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/environment.json)。运行前加载 PPU envsetup，不改装 Torch。
- 数据源为 Imagenette 的 **13,394 张图片**。20 万行通过循环这些图片并重新编号生成，**不是 20 万张独立图片**；因此包含重复图片/文件缓存效应，不能外推独立图片的大规模 I/O。
- 算子链：`image_shape_filter → image_nsfw_filter → image_watermark_filter → image_text_similarity_filter`。GPU 内部推理 batch 为 32；读入配置目标为每 64 行一个 block，但实际执行会受辅助 `map_batches` 和 Ray 优化影响，不能把配置值当成实测 block 大小。
- 测量为新 CLI 进程启动到最终导出完成，包含模型实例加载；下载、准备输入、模型预热和输出比对不计入耗时。每次使用新工作目录，没有恢复复用正常运行结果。
- 正常性能实验每组只有 1 轮正式，不提供统计显著性结论；资源采样没有观测到外部 GPU 争用，不声称共享主机具有硬独占保证。

### 2. 图片正常执行结果

#### 13,394 行：原设计及旧版分区补充实验

| 组别 | 预热（秒） | 正式（秒） | 输出行数 |
|---|---:|---:|---:|
| 不开 checkpoint | 185.5 | 188.4 | 10,565 |
| 旧 checkpoint，1 分区 | 206.6 | 208.9 | 10,565 |
| 旧 checkpoint，2 分区 | 197.3 | 184.6 | 10,565 |
| 旧 checkpoint，4 分区 | 197.8 | 181.9 | 10,565 |
| main checkpoint，1 分区 | 208.2 | 209.2 | 10,565 |
| 原新设计，提交目标 256 | 158.9 | 161.0 | 10,565 |

这些数据说明旧版分区间确实能并发，不能把旧版概括为“所有分区串行”。它们来自 2026-10-19，不能与修改后的版本混为同一次实验。修改后 `size=1024` 的单轮 GPU 冒烟为 **144.6 秒**，输出及统计完全一致；这是冒烟，不作为正式多轮性能结论。

原始结果：[主对照](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/image-13k.json)、[旧版多分区](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/image-13k-old-partitions.json)。

#### 200,000 行：当前整块提交方案

| 组别 | 预热（秒） | 正式（秒） | checkpoint 文件总数 | checkpoint 大小 |
|---|---:|---:|---:|---:|
| 不开 checkpoint | 576.3 | 569.8 | 0 | 0 |
| 旧 checkpoint，4 分区 | 820.7 | 833.0 | 689 | 38.16 MB |
| main checkpoint | 816.9 | 818.6 | 687 | 29.01 MB |
| 当前新设计，size=1024 | 551.5 | 552.0 | 1570 | 29.68 MB |

MB 按十进制计。每轮均保留 **157,762 行**，ID 哈希相同，全部统计值最大差为 **0.0**，无重复或未知 ID。

原始结果：[image-200k.json](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/image-200k.json)。对应 recipe、运行日志、完整资源采样和代码树校验表压缩在 [normal-run-evidence.tar.gz](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/normal-run-evidence.tar.gz)，没有打包图片或模型。

### 3. 当前版本 GPU 故障恢复

同一 20 万行输入和 actor recipe，每个故障时点做 1 次试验。CLI 启动后到指定时间，用 SIGKILL 终止**本实验自己的整个进程组**；清理该组后启动新 CLI，执行 `--resume job`，计时到最终导出完成。没有使用 `ray stop` 或终止其他作业。

| 中断时点 | 恢复耗时 | 中断前已有提交 | 中断前部分导出行数 | 恢复输出行数 | 重复 / 缺失 | 全部统计最大差 |
|---|---:|---:|---:|---:|---:|---:|
| 180 秒 | 502.0 秒 | 334 | 9,690 | 157,762 | 0 / 0 | 0.0 |
| 400 秒 | 251.3 秒 | 693 | 84,815 | 157,762 | 0 / 0 | 0.0 |

中断前各阶段**已提交的消费行数**如下；不同阶段输入经过过滤，行数不应按同一个分母解释：

| 中断时点 | shape | nsfw | watermark | similarity |
|---|---:|---:|---:|---:|
| 180 秒 | 200000 | 81807 | 40895 | 10114 |
| 400 秒 | 200000 | 190190 | 190175 | 88509 |

两次恢复均检查：故障前所有 manifest 的路径与 SHA-256 保持不变；最终第 0 阶段覆盖 200,000 源行；最终导出与正常基线逐 ID、输入字段和全部统计值一致。中断前已经写出的部分导出文件没有导致恢复后重复行。恢复耗时包含重新读取输入指纹、加载提交记录和模型初始化。

与当前版本正常全程 552.0 秒相比，两种中断后恢复墙钟分别只减少约 **9.0%** 和 **54.5%**。早期中断仍需 502.0 秒，不能声称已经运行的 180 秒都能节省；较晚中断时前三阶段已全部提交，只剩最后阶段未消费的输入。此处沿用原 actor 资源配置，未重新优化恢复时的剩余阶段并发，也未逐项拆分初始化、读取和重算成本。加上中断前耗时，两次总投入约 **682.0 / 651.3 秒**，故障并非没有代价。

本实验验证的是这些中断时点的结果正确性和提交复用，**没有给全部算子计算加逐行计数器**。已提交切片不再运行算子还由本轮 actor/task worker 死亡测试的调用日志验证，不能将未提交或并发尝试的执行次数描述成 exactly once。

结果：[image-200k-recovery.json](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/image-200k-recovery.json)，原始日志、资源采样、故障前/后提交校验值见 [recovery-run-evidence.tar.gz](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/recovery-run-evidence.tar.gz)。

前期文本恢复复测也归档在 [text-recovery-8142c677.json](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/text-recovery-8142c677.json)：49,152 行、120/200 秒中断，各 2 次；`8142c677` 修复后 4/4 正确，恢复耗时中位数约 221.6 / 110.0 秒。它不是本轮图片结果，也不是本轮整块提交版本。

### 4. 实测与阅读实际代码发现的问题

#### A. 旧 checkpoint：正式目录出现不代表写完

重新复现使用 `276f7784` 的原 `RayCheckpointManager`，Ray 2.56.1，20,000 行 / 40 blocks。保存过程中写到 8 个 Parquet 文件时 SIGKILL；`find_latest_checkpoint` 返回该目录，`load_checkpoint().count()` 得到 **4,000 行**，没有完成性校验。这是实际复现，不只是“可能出错”。CPU 复现只验证 checkpoint manager，不冒充完整 GPU executor 的故障计时。

代码原因：旧版 [直接 write_parquet 到正式目录](https://github.com/cmgzn/data-juicer/blob/276f77849a899a8f91570e835d231094be13f3ce/data_juicer/utils/ckpt_utils.py#L313-L323)，[存在即读取](https://github.com/cmgzn/data-juicer/blob/276f77849a899a8f91570e835d231094be13f3ce/data_juicer/utils/ckpt_utils.py#L360-L370)，[按目录名挑最新](https://github.com/cmgzn/data-juicer/blob/276f77849a899a8f91570e835d231094be13f3ce/data_juicer/utils/ckpt_utils.py#L409-L427)，没有完成标记/事务发布。结果：[old-partial-checkpoint-result.json](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/old-partial-checkpoint-result.json)。

#### B. 旧版/main：checkpoint 带来阶段物化屏障

- 旧版各分区可并发，但每分区在 `every_op` 下逐操作组执行、物化再写盘：[分区并发](https://github.com/cmgzn/data-juicer/blob/276f77849a899a8f91570e835d231094be13f3ce/data_juicer/core/executor/ray_executor_partitioned.py#L813-L844)、[组内执行及物化](https://github.com/cmgzn/data-juicer/blob/276f77849a899a8f91570e835d231094be13f3ce/data_juicer/core/executor/ray_executor_partitioned.py#L1283-L1314)。因此是各模型阶段顺序推进，不是同一条 Ray 流水线中三个模型同时处理不同批数据。
- main 的 execution group 仍[逐组顺序推进](https://github.com/cmgzn/data-juicer/blob/cb196ae20f08257068a689ea63e8b9cec031c316/data_juicer/core/executor/ray_executor_partitioned.py#L1237)，开启 checkpoint 时仍[物化后逐逻辑分区写盘](https://github.com/cmgzn/data-juicer/blob/cb196ae20f08257068a689ea63e8b9cec031c316/data_juicer/core/executor/ray_executor_partitioned.py#L1303-L1341)。不能因名字有 execution group 就认为阶段屏障已消失。
- 图片实验观察到正常耗时差异；具体差异还包含模型并发资源配置和辅助步骤合块，不能把全部约 33% 都归因于磁盘写入。

#### C. 辅助步骤的 1000 行 batch 会影响 Ray 分块

当前代码的 [路径转换](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/data_juicer/core/data/ray_dataset.py#L85-L90)、[补 stats](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/data_juicer/core/data/ray_dataset.py#L391-L395)、[filter_batch](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/data_juicer/core/data/ray_dataset.py#L447-L453) 仍指定 `DEFAULT_BATCH_SIZE=1000`；补 meta 也有同类调用。整数 batch_size 会影响 Ray bundling，不只是算子的推理 batch。

当前 checkpoint 并没有跳过 `filter_batch`，而是把它放在 commit 内执行。向 Ray 交付整块时使用 `batch_size=None`，小块不为提交上限合并，块内按最多 1024 输入行切片；内部推理 batch 仍为 32。本轮测试确认小块不合并、大块切片和 GPU 整块逻辑计划没有 bundling threshold。旧普通路径的辅助调用没有在本次顺手修改。

#### D. 当前新设计：细粒度提交带来更多文件

| 类型 | 旧版 | 当前新设计 |
|---|---:|---:|
| Parquet 数据文件 | 688 | 784 |
| 提交 manifest | 0 | 784 |
| 其他元数据 | 1 | 2 |
| 合计 | 689 | 1570 |

旧版数据文件逐阶段为 **196 / 196 / 196 / 100**，新版为 **196 / 196 / 196 / 196**。多出的 96 个数据分片全部在最后阶段；旧版辅助批处理将过滤后的小块重新合并，而新版保留提交边界。总文件数差异主要来自逐提交 manifest，不是把数据量翻倍。[分类原始统计](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/checkpoint-file-counts.json)。

旧版“大恢复分区”本身也没有保证“大存储文件”：`write_parquet` 输出的是多分片目录。当前 `partition.size` 只是输入行数上限，不是文件字节目标；小 block 不会跨块攒大，过滤/扩行/压缩也会改变文件大小。失败或并发尝试写出的、尚未提交的数据文件目前没有自动垃圾回收。

#### E. 导出恢复与当前保证的边界

前期新设计曾在恢复后出现重复导出行，已由 `8142c677` 修复：保留上一批导出，新批写完且交付校验通过后清掉旧批。本轮两次图片恢复再次检查最终输出无重复。它是**成功结束后的最终目录正确性**，不是导出目录中途原子切换；中途仍可能同时存在两批文件。

另一个已经修掉的执行问题是导出前探测未知 schema：这会提前触发 Ray 计算，而不是纯粹读取元数据。`1455f2fa` 改为先用 `columns(fetch_if_missing=False)`，必要时写出后检查；[当前代码](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/data_juicer/core/ray_exporter.py#L194-L200)。但非零 export shard size 仍调用 `size_bytes/count`，不能把 schema 修复泛化为所有导出路径都不额外触发执行。

当前 checkpoint 的关键是：worker 先写输出，协调者发布 manifest，之后才 yield 下游；相同已提交消费范围直接重放赢家。它解决了数据流继续交由 Ray 调度、按提交恢复及提交后 worker 重试不重算，但仍有以下限制：

- 输入/算子配置必须匹配；partial-overlap retry 报错，不能自动接受任意重分批。
- 只覆盖连续前导 Mapper/Filter；遇到 Pipeline、Deduplicator、共享状态或 `converge_after` 后，后续原样运行但没有 checkpoint。
- 算子的外部写入等副作用不保证 exactly once；未提交计算和并发尝试可重复。
- 整块 GPU 接入用了 Ray 私有 API；已验证本轮 2.56.1，不提供任意未来 Ray 版本兼容保证。
- 输入行数上限不限制扩行后的内存/字节量；单协调者的大规模吞吐、内存占用及实际多机 S3 性能未在本轮覆盖。
- 支持共享 POSIX 和 S3 条件创建，但本轮 GPU 用共享 POSIX；不能由本地测试外推真实 S3 表现。
- Lance 自动替换和非零 export shard size 下额外 size/count 执行路径没有由本轮默认 JSON 导出测试覆盖。

### 5. 本轮验证范围与协调者压测

- 协议、RayDataset、恢复集成：**69 项通过**；模拟多节点的节点丢失/协调者放置：**2 项通过**。覆盖 actor/task worker 提交后死亡、跳过已提交计算、扩行/缩行/全过滤、nullable schema、统计发布恢复和不同提交上限恢复等。
- 格式整理后补跑协议＋RayDataset：**43 项通过**，与上表有重叠，不相加。
- 原 executor/parallel 测试：46 通过、12 因 `perplexity_filter` 初始化缺 kenlm 而失败（安装权限不足，源码构建缺 cmake）；12 项都未进入断言。无模型依赖的临时副本 **26 项通过**，保留原断言但替换 recipe，不能算原 perplexity 配方已验证。未修改原测试文件或重新安装 GPU 环境。
- 协调者简化压测每组 1 预热＋1 正式，2000 条空输出提交，包含 RPC、条件写和日志装载；本地 16/64 并发正式约 **380 / 433 commits/s**，模拟每次存储请求额外 10ms 为 **478 / 433 commits/s**。2000 manifests 的并行装载约 **0.5–1.0 秒**。[原始结果](https://github.com/cmgzn/data-juicer/blob/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/results/coordinator.json)。这不是带 Parquet/GPU 的端到端吞吐，也不是真实 S3，不能作为亿级数据容量承诺。

### 6. 可复核材料与下一步

本轮 [基准目录](https://github.com/cmgzn/data-juicer/tree/ae2e99a6e48f74b0a35223aa691f1f71b90cb927/tools/benchmark/checkpoint_20261020/) 包含正常/恢复脚本、协调者压测、旧半成品复现、原始结果、日志和校验值；模型和数据不上传。原始日志保留原 H20 路径，重跑需按本机调整输入、模型和代码树位置。

在已准备相同环境的实验目录 `ROOT` 中，可用归档脚本复现（结果目录必须是新的，勿覆盖已有证据）：

```bash
source /usr/local/PPU_SDK/envsetup.sh
export HF_HOME=/mnt/data/cmgzn.cmx/hf-cache
# ROOT 内需要 environment.json / ready.json / verified-sources.json / spec.json / code/{old,main,new}
python tools/benchmark/checkpoint_20261020/gimg_benchmark.py \
  --root "$ROOT" --results "$ROOT/full-repeat" --spec "$ROOT/spec.json" \
  --rows 200000 --warmups 1 --repeats 1 --timeout 7200 \
  --labels nockpt-S14 old-n4-a16 main-n1-a16 new-S14-s1024
# 恢复脚本使用 ROOT/full-200000 的基线与输入；默认创建 ROOT/recovery-200000
python tools/benchmark/checkpoint_20261020/gimg_recovery.py --root "$ROOT" --kill-at 180 400
```

旧半成品独立复现：从 git 提取 `276f7784:data_juicer/utils/ckpt_utils.py` 到临时文件，运行 `old_partial_checkpoint.py --old-checkpoint-module <文件> --output <结果.json>`。归档脚本只把共享 helper 导入本地化并整理格式；原计时脚本 SHA 在各实验 manifest 中保留，运行配置/原始日志可直接核对。

当前设计已经有可展示的亮点：恢复控制面不替代 Ray Data、消除 checkpoint 造成的逐算子物化屏障、提交后故障可重放、最终导出恢复正确，并且本轮性能接近不开 checkpoint。下一步“保存完全成为旁路、持久化粒度跨 block 聚合”仍是待设计方案；优先减少碎文件、允许更多重算，同时解决上下游恢复一致性，不把它写成当前已完成能力。
