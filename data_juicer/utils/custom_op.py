"""
Custom Operator Management
===========================

Manages a persistent JSON registry at ``~/.data_juicer/custom_op.json``
so that custom operators survive across processes.

The registry file stores source-file paths keyed by operator name.
On startup, ``load_persistent_custom_ops()`` replays those registrations
into the in-process ``OPERATORS`` registry, automatically cleaning up
entries whose source files no longer exist.

Also provides a CLI for managing custom operators::

    python -m data_juicer.utils.custom_op list
    python -m data_juicer.utils.custom_op register /path/to/my_mapper.py
    python -m data_juicer.utils.custom_op unregister my_mapper
    python -m data_juicer.utils.custom_op reset
"""

import argparse
import importlib.util
import inspect
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

_EMPTY_REGISTRY: Dict = {"version": 1, "custom_operators": {}}


def _read_registry() -> dict:
    """Read the JSON registry.  Returns the empty structure when the file
    does not exist or is malformed."""
    path = get_registry_path()
    if not path.exists():
        return json.loads(json.dumps(_EMPTY_REGISTRY))  # deep copy
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "custom_operators" not in data:
            logger.warning(f"Malformed op registry at {path}, resetting to empty.")
            return json.loads(json.dumps(_EMPTY_REGISTRY))
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to read op registry at {path}: {exc}")
        return json.loads(json.dumps(_EMPTY_REGISTRY))


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
# Custom Op management
# ---------------------------------------------------------------------------


def register_persistent(paths: List[str]) -> dict:
    """Register custom operators to the persistent registry **and** the
    current-process ``OPERATORS``.

    *paths* is a list of file / directory paths (same semantics as
    ``load_custom_operators``).

    Returns ``{"registered": [...], "warnings": [...]}``.
    """
    from data_juicer.ops.base_op import OPERATORS

    # Snapshot operator names before loading.
    before = set(OPERATORS.modules.keys())

    warnings: List[str] = []
    valid_paths: List[str] = []
    for p in paths:
        abs_p = os.path.abspath(p)
        if not os.path.exists(abs_p):
            warnings.append(f"Path does not exist: {abs_p}")
            continue
        valid_paths.append(abs_p)

    if valid_paths:
        load_custom_operators(valid_paths)

    # Diff to find newly registered names.
    after = set(OPERATORS.modules.keys())
    new_names = sorted(after - before)

    # Build a mapping from op name -> source path.
    name_to_path: Dict[str, str] = {}
    for p in valid_paths:
        abs_p = os.path.abspath(p)
        if os.path.isfile(abs_p):
            # Find which new names came from this file.
            for n in new_names:
                op_cls = OPERATORS.modules.get(n)
                if op_cls is not None:
                    try:
                        cls_file = os.path.abspath(inspect.getfile(op_cls))
                        if cls_file == abs_p:
                            name_to_path[n] = abs_p
                    except (TypeError, OSError):
                        pass
        elif os.path.isdir(abs_p):
            # Directory – inspect each new op to find its file.
            for n in new_names:
                if n in name_to_path:
                    continue
                op_cls = OPERATORS.modules.get(n)
                if op_cls is not None:
                    try:
                        cls_file = os.path.abspath(inspect.getfile(op_cls))
                        if cls_file.startswith(abs_p):
                            name_to_path[n] = cls_file
                    except (TypeError, OSError):
                        pass

    # Fallback: for any new name not yet mapped, try inspect.
    for n in new_names:
        if n not in name_to_path:
            op_cls = OPERATORS.modules.get(n)
            if op_cls is not None:
                try:
                    name_to_path[n] = os.path.abspath(inspect.getfile(op_cls))
                except (TypeError, OSError):
                    warnings.append(f"Could not determine source path for '{n}'")

    # Persist.
    registry = _read_registry()
    now = datetime.now().isoformat(timespec="seconds")
    for n in new_names:
        src = name_to_path.get(n)
        if src:
            registry["custom_operators"][n] = {
                "source_path": src,
                "registered_at": now,
            }

    _write_registry(registry)

    return {"registered": new_names, "warnings": warnings}


def unregister_ops(names: List[str]) -> dict:
    """Remove the given custom operators from the persistent registry and
    the current-process ``OPERATORS``.

    Returns ``{"removed": [...], "not_found": [...]}``.
    """
    from data_juicer.ops.base_op import OPERATORS

    registry = _read_registry()
    removed: List[str] = []
    not_found: List[str] = []

    for name in names:
        if name in registry["custom_operators"]:
            del registry["custom_operators"][name]
            removed.append(name)
        else:
            not_found.append(name)

        # Also remove from in-process registry.
        OPERATORS.unregister_module(name)

        # Remove from sys.modules if present.
        # The module name is typically the stem of the source file.
        to_remove = [k for k in sys.modules if k == name or k.endswith(f".{name}")]
        for k in to_remove:
            del sys.modules[k]

    _write_registry(registry)
    return {"removed": removed, "not_found": not_found}


def reset_registry() -> dict:
    """Clear **all** custom operators from the persistent registry and the
    current-process ``OPERATORS``.

    Returns ``{"removed": [...]}``.
    """
    from data_juicer.ops.base_op import OPERATORS

    registry = _read_registry()
    removed = sorted(registry["custom_operators"].keys())

    for name in removed:
        OPERATORS.unregister_module(name)
        to_remove = [k for k in sys.modules if k == name or k.endswith(f".{name}")]
        for k in to_remove:
            del sys.modules[k]

    registry["custom_operators"] = {}
    _write_registry(registry)

    return {"removed": removed}


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def list_registered() -> dict:
    """Return the contents of the persistent registry.

    Returns ``{"custom_operators": {...}}``.
    """
    registry = _read_registry()
    return {"custom_operators": registry.get("custom_operators", {})}


# ---------------------------------------------------------------------------
# Startup loading
# ---------------------------------------------------------------------------


def load_persistent_custom_ops() -> dict:
    """Load all custom operators from the persistent registry into the
    current-process ``OPERATORS``.

    Entries whose source files no longer exist are automatically removed
    from the registry and a warning is logged.

    Returns ``{"loaded": [...], "cleaned": [...], "warnings": [...]}``.
    """
    registry = _read_registry()
    custom_ops = registry.get("custom_operators", {})

    if not custom_ops:
        return {"loaded": [], "cleaned": [], "warnings": []}

    loaded: List[str] = []
    cleaned: List[str] = []
    warnings: List[str] = []

    # Validate paths first.
    valid_entries: Dict[str, dict] = {}
    for name, meta in list(custom_ops.items()):
        src = meta.get("source_path", "")
        if not src or not os.path.exists(src):
            logger.warning(f"Custom op '{name}' source not found at '{src}', " f"removing from registry.")
            cleaned.append(name)
            warnings.append(f"Cleaned stale entry '{name}': source '{src}' not found.")
        else:
            valid_entries[name] = meta

    # If we cleaned anything, persist the updated registry.
    if cleaned:
        registry["custom_operators"] = valid_entries
        _write_registry(registry)

    # Load valid entries.
    # Group by source_path to avoid loading the same file twice.
    paths_to_load: List[str] = []
    seen_paths: set = set()
    for name, meta in valid_entries.items():
        src = meta["source_path"]
        if src not in seen_paths:
            paths_to_load.append(src)
            seen_paths.add(src)

    if paths_to_load:
        try:
            load_custom_operators(paths_to_load)
            loaded = sorted(valid_entries.keys())
        except Exception as exc:
            msg = f"Failed to load persistent custom ops: {exc}"
            logger.error(msg)
            warnings.append(msg)

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
        help="Unregister custom operator(s) from the persistent registry",
    )
    p_unreg.add_argument(
        "names",
        nargs="+",
        help="Name(s) of custom operators to remove",
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
    custom_ops = result.get("custom_operators", {})
    if not custom_ops:
        print("No custom operators registered.")
        return 0
    print(f"Custom operators ({len(custom_ops)}):")
    for name, meta in sorted(custom_ops.items()):
        src = meta.get("source_path", "?")
        reg_at = meta.get("registered_at", "?")
        print(f"  {name}")
        print(f"    source: {src}")
        print(f"    registered_at: {reg_at}")
    return 0


def _cmd_register(args) -> int:
    """Register custom operator(s) persistently."""
    result = register_persistent(args.paths)
    registered = result.get("registered", [])
    warnings = result.get("warnings", [])

    if registered:
        print(f"Registered {len(registered)} operator(s):")
        for name in registered:
            print(f"  + {name}")
    else:
        print("No new operators registered.")

    for warning in warnings:
        print(f"  WARNING: {warning}", file=sys.stderr)

    return 0


def _cmd_unregister(args) -> int:
    """Unregister custom operator(s) from the persistent registry."""
    result = unregister_ops(args.names)
    removed = result.get("removed", [])
    not_found = result.get("not_found", [])

    if removed:
        print(f"Removed {len(removed)} operator(s):")
        for name in removed:
            print(f"  - {name}")

    if not_found:
        print(f"Not found ({len(not_found)}):")
        for name in not_found:
            print(f"  ? {name}")

    return 0


def _cmd_reset(args) -> int:
    """Clear all custom operators from the persistent registry."""
    result = reset_registry()
    removed = result.get("removed", [])

    if removed:
        print(f"Removed {len(removed)} custom operator(s):")
        for name in removed:
            print(f"  - {name}")
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
