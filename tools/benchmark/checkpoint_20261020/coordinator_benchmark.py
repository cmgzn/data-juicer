import argparse
import json
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ray

from data_juicer.core.executor.partition_protocol import (
    SOURCE_SEQ,
    CommitLog,
    LocalStore,
)
from data_juicer.core.executor.ray_partition_runner import _CommitCoordinator


class LatencyStore(LocalStore):
    def put_if_absent(self, key, data):
        time.sleep(0.01)
        return super().put_if_absent(key, data)

    def get(self, key):
        time.sleep(0.01)
        return super().get(key)


def run(root, store_class, concurrency, iteration):
    rows = 2000
    store = store_class(str(root / f"{store_class.__name__}-{concurrency}-{iteration}"))
    coordinator = _CommitCoordinator.remote(store, 1, rows)
    ray.get(coordinator.plan.remote())

    def commit(index):
        return ray.get(coordinator.commit.remote(0, ((SOURCE_SEQ, index, index + 1),), (), ()))

    try:
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            commits = list(pool.map(commit, range(rows)))
        elapsed = time.perf_counter() - start
        assert len({item.seq for item in commits}) == rows
        assert ray.get(coordinator.summary.remote()) == {0: (rows, rows, 0)}
        start = time.perf_counter()
        log = CommitLog(store, 1, rows)
        load = time.perf_counter() - start
        assert log.summary() == {0: (rows, rows, 0)}
        return {
            "storage": store_class.__name__,
            "concurrency": concurrency,
            "warmup": iteration == 0,
            "commits": rows,
            "seconds": elapsed,
            "commits_per_second": rows / elapsed,
            "parallel_load_seconds": load,
        }
    finally:
        ray.kill(coordinator)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("coordinator-results.json"))
    args = parser.parse_args()
    ray.init(num_cpus=2, include_dashboard=False, log_to_driver=False)
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix="coordinator-bench-") as directory:
            for store_class in (LocalStore, LatencyStore):
                for concurrency in (1, 16, 64):
                    for iteration in (0, 1):
                        result = run(Path(directory), store_class, concurrency, iteration)
                        results.append(result)
                        print(json.dumps(result), flush=True)
        args.output.write_text(json.dumps(results, indent=2))
    finally:
        ray.shutdown()
