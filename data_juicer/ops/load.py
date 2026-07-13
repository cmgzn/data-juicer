"""Operator loading with optional environment isolation.

When ``op_env_manager`` is provided **and** running in local (non-Ray)
mode, operators whose merged environment spec declares pip dependencies
are **not instantiated** in the main process.  Instead, an
:class:`IsolatedOpProxy` placeholder is created, and its ``run`` method
is replaced with a subprocess+venv execution by
:func:`~data_juicer.ops.local_env_runner.wrap_op_with_isolation`.

The venv is created without ``--system-site-packages``.  Instead, a
``.pth`` file (``_data_juicer_parent_env.pth``) managed by Data-Juicer
is written into the child venv's site-packages to explicitly inherit
the parent project environment.  This mirrors Ray mode, where each env
group gets its own runtime_env virtualenv.

In Ray mode (or when no ``op_env_manager`` is given), the existing
behaviour is preserved: all operators are instantiated eagerly.
"""

import inspect
import types

from .base_op import OPERATORS
from .op_env import (
    analyze_lazy_loaded_requirements_for_code_file,
    op_requirements_to_op_env_spec,
    resolve_local_env_spec,
)

# ---------------------------------------------------------------------------
# Helpers (module-level so tests can import them directly)
# ---------------------------------------------------------------------------


def _get_class_env_spec(op_cls):
    """Compute :class:`OPEnvSpec` from the class itself (no instantiation).

    Relies on ``_name`` and ``_requirements`` being class attributes set
    by the registry / the operator definition.
    """
    auto_analyzed = analyze_lazy_loaded_requirements_for_code_file(inspect.getfile(op_cls))
    return op_requirements_to_op_env_spec(op_cls._name, op_cls._requirements, auto_analyzed)


# ---------------------------------------------------------------------------
# Proxy
# ---------------------------------------------------------------------------


class IsolatedOpProxy:
    """Lightweight stand-in for an operator that will run in a subprocess.

    The pipeline iterates over ops and calls ``op.run(dataset)``.  For
    isolated ops we avoid instantiation in the main process; this proxy
    holds the class reference and constructor kwargs instead.  Its
    ``run`` is replaced by
    :func:`~data_juicer.ops.local_env_runner.wrap_op_with_isolation`.

    The proxy exposes the minimum interface required by
    ``NestedDataset.process`` (``use_cuda``, ``run``, ``_op_cfg``,
    ``_name``).  Everything else is resolved lazily via ``__getattr__``:
    constructor kwargs first, then the operator class.  This keeps the
    proxy decoupled from concrete OP implementations.
    """

    def __init__(self, op_name, op_cls, init_args, env_spec):
        self._name = op_name
        self._op_cls = op_cls
        self._init_args = init_args  # dict of constructor kwargs
        self._env_spec = env_spec
        self._op_cfg = None
        self._run_func = None  # set by wrap_op(s)_with_isolation
        self._is_segment_follower = False  # True for non-leader proxies
        # Isolated ops monitor themselves inside the subprocess, so the
        # main process must not wrap them again with the outer Monitor
        # (read as `_use_child_monitor` in NestedDataset.process).
        self._use_child_monitor = True
        self._open_monitor = True
        self._isolation_stats = None
        # Runtime context, bound by the executor via bind_runtime() after
        # load_ops() returns (the values depend on executor state such as
        # work_dir that is not known at construction time).
        self._exporter_config = None
        self._tracer_config = None
        self._isolated_log_dir = None

    # -- interface expected by NestedDataset.process -----------------------

    @property
    def runtime_env(self):
        return self._env_spec.to_dict()

    def bind_runtime(self, *, exporter_config, tracer_config, open_monitor, isolated_log_dir):
        """Bind executor-provided runtime context to this proxy.

        Keeps the executor from reaching into the proxy's private fields:
        the subprocess launcher reads these back at call time to rebuild
        the exporter/tracer and to route isolated logs.
        """
        self._exporter_config = exporter_config
        self._tracer_config = tracer_config
        self._open_monitor = open_monitor
        self._isolated_log_dir = isolated_log_dir

    def run(self, dataset, *, exporter=None, tracer=None, **kwargs):
        if self._run_func is not None:
            return self._run_func(dataset, exporter=exporter, tracer=tracer, **kwargs)
        raise RuntimeError(
            f"IsolatedOpProxy for [{self._name}] has no run function set. "
            "Did you forget to call wrap_op_with_isolation()?"
        )

    def __getattr__(self, name):
        # 1. Constructor kwargs (e.g. user-provided accelerator, num_cpus, ...)
        if name in self._init_args:
            return self._init_args[name]
        # 2. Operator class attributes / methods.  This also provides a
        #    convention-based fallback for public attributes whose class
        #    default is stored with a leading underscore (e.g. accelerator
        #    -> _accelerator).
        if hasattr(self._op_cls, name):
            attr = getattr(self._op_cls, name)
            if inspect.isfunction(attr):
                return types.MethodType(attr, self)
            return attr
        if not name.startswith("_") and hasattr(self._op_cls, f"_{name}"):
            return getattr(self._op_cls, f"_{name}")
        raise AttributeError(name)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def load_ops(process_list, op_env_manager=None):
    """Load operator instances from the config process list.

    :param process_list: list of ``{op_name: kwargs}`` dicts.
    :param op_env_manager: when provided, env-spec merging is performed.
        In **Ray** mode every op is instantiated and ``runtime_env`` is
        set on each (existing behaviour).  In **local** mode, operators
        whose merged env spec has pip dependencies are replaced by
        :class:`IsolatedOpProxy` and run in isolated venvs; operators
        with no extra dependencies are instantiated normally.
    :return: list of operator instances and/or proxies.
    """
    from data_juicer.utils.ray_utils import is_ray_mode

    # ------------------------------------------------------------------
    # Path A — no env manager (``min_common_dep_num_to_combine == -1``)
    # ------------------------------------------------------------------
    if not op_env_manager:
        ops = []
        new_process_list = []
        for process in process_list:
            op_name, args = list(process.items())[0]
            ops.append(OPERATORS.modules[op_name](**args))
            new_process_list.append(process)
        for op_cfg, op in zip(new_process_list, ops):
            op._op_cfg = op_cfg
        return ops

    # ------------------------------------------------------------------
    # Path B — Ray mode (existing behaviour: instantiate all, set runtime_env)
    # ------------------------------------------------------------------
    if is_ray_mode():
        ops = []
        new_process_list = []
        for process in process_list:
            op_name, args = list(process.items())[0]
            ops.append(OPERATORS.modules[op_name](**args))
            new_process_list.append(process)
        for op_cfg, op in zip(new_process_list, ops):
            op._op_cfg = op_cfg

        # first round: record and merge possible common env specs
        for op in ops:
            op_env_spec = op.get_env_spec()
            op_env_manager.record_op_env_spec(op._name, op_env_spec)
        # second round: update op runtime environment
        for op in ops:
            op_env_spec = op_env_manager.get_op_env_spec(op._name)
            op._requirements = op_env_spec.pip_pkgs
            if op.runtime_env is None:
                op.runtime_env = op_env_spec.to_dict()
        return ops

    # ------------------------------------------------------------------
    # Path C — local mode with isolation
    #
    # Each env group whose merged spec has pip_pkgs → IsolatedOpProxy
    # (subprocess + venv).  Groups with empty pip_pkgs → instantiate
    # normally in the main process.
    #
    # This mirrors Ray mode: each group with dependencies gets its own
    # virtualenv.  Parent environment inheritance is handled via a .pth
    # file rather than --system-site-packages.
    # ------------------------------------------------------------------
    from .local_env_runner import wrap_ops_with_isolation

    op_infos = []  # (op_name, op_cls, args, op_cfg, local_env_spec)
    for process in process_list:
        op_name, args = list(process.items())[0]
        op_cls = OPERATORS.modules[op_name]
        raw_env_spec = _get_class_env_spec(op_cls)
        local_env_spec = resolve_local_env_spec(raw_env_spec)
        op_infos.append((op_name, op_cls, args, process, local_env_spec))

    # Class-level env spec collection + OPEnvManager recording/merging
    for op_name, _, _, _, env_spec in op_infos:
        op_env_manager.record_op_env_spec(op_name, env_spec)

    # Build the operator list, grouping consecutive same-spec isolated
    # ops into segments that share a single subprocess call.
    ops = []
    # Collect (op_info, final_spec, is_isolated) tuples first
    annotated = []
    for op_name, op_cls, args, op_cfg, _ in op_infos:
        final_spec = op_env_manager.get_op_env_spec(op_name)
        annotated.append(((op_name, op_cls, args, op_cfg), final_spec, bool(final_spec.pip_pkgs)))

    # Group consecutive isolated ops with the same spec hash
    i = 0
    while i < len(annotated):
        info, spec, is_isolated = annotated[i]
        if not is_isolated:
            # Non-isolated: instantiate normally
            op_name, op_cls, args, op_cfg = info
            op = op_cls(**args)
            op._op_cfg = op_cfg
            ops.append(op)
            i += 1
            continue

        # Start of an isolated segment — collect consecutive ops
        # with the same spec hash.
        spec_hash = spec.get_hash()
        segment_infos = [info]
        segment_spec = spec
        j = i + 1
        while j < len(annotated):
            _, next_spec, next_isolated = annotated[j]
            if next_isolated and next_spec.get_hash() == spec_hash:
                segment_infos.append(annotated[j][0])
                j += 1
            else:
                break

        # Create proxies for the whole segment
        segment_proxies = []
        for op_name, op_cls, args, op_cfg in segment_infos:
            proxy = IsolatedOpProxy(op_name, op_cls, args, segment_spec)
            proxy._op_cfg = op_cfg
            segment_proxies.append(proxy)

        # Wrap the segment: leader + followers
        wrap_ops_with_isolation(segment_proxies, segment_spec)

        ops.extend(segment_proxies)
        i = j

    return ops
