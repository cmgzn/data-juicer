import argparse
import fcntl
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml
from g4_benchmark import sha256  # noqa: E402
from g4_benchmark import cleanup, observe, save, verify_sources, wait_idle  # noqa: E402

STATS = "__dj__stats__"
INPUT_FIELDS = ["id", "images", "text", "source", "label"]


def recipe(spec, data, models, run, rows):
    model_args = {item["op"]: {item["arg"]: item["path"]} for item in models}
    op_args = {
        "image_shape_filter": {"min_width": 160, "min_height": 160},
        "image_nsfw_filter": {"max_score": 0.5},
        "image_watermark_filter": {"prob_threshold": 0.8},
        "image_text_similarity_filter": {"min_score": 0.2, "max_score": 1.0},
    }
    process = []
    for name, args in op_args.items():
        cfg = dict(args, **model_args.get(name, {}))
        if name in model_args:
            cfg.update(accelerator="cuda", ray_execution_mode="actor", num_cpus=1, batch_size=spec.get("batch", 32))
            cfg.update(spec["gpu"])
            cfg.update(spec.get("ops", {}).get(name, {}))
        else:
            cfg.update(batch_size=spec.get("cpu_batch", 64))
            cfg.update(spec.get("cpu", {}))
        process.append({name: cfg})
    ckpt = spec["ckpt"]
    cfg = {
        "project_name": "gimg",
        "executor_type": "ray_partitioned",
        "ray_address": "local",
        "dataset_path": str(data),
        "work_dir": str(run / "{job_id}"),
        "export_path": str(run / "{job_id}" / "out.jsonl"),
        "checkpoint_dir": str(run / "{job_id}" / "checkpoints"),
        "job_id": "job",
        "np": spec.get("np", 8),
        "auto_op_parallelism": False,
        "skip_op_error": False,
        "op_fusion": False,
        "keep_stats_in_res_ds": True,
        "override_num_blocks": math.ceil(rows / spec.get("block_rows", 64)),
        "checkpoint": {"enabled": ckpt, "strategy": "every_op" if ckpt else "disabled"},
        "partition": dict(spec["partition"]),
        "process": process,
    }
    cfg.update(spec.get("top", {}))
    return cfg


def read_rows(path):
    files = sorted(path.rglob("*.json*")) if path.is_dir() else [path]
    rows = []
    for file in files:
        if file.is_file():
            rows.extend(json.loads(line) for line in file.read_text().splitlines() if line.strip())
    return sorted(rows, key=lambda row: row["id"])


def compare(reference, actual, tolerance):
    maximum = 0.0

    def check(left, right, path=""):
        nonlocal maximum
        if isinstance(left, dict):
            if not isinstance(right, dict) or left.keys() != right.keys():
                raise AssertionError(f"Key mismatch at {path}")
            for key in left:
                check(left[key], right[key], f"{path}/{key}")
        elif isinstance(left, list):
            if not isinstance(right, list) or len(left) != len(right):
                raise AssertionError(f"Length mismatch at {path}")
            for i, (a, b) in enumerate(zip(left, right)):
                check(a, b, f"{path}/{i}")
        elif isinstance(left, float) or isinstance(right, float):
            if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (left, right)):
                raise AssertionError(f"Invalid number at {path}")
            maximum = max(maximum, abs(left - right))
            if not math.isclose(left, right, abs_tol=tolerance["absolute"], rel_tol=tolerance["relative"]):
                raise AssertionError(f"Number mismatch at {path}: {left} != {right}")
        elif type(left) is not type(right) or left != right:
            raise AssertionError(f"Value mismatch at {path}: {left!r} != {right!r}")

    check(reference, actual)
    return maximum


def markers(spec):
    version, ckpt = spec["version"], spec["ckpt"]
    if not ckpt:
        return [], ["Checkpointing selected", "GPU execution grouping:", "Checkpoint strategy: every_op"]
    return {
        "new": (["Checkpointing selected; skipping ordinary input partitioning."], []),
        "old": (["Checkpoint strategy: every_op"], []),
        "main": (["Checkpoint strategy: every_op", "GPU execution grouping:"], []),
    }[version]


def validate_run(run, spec, inputs, baseline, tolerance):
    rows = read_rows(run / "job" / "out.jsonl")
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)) or not set(ids) <= inputs.keys():
        raise AssertionError("Duplicate or unknown output IDs")
    for row in rows:
        if any(row.get(key) != inputs[row["id"]][key] for key in INPUT_FIELDS):
            raise AssertionError(f'Input field changed on row {row["id"]}')
        if not isinstance(row.get(STATS), dict):
            raise AssertionError(f'Missing stats on row {row["id"]}')
    view = [{"id": row["id"], STATS: row[STATS]} for row in rows]
    difference = 0.0 if baseline is None else compare(baseline, view, tolerance)
    log_text = (run / "run.log").read_text(errors="replace")
    required, forbidden = markers(spec)
    for marker in forbidden:
        if marker in log_text:
            raise AssertionError(f"Unexpected protocol marker: {marker}")
    for marker in required:
        if marker not in log_text:
            raise AssertionError(f"Execution protocol not verified: {marker}")
    samples = [json.loads(line) for line in (run / "resources.jsonl").read_text().splitlines()]
    if any(sample.get("foreign_gpu_pids") for sample in samples):
        raise AssertionError("Observed foreign GPU contention; timing rejected")
    observed = sorted({pid for sample in samples for pid in sample.get("gpu_pids", [])})
    if not observed:
        raise AssertionError("No GPU worker observed; inspect raw PPU samples")
    files = (
        [p for p in (run / "job" / "checkpoints").rglob("*") if p.is_file()]
        if (run / "job" / "checkpoints").exists()
        else []
    )
    rounded = json.dumps(
        [
            {
                "id": r["id"],
                "s": {k: [round(x, 3) for x in v] if isinstance(v, list) else v for k, v in sorted(r[STATS].items())},
            }
            for r in rows
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    evidence = {
        "output_rows": len(rows),
        "max_stat_difference": difference,
        "kept_ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
        "rounded_stats_sha256": hashlib.sha256(rounded.encode()).hexdigest(),
        "checkpoint_files": len(files),
        "checkpoint_bytes": sum(p.stat().st_size for p in files),
        "validation_passed": True,
        "observed_gpu_pids": observed,
        "protocol_markers": required,
    }
    return view, evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--labels", nargs="+", required=True)
    parser.add_argument("--rows", type=int, default=13394)
    parser.add_argument("--rows-per-file", type=int, default=64)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--warmups", type=int, default=0)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--seed", type=int, default=1075)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--keep-going", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    results = args.results.resolve()
    lock = (root / "benchmark.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    sources = verify_sources(root)
    environment = json.loads((root / "environment.json").read_text())
    if not (root / "ready.json").exists():
        raise RuntimeError("Complete setup before running benchmarks")
    if sha256(Path(environment["data"]["path"])) != environment["data"]["sha256"]:
        raise RuntimeError("Input changed")
    for item in environment["models"]:
        for name, digest in item["files_sha256"].items():
            if sha256(Path(item["path"]) / name) != digest:
                raise RuntimeError(f'Model changed: {item["op"]}/{name}')
    specs = json.loads(args.spec.read_text())
    unknown = set(args.labels) - specs.keys()
    if unknown:
        raise ValueError(f"Unknown labels: {sorted(unknown)}")
    results.mkdir(exist_ok=False)
    data = results / "input"
    data.mkdir()
    original = Path(environment["data"]["path"]).read_text().splitlines()
    if args.rows > len(original):
        records = [json.loads(line) for line in original]
        lines = [json.dumps(dict(records[i % len(records)], id=i), ensure_ascii=False) for i in range(args.rows)]
    else:
        lines = original[: args.rows]
    for i in range(0, len(lines), args.rows_per_file):
        (data / f"part-{i // args.rows_per_file:05d}.jsonl").write_text(
            "\n".join(lines[i : i + args.rows_per_file]) + "\n"
        )
    inputs = {row["id"]: row for row in map(json.loads, lines)}
    save(results / "spec.json", {label: specs[label] for label in args.labels})
    manifest = {
        "heads": sources["heads"],
        "input_sha256": hashlib.sha256("\n".join(lines).encode()).hexdigest(),
        "rows": len(lines),
        "unique_source_images": min(args.rows, len(original)),
        "repeated_source": args.rows > len(original),
        "rows_per_file": args.rows_per_file,
        "seed": args.seed,
        "score_tolerance": environment["score_tolerance"],
        "labels": args.labels,
        "timing": "fresh CLI process through export; excludes input creation, model prewarm and validation",
        "runner_sha256": sha256(Path(__file__)),
        "baseline": str(args.baseline) if args.baseline else None,
        "recipes": {},
    }
    save(results / "environment.json", environment)
    baseline = json.loads(args.baseline.read_text()) if args.baseline else None
    outcomes = []
    previous_gpu_pids = set()
    rng = random.Random(args.seed)
    for iteration in range(args.warmups + args.repeats):
        labels = args.labels[:]
        rng.shuffle(labels)
        for label in labels:
            spec = specs[label]
            version = spec["version"]
            run = results / f"{label}-r{iteration:02d}"
            run.mkdir()
            cfg = recipe(spec, data, environment["models"], run, args.rows)
            config = run / "recipe.yaml"
            config.write_text(yaml.safe_dump(cfg, sort_keys=False))
            manifest["recipes"][run.name] = {"path": str(config), "sha256": sha256(config), "version": version}
            save(results / "manifest.json", manifest)
            before = wait_idle(run, previous_gpu_pids)
            (run / "ppu-before.txt").write_text(before)
            source = root / "code" / version
            env = dict(
                os.environ,
                PYTHONPATH=str(source),
                HF_HUB_OFFLINE="1",
                TRANSFORMERS_OFFLINE="1",
                OMP_NUM_THREADS="1",
                OPENBLAS_NUM_THREADS="1",
                RAY_DEDUP_LOGS="0",
                RAY_TMPDIR="/mnt/data/cmgzn.cmx/g20rt",
                TOKENIZERS_PARALLELISM="false",
                PYTHONDONTWRITEBYTECODE="1",
            )
            start = time.monotonic()
            stop = threading.Event()
            timed_out = False
            with (run / "run.log").open("w") as log:
                child = subprocess.Popen(
                    [sys.executable, "-B", str(source / "tools/process_data.py"), "--config", str(config)],
                    cwd=source,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                monitor = None
                try:
                    save(run / "process.json", {"pid": child.pid, "pgid": child.pid, "start_unix": time.time()})
                    monitor = threading.Thread(
                        target=observe, args=(stop, child.pid, run / "resources.jsonl"), daemon=True
                    )
                    monitor.start()
                    child.wait(timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                finally:
                    seconds = time.monotonic() - start
                    stop.set()
                    if monitor is not None:
                        monitor.join(timeout=25)
                    remaining = cleanup(child)
                    save(run / "cleanup.json", {"stopped_owned_processes": remaining, "all_stopped": True})
            outcome = {
                "label": label,
                "version": version,
                "head": sources["heads"][version],
                "iteration": iteration,
                "warmup": iteration < args.warmups,
                "returncode": child.returncode,
                "timed_out": timed_out,
                "wall_seconds": seconds,
                "input_rows_per_second": args.rows / seconds,
                "log": str(run / "run.log"),
            }
            outcomes.append(outcome)
            previous_gpu_pids.update(int(line.split()[0]) for line in remaining)
            try:
                if child.returncode:
                    raise RuntimeError("CLI failed; inspect retained log")
                view, evidence = validate_run(run, spec, inputs, baseline, environment["score_tolerance"])
                outcome.update(evidence)
                previous_gpu_pids.update(evidence["observed_gpu_pids"])
                if baseline is None:
                    baseline = view
                    (results / "baseline.json").write_text(json.dumps(view))
            except Exception as error:
                outcome.update(validation_passed=False, validation_error=f"{type(error).__name__}: {error}")
                save(results / "results.json", outcomes)
                print(json.dumps(outcome), flush=True)
                if not args.keep_going:
                    raise
                continue
            save(results / "results.json", outcomes)
            print(json.dumps(outcome), flush=True)
    verify_sources(root)
    summary = {}
    for label in args.labels:
        values = [
            o["wall_seconds"]
            for o in outcomes
            if o["label"] == label and not o["warmup"] and o.get("validation_passed")
        ]
        if values:
            summary[label] = {
                "runs": len(values),
                "median_seconds": statistics.median(values),
                "min_seconds": min(values),
                "max_seconds": max(values),
            }
    save(results / "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
