# recognize-anything patches

Patches for [xinyu1205/recognize-anything](https://github.com/xinyu1205/recognize-anything) applied automatically by `LazyLoader._apply_patches()` after cloning.

## recognize_anything_changes.diff

1. **setup.py**: Reads `requirements.txt` and passes dependencies to `setuptools.setup(install_requires=...)`. Without this, `pip install` does not install required packages.
2. **ram/models/bert.py**: Moves `apply_chunking_to_forward`, `find_pruneable_heads_and_indices`, `prune_linear_layer` imports from `transformers.modeling_utils` to `transformers.pytorch_utils` (where they live in transformers >= 4.x).
