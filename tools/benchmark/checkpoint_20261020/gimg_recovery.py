import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml
from g4_benchmark import cleanup, observe, save, verify_sources, wait_idle
from gimg_benchmark import INPUT_FIELDS, STATS, compare, read_rows, recipe


def snapshot(job):
    root = job / "checkpoints" / "partition_recovery"
    commits = [json.loads(path.read_bytes()) for path in sorted((root / "commits").glob("*.json"))]
    manifests = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (root / "commits").glob("*.json")
    }
    export = job / "out.jsonl"
    shards = list(export.rglob("*.json")) if export.is_dir() else ([export] if export.exists() else [])
    files = [path for path in root.rglob("*") if path.is_file()]
    return {
        "manifest_sha256": manifests,
        "commits": len(commits),
        "by_stage": {
            str(stage): {
                "commits": sum(item["stage"] == stage for item in commits),
                "consumed_rows": sum(
                    stop - start for item in commits if item["stage"] == stage for _, start, stop in item["consumed"]
                ),
                "output_rows": sum(
                    file["rows"] for item in commits if item["stage"] == stage for file in item["files"]
                ),
            }
            for stage in range(4)
        },
        "checkpoint_files": len(files),
        "checkpoint_bytes": sum(path.stat().st_size for path in files),
        "partial_export_rows": sum(len(path.read_text().splitlines()) for path in shards),
    }


def run_cli(run, phase, source, config, env, kill_at):
    stop = threading.Event()
    with (run / f"{phase}.log").open("x") as log:
        args = [sys.executable, "-B", str(source / "tools/process_data.py"), "--config", str(config)]
        if phase == "recover":
            args += ["--resume", "job"]
        child = subprocess.Popen(
            args, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        save(run / f"{phase}-process.json", {"pid": child.pid, "pgid": child.pid, "start_unix": time.time()})
        start = time.monotonic()
        monitor = threading.Thread(
            target=observe, args=(stop, child.pid, run / f"{phase}-resources.jsonl"), daemon=True
        )
        monitor.start()
        killed = False
        try:
            try:
                child.wait(timeout=kill_at if kill_at is not None else 3600)
            except subprocess.TimeoutExpired:
                killed = kill_at is not None
        finally:
            elapsed = time.monotonic() - start
            stop.set()
            remaining = cleanup(child)
            monitor.join(timeout=25)
    samples = [json.loads(line) for line in (run / f"{phase}-resources.jsonl").read_text().splitlines()]
    result = {
        "seconds": elapsed,
        "returncode": child.returncode,
        "killed": killed,
        "foreign_gpu": any(sample.get("foreign_gpu_pids") for sample in samples),
        "gpu_pids": sorted({pid for sample in samples for pid in sample.get("gpu_pids", [])}),
        "stopped_owned_processes": len(remaining),
    }
    save(run / f"{phase}-result.json", result)
    if result["foreign_gpu"]:
        raise RuntimeError("Foreign GPU contention observed; timing rejected")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--kill-at", type=int, nargs="+", default=[180, 400])
    args = parser.parse_args()
    root = args.root
    lock = (root / "benchmark.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    sources = verify_sources(root)
    full = root / "full-200000"
    results = root / "recovery-200000"
    results.mkdir(exist_ok=False)
    environment = json.loads((root / "environment.json").read_text())
    specs = json.loads((root / "spec.json").read_text())
    inputs = {row["id"]: row for row in read_rows(full / "input")}
    baseline = json.loads((full / "baseline.json").read_text())
    expected_ids = [row["id"] for row in baseline]
    source = root / "code" / "new"
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
    save(
        results / "manifest.json",
        {
            "heads": sources["heads"],
            "input_rows": len(inputs),
            "unique_images": 13394,
            "input_manifest": json.loads((full / "manifest.json").read_text()),
            "spec": specs["new-S14-s1024"],
            "kill_at_seconds": args.kill_at,
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "method": "one fault trial per kill point; kill only owned CLI process group; fresh CLI --resume job through export",
        },
    )
    outcomes = []
    previous = set()
    for kill_at in args.kill_at:
        run = results / f"new-k{kill_at}"
        run.mkdir()
        config = run / "recipe.yaml"
        config.write_text(
            yaml.safe_dump(
                recipe(specs["new-S14-s1024"], full / "input", environment["models"], run, len(inputs)), sort_keys=False
            )
        )
        wait_idle(run, previous)
        crash = run_cli(run, "crash", source, config, env, kill_at)
        previous.update(crash["gpu_pids"])
        assert crash["killed"], "Run finished before injected fault"
        before = snapshot(run / "job")
        save(run / "state-at-kill.json", before)
        assert before["commits"] > 0, "Fault happened before any durable commit"
        wait_idle(run, previous)
        recover = run_cli(run, "recover", source, config, env, None)
        previous.update(recover["gpu_pids"])
        assert recover["returncode"] == 0, "Recovery CLI failed"
        after = snapshot(run / "job")
        save(run / "state-after.json", after)
        assert all(after["manifest_sha256"].get(key) == value for key, value in before["manifest_sha256"].items())
        rows = read_rows(run / "job" / "out.jsonl")
        ids = [row["id"] for row in rows]
        assert ids == expected_ids, "Missing, unexpected or duplicate output IDs"
        for row in rows:
            assert all(row.get(key) == inputs[row["id"]][key] for key in INPUT_FIELDS), "Input fields changed"
        view = [{"id": row["id"], STATS: row[STATS]} for row in rows]
        difference = compare(baseline, view, environment["score_tolerance"])
        assert after["by_stage"]["0"]["consumed_rows"] == len(inputs)
        outcome = {
            "kill_at": kill_at,
            "crash": crash,
            "recover": recover,
            "state_at_kill": before,
            "checkpoint_after": after,
            "output_rows": len(rows),
            "duplicate_rows": len(ids) - len(set(ids)),
            "missing_ids": len(set(expected_ids) - set(ids)),
            "max_stat_difference": difference,
            "kept_ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
            "original_commits_unchanged": True,
            "validation_passed": True,
        }
        outcomes.append(outcome)
        save(results / "results.json", outcomes)
        print(
            json.dumps(
                {key: value for key, value in outcome.items() if key not in ("state_at_kill", "checkpoint_after")}
            ),
            flush=True,
        )
    verify_sources(root)


if __name__ == "__main__":
    main()
