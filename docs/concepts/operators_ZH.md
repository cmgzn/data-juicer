# 算子（Operators）

**算子**是单个、可组合的处理步骤。Data-Juicer 提供 200+ 面向生产的算子，覆盖文本、图像、音频、视频和多模态数据。你从算子库中选取算子、设置参数，然后在菜谱的 `process` 列表中将它们串联起来。

## 算子类型

每个算子归属于八种类型之一，按其对数据的作用方式分组：

| 类型 | 作用 | 示例 |
|------|------|------|
| **formatter** | 发现、加载、规范化原始数据为 DJ 格式。 | `json_formatter`、`parquet_formatter` |
| **mapper** | 编辑、转换单个样本。 | `clean_html_mapper`、`fix_unicode_mapper` |
| **filter** | 逐样本计算统计量，按阈值保留或丢弃样本。 | `language_id_score_filter`、`text_length_filter` |
| **deduplicator** | 检测并移除重复样本。 | `document_minhash_deduplicator` |
| **selector** | 基于排序选取高质量样本子集。 | `topk_specified_field_selector` |
| **grouper** | 将样本分组为批量样本。 | `naive_grouper` |
| **aggregator** | 将一批样本汇总为总结或结论。 | `simple_aggregator` |
| **pipeline** | 执行数据集级别的处理，输入和输出均为完整数据集。 | `dataset_process_pipeline` |

最常见的工作流是按顺序使用 **mapper**、**filter** 和 **deduplicator**。其余类型用于特定场景。

## 组合算子

算子像积木一样组合。每个算子的输出作为下一个算子的输入：

```yaml
process:
  - language_id_score_filter:    # 第 1 步：保留中文文本
      lang: 'zh'
      min_score: 0.8
  - text_length_filter:          # 第 2 步：按长度过滤
      min_len: 10
      max_len: 50000
  - clean_html_mapper: {}        # 第 3 步：去除 HTML
```

> **提示：** 顺序很重要。先放低成本、高影响力的过滤器（语言识别、文本长度），在进入昂贵的模型算子之前减少样本数量。

## 能力标签

[算子库](../Operators.md)中的每个算子都带有标签，让你一眼看清它的需求和成熟度：

| 标签 | 取值 | 含义 |
|------|------|------|
| **模态** | Text、Image、Audio、Video、Multimodal | 算子处理的数据类型。 |
| **资源** | CPU、GPU | 是否需要 GPU，还是仅用 CPU 即可。 |
| **可用性** | Alpha、Beta、Stable | Alpha = 基础实现；Beta = 已测试；Stable = DJ 优化版。 |
| **模型** | API、vLLM、HuggingFace | 是否需要下载或调用外部模型。 |

搜索算子时，可以用这些标签在算子库中快速筛选。

## 统计量与元数据

处理过程中，算子会给每个样本附加中间字段：

- **统计量（`__dj__stats__`）**：由 filter 计算的数值指标——文本长度、语言得分、困惑度等。Filter 通过把统计量与你设定的阈值比较来决定保留哪些样本。
- **元数据（`__dj__meta__`）**：由打标算子产出的标签和类别——语言标签、识别出的实体等。

这些字段支撑着另外两项功能：

1. [分析器](../tutorial/QuickStart_ZH.md#4-分析数据集)读取统计量，产出数据集的分布与相关性画像——这正是你挑选合适 filter 阈值的依据。
2. 默认情况下，统计量和元数据字段会从最终输出中剥离。如需保留，在菜谱中设置 `keep_stats_in_res_ds: true` 或 `keep_hashes_in_res_ds: true`。详见[导出指南](../Export_ZH.md)。

## 下一步去哪

- [算子库](../Operators.md)——浏览所有算子的完整参数列表与示例。
- [数据菜谱](recipes_ZH.md)——学习如何在 YAML 菜谱中串联算子。
- [数据集配置](../DatasetCfg_ZH.md)——为算子配置输入数据。
- [开发者指南](../DeveloperGuide_ZH.md)——开发你自己的算子。
