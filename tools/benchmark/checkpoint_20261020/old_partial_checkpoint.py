import argparse
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import ray
from g4_benchmark import cleanup


def manager(module_path, checkpoint_dir):
    spec = importlib.util.spec_from_file_location("historical_checkpoint", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.RayCheckpointManager(str(checkpoint_dir))


def slow_batch(batch):
    time.sleep(0.25)
    return batch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-checkpoint-module", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--writer-root", type=Path)
    args = parser.parse_args()
    if args.writer_root:
        ray.init(num_cpus=2, include_dashboard=False, log_to_driver=False)
        try:
            data = ray.data.range(20000, override_num_blocks=40).map_batches(
                slow_batch,
                batch_size=500,
                concurrency=1,
                num_cpus=1,
            )
            manager(args.old_checkpoint_module, args.writer_root).save_checkpoint(data, op_idx=0, partition_id=0)
        finally:
            ray.shutdown()
        return
    with tempfile.TemporaryDirectory(prefix="old-partial-") as directory:
        root = Path(directory)
        with (root / "writer.log").open("w") as log:
            child = subprocess.Popen(
                [
                    sys.executable,
                    __file__,
                    "--old-checkpoint-module",
                    str(args.old_checkpoint_module),
                    "--output",
                    str(args.output),
                    "--writer-root",
                    str(root / "checkpoints"),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            deadline = time.monotonic() + 180
            try:
                while child.poll() is None:
                    files = list((root / "checkpoints").rglob("*.parquet"))
                    files = [path for path in files if path.is_file()]
                    if len(files) >= 8:
                        os.killpg(child.pid, signal.SIGKILL)
                        break
                    if time.monotonic() > deadline:
                        raise RuntimeError("Writer did not reach fault point")
                    time.sleep(0.05)
            finally:
                cleanup(child)
        args.output.with_suffix(".writer.log").write_text((root / "writer.log").read_text())
        files = [path for path in (root / "checkpoints").rglob("*.parquet") if path.is_file()]
        ray.init(num_cpus=2, include_dashboard=False, log_to_driver=False)
        try:
            checkpoint = manager(args.old_checkpoint_module, root / "checkpoints")
            latest = checkpoint.find_latest_checkpoint(0)
            loaded = checkpoint.load_checkpoint(op_idx=0, partition_id=0)
            rows = loaded.count() if loaded is not None else None
            result = {
                "expected_rows": 20000,
                "files_at_kill": len(files),
                "loaded_rows": rows,
                "recognized_as_latest": latest is not None,
                "accepted_partial_checkpoint": latest is not None and rows is not None and 0 < rows < 20000,
                "checkpoint_module": str(args.old_checkpoint_module),
                "ray_version": ray.__version__,
            }
            args.output.write_text(json.dumps(result, indent=2))
            print(json.dumps(result))
            assert result["accepted_partial_checkpoint"], "Did not reproduce partial acceptance"
        finally:
            ray.shutdown()


if __name__ == "__main__":
    main()
