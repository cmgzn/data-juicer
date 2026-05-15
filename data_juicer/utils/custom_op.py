"""
Custom Operator Management
===========================

Manages a persistent JSON registry at ``~/.data_juicer/custom_op.json``
so that custom operators survive across processes.

The registry stores only **registration paths** (file or directory) as
primary keys.  It does **not** cache operator names — the actual operator
list is always derived at runtime from the in-process ``OPERATORS``
registry after loading, so it is always up-to-date with the file system.

On startup, ``load_persistent_custom_ops()`` replays those registrations
into the in-process ``OPERATORS`` registry, automatically cleaning up
entries whose source paths no longer exist.

Also provides a CLI for managing custom operators::

    python -m data_juicer.utils.custom_op list
    python -m data_juicer.utils.custom_op register /path/to/my_mapper.py
    python -m data_juicer.utils.custom_op unregister /path/to/my_mapper.py
    python -m data_juicer.utils.custom_op reset
"""

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

# ---------------------------------------------------------------------------
# Dynamic module loading
# ---------------------------------------------------------------------------


def _generate_module_name(abs_path):
    """Generate a module name based on the absolute path of the file."""
    return os.path.splitext(os.path.basename(abs_path))[0]


def _rollback_operators(new_names):
    """Remove the given operator names from OPERATORS.

    Used to roll back a partially-successful load: *new_names* is the set
    of operators that were registered after the snapshot but before the
    error occurred.
    """
    try:
        from data_juicer.ops.base_op import OPERATORS
    except ImportError:
        return
    for name in new_names:
        OPERATORS.unregister_module(name)


def load_custom_operators(paths):
    """Dynamically load custom operator modules or packages in the specified path."""
    for path in paths:
        abs_path = os.path.realpath(path)
        if os.path.isfile(abs_path):
            module_name = _generate_module_name(abs_path)
            if module_name in sys.modules:
                existing_path = sys.modules[module_name].__file__
                raise RuntimeError(
                    f"Module '{module_name}' already loaded from '{existing_path}'. "
                    f"Conflict detected while loading '{abs_path}'."
                )
            from data_juicer.ops.base_op import OPERATORS

            ops_before = set(OPERATORS.modules.keys())
            try:
                spec = importlib.util.spec_from_file_location(module_name, abs_path)
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"Failed to create spec for '{abs_path}'")
                module = importlib.util.module_from_spec(spec)
                # register the module first to avoid recursive import issues
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            except Exception as e:
                # Clean up partially-initialized module to avoid stale entries
                sys.modules.pop(module_name, None)
                ops_after = set(OPERATORS.modules.keys())
                _rollback_operators(ops_after - ops_before)
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
            from data_juicer.ops.base_op import OPERATORS

            ops_before = set(OPERATORS.modules.keys())
            original_sys_path = sys.path.copy()
            try:
                sys.path.insert(0, parent_dir)
                importlib.import_module(package_name)
                # record the loading path of the package (custom attribute)
                setattr(sys.modules[package_name], "__loaded_from__", abs_path)
            except Exception as e:
                ops_after = set(OPERATORS.modules.keys())
                _rollback_operators(ops_after - ops_before)
                raise RuntimeError(f"Error loading package '{abs_path}': {e}")
            finally:
                sys.path = original_sys_path
        else:
            raise ValueError(f"Path '{abs_path}' is neither a file nor a directory")


# ---------------------------------------------------------------------------
# Path management
# ---------------------------------------------------------------------------


def get_registry_path() -> Path:
    """Return the path to the persistent op registry JSON file.

    Defaults to ``~/.data_juicer/custom_op.json``.
    Override with the ``DJ_CUSTOM_OP_REGISTRY`` environment variable.
    """
    override = os.environ.get("DJ_CUSTOM_OP_REGISTRY")
    if override:
        return Path(override)
    return Path.home() / ".data_juicer" / "custom_op.json"


# ---------------------------------------------------------------------------
# Low-level read / write helpers
# ---------------------------------------------------------------------------
def _empty_registry() -> dict:
    """Return a fresh empty registry structure."""
    return {"version": 1, "registrations": {}}


def _read_registry() -> dict:
    """Read the JSON registry.  Returns the empty structure when the file
    does not exist or is malformed.
    """
    path = get_registry_path()
    if not path.exists():
        return _empty_registry()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "registrations" not in data:
            logger.warning(f"Malformed op registry at {path}, resetting to empty.")
            return _empty_registry()
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to read op registry at {path}: {exc}")
        return _empty_registry()


def _write_registry(data: dict) -> None:
    """Atomically write *data* to the registry JSON file.

    Uses write-to-tmp + ``os.replace`` to avoid partial writes.
    """
    path = get_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temp file in the same directory, then atomically replace.
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=".op_registry_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp_path, str(path))
    except BaseException:
        # Clean up the temp file on failure.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_modules_for_path(abs_path: str) -> List[str]:
    """Return the sys.modules keys that were loaded from *abs_path*.

    For a single file, this is the module whose ``__file__`` matches.
    For a directory/package, this includes all modules whose ``__file__``
    lives under *abs_path*.
    """
    result = []
    for mod_name, mod in list(sys.modules.items()):
        mod_file = getattr(mod, "__file__", None)
        if mod_file is None:
            continue
        try:
            mod_file = os.path.realpath(mod_file)
        except (TypeError, OSError):
            continue
        if os.path.isfile(abs_path):
            if mod_file == abs_path:
                result.append(mod_name)
        elif os.path.isdir(abs_path):
            if mod_file.startswith(abs_path + os.sep) or mod_file == abs_path:
                result.append(mod_name)
    return result


def _ops_for_path(abs_path: str) -> List[str]:
    """Return the OPERATORS names whose class was defined under *abs_path*.

    Inspects each registered operator class to find its source file and
    checks whether it matches *abs_path* (file) or lives under it
    (directory).  Only called during unregister/list — not on the hot path.
    """
    import inspect

    try:
        from data_juicer.ops.base_op import OPERATORS
    except ImportError:
        return []

    abs_path = os.path.realpath(abs_path)
    result = []
    for name, cls in list(OPERATORS.modules.items()):
        try:
            cls_file = os.path.realpath(inspect.getfile(cls))
        except (TypeError, OSError):
            continue
        if os.path.isfile(abs_path):
            if cls_file == abs_path:
                result.append(name)
        elif os.path.isdir(abs_path):
            if cls_file.startswith(abs_path + os.sep):
                result.append(name)
    return sorted(result)


# ---------------------------------------------------------------------------
# Custom Op management
# ---------------------------------------------------------------------------


def register_persistent(paths: List[str]) -> dict:
    """Register custom operators to the persistent registry **and** the
    current-process ``OPERATORS``.

    *paths* is a list of file / directory paths (same semantics as
    ``load_custom_operators``).  Each path becomes a top-level key in the
    registry so that unregister and reload operate at the same granularity.

    If a path is already registered it is skipped (idempotent).

    Returns ``{"registered": [...], "skipped": [...], "warnings": [...]}``.
    """
    from data_juicer.ops.base_op import OPERATORS

    warnings: List[str] = []
    skipped: List[str] = []
    valid_paths: List[str] = []

    registry = _read_registry()
    existing_paths = set(registry.get("registrations", {}).keys())

    for p in paths:
        abs_p = os.path.realpath(p)
        if not os.path.exists(abs_p):
            warnings.append(f"Path does not exist: {abs_p}")
            continue
        if abs_p in existing_paths:
            skipped.append(abs_p)
            continue
        valid_paths.append(abs_p)

    # Snapshot operator names before loading.
    before = set(OPERATORS.modules.keys())

    if valid_paths:
        load_custom_operators(valid_paths)

    # Diff to find newly registered names.
    after = set(OPERATORS.modules.keys())
    all_new_names = sorted(after - before)

    # Persist only newly registered paths.
    if valid_paths:
        now = datetime.now().isoformat(timespec="seconds")
        for abs_p in valid_paths:
            path_type = "directory" if os.path.isdir(abs_p) else "file"
            registry["registrations"][abs_p] = {
                "type": path_type,
                "registered_at": now,
            }
        _write_registry(registry)

    if skipped:
        for sp in skipped:
            warnings.append(f"Path already registered: {sp}")

    return {"registered": all_new_names, "skipped": skipped, "warnings": warnings}


def unregister_paths(paths: List[str]) -> dict:
    """Remove the given registration paths (and all their operators) from
    the persistent registry and the current-process ``OPERATORS``.

    Paths must match exactly what was originally registered.  For example,
    if a directory was registered, only that directory path can be used to
    unregister — individual files within it are not accepted.

    Returns ``{"removed": [...], "not_found": [...], "warnings": [...]}``.
    """
    from data_juicer.ops.base_op import OPERATORS

    removed: List[str] = []
    not_found: List[str] = []
    warnings: List[str] = []

    registry = _read_registry()
    for p in paths:
        abs_p = os.path.realpath(p)
        if abs_p in registry["registrations"]:
            del registry["registrations"][abs_p]
            removed.append(abs_p)

            # Remove all operators whose class was defined under this path.
            for name in _ops_for_path(abs_p):
                OPERATORS.unregister_module(name)

            # Remove associated modules from sys.modules.
            for mod_name in _collect_modules_for_path(abs_p):
                sys.modules.pop(mod_name, None)
        else:
            not_found.append(abs_p)

    _write_registry(registry)

    if not_found:
        warnings.append(
            "Only exact registration paths can be unregistered "
            "(e.g. if a directory was registered, the entire directory "
            "path must be used). Run 'list' to see all registered paths."
        )

    return {"removed": removed, "not_found": not_found, "warnings": warnings}


def reset_registry() -> dict:
    """Clear **all** custom operators from the persistent registry and the
    current-process ``OPERATORS``.

    Returns ``{"removed": [...]}``.
    """
    from data_juicer.ops.base_op import OPERATORS

    registry = _read_registry()
    registrations = registry.get("registrations", {})
    removed_paths = sorted(registrations.keys())

    for reg_path in removed_paths:
        for name in _ops_for_path(reg_path):
            OPERATORS.unregister_module(name)
        for mod_name in _collect_modules_for_path(reg_path):
            sys.modules.pop(mod_name, None)

    registry["registrations"] = {}
    _write_registry(registry)

    return {"removed": removed_paths}


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def list_registered() -> dict:
    """Return the contents of the persistent registry with a live operator
    view.

    Returns a dict with two views:

    - ``"registrations"``: the path-keyed registry data, each entry
      augmented with a live ``"operators"`` list derived from the
      current-process ``OPERATORS``.
    - ``"custom_operators"``: a flattened ``{op_name: {"source_path": ...,
      "registered_at": ...}}`` dict for backward compatibility with
      tooling that enumerates custom op names (e.g. ``op_search``).
    """
    registry = _read_registry()
    registrations = registry.get("registrations", {})

    # Augment each registration with a live operator list.
    augmented: Dict[str, dict] = {}
    flat: Dict[str, dict] = {}
    for reg_path, meta in registrations.items():
        live_ops = _ops_for_path(reg_path)
        augmented[reg_path] = {
            **meta,
            "operators": live_ops,
        }
        for name in live_ops:
            flat[name] = {
                "source_path": reg_path,
                "registered_at": meta.get("registered_at", ""),
            }

    return {
        "registrations": augmented,
        "custom_operators": flat,
    }


# ---------------------------------------------------------------------------
# Startup loading
# ---------------------------------------------------------------------------


def load_persistent_custom_ops() -> dict:
    """Load all custom operators from the persistent registry into the
    current-process ``OPERATORS``.

    Entries whose source paths no longer exist are automatically removed
    from the registry and a warning is logged.

    Returns ``{"loaded": [...], "cleaned": [...], "warnings": [...]}``.
    """
    registry = _read_registry()
    registrations = registry.get("registrations", {})

    if not registrations:
        return {"loaded": [], "cleaned": [], "warnings": []}

    loaded: List[str] = []
    cleaned: List[str] = []
    warnings: List[str] = []

    # Validate registration paths.
    valid_entries: Dict[str, dict] = {}
    for reg_path, meta in list(registrations.items()):
        if not reg_path or not os.path.exists(reg_path):
            logger.warning(f"Custom op registration path not found: '{reg_path}', " f"removing from registry.")
            cleaned.append(reg_path)
            warnings.append(f"Cleaned stale entry '{reg_path}': path not found.")
        else:
            valid_entries[reg_path] = meta

    # If we cleaned anything, persist the updated registry.
    if cleaned:
        for cp in cleaned:
            registry["registrations"].pop(cp, None)
        _write_registry(registry)

    # Load valid entries one-by-one so that a failure in one path does
    # not prevent the remaining paths from loading.
    paths_to_load = sorted(valid_entries.keys())
    if paths_to_load:
        from data_juicer.ops.base_op import OPERATORS

        before = set(OPERATORS.modules.keys())
        for path in paths_to_load:
            try:
                load_custom_operators([path])
            except Exception as exc:
                msg = f"Failed to load custom op from '{path}': {exc}"
                logger.error(msg)
                warnings.append(msg)
        after = set(OPERATORS.modules.keys())
        loaded = sorted(after - before)

    return {"loaded": loaded, "cleaned": cleaned, "warnings": warnings}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m data_juicer.utils.custom_op",
        description="Data-Juicer Custom Operator Management Tool " "(does not affect built-in operators)",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # --- list ---
    sub.add_parser(
        "list",
        help="List registered custom operators",
    )

    # --- register ---
    p_reg = sub.add_parser(
        "register",
        help="Register custom operator(s) persistently",
    )
    p_reg.add_argument(
        "paths",
        nargs="+",
        help="Path(s) to custom operator file(s) or directory(ies)",
    )

    # --- unregister ---
    p_unreg = sub.add_parser(
        "unregister",
        help="Unregister custom operator(s) by their registration path(s)",
    )
    p_unreg.add_argument(
        "paths",
        nargs="+",
        help="Registration path(s) to remove (file or directory)",
    )

    # --- reset ---
    sub.add_parser(
        "reset",
        help="Clear all custom operators from the persistent registry",
    )

    return parser


def _cmd_list(args) -> int:
    """List registered custom operators."""
    result = list_registered()
    registrations = result.get("registrations", {})
    if not registrations:
        print("No custom operators registered.")
        return 0
    total_ops = sum(len(m.get("operators", [])) for m in registrations.values())
    print(f"Custom operators ({total_ops} op(s) from {len(registrations)} path(s)):")
    for reg_path, meta in sorted(registrations.items()):
        path_type = meta.get("type", "?")
        reg_at = meta.get("registered_at", "?")
        ops = meta.get("operators", [])
        print(f"  [{path_type}] {reg_path}")
        print(f"    registered_at: {reg_at}")
        ops_str = ", ".join(sorted(ops)) if ops else "(none loaded)"
        print(f"    operators: {ops_str}")
    return 0


def _cmd_register(args) -> int:
    """Register custom operator(s) persistently."""
    result = register_persistent(args.paths)
    registered = result.get("registered", [])
    skipped = result.get("skipped", [])
    warnings = result.get("warnings", [])

    if registered:
        print(f"Registered {len(registered)} operator(s):")
        for name in registered:
            print(f"  + {name}")

    if skipped:
        print(f"Skipped {len(skipped)} already-registered path(s):")
        for p in skipped:
            print(f"  ~ {p}")

    if not registered and not skipped:
        print("No new operators registered.")

    for warning in warnings:
        print(f"  WARNING: {warning}", file=sys.stderr)

    return 0


def _cmd_unregister(args) -> int:
    """Unregister custom operator(s) by their registration path(s)."""
    result = unregister_paths(args.paths)
    removed = result.get("removed", [])
    not_found = result.get("not_found", [])
    warnings = result.get("warnings", [])

    if removed:
        print(f"Removed {len(removed)} registration(s):")
        for p in removed:
            print(f"  - {p}")

    if not_found:
        print(f"Not found ({len(not_found)}):")
        for p in not_found:
            print(f"  ? {p}")

    for warning in warnings:
        print(f"  WARNING: {warning}", file=sys.stderr)

    return 0


def _cmd_reset(args) -> int:
    """Clear all custom operators from the persistent registry."""
    result = reset_registry()
    removed = result.get("removed", [])

    if removed:
        print(f"Removed {len(removed)} registration(s):")
        for p in removed:
            print(f"  - {p}")
    else:
        print("Registry was already empty.")
    return 0


_COMMAND_MAP = {
    "list": _cmd_list,
    "register": _cmd_register,
    "unregister": _cmd_unregister,
    "reset": _cmd_reset,
}


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for custom operator management."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    handler = _COMMAND_MAP.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
