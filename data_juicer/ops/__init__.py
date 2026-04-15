import time
from contextlib import contextmanager

from loguru import logger


@contextmanager
def timing_context(description):
    start_time = time.time()
    yield
    elapsed_time = time.time() - start_time
    logger.debug(f"{description} took {elapsed_time:.2f} seconds")


# yapf: disable
with timing_context('Importing operator modules'):
    # 1. Built-in operators (registered via @OPERATORS.register_module decorators
    #    that fire as each sub-package is imported)
    # 2. Persistent custom operators (loaded from ~/.data_juicer/custom_op.json;
    #    no-op when the registry file does not exist)
    from data_juicer.utils.custom_op import (
        load_persistent_custom_ops as _load_persistent,
    )

    from . import aggregator, deduplicator, filter, grouper, mapper, pipeline, selector
    _load_persistent()
    del _load_persistent

    from .base_op import (
        ATTRIBUTION_FILTERS,
        NON_STATS_FILTERS,
        OPERATORS,
        TAGGING_OPS,
        UNFORKABLE,
        Aggregator,
        Deduplicator,
        Filter,
        Grouper,
        Mapper,
        Pipeline,
        Selector,
    )
    from .load import load_ops
    from .op_env import (
        OPEnvManager,
        OPEnvSpec,
        analyze_lazy_loaded_requirements,
        analyze_lazy_loaded_requirements_for_code_file,
        op_requirements_to_op_env_spec,
    )

__all__ = [
    "load_ops",
    "Filter",
    "Mapper",
    "Deduplicator",
    "Selector",
    "Grouper",
    "Aggregator",
    "UNFORKABLE",
    "NON_STATS_FILTERS",
    "OPERATORS",
    "TAGGING_OPS",
    "Pipeline",
    "OPEnvSpec",
    "op_requirements_to_op_env_spec",
    "OPEnvManager",
    "analyze_lazy_loaded_requirements",
    "analyze_lazy_loaded_requirements_for_code_file",
]
