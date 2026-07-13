"""Subprocess entry-point for running isolated operator(s).

Invoked by :mod:`local_env_runner` in a venv python::

    python -m data_juicer.ops._isolated_worker \
        --ops_spec '[{"op_name": "clean_email_mapper", "init_kwargs": {}}]' \
        --input_path /tmp/input_dataset \
        --output_path /tmp/output_dataset \
        [--exporter_config '{"export_path": "/tmp/out.jsonl", ...}'] \
        [--tracer_config '{"work_dir": "/tmp/work", ...}']
"""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Run operator(s) in an isolated environment.")
    parser.add_argument(
        "--ops_spec",
        required=True,
        help="JSON array of operator specs: " '[{"op_name": "...", "init_kwargs": {...}}, ...]',
    )
    parser.add_argument("--input_path", required=True, help="Path to input dataset")
    parser.add_argument("--output_path", required=True, help="Path to output dataset")
    parser.add_argument("--op_stats_path", default=None, help="Path to write per-op execution stats")
    parser.add_argument("--open_monitor", action="store_true", help="Collect per-op resource utilization")
    parser.add_argument(
        "--exporter_config",
        default=None,
        help="JSON-encoded Exporter constructor kwargs (optional)",
    )
    parser.add_argument(
        "--tracer_config",
        default=None,
        help="JSON-encoded Tracer constructor kwargs (optional)",
    )
    parser.add_argument(
        "--log_file",
        default=None,
        help="Path to an independent log file for this subprocess (optional)",
    )
    args = parser.parse_args()

    # Set up an independent loguru file sink if --log_file is provided.
    # The default stderr sink is kept so terminal output remains visible.
    if args.log_file:
        from loguru import logger as _logger

        os.makedirs(os.path.dirname(args.log_file), exist_ok=True)
        _logger.add(args.log_file, level="INFO")

    # Imports are deferred to here so that the venv's site-packages are
    # fully configured before data_juicer is loaded.
    from data_juicer.core.data.dj_dataset import NestedDataset
    from data_juicer.ops.base_op import OPERATORS

    # --- Rebuild exporter/tracer from source config (if provided) ---
    exporter = None
    if args.exporter_config:
        from data_juicer.core.exporter import Exporter

        exporter = Exporter(**json.loads(args.exporter_config))

    tracer = None
    if args.tracer_config:
        from data_juicer.core.tracer.tracer import Tracer

        tracer = Tracer(**json.loads(args.tracer_config), clear_existing=False)

    # --- Deserialize and run operator sequence ---
    ops_spec = json.loads(args.ops_spec)
    dataset = NestedDataset.load_from_disk(args.input_path)
    ops = []

    for spec in ops_spec:
        op_cls = OPERATORS.modules[spec["op_name"]]
        op = op_cls(**spec["init_kwargs"])
        ops.append(op)

    op_stats = []
    dataset = dataset.process(
        ops,
        exporter=exporter,
        tracer=tracer,
        open_monitor=args.open_monitor,
        op_stats_sink=op_stats,
    )
    dataset.save_to_disk(args.output_path)
    if args.op_stats_path:
        with open(args.op_stats_path, "w") as out:
            json.dump(op_stats, out)


if __name__ == "__main__":
    sys.exit(main())
