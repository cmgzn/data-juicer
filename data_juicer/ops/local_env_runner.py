"""Local-mode isolation runner.

Provides subprocess-based environment isolation for operators whose
dependencies conflict with the main process environment.

The package installation backend (``pip`` or ``uv``) is read from
``OPEnvSpec.backend`` so that local isolation stays consistent with
Ray mode, where the same field controls ``runtime_env`` generation.

Parent environment inheritance
------------------------------
Instead of ``--system-site-packages``, a ``.pth`` file managed by
Data-Juicer (``_data_juicer_parent_env.pth``) is written into the
child venv's site-packages directory.  This file explicitly lists the
project root and the parent environment's site-packages so that the
subprocess can import ``data_juicer`` and its dependencies.  The
``.pth`` is rewritten every time the venv is acquired, keeping paths
in sync with the current parent environment.

Subprocess logging
------------------
The subprocess inherits the parent's stdout/stderr for real-time
visibility.  An independent log file is created under
``<work_dir>/isolated_logs/`` for persistent tracing.
"""

import json
import os
import re
import shutil
import site
import subprocess
import sys
import tempfile
from datetime import datetime

from filelock import FileLock
from loguru import logger

# Fixed filename for the parent-env .pth managed by Data-Juicer.
_PARENT_ENV_PTH_NAME = "_data_juicer_parent_env.pth"


def _sanitize_filename(name, max_length=80):
    """Sanitize a string for use in filenames."""
    sanitized = re.sub(r"[^\w\-.]", "_", name)
    return sanitized[:max_length]


def _generate_isolated_log_path(log_dir, spec_hash, op_names):
    """Generate a log file path for an isolated subprocess invocation."""
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    op_summary = _sanitize_filename("_".join(op_names))
    filename = f"isolated_{timestamp}_{spec_hash[:8]}_{op_summary}.log"
    return os.path.join(log_dir, filename)


# ---------------------------------------------------------------------------
# Parent-environment path discovery
# ---------------------------------------------------------------------------


def _discover_parent_site_packages():
    """Return the parent process' site-packages directories.

    These paths describe the Python environment that is running
    Data-Juicer.  They are written into the child venv's ``.pth`` file
    so isolated subprocesses can reuse the same project dependencies.
    """
    candidates = []

    try:
        candidates.extend(site.getsitepackages())
    except AttributeError:
        pass

    try:
        user_site = site.getusersitepackages()
        if user_site:
            candidates.append(user_site)
    except AttributeError:
        pass

    seen = set()
    unique = []
    for path in candidates:
        normalized = os.path.normpath(path)
        if normalized not in seen and os.path.isdir(normalized):
            seen.add(normalized)
            unique.append(normalized)

    return unique


# ---------------------------------------------------------------------------
# .pth management
# ---------------------------------------------------------------------------


def _get_child_site_packages(venv_path):
    """Return the site-packages directory inside *venv_path*."""
    # Standard layout: <venv>/lib/pythonX.Y/site-packages
    lib_dir = os.path.join(venv_path, "lib")
    if os.path.isdir(lib_dir):
        for entry in os.listdir(lib_dir):
            if entry.startswith("python"):
                candidate = os.path.join(lib_dir, entry, "site-packages")
                if os.path.isdir(candidate):
                    return candidate
    # Fallback for non-standard layouts (e.g. Windows)
    fallback = os.path.join(venv_path, "Lib", "site-packages")
    if os.path.isdir(fallback):
        return fallback
    raise FileNotFoundError(f"Cannot locate site-packages directory inside venv: {venv_path}")


def _sync_parent_env_pth(venv_path, project_root, parent_site_packages):
    """Write (overwrite) ``_data_juicer_parent_env.pth`` in the child venv.

    The file contains only plain path lines (no ``import`` statements)
    so that the standard ``site`` module appends them to ``sys.path``
    *after* the child venv's own site-packages, preserving isolation
    priority.
    """
    child_site_packages = _get_child_site_packages(venv_path)

    pth_lines = [project_root] + parent_site_packages
    pth_content = "\n".join(pth_lines) + "\n"

    pth_path = os.path.join(child_site_packages, _PARENT_ENV_PTH_NAME)
    with open(pth_path, "w") as pth_file:
        pth_file.write(pth_content)

    logger.debug(f"Synced {_PARENT_ENV_PTH_NAME} at {pth_path} with {len(pth_lines)} path(s)")


# ---------------------------------------------------------------------------
# VenvManager
# ---------------------------------------------------------------------------


class VenvManager:
    """Manages virtual environments for isolated operators.

    Each unique OPEnvSpec gets its own venv.  The venv is created
    **without** ``--system-site-packages`` so inherited paths remain
    explicit and tied to the current parent process.  A ``.pth`` file
    is written into the child venv's site-packages to inherit the parent
    project environment (project root + parent site-packages).
    """

    def __init__(self, cache_dir=None):
        cache_root = cache_dir or os.path.join(tempfile.gettempdir(), "dj_venvs")
        python_cache_tag = sys.implementation.cache_tag
        self.cache_dir = os.path.join(cache_root, python_cache_tag)
        os.makedirs(self.cache_dir, exist_ok=True)
        self._venv_cache = {}  # spec_hash -> venv_path
        self._project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._parent_site_packages = _discover_parent_site_packages()

    def get_venv_path(self, env_spec):
        """Return the venv directory for *env_spec*, creating it if needed."""
        spec_hash = env_spec.get_hash()
        if spec_hash in self._venv_cache:
            return self._venv_cache[spec_hash]

        venv_path = os.path.join(self.cache_dir, spec_hash)
        complete_path = os.path.join(venv_path, ".complete")
        lock_path = os.path.join(self.cache_dir, f"{spec_hash}.lock")

        with FileLock(lock_path):
            if self._is_complete(venv_path, complete_path):
                # Parent paths can change while /tmp survives, so keep the
                # managed inheritance file synchronized on every acquisition.
                _sync_parent_env_pth(venv_path, self._project_root, self._parent_site_packages)
            else:
                if os.path.lexists(venv_path):
                    logger.warning(f"Removing incomplete isolated venv at {venv_path}")
                    shutil.rmtree(venv_path, ignore_errors=True)

                try:
                    logger.info(f"Creating isolated venv at {venv_path} ...")
                    subprocess.run(
                        [sys.executable, "-m", "venv", venv_path],
                        check=True,
                    )
                    _sync_parent_env_pth(venv_path, self._project_root, self._parent_site_packages)

                    if env_spec.pip_pkgs:
                        venv_python = self._venv_python(venv_path)
                        install_cmd = self._build_install_cmd(
                            venv_python,
                            env_spec.backend,
                            env_spec.pip_pkgs,
                        )
                        logger.info(
                            f"Installing packages in isolated venv "
                            f"(backend={env_spec.backend}): {env_spec.pip_pkgs}"
                        )
                        subprocess.run(install_cmd, check=True)

                    with open(complete_path, "w") as complete_file:
                        complete_file.write("complete\n")
                except Exception:
                    shutil.rmtree(venv_path, ignore_errors=True)
                    raise

        self._venv_cache[spec_hash] = venv_path
        return venv_path

    def get_venv_python(self, env_spec):
        """Return the python executable path for the venv of *env_spec*."""
        return self._venv_python(self.get_venv_path(env_spec))

    @staticmethod
    def _venv_python(venv_path):
        return os.path.join(venv_path, "bin", "python")

    @classmethod
    def _is_complete(cls, venv_path, complete_path):
        return os.path.isfile(complete_path) and os.path.isfile(cls._venv_python(venv_path))

    @staticmethod
    def _build_install_cmd(venv_python, backend, pip_pkgs):
        """Build the install command based on *backend*.

        Mirrors the ``OPEnvSpec.backend`` field used by Ray mode so that
        both execution paths honour the same user configuration.
        """
        if backend == "uv":
            return ["uv", "pip", "install", "--python", venv_python] + pip_pkgs
        # default / fallback: pip
        return [venv_python, "-m", "pip", "install"] + pip_pkgs


# Module-level singleton --------------------------------------------------
_venv_manager = None


def _get_venv_manager():
    global _venv_manager
    if _venv_manager is None:
        _venv_manager = VenvManager()
    return _venv_manager


def reset_venv_manager(cache_dir=None):
    """Reset the singleton (mainly for testing)."""
    global _venv_manager
    _venv_manager = VenvManager(cache_dir=cache_dir) if cache_dir else None


def wrap_op_with_isolation(proxy, env_spec):
    """Replace *proxy*'s ``run`` with a subprocess-based implementation.

    Convenience wrapper for a single proxy.  Delegates to
    :func:`wrap_ops_with_isolation`.
    """
    wrap_ops_with_isolation([proxy], env_spec)


def wrap_ops_with_isolation(proxies, env_spec):
    """Replace ``run`` of each proxy in *proxies* for subprocess execution.

    All *proxies* share the same *env_spec* and will be executed in a
    **single** subprocess invocation.  Only the first proxy ("segment
    leader") actually spawns the subprocess; the remaining proxies
    ("followers") become no-ops whose ``run`` returns the input dataset
    unchanged — their processing has already been handled by the leader's
    subprocess call.

    The leader's ``_isolated_run`` closure reads ``proxy._exporter_config``
    and ``proxy._tracer_config`` (injected by ``DefaultExecutor`` after
    ``load_ops`` returns) to forward exporter/tracer configuration to the
    subprocess.
    """
    venv_python = _get_venv_manager().get_venv_python(env_spec)

    # Build subprocess env: inherit current env, then overlay env_vars
    # from the OPEnvSpec (mirrors Ray's runtime_env["env_vars"]).
    # Parent environment paths are inherited via the .pth file written
    # into the child venv's site-packages — no PYTHONPATH injection.
    sub_env = os.environ.copy()
    sub_env["PYTHONUNBUFFERED"] = "1"

    if env_spec.env_vars:
        sub_env.update(env_spec.env_vars)

    # Working directory (mirrors Ray's runtime_env["working_dir"]).
    sub_cwd = env_spec.working_dir or None

    # Collect the full ops_spec list from all proxies in this segment.
    ops_spec = [{"op_name": p._name, "init_kwargs": p._init_args} for p in proxies]
    op_names_str = ", ".join(p._name for p in proxies)

    # The leader proxy — used to read _exporter_config / _tracer_config
    # at *call time* (they are injected after load_ops returns).
    leader = proxies[0]

    def _isolated_run(dataset, *, exporter=None, tracer=None, **kwargs):
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = os.path.join(tmp_dir, "input_dataset")
            output_path = os.path.join(tmp_dir, "output_dataset")
            op_stats_path = os.path.join(tmp_dir, "op_stats.json")

            dataset.save_to_disk(input_path)

            cmd = [
                venv_python,
                "-m",
                "data_juicer.ops._isolated_worker",
                "--ops_spec",
                json.dumps(ops_spec),
                "--input_path",
                input_path,
                "--output_path",
                output_path,
                "--op_stats_path",
                op_stats_path,
            ]

            if getattr(leader, "_open_monitor", True):
                cmd.append("--open_monitor")

            # Forward exporter/tracer config (read from leader proxy)
            exporter_cfg = getattr(leader, "_exporter_config", None)
            if exporter_cfg is not None:
                cmd.extend(["--exporter_config", json.dumps(exporter_cfg)])

            tracer_cfg = getattr(leader, "_tracer_config", None)
            if tracer_cfg is not None:
                cmd.extend(["--tracer_config", json.dumps(tracer_cfg)])

            # Generate isolated log file path
            log_dir = getattr(leader, "_isolated_log_dir", None)
            log_file = None
            if log_dir:
                op_name_list = [p._name for p in proxies]
                log_file = _generate_isolated_log_path(log_dir, env_spec.get_hash(), op_name_list)
                cmd.extend(["--log_file", log_file])

            logger.info(
                f"Running ops [{op_names_str}] in isolated subprocess" + (f". Log: {log_file}" if log_file else "")
            )
            result = subprocess.run(
                cmd,
                env=sub_env,
                cwd=sub_cwd,
            )

            if result.returncode != 0:
                error_msg = f"Isolated ops [{op_names_str}] failed " f"(rc={result.returncode})"
                if log_file:
                    error_msg += f". Log: {log_file}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            op_stats = []
            if os.path.exists(op_stats_path):
                with open(op_stats_path) as stats_file:
                    op_stats = json.load(stats_file)
            if len(op_stats) != len(proxies):
                logger.warning(
                    f"Isolated ops [{op_names_str}] returned {len(op_stats)} stats "
                    f"for {len(proxies)} proxies. Falling back to outer timing where needed."
                )
            for proxy, stats in zip(proxies, op_stats):
                proxy._isolation_stats = stats

            # Lazy import to avoid circular dependency
            from data_juicer.core.data.dj_dataset import NestedDataset

            # keep_in_memory=True avoids mmap'd Arrow files which
            # are not fork-safe -- subsequent datasets.map(num_proc>=1)
            # in the main process would segfault on the mmap'd data.
            return NestedDataset.load_from_disk(output_path, keep_in_memory=True)

    # Segment leader: runs the subprocess
    leader._run_func = _isolated_run

    # Followers: identity (their work is already done in the leader call)
    def _follower_identity_run(dataset, **kwargs):
        return dataset

    for follower in proxies[1:]:
        follower._run_func = _follower_identity_run
        follower._is_segment_follower = True
