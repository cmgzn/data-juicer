import hashlib
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

PPU_SMI = "/usr/local/PPU_SDK/ppu-smi/bin/ppu-smi"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False))


def verify_sources(root):
    manifest = json.loads((root / "verified-sources.json").read_text())
    for arm, source in manifest["sources"].items():
        directory = root / "code" / arm
        for path in directory.rglob("*"):
            name = str(path.relative_to(directory))
            if path.is_file() and name not in source["files_sha256"]:
                if path.suffix == ".pyc" and "__pycache__" in path.parts:
                    path.unlink()
                elif path.suffix in {".py", ".pyc", ".so", ".pyd", ".zip", ".egg"}:
                    raise RuntimeError(f"Unexpected executable source: {arm}/{name}")
        for name, digest in source["files_sha256"].items():
            if sha256(directory / name) != digest:
                raise RuntimeError(f"Source changed: {arm}/{name}")
    return manifest


def owned_processes(pgid):
    lines = subprocess.check_output(["ps", "-eo", "pid,pgid,stat,comm,args"], text=True, timeout=10).splitlines()
    return [
        line
        for line in lines[1:]
        if len(line.split()) >= 4 and line.split()[1] == str(pgid) and not line.split()[2].startswith("Z")
    ]


def cleanup(child):
    processes = owned_processes(child.pid)
    if processes:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    child.wait()
    deadline = time.monotonic() + 10
    while owned_processes(child.pid):
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Owned process group {child.pid} did not stop")
        time.sleep(0.1)
    return processes


def gpu_pids(text):
    return sorted(
        set(int(pid) for pid in re.findall(r"^\|\s*\d+\s+(?:N/A|\d+)\s+(?:N/A|\d+)\s+(\d+)\s+", text, re.MULTILINE))
    )


def wait_idle(run, previous_gpu_pids):
    deadline = time.monotonic() + 60
    with (run / "idle-checks.jsonl").open("w") as log:
        while True:
            status = subprocess.check_output([PPU_SMI], text=True, timeout=15)
            log.write(json.dumps({"time": time.time(), "ppu": status}) + "\n")
            log.flush()
            pids = gpu_pids(status)
            if "No running processes found" in status:
                return status
            if not pids or set(pids) - previous_gpu_pids:
                raise RuntimeError("PPU occupied by an unknown process; timing not started")
            for pid in pids:
                stat = Path(f"/proc/{pid}/stat")
                try:
                    state = stat.read_text().rsplit(")", 1)[1].split()[0]
                except FileNotFoundError:
                    continue
                if state != "Z":
                    raise RuntimeError(f"Previously observed GPU PID {pid} is still active")
            if time.monotonic() >= deadline:
                raise RuntimeError("PPU driver did not release exited benchmark processes within 60s")
            time.sleep(0.5)


def observe(stop, pgid, path):
    with path.open("w") as stream:
        while not stop.is_set():
            entry = {"time": time.time()}
            try:
                entry["ppu"] = subprocess.check_output([PPU_SMI], text=True, timeout=10)
                entry["owned_processes"] = owned_processes(pgid)
                entry["gpu_pids"] = gpu_pids(entry["ppu"])
                entry["foreign_gpu_pids"] = []
                for pid in entry["gpu_pids"]:
                    try:
                        if os.getpgid(pid) != pgid:
                            entry["foreign_gpu_pids"].append(pid)
                    except ProcessLookupError:
                        pass
            except (subprocess.SubprocessError, OSError) as error:
                entry["error"] = str(error)
            stream.write(json.dumps(entry) + "\n")
            stream.flush()
            stop.wait(5)
