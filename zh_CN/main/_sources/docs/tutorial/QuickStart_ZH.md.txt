# 快速上手

本指南带你逐步完成一次完整的 Data-Juicer 工作流：运行第一个数据处理任务、构建自定义菜谱、分析数据集、交互式调优过滤阈值。五分钟内即可获得清洗过滤后的输出数据。

> **注意：** 部分算子在首次使用时会下载模型权重（例如 `language_id_score_filter` 会下载 fastText 语言识别模型）。首次运行可能需要多等几分钟来下载这些资源，后续运行使用本地缓存，立即启动。

## 前置条件

- 已安装 Data-Juicer——参见[安装文档](Installation_ZH.md)。
- Python 环境已安装菜谱中算子所需的 extras。

---

## 1. 运行第一个处理任务

Data-Juicer 依照**菜谱**处理数据集——菜谱是一个 YAML 配置文件，指定了输入数据集、输出路径和要应用的算子。

从内置的示例菜谱 [`demos/process_simple/process.yaml`](https://github.com/datajuicer/data-juicer/blob/main/demos/process_simple/process.yaml) 开始，它只保留语言置信度较高的中文样本：

```yaml
# 全局参数
project_name: 'demo-process'
dataset_path: './demos/data/demo-dataset.jsonl'
np: 4

export_path: './outputs/demo-process/demo-processed.jsonl'

# 要应用的算子
process:
  - language_id_score_filter:
      lang: 'zh'
      min_score: 0.8
```

以配置文件路径作为参数来运行 `dj-process` 命令行工具或者 `process_data.py` 来处理数据集：

```shell
# 使用命令行工具
dj-process --config demos/process_simple/process.yaml

# 适用于从源码安装
python tools/process_data.py --config demos/process_simple/process.yaml
```

这会在工作目录（`export_path` 所在目录）中产出以下输出：

```
outputs/demo-process/
├── demo-processed.jsonl    # 处理后的数据集
├── *.yaml                  # 完整解析配置的备份
└── logs/                   # 运行日志
```

至此，你已完成第一个数据集的处理。

> **注意：** 使用未保存在本地的第三方模型或资源的算子第一次运行可能会很慢，因为这些算子需要将相应的资源下载到缓存目录中。默认的下载缓存目录为 `~/.cache/data_juicer`。您可通过设置 shell 环境变量 `DATA_JUICER_CACHE_HOME` 更改缓存目录位置，您也可以通过同样的方式更改 `DATA_JUICER_MODELS_CACHE` 或 `DATA_JUICER_ASSETS_CACHE` 来分别修改模型缓存或资源缓存目录：
>
> ```shell
> export DATA_JUICER_CACHE_HOME="/path/to/another/directory"
> export DATA_JUICER_MODELS_CACHE="/path/to/another/directory/models"
> export DATA_JUICER_ASSETS_CACHE="/path/to/another/directory/assets"
> ```

> **注意：** 对于使用了第三方模型的算子，在填写 config 文件时需要去声明其对应的 `memory`（可以参考 [`config_all.yaml`](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/config/config_all.yaml) 中的设置）。Data-Juicer 在运行过程中会根据内存情况和算子模型所需的 memory 大小来控制对应的进程数，以达成更好的数据处理的性能效率。而在使用 CUDA 环境运行时，如果不正确的声明算子的 `memory` 情况，则有可能导致 CUDA Out of Memory。

---

## 2. 构建自己的菜谱

配置文件包含一系列全局参数和用于数据处理的算子列表。您需要设置：

- **全局参数**：输入/输出数据集路径，worker 进程数量等。
- **算子列表**：列出用于处理数据集的算子及其参数。

您可以通过如下方式构建自己的配置文件：

| 方式 | 做法 |
|------|------|
| **➖ 减法** | 修改样例配置文件 [`config_all.yaml`](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/config/config_all.yaml)。该文件包含了**所有**算子以及算子对应的默认参数。您只需要**移除**不需要的算子并重新设置部分算子的参数即可。 |
| **➕ 加法** | 从头开始构建自己的配置文件。您可以参考 [`config_all.yaml`](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/config/config_all.yaml)、[算子文档](../Operators.md)，以及[开发者指南](../DeveloperGuide_ZH.md#2-构建你自己的数据菜谱和配置项)。 |

除了使用 yaml 文件外，您还可以在命令行上指定一个或多个参数，这些参数将覆盖 yaml 文件中的值：

```shell
dj-process --config demos/process_simple/process.yaml --language_id_score_filter.lang=en
```

> **提示：** 基础的配置项格式及定义如下图所示：
>
> ![基础配置项格式及定义样例](https://img.alicdn.com/imgextra/i4/O1CN01xPtU0t1YOwsZyuqCx_!!6000000003050-0-tps-1692-879.jpg "基础配置文件样例")

---

## 3. 配置输入数据集

Data-Juicer 支持多种数据集输入类型，包括本地文件、远程数据集（如 Hugging Face）；还支持数据验证和数据混合。

配置输入文件的两种方法：

- **简单场景**，本地/HF 文件的单一路径：

```yaml
dataset_path: '/path/to/your/dataset'   # 数据集目录或文件的路径
```

- **高级方法**，支持子配置项和更多功能：

```yaml
dataset:
  configs:
    - type: 'local'
      path: 'path/to/your/dataset'   # 数据集目录或文件的路径
```

更多详细信息，请参阅[数据集配置指南](../DatasetCfg_ZH.md)。

---

## 4. 分析数据集

在确定过滤阈值之前，通常需要先了解数据集的统计概况。分析器会计算算子产出的所有统计量的分布和相关性。

```shell
# 使用命令行工具
dj-analyze --config demos/analyze_simple/analyzer.yaml

# 适用于从源码安装
python tools/analyze_data.py --config demos/analyze_simple/analyzer.yaml

# 你也可以使用"自动"模式来避免写一个新的数据菜谱。它会使用全部可产出统计信息的 Filter 来分析
# 你的数据集的一小部分（如1000条样本，可通过 `auto_num` 参数指定）
dj-analyze --auto --dataset_path xx.jsonl [--auto_num 1000]
```

> **注意：** Analyzer 只用于能在 stats 字段里产出统计信息的 Filter 算子和能在 meta 字段里产出 tags 或类别标签的其他算子。除此之外的其他的算子会在分析过程中被忽略。我们使用以下两种注册器来装饰相关的算子：
> - `NON_STATS_FILTERS`：装饰那些**不能**产出任何统计信息的 Filter 算子。
> - `TAGGING_OPS`：装饰那些能在 meta 字段中产出 tags 或类别标签的算子。

> **提示：** 有时会产生 "Glyph missing" 的警告，并且在分析结果图表中会出现一些非法字符。用户可以使用环境变量 `ANALYZER_FONT` 来指定合适的字体。例如：
>
> ```shell
> export ANALYZER_FONT="Heiti TC"  # 使用黑体来支持中文字符，这也是 Analyzer 的默认字体
> ```

**基于 Ray 的分布式分析：** `dj-analyze` 同样支持 Ray 模式进行大规模分布式数据分析。在配置文件中设置 `executor_type: ray`，分析器将自动使用 `RayAnalyzer`，通过 Ray 原生聚合算子计算总体统计信息（count/mean/std/min/max），无需 pandas 物化。注意 RayAnalyzer 不会产出逐列分布图表或相关性分析。更多细节请参考[分布式处理文档](../Distributed_ZH.md)。

```shell
dj-analyze --config demos/analyze_simple/ray_analyzer.yaml
```

---

## 5. 交互式可视化与菜谱调优（Web Playground）

运行项目根目录下的 `app.py` 来在浏览器中可视化您的数据集。

> **注意：** 只可用于从源码安装的方法。

```shell
# 在项目根目录下运行
streamlit run app.py
```

典型使用流程：

1. **解析配置（Parse Cfg）**——指定一个菜谱（已预填示例）、上传你自己的 YAML，或覆盖参数。界面并排展示解析后的配置与原始 YAML。
2. **分析原始数据（Analyze original data）**——对数据集运行[分析器](#4-分析数据集)，展示整体统计表和各类统计量的分布图表。
3. **处理数据（Process data）**——运行完整菜谱，并排展示原始与处理后数据的统计信息。
4. **调优 Filter 算子**——拖动滑块调整每个 filter 的阈值。页面即时报告**丢弃比例**，绘制标注了截断线的统计直方图，并列出具体的**保留 vs. 丢弃样本**。你还可以查看各 filter 效果的堆叠柱状图、词汇多样性分析，并**将保留/丢弃的数据分别下载为 JSONL**。

对阈值满意后，把它们抄回你的菜谱 YAML 即可。这个「分析 → 处理 → 调优 → 导出」的收敛闭环，正是用 Data-Juicer 打磨优质数据菜谱的核心。

---

## 6. 在 Python 中使用 Data-Juicer

除了命令行工具，Data-Juicer 还提供简洁的编程接口：

```python
# ... init op & dataset ...

# 链式调用风格，支持单算子或算子列表
dataset = dataset.process(op)
dataset = dataset.process([op1, op2])

# 函数式编程风格，方便快速集成或脚本原型迭代
dataset = op(dataset)
dataset = op.run(dataset)
```

---

## 7. 规模扩展：分布式处理

Data-Juicer 支持基于 [Ray](https://www.ray.io/) 的多机分布式处理：

```shell
# 运行文字数据处理
python tools/process_data.py --config ./demos/process_on_ray/configs/demo.yaml

# 运行视频数据处理
python tools/process_data.py --config ./demos/process_video_on_ray/configs/demo.yaml
```

- 如果需要在多机上使用 RAY 执行数据处理，需要确保所有节点都可以访问对应的数据路径，即将对应的数据路径挂载在共享文件系统（如 NAS）中。
- RAY 模式下的去重算子与单机版本不同，所有 RAY 模式下的去重算子名称都以 `ray` 作为前缀，例如 `ray_video_deduplicator` 和 `ray_document_deduplicator`。
- 更多细节请参考[分布式处理文档](../Distributed_ZH.md)。

> **注意：** 你也可以不使用 Ray，而是拆分数据集后使用 [Slurm](https://slurm.schedmd.com/) 在集群上运行。此时使用不包含 Ray 的原版 Data-Juicer 即可。[阿里云 PAI-DLC](https://www.aliyun.com/activity/bigdata/pai-dlc) 同时支持 Ray 和 Slurm 框架。

---

## 8. 沙盒实验室（可选）

数据沙盒实验室 (DJ-Sandbox) 为用户提供了持续生产数据菜谱的最佳实践，其具有低开销、可迁移、有指导性等特点。

- 基于小规模数据集快速实验、迭代、优化菜谱，再迁移到更大规模。
- 除基础的数据优化与菜谱微调外，沙盒还提供可配置组件：数据洞察与分析、模型训练与评测、基于数据/模型反馈优化菜谱——组成完整的一站式数据-模型研发流水线。

更多介绍和细节请参阅[沙盒文档](https://datajuicer.github.io/data-juicer-sandbox/zh_CN/main/index_ZH.html)。

---

## 9. 预处理原始数据（可选）

Data-Juicer 的 formatter 开箱支持常见输入格式：

| 格式 | 每文件样本数 |
|------|------------|
| jsonl/json、parquet、csv/tsv | 多个 |
| txt、code、docx、pdf | 单个 |

但来自不同源的现实数据可能很复杂：

- [从 S3 下载的 arXiv 原始数据](https://info.arxiv.org/help/bulk_data_s3.html)包含数千个 tar/gzip 文件，内嵌的 tex 文件难以直接获取。
- 爬取的数据可能包含混合文件类型（pdf、html、docx），表格和图表难以提取。

我们在 [`tools/preprocess`](../../tools/preprocess/README_ZH.md) 中提供了**常见预处理工具**来处理这些情况。欢迎贡献新数据类型的处理能力。我们**强烈建议**将复杂数据预处理为 jsonl 或 parquet 后再输入 Data-Juicer。

---

## 10. 对于 Docker 用户

如果您构建或者拉取了 `data-juicer` 的 Docker 镜像，您可以使用这个 Docker 镜像来运行上面提到的这些命令或者工具。

**直接运行：**

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

**或者您可以进入正在运行的容器，然后在可编辑模式下运行命令：**

```shell
# 启动容器
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

# 进入这个容器，然后您可以在编辑模式下使用 data-juicer
docker exec -it <container_id> bash
```

---

## 下一步

- 在[算子库](../Operators.md)中浏览 200+ 内置算子，并通过[数据集配置指南](../DatasetCfg_ZH.md)灵活配置输入。
- 理解心智模型：[数据菜谱](concepts/recipes_ZH.md)、[算子](concepts/operators_ZH.md)、[执行引擎](concepts/executor_ZH.md)。
- 通过[导出指南](../Export_ZH.md)控制输出格式，通过[缓存管理](../Cache_ZH.md)加速重复运行，通过[数据追踪](../Tracing_ZH.md)调试样本级变化。
- 通过[分布式处理](../Distributed_ZH.md)和[分区与检查点](../PartitionAndCheckpoint_ZH.md)扩展到集群规模。
- 参照[开发者指南](../DeveloperGuide_ZH.md)开发自己的算子，或从 [DJ-Cookbook](DJ-Cookbook_ZH.md) 复用社区菜谱。
