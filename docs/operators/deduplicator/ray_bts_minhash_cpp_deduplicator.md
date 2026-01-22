# ray_bts_minhash_cpp_deduplicator

A basic exact matching deduplicator for RAY. Although its functionality is deduplication, it is implemented as Filter sub-class.

一个适用于 RAY 的基础精确匹配去重器。尽管其功能是去重，但其实现为 Filter 的子类。

Type 算子类型: **deduplicator**

Tags 标签: cpu, text

## 🔧 Parameter Configuration 参数配置
| name 参数名 | type 类型 | default 默认值 | desc 说明 |
|--------|------|--------|------|
| `tokenization` | <class 'str'> | `'space'` | tokenization method for sample texts. It should be one of [space, punctuation, character, sentencepiece]. For English-like languages, we recommend to use 'space', for Chinese-like languages, we recommend to use 'character', and for multiple languages, we recommend to use 'sentencepiece'. If using 'sentencepiece', please provided the model path in the 'tokenizer_model' field. |
| `window_size` | typing.Annotated[int, Gt(gt=0)] | `5` | window size of shingling |
| `lowercase` | <class 'bool'> | `True` | whether to convert text to lower case first |
| `ignore_pattern` | typing.Optional[str] | `None` | whether to ignore sub-strings with specific pattern when computing minhash |
| `tokenizer_model` | typing.Optional[str] | `None` | path for the sentencepiece model, used for sentencepiece tokenization. |
| `num_permutations` | typing.Annotated[int, Gt(gt=0)] | `256` | number of permutations in minhash computing |
| `jaccard_threshold` | typing.Annotated[float, FieldInfo(annotation=NoneType, required=True, metadata=[Ge(ge=0), Le(le=1)])] | `0.7` | the min jaccard similarity threshold in near-duplicate detection. When the jaccard similarity of two sample texts is >= this threshold, they are regarded as similar samples and this op will only keep one of them after deduplication |
| `num_bands` | typing.Optional[typing.Annotated[int, Gt(gt=0)]] | `None` | number of bands in LSH. Default it's None, and it will be determined by an optimal params computation algorithm by minimize the weighted sum of probs of False Positives and False Negatives |
| `num_rows_per_band` | typing.Optional[typing.Annotated[int, Gt(gt=0)]] | `None` | number of rows in each band in LSH. Default it's None, and it will be determined by an optimal params computation algorithm |
| `union_find_parallel_num` | typing.Union[int, str] | `'auto'` |  |
| `union_threshold` | typing.Optional[int] | `256` |  |
| `max_pending_edge_buffer_task` | typing.Optional[int] | `20` |  |
| `num_edge_buffer_task_returns` | typing.Optional[int] | `10` |  |
| `max_pending_filter_tasks` | typing.Optional[int] | `20` |  |
| `num_filter_task_returns` | typing.Optional[int] | `10` |  |
| `merge_batch_size` | typing.Optional[int] | `1000` |  |
| `args` |  | `''` |  |
| `kwargs` |  | `''` |  |


## 🔗 related links 相关链接
- [source code 源代码](../../../data_juicer/ops/deduplicator/ray_bts_minhash_cpp_deduplicator.py)
- [unit test 单元测试]()
- [Return operator list 返回算子列表](../../Operators.md)