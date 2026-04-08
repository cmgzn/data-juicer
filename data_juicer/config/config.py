import argparse
import copy
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from argparse import ArgumentError
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Union

import yaml
from jsonargparse import (
    ActionConfigFile,
    ArgumentParser,
    Namespace,
    dict_to_namespace,
    namespace_to_dict,
)
from jsonargparse._typehints import ActionTypeHint
from loguru import logger

from data_juicer.ops.base_op import OPERATORS
from data_juicer.ops.op_fusion import FUSION_STRATEGIES
from data_juicer.utils.constant import RAY_JOB_ENV_VAR
from data_juicer.utils.logger_utils import setup_logger
from data_juicer.utils.mm_utils import SpecialTokens
from data_juicer.utils.ray_utils import is_ray_mode

global_cfg = None
global_parser = None


@contextmanager
def timing_context(description):
    start_time = time.time()
    yield
    elapsed_time = time.time() - start_time
    # Use a consistent format that won't be affected by logger reconfiguration
    logger.debug(f"{description} took {elapsed_time:.2f} seconds")


def _generate_module_name(abs_path):
    """Generate a module name based on the absolute path of the file."""
    return os.path.splitext(os.path.basename(abs_path))[0]


def load_custom_operators(paths):
    """Dynamically load custom operator modules or packages in the specified path."""
    for path in paths:
        abs_path = os.path.abspath(path)
        if os.path.isfile(abs_path):
            module_name = _generate_module_name(abs_path)
            if module_name in sys.modules:
                existing_path = sys.modules[module_name].__file__
                raise RuntimeError(
                    f"Module '{module_name}' already loaded from '{existing_path}'. "
                    f"Conflict detected while loading '{abs_path}'."
                )
            try:
                spec = importlib.util.spec_from_file_location(module_name, abs_path)
                if spec is None:
                    raise RuntimeError(f"Failed to create spec for '{abs_path}'")
                module = importlib.util.module_from_spec(spec)
                # register the module first to avoid recursive import issues
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            except Exception as e:
                raise RuntimeError(f"Error loading '{abs_path}' as '{module_name}': {e}")

        elif os.path.isdir(abs_path):
            if not os.path.isfile(os.path.join(abs_path, "__init__.py")):
                raise ValueError(f"Package directory '{abs_path}' must contain __init__.py")
            package_name = os.path.basename(abs_path)
            parent_dir = os.path.dirname(abs_path)
            if package_name in sys.modules:
                existing_path = sys.modules[package_name].__path__[0]
                raise RuntimeError(
                    f"Package '{package_name}' already loaded from '{existing_path}'. "
                    f"Conflict detected while loading '{abs_path}'."
                )
            original_sys_path = sys.path.copy()
            try:
                sys.path.insert(0, parent_dir)
                importlib.import_module(package_name)
                # record the loading path of the package (for subsequent conflict detection)
                sys.modules[package_name].__loaded_from__ = abs_path
            except Exception as e:
                raise RuntimeError(f"Error loading package '{abs_path}': {e}")
            finally:
                sys.path = original_sys_path
        else:
            raise ValueError(f"Path '{abs_path}' is neither a file nor a directory")


def build_base_parser() -> ArgumentParser:
    parser = ArgumentParser(default_env=True, default_config_files=None, usage=argparse.SUPPRESS)

    # required but mutually exclusive args group
    # These are parser-behavior arguments, not configuration fields,
    # so they are registered manually rather than via the schema.
    required_group = parser.add_mutually_exclusive_group(required=True)
    required_group.add_argument("--config", action=ActionConfigFile, help="Path to a dj basic configuration file.")
    required_group.add_argument(
        "--auto",
        action="store_true",
        help="Whether to use an auto analyzing "
        "strategy instead of a specific data "
        "recipe. If a specific config file is "
        "given by --config arg, this arg is "
        "disabled. Only available for Analyzer.",
    )

    # Register all configuration fields from the declarative schema
    from data_juicer.config.schema import register_schema_to_parser

    register_schema_to_parser(parser)

    return parser


def init_configs(args: Optional[List[str]] = None, which_entry: object = None, load_configs_only=False):
    """
    initialize the jsonargparse parser and parse configs from one of:
        1. POSIX-style commands line args;
        2. config files in yaml (json and jsonnet supersets);
        3. environment variables
        4. hard-coded defaults

    :param args: list of params, e.g., ['--config', 'cfg.yaml'], default None.
    :param which_entry: which entry to init configs (executor/analyzer)
    :param load_configs_only: whether to load the configs only, not including backing up config files, display them, and
        setting up logger.
    :return: a global cfg object used by the DefaultExecutor or Analyzer
    """
    if args is None:
        args = sys.argv[1:]
    with timing_context("Total config initialization time"):
        with timing_context("Initializing parser"):
            parser = build_base_parser()
            # Filter out non-essential arguments for initial parsing
            essential_args = []
            if args:
                i = 0
                while i < len(args):
                    arg = args[i]
                    # Handle --help, --config, and --auto in first pass
                    if arg == "--help":
                        essential_args.append(arg)
                    elif arg == "--config":
                        essential_args.append(arg)
                        # The next argument must be the config file path
                        if i + 1 < len(args):
                            essential_args.append(args[i + 1])
                            i += 1
                    elif arg == "--auto":
                        essential_args.append(arg)
                    i += 1

            # Parse essential arguments first
            essential_cfg = parser.parse_args(args=essential_args)

            # Now add remaining arguments based on essential config
            used_ops = None
            if essential_cfg.config:
                # Load config file to determine which operators are used
                with open(os.path.abspath(essential_cfg.config[0])) as f:
                    config_data = yaml.safe_load(f)
                    used_ops = set()
                    if "process" in config_data:
                        for op in config_data["process"]:
                            used_ops.add(list(op.keys())[0])

                # Add remaining arguments
                ops_sorted_by_types = sort_op_by_types_and_names(OPERATORS.modules.items())

                # Only add arguments for used operators
                _collect_config_info_from_class_docs(
                    [(op_name, op_class) for op_name, op_class in ops_sorted_by_types if op_name in used_ops], parser
                )

            # Parse all arguments
            with timing_context("Parsing arguments"):
                cfg = parser.parse_args(args=args)

                if cfg.executor_type == "ray":
                    os.environ[RAY_JOB_ENV_VAR] = "1"

                if cfg.custom_operator_paths:
                    load_custom_operators(cfg.custom_operator_paths)

                # check the entry
                from data_juicer.core.analyzer import Analyzer

                if not isinstance(which_entry, Analyzer) and cfg.auto:
                    err_msg = "--auto argument can only be used for analyzer!"
                    logger.error(err_msg)
                    raise NotImplementedError(err_msg)

        with timing_context("Initializing setup from config"):
            cfg = init_setup_from_cfg(cfg, load_configs_only)

        with timing_context("Updating operator process"):
            cfg = update_op_process(cfg, parser, used_ops)

        # Validate config for resumption if job_id is provided
        if not load_configs_only and hasattr(cfg, "job_id") and cfg.job_id:
            # Check if this is a resumption attempt by looking for existing job directory
            if cfg.work_dir and os.path.exists(cfg.work_dir):
                logger.info(f"🔍 Checking for job resumption: {cfg.job_id}")
                cfg._same_yaml_config = validate_config_for_resumption(cfg, cfg.work_dir, args)
            else:
                # New job, set flag to True
                cfg._same_yaml_config = True

        # copy the config file into the work directory
        if not load_configs_only:
            config_backup(cfg)

        # show the final config tables before the process started
        if not load_configs_only:
            display_config(cfg)

        # Convert nested Namespace objects (from Pydantic sub-models)
        # back to plain dicts so downstream code can keep using
        # dict-access patterns (e.g. cfg.dataset["configs"]).
        from data_juicer.config.schema import flatten_nested_namespaces

        flatten_nested_namespaces(cfg)

        global global_cfg, global_parser
        global_cfg = cfg
        global_parser = parser

        if cfg.get("debug", False):
            logger.debug("In DEBUG mode.")

        return cfg


def update_ds_cache_dir_and_related_vars(new_ds_cache_path):
    from pathlib import Path

    from datasets import config

    # update the HF_DATASETS_CACHE
    config.HF_DATASETS_CACHE = Path(new_ds_cache_path)
    # and two more PATHS that depend on HF_DATASETS_CACHE
    # - path to store downloaded datasets (e.g. remote datasets)
    config.DEFAULT_DOWNLOADED_DATASETS_PATH = os.path.join(config.HF_DATASETS_CACHE, config.DOWNLOADED_DATASETS_DIR)
    config.DOWNLOADED_DATASETS_PATH = Path(config.DEFAULT_DOWNLOADED_DATASETS_PATH)
    # - path to store extracted datasets (e.g. xxx.jsonl.zst)
    config.DEFAULT_EXTRACTED_DATASETS_PATH = os.path.join(
        config.DEFAULT_DOWNLOADED_DATASETS_PATH, config.EXTRACTED_DATASETS_DIR
    )
    config.EXTRACTED_DATASETS_PATH = Path(config.DEFAULT_EXTRACTED_DATASETS_PATH)


def init_setup_from_cfg(cfg: Namespace, load_configs_only=False):
    """
    Do some extra setup tasks after parsing config file or command line.

    1. create working directory and logs directory
    2. update cache directory
    3. update checkpoint and `temp_dir` of tempfile

    :param cfg: an original cfg
    :param cfg: an updated cfg
    """

    # Handle S3 paths differently from local paths
    if cfg.export_path.startswith("s3://"):
        # For S3 paths, keep as-is (don't use os.path.abspath)
        # If work_dir is not provided, use a default local directory for logs/checkpoints
        if cfg.work_dir is None:
            # Use a default local work directory for S3 exports
            # This is where logs, checkpoints, and other local artifacts will be stored
            cfg.work_dir = os.path.abspath("./outputs")
            logger.info(f"Using default work_dir [{cfg.work_dir}] for S3 export_path [{cfg.export_path}]")
    else:
        # For local paths, convert to absolute path
        cfg.export_path = os.path.abspath(cfg.export_path)
        if cfg.work_dir is None:
            cfg.work_dir = os.path.dirname(cfg.export_path)

    # Call resolve_job_directories to finalize all job-related paths
    cfg = resolve_job_id(cfg)
    cfg = resolve_job_directories(cfg)

    timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime(time.time()))
    if not load_configs_only:
        # For S3 paths, use a simplified export path for log filename
        if cfg.export_path.startswith("s3://"):
            # Extract bucket and key from S3 path for log filename
            s3_path_parts = cfg.export_path.replace("s3://", "").split("/", 1)
            export_rel_path = s3_path_parts[1] if len(s3_path_parts) > 1 else s3_path_parts[0]
        else:
            export_rel_path = os.path.relpath(cfg.export_path, start=cfg.work_dir)

        # Ensure event_log_dir (logs/) exists - this is where logs are actually saved
        if not os.path.exists(cfg.event_log_dir):
            os.makedirs(cfg.event_log_dir, exist_ok=True)
        logfile_name = f"export_{export_rel_path}_time_{timestamp}.txt"
        setup_logger(
            save_dir=cfg.event_log_dir,
            filename=logfile_name,
            level="DEBUG" if cfg.get("debug", False) else "INFO",
            redirect=cfg.get("executor_type", "default") == "default",
        )

    # check and get dataset dir
    if cfg.get("dataset_path", None) and os.path.exists(cfg.dataset_path):
        logger.info("dataset_path config is set and a valid local path")
        cfg.dataset_path = os.path.abspath(cfg.dataset_path)
    elif cfg.get("dataset_path", "") == "" and cfg.get("dataset", None):
        logger.info("dataset_path config is empty; dataset is present")
    else:
        logger.warning(
            f"dataset_path [{cfg.get('dataset_path', '')}] is not a valid "
            f"local path, AND dataset is not present. "
            f"Please check and retry, otherwise we "
            f"will treat dataset_path as a remote dataset or a "
            f"mixture of several datasets."
        )

    # check number of processes np
    from data_juicer.utils.resource_utils import cpu_count

    sys_cpu_count = cpu_count(cfg)
    if cfg.get("np", None) and cfg.np > sys_cpu_count:
        logger.warning(
            f"Number of processes `np` is set as [{cfg.np}], which "
            f"is larger than the cpu count [{sys_cpu_count}]. Due "
            f"to the data processing of Data-Juicer is a "
            f"computation-intensive task, we recommend to set it to"
            f" a value <= cpu count. Set it to [{sys_cpu_count}] "
            f"here."
        )
        cfg.np = sys_cpu_count

    # whether or not to use cache management
    # disabling the cache or using checkpoint explicitly will turn off the
    # cache management.
    if not cfg.get("use_cache", True) or cfg.get("use_checkpoint", False):
        logger.warning("Cache management of datasets is disabled.")
        from datasets import disable_caching

        disable_caching()
        cfg.use_cache = False

        # disabled cache compression when cache is disabled
        if cfg.cache_compress:
            logger.warning("Disable cache compression due to disabled cache.")
            cfg.cache_compress = None

        # when disabling cache, enable the temp_dir argument
        logger.warning(f"Set temp directory to store temp files to " f"[{cfg.temp_dir}].")
        import tempfile

        if cfg.temp_dir is not None and not os.path.exists(cfg.temp_dir):
            os.makedirs(cfg.temp_dir, exist_ok=True)
        tempfile.tempdir = cfg.temp_dir

    # The checkpoint mode is not compatible with op fusion for now.
    if cfg.get("op_fusion", False):
        cfg.use_checkpoint = False
        cfg.fusion_strategy = cfg.fusion_strategy.lower()
        if cfg.fusion_strategy not in FUSION_STRATEGIES:
            raise NotImplementedError(
                f"Unsupported OP fusion strategy [{cfg.fusion_strategy}]. " f"Should be one of {FUSION_STRATEGIES}."
            )

    # update huggingface datasets cache directory only when ds_cache_dir is set
    from datasets import config

    if cfg.get("ds_cache_dir", None) is not None:
        logger.warning(
            f"Set dataset cache directory to {cfg.ds_cache_dir} "
            f"using the ds_cache_dir argument, which is "
            f"{config.HF_DATASETS_CACHE} before based on the env "
            f"variable HF_DATASETS_CACHE."
        )
        update_ds_cache_dir_and_related_vars(cfg.ds_cache_dir)
    else:
        cfg.ds_cache_dir = str(config.HF_DATASETS_CACHE)

    # add all filters that produce stats
    if cfg.get("auto", False):
        cfg.process = load_ops_with_stats_meta()

    # Apply text_key modification during initializing configs
    # users can freely specify text_key for different ops using `text_key`
    # otherwise, set arg text_key of each op to text_keys
    cfg.text_keys = cfg.get("text_keys", "text")
    if isinstance(cfg.text_keys, list):
        text_key = cfg.text_keys[0]
    else:
        text_key = cfg.text_keys

    SpecialTokens.image = cfg.get("image_special_token", SpecialTokens.image)
    SpecialTokens.audio = cfg.get("audio_special_token", SpecialTokens.audio)
    SpecialTokens.video = cfg.get("video_special_token", SpecialTokens.video)
    SpecialTokens.eoc = cfg.get("eoc_special_token", SpecialTokens.eoc)

    op_attrs = {
        "text_key": text_key,
        "image_key": cfg.get("image_key", "images"),
        "audio_key": cfg.get("audio_key", "audios"),
        "video_key": cfg.get("video_key", "videos"),
        "image_bytes_key": cfg.get("image_bytes_key", "image_bytes"),
        "turbo": cfg.get("turbo", False),
        "skip_op_error": cfg.get("skip_op_error", True),
        "auto_op_parallelism": cfg.get("auto_op_parallelism", True),
        "work_dir": cfg.work_dir,
    }
    if not is_ray_mode():
        op_attrs.update({"num_proc": cfg.get("np", None)})
    cfg.process = update_op_attr(cfg.process, op_attrs)

    return cfg


def load_ops_with_stats_meta():
    import pkgutil

    import data_juicer.ops.filter as djfilter
    from data_juicer.ops import NON_STATS_FILTERS, TAGGING_OPS

    stats_filters = [
        {filter_name: {}}
        for _, filter_name, _ in pkgutil.iter_modules(djfilter.__path__)
        if filter_name not in NON_STATS_FILTERS.modules
    ]
    meta_ops = [{op_name: {}} for op_name in TAGGING_OPS.modules]
    return stats_filters + meta_ops


def update_op_attr(op_list: list, attr_dict: dict = None):
    if not attr_dict:
        return op_list
    updated_op_list = []
    for op in op_list:
        for op_name in op:
            args = op[op_name]
            if args is None:
                args = attr_dict
            else:
                for key in attr_dict:
                    if key not in args or args[key] is None:
                        args[key] = attr_dict[key]
            op[op_name] = args
        updated_op_list.append(op)
    return updated_op_list


def _collect_config_info_from_class_docs(configurable_ops, parser):
    """
    Add ops and its params to parser for command line with optimized performance.
    """
    with timing_context("Collecting operator configuration info"):
        op_params = {}

        # Add arguments for all provided operators
        for op_name, op_class in configurable_ops:
            params = parser.add_class_arguments(
                theclass=op_class, nested_key=op_name, fail_untyped=False, instantiate=False
            )
            op_params[op_name] = params

        return op_params


def sort_op_by_types_and_names(op_name_classes):
    """
    Split ops items by op type and sort them to sub-ops by name, then concat
    together.

    :param op_name_classes: a list of op modules
    :return: sorted op list , each item is a pair of op_name and
        op_class
    """
    with timing_context("Sorting operators by types and names"):
        mapper_ops = [(name, c) for (name, c) in op_name_classes if "mapper" in name]
        filter_ops = [(name, c) for (name, c) in op_name_classes if "filter" in name]
        deduplicator_ops = [(name, c) for (name, c) in op_name_classes if "deduplicator" in name]
        selector_ops = [(name, c) for (name, c) in op_name_classes if "selector" in name]
        grouper_ops = [(name, c) for (name, c) in op_name_classes if "grouper" in name]
        aggregator_ops = [(name, c) for (name, c) in op_name_classes if "aggregator" in name]
        ops_sorted_by_types = (
            sorted(mapper_ops)
            + sorted(filter_ops)
            + sorted(deduplicator_ops)
            + sorted(selector_ops)
            + sorted(grouper_ops)
            + sorted(aggregator_ops)
        )
        return ops_sorted_by_types


def update_op_process(cfg, parser, used_ops=None):
    """
    Update operator process configuration with optimized performance.

    Args:
        cfg: Configuration namespace
        parser: Argument parser
        used_ops: Set of operator names that are actually used in the config
    """
    if used_ops is None:
        used_ops = set(OPERATORS.modules.keys())

    # Get command line args for operators in one pass
    option_in_commands = set()
    full_option_in_commands = set()

    for arg in parser.args:
        if arg.startswith("--"):
            parts = arg.split("--")[1].split(".")
            op_name = parts[0]
            if op_name in used_ops:
                option_in_commands.add(op_name)
                full_option_in_commands.add(arg.split("=")[0])

    if cfg.process is None:
        cfg.process = []

    # Create direct mapping of operator names to their configs
    op_configs = {}
    for op in cfg.process:
        op_configs.setdefault(list(op.keys())[0], []).append(op[list(op.keys())[0]])

    # Process each used operator
    temp_cfg = cfg
    op_name_count = {}
    for op_name in used_ops:
        op_config = op_configs.get(op_name)
        op_config_list = []
        if op_name not in option_in_commands:
            # Update op params if set
            if op_config:
                for op_c in op_config:
                    temp_cfg = parser.merge_config(dict_to_namespace({op_name: op_c}), temp_cfg)
                    oc = namespace_to_dict(temp_cfg)[op_name]
                    op_config_list.append(oc)
                temp_cfg = parser.merge_config(dict_to_namespace({op_name: op_config_list}), temp_cfg)
        else:
            # Remove args that will be overridden by command line
            if op_config:
                for op_c in op_config:
                    for full_option in full_option_in_commands:
                        key = full_option.split(".")[1]
                        if key in op_c:
                            op_c.pop(key)
                    temp_cfg = parser.merge_config(dict_to_namespace({op_name: op_c}), temp_cfg)
                    oc = namespace_to_dict(temp_cfg)[op_name]
                    op_config_list.append(oc)
                temp_cfg = parser.merge_config(dict_to_namespace({op_name: op_config_list}), temp_cfg)

        # Update op params
        internal_op_para = temp_cfg.get(op_name)
        # Update or add the operator to process list
        if op_name in op_configs:
            # Update existing operator
            for i, op_in_process in enumerate(cfg.process):
                if isinstance(internal_op_para, list):
                    if list(op_in_process.keys())[0] == op_name:
                        if op_name not in op_name_count:
                            op_name_count[op_name] = 0
                        else:
                            op_name_count[op_name] += 1
                        cfg.process[i] = {
                            op_name: (
                                None
                                if internal_op_para is None
                                else namespace_to_dict(internal_op_para[op_name_count[op_name]])
                            )
                        }
        else:
            # Add new operator
            cfg.process.append({op_name: None if internal_op_para is None else namespace_to_dict(internal_op_para)})

    # Optimize type checking
    recognized_args = {
        action.dest for action in parser._actions if hasattr(action, "dest") and isinstance(action, ActionTypeHint)
    }

    # check the op params via type hint
    temp_parser = copy.deepcopy(parser)

    temp_args = namespace_to_arg_list(temp_cfg, includes=recognized_args, excludes=["config"])

    if temp_cfg.config:
        temp_args.extend(["--config", os.path.abspath(temp_cfg.config[0])])
    else:
        temp_args.append("--auto")

    # validate
    temp_parser.parse_args(temp_args)

    return cfg


def namespace_to_arg_list(namespace, prefix="", includes=None, excludes=None):
    arg_list = []

    for key, value in vars(namespace).items():
        if issubclass(type(value), Namespace):
            nested_args = namespace_to_arg_list(value, f"{prefix}{key}.")
            arg_list.extend(nested_args)
        elif value is not None:
            concat_key = f"{prefix}{key}"
            if includes is not None and concat_key not in includes:
                continue
            if excludes is not None and concat_key in excludes:
                continue
            if key == "process":
                arg_list.append(f"--{concat_key}={json.dumps(value, ensure_ascii=False)}")
            else:
                arg_list.append(f"--{concat_key}={value}")

    return arg_list


def save_cli_arguments(cfg: Namespace):
    """Save CLI arguments to cli.yaml in the work directory."""
    if not hasattr(cfg, "work_dir") or not cfg.work_dir:
        return

    # Get the original CLI arguments if available
    original_args = getattr(cfg, "_original_args", None)
    if not original_args:
        # Try to reconstruct from sys.argv if available
        import sys

        original_args = sys.argv[1:] if len(sys.argv) > 1 else []

    if not original_args:
        logger.warning("No CLI arguments available to save")
        return

    # Create cli.yaml in work directory
    cli_path = os.path.join(cfg.work_dir, "cli.yaml")

    # Convert args to a simple format
    cli_data = {"arguments": original_args}

    # Save as YAML
    import yaml

    with open(cli_path, "w") as f:
        yaml.dump(cli_data, f, default_flow_style=False, indent=2)

    logger.info(f"💾 Saved CLI arguments to: {cli_path}")


def validate_config_for_resumption(cfg: Namespace, work_dir: str, original_args: List[str] = None) -> bool:
    """Validate that the current config matches the job's saved config for safe resumption.

    Does verbatim comparison between:
    1. Original config.yaml + cli.yaml (saved during job creation)
    2. Current config (from current command)

    Sets cfg._same_yaml_config = True/False for the executor to use.
    """
    try:
        from pathlib import Path

        # Find the original config file in the work directory
        config_files = list(Path(work_dir).glob("*.yaml")) + list(Path(work_dir).glob("*.yml"))
        if not config_files:
            logger.warning(f"No config file found in work directory: {work_dir}")
            cfg._same_yaml_config = False
            return False

        # Find the original config.yaml (not cli.yaml)
        original_config_file = None
        for config_file in config_files:
            if config_file.name != "cli.yaml":
                original_config_file = config_file
                break

        if not original_config_file:
            logger.warning(f"No original config file found in work directory: {work_dir}")
            cfg._same_yaml_config = False
            return False

        # 1. Direct file comparison for config files
        current_config_file = cfg.config[0] if hasattr(cfg, "config") and cfg.config else None
        if not current_config_file:
            logger.error("No current config file found")
            cfg._same_yaml_config = False
            return False

        with open(original_config_file, "r") as f:
            original_config_content = f.read()
        with open(current_config_file, "r") as f:
            current_config_content = f.read()

        config_match = original_config_content.strip() == current_config_content.strip()

        # 2. Per-key comparison for CLI arguments
        cli_file = Path(work_dir) / "cli.yaml"
        cli_config = {}
        if cli_file.exists():
            with open(cli_file, "r") as f:
                cli_data = yaml.safe_load(f)
                cli_config = _parse_cli_to_config(cli_data.get("arguments", []))

        # Get current CLI arguments from the original args passed to init_configs
        current_cli_args = original_args
        if not current_cli_args:
            # Fallback: try to get from sys.argv
            import sys

            current_cli_args = sys.argv[1:] if len(sys.argv) > 1 else []

        current_cli_config = _parse_cli_to_config(current_cli_args)

        # Compare CLI arguments per key
        cli_differences = []
        all_cli_keys = set(cli_config.keys()) | set(current_cli_config.keys())
        excluded_keys = {"config", "_original_args", "backed_up_config_path", "_same_yaml_config", "job_id", "work_dir"}

        for key in all_cli_keys:
            if key in excluded_keys:
                continue

            original_value = cli_config.get(key)
            current_value = current_cli_config.get(key)

            if original_value != current_value:
                cli_differences.append({"key": key, "original": original_value, "current": current_value})

        cli_match = len(cli_differences) == 0

        if not config_match or not cli_match:
            logger.error("❌ Config validation failed - configurations don't match:")
            if not config_match:
                logger.error("   [config] Config file content differs")
            if not cli_match:
                logger.error("   [cli] CLI arguments differ:")
                for diff in cli_differences:
                    logger.error(f"      {diff['key']}: {diff['original']} → {diff['current']}")
            logger.error("💡 Use the same config file and CLI arguments for resumption")
            cfg._same_yaml_config = False
            return False

        logger.info("✅ Config validation passed - configurations match exactly")
        cfg._same_yaml_config = True
        return True

    except Exception as e:
        logger.error(f"Error validating config for resumption: {e}")
        cfg._same_yaml_config = False
        return False


def _parse_cli_to_config(cli_args: list) -> dict:
    """
    Parse CLI arguments into config dictionary format using the global parser.

    This ensures proper handling of:
    - --key=value syntax
    - Arguments with spaces
    - Multiple values (nargs='+')
    - Complex type conversions

    Args:
        cli_args: List of CLI arguments to parse

    Returns:
        Dictionary of parsed configuration values
    """
    global global_parser

    if not cli_args:
        return {}

    # If global_parser is available, use it for robust parsing
    if global_parser:
        try:
            # For comparison purposes, we only care about override arguments, not the config file
            # Filter out --config and --auto since they're handled separately
            filtered_args = []
            i = 0
            while i < len(cli_args):
                arg = cli_args[i]
                if arg == "--config" or arg == "--auto":
                    # Skip --config/--auto and its value (if any)
                    if i + 1 < len(cli_args) and not cli_args[i + 1].startswith("--"):
                        i += 2
                    else:
                        i += 1
                elif arg.startswith("--"):
                    # Keep other flags
                    filtered_args.append(arg)
                    i += 1
                elif filtered_args:
                    # Keep values that follow flags
                    filtered_args.append(arg)
                    i += 1
                else:
                    # Skip positional arguments (e.g., pytest test names)
                    i += 1

            # If no override args, return empty dict
            if not filtered_args:
                return {}

            # Add --auto to satisfy the required argument (we'll filter it out later)
            temp_cli_args = ["--auto"] + filtered_args

            # Use parse_known_args to handle unrecognized arguments gracefully
            parsed_cfg, unknown = global_parser.parse_known_args(temp_cli_args)
            # Convert to dict for comparison
            config_dict = namespace_to_dict(parsed_cfg)

            # Remove arguments we don't want to compare
            config_dict.pop("config", None)
            config_dict.pop("auto", None)

            return config_dict
        except (Exception, SystemExit) as e:
            logger.debug(f"Failed to parse CLI args with global_parser: {e}. Falling back to manual parsing.")

    # Fallback to improved manual parsing if parser not available
    config = {}
    i = 0

    while i < len(cli_args):
        arg = cli_args[i]

        if arg.startswith("--"):
            # Handle --key=value syntax
            if "=" in arg:
                key, value = arg[2:].split("=", 1)
                config[key] = _parse_value(value)
                i += 1
            else:
                key = arg[2:]

                # Collect all values until next flag
                values = []
                j = i + 1
                while j < len(cli_args) and not cli_args[j].startswith("--"):
                    values.append(cli_args[j])
                    j += 1

                if values:
                    # If multiple values, keep as list; otherwise, single value
                    if len(values) == 1:
                        config[key] = _parse_value(values[0])
                    else:
                        config[key] = [_parse_value(v) for v in values]
                    i = j
                else:
                    # Boolean flag (no value)
                    config[key] = True
                    i += 1
        else:
            i += 1

    return config


def _parse_value(value: str):
    """Parse a string value to its appropriate type."""
    # Try to parse as different types
    if value.lower() in ["true", "false"]:
        return value.lower() == "true"

    try:
        # Try int first
        if "." not in value and "e" not in value.lower():
            return int(value)
    except ValueError:
        pass

    try:
        # Try float
        return float(value)
    except ValueError:
        pass

    # Return as string
    return value


def config_backup(cfg: Namespace):
    if not cfg.get("config", None):
        return
    cfg_path = os.path.abspath(cfg.config[0])

    # Use the backed_up_config_path which should be set by resolve_job_directories
    if hasattr(cfg, "backed_up_config_path"):
        target_path = cfg.backed_up_config_path
    else:
        # Fallback: use work_dir with original filename
        work_dir = cfg.work_dir
        original_config_name = os.path.basename(cfg_path)
        target_path = os.path.join(work_dir, original_config_name)

    if not os.path.exists(target_path):
        logger.info(f"Back up the input config file [{cfg_path}] to [{target_path}]")
        shutil.copyfile(cfg_path, target_path)
    else:
        logger.info(f"Config file [{cfg_path}] already exists at [{target_path}]")

    # Also save CLI arguments
    save_cli_arguments(cfg)


def display_config(cfg: Namespace):
    import pprint

    from tabulate import tabulate

    table_header = ["key", "values"]

    # remove ops outside the process list for better displaying
    shown_cfg = cfg.clone()
    for op in OPERATORS.modules.keys():
        _ = shown_cfg.pop(op)

    # construct the table as 2 columns
    config_table = [(k, pprint.pformat(v, compact=True)) for k, v in shown_cfg.items()]
    table = tabulate(config_table, headers=table_header, tablefmt="fancy_grid")

    logger.info("Configuration table: ")
    print(table)


def export_config(
    cfg: Namespace,
    path: str,
    format: str = "yaml",
    skip_none: bool = True,
    skip_check: bool = True,
    overwrite: bool = False,
    multifile: bool = True,
):
    """
    Save the config object, some params are from jsonargparse

    :param cfg: cfg object to save (Namespace type)
    :param path: the save path
    :param format: 'yaml', 'json', 'json_indented', 'parser_mode'
    :param skip_none: Whether to exclude entries whose value is None.
    :param skip_check: Whether to skip parser checking.
    :param overwrite: Whether to overwrite existing files.
    :param multifile: Whether to save multiple config files
        by using the __path__ metas.

    :return:
    """
    # remove ops outside the process list for better displaying
    cfg_to_export = cfg.clone()
    cfg_to_export = prepare_cfgs_for_export(cfg_to_export)

    global global_parser
    if not global_parser:
        init_configs()  # enable the customized type parser
    if isinstance(cfg_to_export, Namespace):
        cfg_to_export = namespace_to_dict(cfg_to_export)
    global_parser.save(
        cfg=cfg_to_export,
        path=path,
        format=format,
        skip_none=skip_none,
        skip_check=skip_check,
        overwrite=overwrite,
        multifile=multifile,
    )

    logger.info(f"Saved the configuration in {path}")


def merge_config(ori_cfg: Namespace, new_cfg: Namespace):
    """
    Merge configuration from new_cfg into ori_cfg

    :param ori_cfg: the original configuration object, whose type is
        expected as namespace from jsonargparse
    :param new_cfg: the configuration object to be merged, whose type is
        expected as dict or namespace from jsonargparse

    :return: cfg_after_merge
    """
    try:
        ori_specified_op_names = set()
        ori_specified_op_idx = {}  # {op_name: op_order}

        for op_order, op_in_process in enumerate(ori_cfg.process):
            op_name = list(op_in_process.keys())[0]
            ori_specified_op_names.add(op_name)
            ori_specified_op_idx[op_name] = op_order

        for new_k, new_v in new_cfg.items():
            # merge parameters other than `cfg.process` and DJ-OPs
            if new_k in ori_cfg and new_k != "process" and "." not in new_k:
                logger.info("=" * 15)
                logger.info(f"Before merging, the cfg item is: " f"{new_k}: {ori_cfg[new_k]}")
                ori_cfg[new_k] = new_v
                logger.info(f"After merging,  the cfg item is: " f"{new_k}: {new_v}")
                logger.info("=" * 15)
            else:
                # merge parameters of DJ-OPs into cfg.process
                # for nested style, e.g., `remove_table_text_mapper.min_col: 2`
                key_as_groups = new_k.split(".")
                if len(key_as_groups) > 1 and key_as_groups[0] in ori_specified_op_names:
                    op_name, para_name = key_as_groups[0], key_as_groups[1]
                    op_order = ori_specified_op_idx[op_name]
                    ori_cfg_val = ori_cfg.process[op_order][op_name][para_name]
                    logger.info("=" * 15)
                    logger.info(f"Before merging, the cfg item is: " f"{new_k}: {ori_cfg_val}")
                    ori_cfg.process[op_order][op_name][para_name] = new_v
                    logger.info(f"After merging,  the cfg item is: " f"{new_k}: {new_v}")
                    logger.info("=" * 15)

        ori_cfg = init_setup_from_cfg(ori_cfg)

        # copy the config file into the work directory
        config_backup(ori_cfg)

        return ori_cfg

    except ArgumentError:
        logger.error("Config merge failed")


def prepare_side_configs(ori_config: Union[str, Namespace, Dict]):
    """
    parse the config if ori_config is a string of a config file path with
        yaml, yml or json format

    :param ori_config: a config dict or a string of a config file path with
        yaml, yml or json format

    :return: a config dict
    """

    if isinstance(ori_config, str):
        # config path
        if ori_config.endswith(".yaml") or ori_config.endswith(".yml"):
            with open(ori_config) as fin:
                config = yaml.safe_load(fin)
        elif ori_config.endswith(".json"):
            with open(ori_config) as fin:
                config = json.load(fin)
        else:
            raise TypeError(
                f"Unrecognized config file type: [{ori_config}]. "
                f'Should be one of the types [".yaml", ".yml", '
                f'".json"].'
            )
    elif isinstance(ori_config, dict) or isinstance(ori_config, Namespace):
        config = ori_config
    else:
        raise TypeError(f"Unrecognized side config type: [{type(ori_config)}].")

    return config


def get_init_configs(cfg: Union[Namespace, Dict], load_configs_only: bool = True):
    """
    set init configs of data-juicer for cfg
    """
    if isinstance(cfg, Namespace):
        cfg = namespace_to_dict(cfg)

    # Remove internal attributes that are not part of the configuration schema
    # to avoid validation errors when re-initializing the config
    if isinstance(cfg, dict):
        cfg = cfg.copy()
        # Remove internal attributes that are added during config processing
        internal_attrs = [
            "_user_provided_job_id",
            "_same_yaml_config",
            "metadata_dir",
            "results_dir",
            "event_log_file",
            "job_summary_file",
            "backed_up_config_path",
        ]
        for attr in internal_attrs:
            cfg.pop(attr, None)

    # Use a unique temporary file per call to avoid race conditions when
    # multiple requests are processed concurrently (e.g. in API service mode).
    # The file is automatically deleted after the with-block exits.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", prefix="job_dj_config_", delete=True) as temp_f:
        json.dump(prepare_cfgs_for_export(cfg), temp_f)
        temp_f.flush()
        inited_dj_cfg = init_configs(["--config", temp_f.name], load_configs_only=load_configs_only)
    return inited_dj_cfg


def get_default_cfg():
    """Get default config values from schema definitions.

    Returns a Namespace populated with the default value for every
    configuration field defined in the schema.  This replaces the
    previous approach of reading a subset from config_min.yaml.
    """
    from data_juicer.config.schema import get_defaults

    cfg = Namespace()
    for key, value in get_defaults().items():
        setattr(cfg, key, value)
    return cfg


def prepare_cfgs_for_export(cfg):
    # 1. convert Path to str
    if "config" in cfg:
        cfg["config"] = [str(p) for p in cfg["config"]]
    # 2. remove level-1 op cfgs outside the process list
    for op in OPERATORS.modules.keys():
        if op in cfg:
            _ = cfg.pop(op)
    return cfg


def resolve_job_id(cfg):
    """Resolve or auto-generate job_id and set it on cfg."""
    job_id = getattr(cfg, "job_id", None)

    # Track whether job_id was user-provided
    if job_id is not None:
        # User explicitly provided a job_id
        setattr(cfg, "_user_provided_job_id", True)
    else:
        # No job_id provided by user
        setattr(cfg, "_user_provided_job_id", False)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        short_hash = uuid.uuid4().hex[:6]
        job_id = f"{timestamp}_{short_hash}"
        setattr(cfg, "job_id", job_id)
    return cfg


def validate_work_dir_config(work_dir: str) -> None:
    """
    Validate work_dir configuration to ensure {job_id} placement rules are followed.

    Args:
        work_dir: The work_dir string to validate

    Raises:
        ValueError: If {job_id} is not at the end of the path
    """
    if "{job_id}" in work_dir:
        # Check if {job_id} is at the end of the path
        if not work_dir.rstrip("/").endswith("{job_id}"):
            raise ValueError(
                f"Invalid work_dir configuration: '{{job_id}}' must be the last part of the path. "
                f"Current: '{work_dir}'. "
                f"Expected format: 'path/to/directory/{{job_id}}'"
            )


def resolve_job_directories(cfg):
    """
    Centralize directory resolution and placeholder substitution. Assumes job_id is already set.

    Job Directory Rules:
    - If work_dir contains '{job_id}' placeholder, it MUST be the last part of the path
    - Examples:
      ✅ work_dir: "./outputs/my_project/{job_id}"     # Valid
      ✅ work_dir: "/data/experiments/{job_id}"        # Valid
      ❌ work_dir: "./outputs/{job_id}/results"        # Invalid - {job_id} not at end
      ❌ work_dir: "./{job_id}/outputs/data"           # Invalid - {job_id} not at end

    - If work_dir does NOT contain '{job_id}', job_id will be appended automatically
    - Examples:
      work_dir: "./outputs/my_project" → work_dir: "./outputs/my_project/20250804_143022_abc123"

    After resolution, work_dir will always include job_id at the end.
    """
    # 1. placeholder map
    placeholder_map = {"work_dir": cfg.work_dir, "job_id": getattr(cfg, "job_id", "")}

    # 2. Validate {job_id} placement in work_dir before substitution
    original_work_dir = cfg.work_dir
    validate_work_dir_config(original_work_dir)

    # 3. substitute placeholders in all relevant paths (change-detection loop)
    max_passes = 10
    for _ in range(max_passes):
        changed = False
        for key in ["work_dir", "event_log_dir", "checkpoint_dir", "export_path", "dataset_path", "partition_dir"]:
            val = getattr(cfg, key, None)
            if isinstance(val, str):
                new_val = val.format(**placeholder_map)
                if new_val != val:
                    setattr(cfg, key, new_val)
                    changed = True
        # update placeholder_map in case work_dir or job_id changed
        placeholder_map = {"work_dir": cfg.work_dir, "job_id": getattr(cfg, "job_id", "")}
        if not changed:
            break
    else:
        raise RuntimeError("Too many placeholder substitution passes (possible recursive placeholders?)")

    # 4. directory resolution
    job_id = getattr(cfg, "job_id", None)
    if not job_id:
        raise ValueError("job_id must be set before resolving job directories.")

    # Ensure work_dir always includes job_id at the end
    # If work_dir already ends with job_id (from placeholder substitution), keep it as-is
    # Otherwise, append job_id automatically
    if not (cfg.work_dir.endswith(job_id) or os.path.basename(cfg.work_dir) == job_id):
        cfg.work_dir = os.path.join(cfg.work_dir, job_id)

    # All job-specific directories are under work_dir
    if getattr(cfg, "event_log_dir", None) is None:
        cfg.event_log_dir = os.path.join(cfg.work_dir, "logs")
    if getattr(cfg, "checkpoint_dir", None) is None:
        cfg.checkpoint_dir = os.path.join(cfg.work_dir, "checkpoints")
    if getattr(cfg, "partition_dir", None) is None:
        cfg.partition_dir = os.path.join(cfg.work_dir, "partitions")
    cfg.metadata_dir = os.path.join(cfg.work_dir, "metadata")
    cfg.results_dir = os.path.join(cfg.work_dir, "results")
    cfg.event_log_file = os.path.join(cfg.work_dir, "events.jsonl")
    cfg.job_summary_file = os.path.join(cfg.work_dir, "job_summary.json")
    # Set backed_up_config_path using original config filename
    if hasattr(cfg, "config") and cfg.config:
        original_config_name = os.path.basename(cfg.config[0])
        cfg.backed_up_config_path = os.path.join(cfg.work_dir, original_config_name)
    else:
        cfg.backed_up_config_path = os.path.join(cfg.work_dir, "config.yaml")

    return cfg
