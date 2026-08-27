# transformers-stream-generator patches

Patches for [LowinLi/transformers-stream-generator](https://github.com/LowinLi/transformers-stream-generator) applied automatically by `LazyLoader._apply_patches()` after cloning.

## transformers_stream_generator_changes.diff

1. **transformers_stream_generator/main.py**: Moves `BeamSearchScorer` import from `transformers` top-level to `transformers.generation.beam_search` (where it lives in transformers >= 4.x).
