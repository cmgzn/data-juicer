"""
Declarative schema definitions for Data-Juicer global configuration.

This module serves as the **single source of truth** for all configuration
fields.  The entire config is defined as a single Pydantic ``DJConfig``
model with nested sub-models for structured sections (dataset, checkpoint,
partition, etc.).

External consumers can use the query APIs to:
- Get the JSON Schema: ``get_json_schema()``
- Get all default values: ``get_defaults()``
- Get the model class itself: ``DJConfig``

The ``register_schema_to_parser()`` function bridges the Pydantic model
back to jsonargparse's ``ArgumentParser``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from jsonargparse import ArgumentParser
from pydantic import BaseModel, Field

from data_juicer.utils.mm_utils import SpecialTokens

# ============================================================
# Pydantic sub-model definitions
# ============================================================


class DatasetConfig(BaseModel):
    """Configuration for dataset loading.

    The ``configs`` field is a list of per-source dataset configurations
    (similar to how ``process`` holds per-operator configurations).
    Each item's schema depends on its ``type`` and the corresponding
    ``DataLoadStrategy`` subclass.

    Common fields shared by all strategies (e.g. ``weight``, ``type``)
    are defined in ``DataLoadStrategy.BASE_CONFIG_RULES``.
    Strategy-specific fields are defined in each subclass's
    ``CONFIG_VALIDATION_RULES``.  Available strategies can be discovered
    via ``DataLoadStrategyRegistry``.
    """

    max_sample_num: Optional[int] = Field(
        default=None,
        description=(
            "Maximum number of samples to load from the dataset configs. "
            "When set, samples are drawn from each dataset source according "
            "to its weight."
        ),
        gt=0,
    )
    configs: List[Dict] = Field(
        default_factory=list,
        description=(
            "List of dataset source configurations. Each entry is a dict "
            "whose schema depends on its 'type' field (e.g. 'local', "
            "'huggingface', 'modelscope'). Common fields for all strategies "
            "(e.g. 'weight', 'type') are defined in "
            "DataLoadStrategy.BASE_CONFIG_RULES. Strategy-specific fields "
            "are defined in each strategy's CONFIG_VALIDATION_RULES. "
            "Available strategies can be discovered via "
            "DataLoadStrategyRegistry."
        ),
    )


class CheckpointConfig(BaseModel):
    """Enhanced checkpoint configuration for PartitionedRayExecutor."""

    enabled: bool = Field(
        default=True,
        description="Enable enhanced checkpointing for PartitionedRayExecutor",
    )
    strategy: Literal["every_op", "every_partition", "every_n_ops", "manual", "disabled"] = Field(
        default="every_n_ops",
        description=(
            "Checkpoint strategy: every_n_ops (default, balanced), every_op "
            "(max protection), manual (after specific ops), disabled (best "
            "performance)"
        ),
    )
    n_ops: int = Field(
        default=5,
        description=(
            "Number of operations between checkpoints for every_n_ops "
            "strategy. Default 5 balances fault tolerance with Ray "
            "optimization."
        ),
    )
    op_names: List[str] = Field(
        default_factory=list,
        description="List of operation names to checkpoint for manual strategy",
    )


class PartitionConfig(BaseModel):
    """Partition configuration for PartitionedRayExecutor."""

    mode: Literal["manual", "auto"] = Field(
        default="auto",
        description=("Partition mode: manual (specify num_of_partitions) or auto " "(use partition size optimizer)"),
    )
    num_of_partitions: int = Field(
        default=4,
        description="Number of partitions for manual mode (ignored in auto mode)",
    )
    target_size_mb: int = Field(
        default=256,
        description=(
            "Target partition size in MB for auto mode (128, 256, 512, or "
            "1024). Controls how large each partition should be. Smaller = "
            "more checkpoints & better recovery, larger = less overhead. "
            "Default 256MB balances memory safety and efficiency."
        ),
    )


class ResourceOptimizationConfig(BaseModel):
    """Resource optimization configuration."""

    auto_configure: bool = Field(
        default=False,
        description=(
            "Enable automatic optimization of partition size, worker count, " "and other resource-dependent settings"
        ),
    )


class IntermediateStorageConfig(BaseModel):
    """Intermediate storage configuration."""

    preserve_intermediate_data: bool = Field(
        default=False,
        description="Preserve intermediate data for debugging",
    )
    cleanup_temp_files: bool = Field(
        default=True,
        description="Clean up temporary files after processing",
    )
    cleanup_on_success: bool = Field(
        default=False,
        description="Clean up intermediate files even on successful completion",
    )
    retention_policy: Literal["keep_all", "keep_failed_only", "cleanup_all"] = Field(
        default="keep_all",
        description="File retention policy",
    )
    max_retention_days: int = Field(
        default=7,
        description="Maximum retention days for files",
    )
    format: Literal["parquet", "arrow", "jsonl"] = Field(
        default="parquet",
        description="Storage format for checkpoints and intermediate data",
    )
    compression: Literal["snappy", "gzip", "none"] = Field(
        default="snappy",
        description="Compression format for storage files",
    )
    write_partitions: bool = Field(
        default=True,
        description=(
            "Whether to write intermediate partition files to disk. "
            "Set to false for better performance when intermediate "
            "files aren't needed."
        ),
    )


class EventLoggingConfig(BaseModel):
    """Event logging configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable event logging for job tracking and resumption",
    )


# ============================================================
# DJConfig: the single Pydantic model for all configuration
# ============================================================

# Metadata dict for fields that need special argparse handling.
# Stored in Field.json_schema_extra so register_schema_to_parser
# can read it.
_ARGPARSE_ACTION = "argparse_action"
_ARGPARSE_NARGS = "argparse_nargs"


class DJConfig(BaseModel):
    """Complete Data-Juicer configuration.

    This is the **single source of truth** for all configuration fields.
    ``DJConfig.model_json_schema()`` produces a full JSON Schema that
    external agents can consume directly.
    """

    # --------------------------------------------------------
    # general: basic global parameters
    # --------------------------------------------------------
    project_name: str = Field(
        default="hello_world",
        description="Name of your data process project.",
    )
    executor_type: Literal["default", "ray", "ray_partitioned"] = Field(
        default="default",
        description='Type of executor, support "default", "ray", or "ray_partitioned".',
    )
    np: int = Field(
        default=4,
        gt=0,
        description="Number of processes to process dataset.",
    )
    turbo: bool = Field(
        default=False,
        description="Enable Turbo mode to maximize processing speed when batch size is 1.",
    )
    skip_op_error: bool = Field(
        default=True,
        description="Skip errors in OPs caused by unexpected invalid samples.",
    )
    auto_op_parallelism: bool = Field(
        default=True,
        description="Whether to automatically set operator parallelism.",
    )
    debug: bool = Field(
        default=False,
        description="Whether to run in debug mode.",
        json_schema_extra={_ARGPARSE_ACTION: "store_true"},
    )
    custom_operator_paths: Optional[List[str]] = Field(
        default=None,
        description=(
            "Paths to custom operator scripts. Multiple paths can be "
            "specified. Operators defined in these scripts will be "
            "registered and available for use in the process pipeline."
        ),
        json_schema_extra={_ARGPARSE_NARGS: "+"},
    )
    use_dag: Optional[bool] = Field(
        default=None,
        description=(
            "Whether to enable DAG execution planning. If None (default), "
            "DAG execution is automatically enabled for distributed/"
            "partitioned executors and disabled for standalone mode. Set "
            "to True to force-enable DAG execution monitoring, or False "
            "to disable it."
        ),
    )

    # --------------------------------------------------------
    # dataset: data input configuration
    # --------------------------------------------------------
    dataset_path: str = Field(
        default="",
        description=(
            "Path to datasets with optional weights(0.0-1.0), 1.0 as "
            "default. Accepted format:<w1> dataset1-path <w2> dataset2-path "
            "<w3> dataset3-path ..."
        ),
    )
    dataset: Optional[DatasetConfig] = Field(
        default=None,
        description=(
            "Dataset setting to define local/remote datasets. Contains "
            "max_sample_num (optional max samples to load) and configs "
            "(list of per-source dataset configurations). Refer to "
            "https://datajuicer.github.io/data-juicer/en/main/docs/DatasetCfg.html "
            "for more detailed examples. "
        ),
    )
    generated_dataset_config: Optional[Dict] = Field(
        default=None,
        description=(
            "Configuration used to create a dataset. "
            "The dataset will be created from this configuration if provided. "
            "It must contain the `type` field to specify the dataset name."
        ),
    )
    validators: List[Dict] = Field(
        default_factory=list,
        description=(
            "List of validators to apply to the dataset. Each validator "
            "must have a `type` field specifying the validator type."
        ),
    )
    load_dataset_kwargs: Dict = Field(
        default_factory=dict,
        description=(
            "Extra keyword arguments passed through to the underlying "
            "datasets.load_dataset() call. Useful for format-specific "
            "options such as chunksize (JSON), columns (Parquet), or "
            "delimiter (CSV). See the HuggingFace Datasets docs for "
            "available options."
        ),
    )
    read_options: Dict = Field(
        default_factory=dict,
        description=(
            "Read options passed through to PyArrow reading functions "
            "(e.g., block_size for JSON reading). This configuration is "
            "especially useful when reading large JSON files."
        ),
    )
    suffixes: List[str] = Field(
        default_factory=list,
        description=(
            "Suffixes of files that will be found and loaded. If not set, "
            "we will find all suffix files, and select a suitable formatter "
            "with the most files as default."
        ),
    )
    add_suffix: bool = Field(
        default=False,
        description=(
            "Whether to add the file suffix to dataset meta info. If "
            "True, a '__dj__suffix' field will be added to each sample "
            "indicating which file type it came from. This is "
            "automatically enabled when suffix_filter is used in the "
            "process list, but can also be manually set to True."
        ),
    )

    # --------------------------------------------------------
    # export: data output / export configuration
    # --------------------------------------------------------
    export_path: str = Field(
        default="./outputs/hello_world/hello_world.jsonl",
        description=(
            "Path to export and save the output processed dataset. The "
            "directory to store the processed dataset will be the work "
            "directory of this process."
        ),
    )
    export_type: Optional[str] = Field(
        default=None,
        description=(
            "The export format type. If it's not specified, Data-Juicer will "
            "parse from the export_path. The supported types can be found in "
            "Exporter._router() for standalone mode and "
            "RayExporter._SUPPORTED_FORMATS for ray mode"
        ),
    )
    export_shard_size: int = Field(
        default=0,
        ge=0,
        description=(
            "Shard size of exported dataset in Byte. In default, it's 0, "
            "which means export the whole dataset into only one file. If "
            "it's set a positive number, the exported dataset will be split "
            "into several sub-dataset shards, and the max size of each shard "
            "won't larger than the export_shard_size"
        ),
    )
    export_in_parallel: bool = Field(
        default=False,
        description=(
            "Whether to export the result dataset in parallel to a single "
            "file, which usually takes less time. It only works when "
            "export_shard_size is 0, and its default number of processes is "
            "the same as the argument np. **Notice**: If it's True, "
            "sometimes exporting in parallel might require much more time "
            "due to the IO blocking, especially for very large datasets. "
            "When this happens, False is a better choice, although it takes "
            "more time."
        ),
    )
    export_extra_args: Dict = Field(
        default_factory=dict,
        description=(
            "Other optional arguments for exporting in dict. For example, "
            "the key mapping info for exporting the WebDataset format."
        ),
    )
    export_aws_credentials: Optional[Dict] = Field(
        default=None,
        description=(
            "Export-specific AWS credentials for S3 export. If export_path "
            "is S3 and this is not provided, an error will be raised. Should "
            "contain aws_access_key_id, aws_secret_access_key, aws_region, "
            "and optionally aws_session_token and endpoint_url."
        ),
    )
    keep_stats_in_res_ds: bool = Field(
        default=False,
        description=(
            "Whether to keep the computed stats in the result dataset. If "
            "it's False, the intermediate fields to store the stats "
            "computed by Filters will be removed. Default: False."
        ),
    )
    keep_hashes_in_res_ds: bool = Field(
        default=False,
        description=(
            "Whether to keep the computed hashes in the result dataset. If "
            "it's False, the intermediate fields to store the hashes "
            "computed by Deduplicators will be removed. Default: False."
        ),
    )

    # --------------------------------------------------------
    # multimodal: multimodal data processing keys & tokens
    # --------------------------------------------------------
    text_keys: Union[str, List[str]] = Field(
        default="text",
        description=(
            "Key name of field where the sample texts to be processed, e.g., "
            "`text`, `text.instruction`, `text.output`, ... Note: currently, "
            "we support specify only ONE key for each op, for cases "
            "requiring multiple keys, users can specify the op multiple "
            "times.  We will only use the first key of `text_keys` when you "
            "set multiple keys."
        ),
    )
    image_key: str = Field(
        default="images",
        description="Key name of field to store the list of sample image paths.",
    )
    image_bytes_key: str = Field(
        default="image_bytes",
        description="Key name of field to store the list of sample image bytes.",
    )
    image_special_token: str = Field(
        default=SpecialTokens.image,
        description=(
            "The special token that represents an image in the text. In "
            'default, it\'s "<__dj__image>". You can specify your own special'
            " token according to your input dataset."
        ),
    )
    audio_key: str = Field(
        default="audios",
        description="Key name of field to store the list of sample audio paths.",
    )
    audio_special_token: str = Field(
        default=SpecialTokens.audio,
        description=(
            "The special token that represents an audio in the text. In "
            'default, it\'s "<__dj__audio>". You can specify your own special'
            " token according to your input dataset."
        ),
    )
    video_key: str = Field(
        default="videos",
        description="Key name of field to store the list of sample video paths.",
    )
    video_special_token: str = Field(
        default=SpecialTokens.video,
        description=(
            "The special token that represents a video in the text. In "
            'default, it\'s "<__dj__video>". You can specify your own special'
            " token according to your input dataset."
        ),
    )
    eoc_special_token: str = Field(
        default=SpecialTokens.eoc,
        description=(
            "The special token that represents the end of a chunk in the "
            'text. In default, it\'s "<|__dj__eoc|>". You can specify your '
            "own special token according to your input dataset."
        ),
    )

    # --------------------------------------------------------
    # cache: cache management
    # --------------------------------------------------------
    use_cache: bool = Field(
        default=True,
        description=(
            "Whether to use the cache management of huggingface datasets. It "
            "might take up lots of disk space when using cache"
        ),
    )
    ds_cache_dir: Optional[str] = Field(
        default=None,
        description=(
            "Cache dir for HuggingFace datasets. In default it's the same "
            "as the environment variable `HF_DATASETS_CACHE`, whose default "
            'value is usually "~/.cache/huggingface/datasets". If this '
            "argument is set to a valid path by users, it will override the "
            "default cache dir. Modifying this arg might also affect the "
            "other two paths to store downloaded and extracted datasets that "
            "depend on `HF_DATASETS_CACHE`"
        ),
    )
    cache_compress: Optional[str] = Field(
        default=None,
        description=(
            "The compression method of the cache file, which can be "
            'specified in ["gzip", "zstd", "lz4"]. If this parameter is '
            "None, the cache file will not be compressed."
        ),
    )
    temp_dir: Optional[str] = Field(
        default=None,
        description=(
            "Path to the temp directory to store intermediate caches when "
            "cache is disabled. In default it's None, so the temp dir will "
            "be specified by system. NOTICE: you should be caution when "
            "setting this argument because it might cause unexpected program "
            "behaviors when this path is set to an unsafe directory."
        ),
    )

    # --------------------------------------------------------
    # checkpoint: checkpoint configuration
    # --------------------------------------------------------
    use_checkpoint: bool = Field(
        default=False,
        description=(
            "Whether to use the checkpoint management to save the latest "
            "version of dataset to work dir when processing. Rerun the same "
            "config will reload the checkpoint and skip ops before it. Cache "
            "will be disabled when it is true . If args of ops before the "
            "checkpoint are changed, all ops will be rerun from the "
            "beginning."
        ),
    )
    checkpoint: CheckpointConfig = Field(
        default_factory=CheckpointConfig,
        description="Enhanced checkpoint configuration for PartitionedRayExecutor.",
    )

    # --------------------------------------------------------
    # tracer: tracing and insight mining
    # --------------------------------------------------------
    open_monitor: bool = Field(
        default=False,
        description=(
            "Whether to open the monitor to trace resource utilization for "
            "each OP during data processing. It's False in default."
        ),
    )
    open_tracer: bool = Field(
        default=False,
        description=(
            "Whether to open the tracer to trace samples changed during "
            "process. It might take more time when opening tracer."
        ),
    )
    op_list_to_trace: List[str] = Field(
        default_factory=list,
        description=(
            "Which ops will be traced by tracer. If it's empty, all ops in "
            "cfg.process will be traced. Only available when open_tracer is "
            "true."
        ),
    )
    trace_num: int = Field(
        default=10,
        description=(
            "Number of samples extracted by tracer to show the dataset "
            "difference before and after a op. Only available when "
            "open_tracer is true."
        ),
    )
    trace_keys: List[str] = Field(
        default_factory=list,
        description=(
            "List of field names to include in trace output. If set, the "
            "specified fields' values will be included in each trace entry. "
            "Only available when open_tracer is true."
        ),
    )
    open_insight_mining: bool = Field(
        default=False,
        description=(
            "Whether to open insight mining to trace the OP-wise stats/tags "
            "changes during process. It might take more time when opening "
            "insight mining."
        ),
    )
    op_list_to_mine: List[str] = Field(
        default_factory=list,
        description=(
            "Which OPs will be applied on the dataset to mine the insights "
            "in their stats changes. Only those OPs that produce stats or "
            "meta are valid. If it's empty, all OPs that produce stats and "
            "meta will be involved. Only available when open_insight_mining "
            "is true."
        ),
    )

    # --------------------------------------------------------
    # op_management: operator fusion and environment management
    # --------------------------------------------------------
    op_fusion: bool = Field(
        default=False,
        description=(
            "Whether to fuse operators that share the same intermediate "
            "variables automatically. Op fusion might reduce the memory "
            "requirements slightly but speed up the whole process."
        ),
    )
    fusion_strategy: str = Field(
        default="probe",
        description=(
            'OP fusion strategy. Support ["greedy", "probe"] now. "greedy" '
            "means keep the basic OP order and put the fused OP to the last "
            'of each fused OP group. "probe" means Data-Juicer will probe '
            "the running speed for each OP at the beginning and reorder the "
            "OPs and fused OPs according to their probed speed (fast to "
            'slow). It\'s "probe" in default.'
        ),
    )
    adaptive_batch_size: bool = Field(
        default=False,
        description=(
            "Whether to use adaptive batch sizes for each OP according to " "the probed results. It's False in default."
        ),
    )
    min_common_dep_num_to_combine: int = Field(
        default=-1,
        description=(
            "The minimum number of common dependencies required to determine "
            "whether to merge two operation environment specifications. If "
            "set to -1, it means no combination of operation environments, "
            "where every OP has its own runtime environment during processing "
            "without any merging. If set to >= 0, environments of OPs that "
            "share at least min_common_dep_num_to_combine common dependencies "
            "will be merged. It will open the operator environment manager to "
            "automatically analyze and merge runtime environment for "
            "different OPs. It helps different OPs share and reuse the same "
            "runtime environment to reduce resource utilization. It's -1 in "
            "default. Only available in ray mode."
        ),
    )
    conflict_resolve_strategy: Literal["split", "overwrite", "latest"] = Field(
        default="split",
        description=(
            "Strategy for resolving dependency conflicts, default is 'split' "
            "strategy. 'split': Keep the two specs split when there is a "
            "conflict. 'overwrite': Overwrite the existing dependency with "
            "one from the later OP. 'latest': Use the latest version of all "
            "specified dependency versions. Only available when "
            "min_common_dep_num_to_combine >= 0."
        ),
    )

    # --------------------------------------------------------
    # process: processing pipeline
    # --------------------------------------------------------
    process: List[Dict] = Field(
        default_factory=list,
        description=(
            "List of several operators with their arguments, these ops will " "be applied to dataset in order"
        ),
    )

    # --------------------------------------------------------
    # distributed: Ray configuration
    # --------------------------------------------------------
    ray_address: str = Field(
        default="auto",
        description="The address of the Ray cluster.",
    )

    # --------------------------------------------------------
    # partition: partitioning configuration
    # --------------------------------------------------------
    partition_size: int = Field(
        default=10000,
        description=("Number of samples per partition for PartitionedRayExecutor " "(legacy flat config)"),
    )
    max_partition_size_mb: int = Field(
        default=128,
        description=("Maximum partition size in MB for PartitionedRayExecutor " "(legacy flat config)"),
    )
    preserve_intermediate_data: bool = Field(
        default=False,
        description="Preserve intermediate data for debugging (legacy flat config)",
    )
    partition: PartitionConfig = Field(
        default_factory=PartitionConfig,
        description="Partition configuration for PartitionedRayExecutor.",
    )
    partition_dir: Optional[str] = Field(
        default=None,
        description=(
            "Directory to store partition files. Supports {work_dir} "
            "placeholder. If not set, defaults to {work_dir}/partitions."
        ),
    )

    # --------------------------------------------------------
    # storage: intermediate storage and resource optimization
    # --------------------------------------------------------
    checkpoint_dir: Optional[str] = Field(
        default=None,
        description="Separate directory for checkpoints (large storage)",
    )
    resource_optimization: ResourceOptimizationConfig = Field(
        default_factory=ResourceOptimizationConfig,
        description="Resource optimization configuration.",
    )
    intermediate_storage: IntermediateStorageConfig = Field(
        default_factory=IntermediateStorageConfig,
        description="Intermediate storage configuration.",
    )

    # --------------------------------------------------------
    # logging: event logging and log management
    # --------------------------------------------------------
    event_logging: EventLoggingConfig = Field(
        default_factory=EventLoggingConfig,
        description="Event logging configuration.",
    )
    max_log_size_mb: int = Field(
        default=100,
        description="Maximum log file size in MB before rotation",
    )
    backup_count: int = Field(
        default=5,
        description="Number of backup log files to keep",
    )
    event_log_dir: Optional[str] = Field(
        default=None,
        description="Separate directory for event logs (fast storage)",
    )

    # --------------------------------------------------------
    # job: job management
    # --------------------------------------------------------
    job_id: Optional[str] = Field(
        default=None,
        description=(
            "Custom job ID for resumption and tracking. If not provided, " "a unique ID will be auto-generated."
        ),
    )
    work_dir: Optional[str] = Field(
        default=None,
        description=(
            "Path to a work directory to store outputs during Data-Juicer "
            "running. It's the directory where export_path is at in default."
        ),
    )

    # --------------------------------------------------------
    # analysis: only for data analysis
    # --------------------------------------------------------
    percentiles: List[float] = Field(
        default_factory=list,
        description=("Percentiles to analyze the dataset distribution. Only used in " "Analysis."),
    )
    export_original_dataset: bool = Field(
        default=False,
        description=(
            "whether to export the original dataset with stats. If you only "
            "need the stats of the dataset, setting it to false could speed "
            "up the exporting."
        ),
    )
    save_stats_in_one_file: bool = Field(
        default=False,
        description=("Whether to save all stats to only one file. Only used in " "Analysis."),
    )

    # --------------------------------------------------------
    # sampling: sandbox / HPO
    # --------------------------------------------------------
    auto_num: int = Field(
        default=1000,
        gt=0,
        description="The number of samples to be analyzed automatically. It's 1000 in default.",
    )
    hpo_config: Optional[str] = Field(
        default=None,
        description="Path to a configuration file when using auto-HPO tool.",
    )
    data_probe_algo: str = Field(
        default="uniform",
        description=(
            'Sampling algorithm to use. Options are "uniform", '
            '"frequency_specified_field_selector", or '
            '"topk_specified_field_selector". Default is "uniform". Only '
            "used for dataset sampling"
        ),
    )
    data_probe_ratio: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "The ratio of the sample size to the original dataset size. "
            "Default is 1.0 (no sampling). Only used for dataset sampling"
        ),
    )


# ============================================================
# Schema query APIs
# ============================================================


def get_json_schema() -> Dict[str, Any]:
    """Return a JSON Schema representation of the full configuration.

    This leverages the ``DJConfig`` Pydantic model to automatically
    generate a complete JSON Schema including all nested structures.
    External agents can use this to discover all available configuration
    parameters and their types.

    Returns:
        A JSON Schema dict compliant with JSON Schema Draft 2020-12.
    """
    return DJConfig.model_json_schema()


def get_defaults() -> Dict[str, Any]:
    """Return a flat dict of {field_name: default_value} for all fields.

    Nested Pydantic sub-models are included as their model instances
    (which can be further serialized with ``.model_dump()``).
    """
    return DJConfig().model_dump()


# ============================================================
# Parser registration
# ============================================================


def register_schema_to_parser(parser: ArgumentParser) -> None:
    """Register all DJConfig fields onto the given ArgumentParser.

    This bridges the Pydantic model back to jsonargparse so that
    ``build_base_parser()`` can remain thin.

    Special handling via ``json_schema_extra``:
    - Fields with ``argparse_action`` (e.g. 'store_true') use
      ``action=`` instead of ``type=``.
    - Fields with ``argparse_nargs`` (e.g. '+') use ``nargs=``
      instead of ``type=``.
    - Nested Pydantic sub-models are registered with ``type=``
      pointing to the sub-model class, letting jsonargparse handle
      the dot-notation expansion automatically.
    - For backward compatibility, nargs fields also register a
      kebab-case alias.
    """
    from pydantic_core import PydanticUndefined

    for field_name, field_info in DJConfig.model_fields.items():
        extra = field_info.json_schema_extra or {}
        action = extra.get(_ARGPARSE_ACTION)
        nargs = extra.get(_ARGPARSE_NARGS)
        description = field_info.description or ""

        # Resolve the actual default value: Pydantic uses
        # PydanticUndefined for fields with default_factory
        if field_info.default is not PydanticUndefined:
            default = field_info.default
        elif field_info.default_factory is not None:
            default = field_info.default_factory()
        else:
            default = None

        kwargs: Dict[str, Any] = {"help": description}

        if action is not None:
            # action-based argument (e.g. --debug with store_true)
            kwargs["action"] = action
        elif nargs is not None:
            # nargs-based argument (e.g. --custom_operator_paths)
            kwargs["nargs"] = nargs
        else:
            # standard typed argument — use the annotation directly
            kwargs["type"] = field_info.annotation
            kwargs["default"] = default

        if action is None and nargs is None:
            kwargs["default"] = default

        parser.add_argument(f"--{field_name}", **kwargs)

        # For backward compatibility, also register kebab-case alias
        # for nargs fields
        if nargs is not None and "_" in field_name:
            kebab_name = field_name.replace("_", "-")
            if kebab_name != field_name:
                alias_kwargs = dict(kwargs)
                alias_kwargs["dest"] = field_name
                parser.add_argument(f"--{kebab_name}", **alias_kwargs)


# ============================================================
# Post-parse normalization
# ============================================================


def _is_pydantic_model_annotation(annotation) -> bool:
    """Check whether *annotation* refers to a Pydantic BaseModel.

    Handles plain ``SubModel`` as well as ``Optional[SubModel]``
    (i.e. ``Union[SubModel, None]``).
    """
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return True
    # Optional[X] is Union[X, None]
    args = getattr(annotation, "__args__", None)
    if args:
        return any(isinstance(a, type) and issubclass(a, BaseModel) for a in args)
    return False


# Field names whose values are Pydantic sub-models and therefore
# arrive as jsonargparse Namespace objects after parsing.  We convert
# them back to plain dicts so that downstream code can keep using
# the established dict-access pattern (e.g. cfg.dataset["configs"]).
_NESTED_MODEL_FIELDS = frozenset(
    field_name
    for field_name, field_info in DJConfig.model_fields.items()
    if _is_pydantic_model_annotation(field_info.annotation)
)


def flatten_nested_namespaces(cfg) -> None:
    """Convert nested Namespace values back to plain dicts **in-place**.

    After ``jsonargparse`` parses a config that contains Pydantic
    sub-models, those fields become ``Namespace`` objects.  The rest
    of the Data-Juicer codebase expects them to be plain ``dict``s
    (e.g. ``cfg.dataset["configs"]``).

    Call this once right before ``init_configs`` returns so that all
    downstream consumers see dicts, not Namespaces.
    """
    from jsonargparse import Namespace as JAPNamespace

    def _namespace_to_dict_recursive(obj):
        """Recursively convert Namespace to dict."""
        if isinstance(obj, JAPNamespace):
            result = {}
            for key in vars(obj):
                result[key] = _namespace_to_dict_recursive(getattr(obj, key))
            return result
        if isinstance(obj, list):
            return [_namespace_to_dict_recursive(item) for item in obj]
        return obj

    for field_name in _NESTED_MODEL_FIELDS:
        value = getattr(cfg, field_name, None)
        if value is not None and isinstance(value, JAPNamespace):
            setattr(cfg, field_name, _namespace_to_dict_recursive(value))
