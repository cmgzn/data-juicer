# 数据菜谱（Recipes）

**数据菜谱**是一个 YAML 配置文件，完整描述了一条数据处理流水线。它记录了运行哪些算子、以什么顺序运行、使用什么参数——是流水线的唯一真相来源。

菜谱在所有执行引擎之间通用——同一份菜谱在笔记本上用默认执行引擎跑，或在 Ray 集群上跑，无需任何修改。你可以对它做版本管理、分享，并在数月后精确复现结果。

## 最小示例

```yaml
# 全局参数
dataset_path: './demos/data/demo-dataset.jsonl'
export_path: './outputs/demo-process/demo-processed.jsonl'
np: 4

# process 列表：一个有序的算子列表
process:
  - language_id_score_filter:
      lang: 'zh'
      min_score: 0.8
```

这份菜谱加载 `demo-dataset.jsonl`，仅保留中文语言得分不低于 0.8 的样本，将结果写入 `demo-processed.jsonl`，使用 4 个 worker 进程。

## 全局参数

这些设置控制整条流水线，而非某个具体算子：

| 参数 | 说明 |
|------|------|
| `dataset_path` | 输入数据集路径（JSONL、Parquet、CSV、TSV 或纯文本）。 |
| `export_path` | 处理后数据的输出路径。 |
| `np` | 并行 worker 进程数。 |
| `executor_type` | 使用的执行引擎：`default`、`ray` 或 `ray_partitioned`。详见[执行引擎](executor_ZH.md)。 |
| `op_fusion` | 是否为默认执行引擎启用算子融合（`true` / `false`）。 |

完整的全局参数列表及默认值，参见[配置参考](https://datajuicer.github.io/data-juicer-hub/zh_CN/main/docs/RecipeGallery_ZH.html)。

## `process` 列表

`process` 键包含一个有序的算子列表。每个条目是算子名称加其参数。算子从上到下依次执行，每个算子接收上一个算子的输出。

```yaml
process:
  # 第 1 步：仅保留中文文本
  - language_id_score_filter:
      lang: 'zh'
      min_score: 0.8

  # 第 2 步：按文本长度过滤
  - text_length_filter:
      min_len: 10
      max_len: 50000

  # 第 3 步：清除 HTML 标签
  - clean_html_mapper: {}

  # 第 4 步：移除近似重复
  - document_minhash_deduplicator:
      tokenization: 'space'
      window_size: 5
```

> **提示：** 算子顺序很重要。把低成本算子（文本长度、语言识别）放在高成本算子（基于模型打分）之前，以减少到达昂贵算子的样本数。

## 运行菜谱

```bash
dj-process --config my_recipe.yaml
```

这就是全部命令。Data-Juicer 读取菜谱，解析算子依赖，按需安装缺失的包，然后运行流水线。

## 下一步去哪

- [算子](operators_ZH.md)——了解菜谱中可用的算子类型。
- [执行引擎](executor_ZH.md)——选择如何运行菜谱（本地或分布式）。
- [数据集配置](../DatasetCfg_ZH.md)——配置输入数据格式与路径。
- [算子库](../Operators.md)——浏览所有可用算子的参数与示例。
- [菜谱 Gallery](https://datajuicer.github.io/data-juicer-hub/zh_CN/main/docs/RecipeGallery_ZH.html)——社区贡献的真实菜谱。
