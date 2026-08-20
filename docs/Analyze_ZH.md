# 数据分析

在确定过滤阈值之前，通常需要先了解数据集的统计概况。`dj-analyze` 会计算算子产出的所有统计量的分布和相关性，帮助你做出数据驱动的阈值决策。

---

## 基本用法

对已有菜谱运行分析器：

```bash
dj-analyze --config path/to/your-recipe.yaml
```

也可以使用**自动模式**，无需编写专门的分析菜谱——它会用全部可产出统计信息的 Filter 来分析数据集的一个子集：

```bash
dj-analyze --auto --dataset_path your-dataset.jsonl [--auto_num 1000]
```

- `--auto_num`：采样分析的样本数量，默认 1000。适合快速了解数据分布。

---

## 分析输出

分析器生成以下内容：

- **整体统计表**：各统计量的 count、mean、std、min、max
- **分布图表**：每个统计量的直方图
- **相关性分析**：统计量之间的相关性热力图

输出默认保存在 `export_path` 所在目录下。

---

## 哪些算子参与分析

Analyzer 只处理两类算子：
- **Filter 算子**中能在 `stats` 字段产出统计信息的（大多数 Filter 都可以）
- **其他算子**中能在 `meta` 字段产出 tags 或类别标签的

使用以下注册器标记例外情况：
- `NON_STATS_FILTERS`：装饰那些**不能**产出统计信息的 Filter 算子
- `TAGGING_OPS`：装饰那些能在 meta 中产出标签的算子

---

## 分布式分析

`dj-analyze` 支持 Ray 模式进行大规模分布式数据分析。在配置文件中设置：

```yaml
executor_type: ray
```

分析器将自动使用 `RayAnalyzer`，通过 Ray 原生聚合算子计算总体统计信息（count/mean/std/min/max），无需 pandas 物化。

> **注意：** RayAnalyzer 不会产出逐列分布图表或相关性分析。更多 Ray 相关细节请参考[分布式处理文档](Distributed_ZH.md)。

```bash
dj-analyze --config demos/analyze_simple/ray_analyzer.yaml
```

---

## 字体设置

分析结果图表中如出现 "Glyph missing" 警告或非法字符，可通过环境变量指定字体：

```bash
export ANALYZER_FONT="Heiti TC"  # 黑体，支持中文字符（默认值）
```

---

## 下一步

- 根据分析结果调整阈值？使用 [Web Playground](Playground_ZH.md) 交互式调优
- 确认阈值后运行处理？参见[快速上手 §4](tutorial/QuickStart_ZH.md#4-运行流水线)
- 大规模分析？参见[分布式处理](Distributed_ZH.md)
