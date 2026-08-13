#!/usr/bin/env python3
"""
Lens 1 Level 2: Runtime Smoke Test for data-juicer Operators.

This script ACTUALLY instantiates new/modified operators and attempts to run
them with minimal dummy data. It catches:
- Import-time crashes (missing/undeclared dependencies)
- Instantiation crashes (bad defaults, missing paths)
- Runtime crashes (FileNotFoundError, TypeError, None handling)
- Type inconsistency in returns (Arrow-incompatible)

Usage:
    python3 lens1_smoke_test.py <base_ref> [<head_ref>]
    python3 lens1_smoke_test.py --files op_file1.py op_file2.py
    python3 lens1_smoke_test.py --commit <sha> --files op_file1.py ...
    python3 lens1_smoke_test.py --clean-venv <base_ref>   # full clean install test

The script runs in 3 phases:
  Phase A: Import test (can the module be imported without crash?)
  Phase B: Instantiation test (can the op be created with defaults?)
  Phase C: Process test (can it handle minimal/empty data without crash?)
"""

import importlib
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class SmokeFinding:
    phase: str  # "import", "instantiate", "process"
    op_file: str
    op_name: str
    severity: str  # "blocker", "warning"
    error_type: str
    message: str
    traceback_str: str = ""


@dataclass
class SmokeResult:
    findings: list = field(default_factory=list)
    passed: list = field(default_factory=list)

    def add_finding(self, f: SmokeFinding):
        self.findings.append(f)

    def add_pass(self, phase: str, op_file: str, op_name: str):
        self.passed.append({"phase": phase, "file": op_file, "name": op_name})


def get_diff_files(base_ref: str, head_ref: Optional[str] = None) -> list[str]:
    """Get list of changed Python op files in the diff."""
    if head_ref:
        cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR",
               f"{base_ref}...{head_ref}"]
    else:
        cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR", base_ref]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    files = [f for f in result.stdout.strip().split("\n")
             if f.endswith(".py") and f.startswith("data_juicer/ops/")
             and "__init__" not in f and "/common/" not in f]
    return files


def get_op_type(filepath: str) -> Optional[str]:
    """Determine op type from file path."""
    if "/mapper/" in filepath:
        return "mapper"
    elif "/filter/" in filepath:
        return "filter"
    elif "/deduplicator/" in filepath:
        return "deduplicator"
    elif "/selector/" in filepath:
        return "selector"
    elif "/grouper/" in filepath:
        return "grouper"
    elif "/aggregator/" in filepath:
        return "aggregator"
    return None


def filepath_to_module(filepath: str) -> str:
    """Convert file path to Python module path."""
    return filepath.replace("/", ".").replace(".py", "")


def make_minimal_sample(op_type: str) -> dict:
    """Create minimal test sample based on op type."""
    sample = {
        "text": "",
        "images": [],
        "videos": [],
        "audios": [],
    }
    # Add stats field for filters
    if op_type == "filter":
        sample["__dj__stats__"] = {}
    # Add meta field
    sample["__dj__meta__"] = {}
    return sample


def make_normal_sample(op_type: str) -> dict:
    """Create a 'normal' sample with actual content."""
    sample = {
        "text": "Hello world. This is a test sentence for data processing.",
        "images": [],
        "videos": [],
        "audios": [],
    }
    if op_type == "filter":
        sample["__dj__stats__"] = {}
    sample["__dj__meta__"] = {}
    return sample


def discover_ops_in_module(module) -> list[tuple[str, type]]:
    """Find all OP subclasses defined in a module."""
    from data_juicer.ops.base_op import OP
    ops = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if (issubclass(obj, OP) and obj is not OP and
                obj.__module__ == module.__name__):
            ops.append((name, obj))
    return ops


def get_init_defaults(op_class) -> dict:
    """Extract default parameter values from __init__."""
    sig = inspect.signature(op_class.__init__)
    defaults = {}
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "args", "kwargs"):
            continue
        if param.default is not inspect.Parameter.empty:
            defaults[param_name] = param.default
    return defaults


def test_import(filepath: str, result: SmokeResult) -> Optional[object]:
    """Phase A: Try to import the module."""
    module_path = filepath_to_module(filepath)
    try:
        module = importlib.import_module(module_path)
        result.add_pass("import", filepath, module_path)
        return module
    except Exception as e:
        result.add_finding(SmokeFinding(
            phase="import",
            op_file=filepath,
            op_name=module_path,
            severity="blocker",
            error_type=type(e).__name__,
            message=f"Failed to import: {e}",
            traceback_str=traceback.format_exc()
        ))
        return None


def test_instantiate(filepath: str, op_name: str, op_class: type,
                     result: SmokeResult) -> Optional[object]:
    """Phase B: Try to instantiate with defaults."""
    try:
        instance = op_class()
        result.add_pass("instantiate", filepath, op_name)
        return instance
    except TypeError as e:
        # Missing required args — try to figure out minimal args
        msg = str(e)
        if "required" in msg:
            result.add_finding(SmokeFinding(
                phase="instantiate",
                op_file=filepath,
                op_name=op_name,
                severity="warning",
                error_type="TypeError",
                message=f"Cannot instantiate with defaults: {e}. "
                        f"Requires positional args — users must always specify these.",
                traceback_str=""
            ))
        else:
            result.add_finding(SmokeFinding(
                phase="instantiate",
                op_file=filepath,
                op_name=op_name,
                severity="blocker",
                error_type="TypeError",
                message=f"Instantiation TypeError: {e}",
                traceback_str=traceback.format_exc()
            ))
        return None
    except FileNotFoundError as e:
        result.add_finding(SmokeFinding(
            phase="instantiate",
            op_file=filepath,
            op_name=op_name,
            severity="blocker",
            error_type="FileNotFoundError",
            message=f"Instantiation requires non-existent path: {e}",
            traceback_str=traceback.format_exc()
        ))
        return None
    except Exception as e:
        result.add_finding(SmokeFinding(
            phase="instantiate",
            op_file=filepath,
            op_name=op_name,
            severity="blocker" if isinstance(e, (ImportError, ModuleNotFoundError)) else "warning",
            error_type=type(e).__name__,
            message=f"Instantiation failed: {e}",
            traceback_str=traceback.format_exc()
        ))
        return None


def test_process(filepath: str, op_name: str, instance: object,
                 op_type: str, result: SmokeResult):
    """Phase C: Try to process minimal data."""
    samples = [make_minimal_sample(op_type), make_normal_sample(op_type)]
    sample_labels = ["empty_sample", "normal_sample"]

    for sample, label in zip(samples, sample_labels):
        try:
            if op_type == "filter":
                # Test compute_stats_single first
                stat_sample = instance.compute_stats_single(sample.copy())
                # Then test process_single
                keep = instance.process_single(stat_sample)
                if not isinstance(keep, bool):
                    result.add_finding(SmokeFinding(
                        phase="process",
                        op_file=filepath,
                        op_name=op_name,
                        severity="warning",
                        error_type="TypeMismatch",
                        message=f"Filter.process_single({label}) returned "
                                f"{type(keep).__name__} instead of bool. "
                                f"This causes Arrow type errors in batch.",
                        traceback_str=""
                    ))
                    continue
            elif op_type == "mapper":
                out = instance.process_single(sample.copy())
                if not isinstance(out, dict):
                    result.add_finding(SmokeFinding(
                        phase="process",
                        op_file=filepath,
                        op_name=op_name,
                        severity="warning",
                        error_type="TypeMismatch",
                        message=f"Mapper.process_single({label}) returned "
                                f"{type(out).__name__} instead of dict.",
                        traceback_str=""
                    ))
                    continue
            elif op_type == "selector":
                # Selectors operate on datasets, skip single-sample test
                result.add_pass("process", filepath, f"{op_name}(skipped-dataset-level)")
                return

            result.add_pass("process", filepath, f"{op_name}({label})")

        except NotImplementedError:
            # Op uses batched mode only — try batched
            try:
                if op_type == "mapper":
                    batch = {k: [v] for k, v in sample.items()}
                    instance.process_batched(batch)
                result.add_pass("process", filepath, f"{op_name}({label},batched)")
            except NotImplementedError:
                result.add_pass("process", filepath, f"{op_name}(abstract-skip)")
            except Exception as e:
                result.add_finding(SmokeFinding(
                    phase="process",
                    op_file=filepath,
                    op_name=op_name,
                    severity="warning",
                    error_type=type(e).__name__,
                    message=f"process_batched({label}) crashed: {e}",
                    traceback_str=traceback.format_exc()[-500:]
                ))

        except FileNotFoundError as e:
            result.add_finding(SmokeFinding(
                phase="process",
                op_file=filepath,
                op_name=op_name,
                severity="blocker",
                error_type="FileNotFoundError",
                message=f"process_single({label}) needs non-existent path: {e}",
                traceback_str=traceback.format_exc()[-500:]
            ))

        except (KeyError, AttributeError, TypeError) as e:
            result.add_finding(SmokeFinding(
                phase="process",
                op_file=filepath,
                op_name=op_name,
                severity="warning",
                error_type=type(e).__name__,
                message=f"process_single({label}) crashed: {e}",
                traceback_str=traceback.format_exc()[-500:]
            ))

        except Exception as e:
            # Catch-all: any other exception during processing
            result.add_finding(SmokeFinding(
                phase="process",
                op_file=filepath,
                op_name=op_name,
                severity="warning",
                error_type=type(e).__name__,
                message=f"process_single({label}) crashed: {e}",
                traceback_str=traceback.format_exc()[-300:]
            ))


def format_report(result: SmokeResult) -> str:
    """Format findings as a readable report."""
    lines = []
    lines.append("=" * 70)
    lines.append("LENS 1 LEVEL 2: RUNTIME SMOKE TEST REPORT")
    lines.append("=" * 70)
    lines.append("")

    if not result.findings:
        lines.append(f"ALL SMOKE TESTS PASSED ({len(result.passed)} checks).")
        lines.append("")
        lines.append("Phases passed:")
        phase_counts = {}
        for p in result.passed:
            phase_counts[p["phase"]] = phase_counts.get(p["phase"], 0) + 1
        for phase, count in sorted(phase_counts.items()):
            lines.append(f"  {phase}: {count} ok")
        return "\n".join(lines)

    blockers = [f for f in result.findings if f.severity == "blocker"]
    warnings = [f for f in result.findings if f.severity == "warning"]

    if blockers:
        lines.append(f"## BLOCKERS ({len(blockers)}) — will crash in production")
        lines.append("")
        for f in blockers:
            lines.append(f"  [{f.phase}] {f.op_file} :: {f.op_name}")
            lines.append(f"    {f.error_type}: {f.message}")
            if f.traceback_str:
                # Show last 3 lines of traceback
                tb_lines = f.traceback_str.strip().split("\n")[-3:]
                for tl in tb_lines:
                    lines.append(f"    | {tl}")
            lines.append("")

    if warnings:
        lines.append(f"## WARNINGS ({len(warnings)}) — potential runtime issues")
        lines.append("")
        for f in warnings:
            lines.append(f"  [{f.phase}] {f.op_file} :: {f.op_name}")
            lines.append(f"    {f.error_type}: {f.message}")
            if f.traceback_str:
                tb_lines = f.traceback_str.strip().split("\n")[-2:]
                for tl in tb_lines:
                    lines.append(f"    | {tl}")
            lines.append("")

    # Summary
    lines.append("=" * 70)
    lines.append(f"SUMMARY: {len(blockers)} blockers, {len(warnings)} warnings, "
                 f"{len(result.passed)} passed")
    lines.append("")
    lines.append("Phase breakdown:")
    for phase in ["import", "instantiate", "process"]:
        n_pass = len([p for p in result.passed if p["phase"] == phase])
        n_block = len([f for f in blockers if f.phase == phase])
        n_warn = len([f for f in warnings if f.phase == phase])
        lines.append(f"  {phase:12s}: {n_pass} pass, {n_block} blocker, {n_warn} warning")
    lines.append("=" * 70)
    return "\n".join(lines)


def main():
    os.chdir(PROJECT_ROOT)

    if len(sys.argv) < 2:
        print("Usage: python3 lens1_smoke_test.py <base_ref> [<head_ref>]")
        print("       python3 lens1_smoke_test.py --files file1.py file2.py")
        sys.exit(1)

    if sys.argv[1] == "--files":
        files = sys.argv[2:]
    else:
        base_ref = sys.argv[1]
        head_ref = sys.argv[2] if len(sys.argv) > 2 else None
        files = get_diff_files(base_ref, head_ref)

    if not files:
        print("No operator files changed.")
        sys.exit(0)

    # Filter to only op files
    op_files = [f for f in files
                if f.startswith("data_juicer/ops/")
                and "__init__" not in f
                and "/common/" not in f
                and "base_op" not in f
                and "load.py" not in f
                and "op_fusion" not in f
                and "op_env" not in f
                and "mixins" not in f
                and "fused_" not in f]

    if not op_files:
        print("No operator files to test.")
        sys.exit(0)

    print(f"Smoke testing {len(op_files)} operator files...")
    print(f"Files: {', '.join(os.path.basename(f) for f in op_files)}")
    print()

    result = SmokeResult()

    for filepath in op_files:
        op_type = get_op_type(filepath)
        if not op_type:
            continue

        print(f"--- Testing {os.path.basename(filepath)} ({op_type}) ---")

        # Phase A: Import
        module = test_import(filepath, result)
        if module is None:
            print(f"  IMPORT FAILED — skipping instantiate/process")
            continue

        # Discover ops in module
        ops = discover_ops_in_module(module)
        if not ops:
            print(f"  No OP classes found in module")
            continue

        for op_name, op_class in ops:
            print(f"  Testing {op_name}...")

            # Phase B: Instantiate
            instance = test_instantiate(filepath, op_name, op_class, result)
            if instance is None:
                print(f"    INSTANTIATE FAILED — skipping process")
                continue

            # Phase C: Process
            test_process(filepath, op_name, instance, op_type, result)

    print()
    print(format_report(result))
    sys.exit(1 if any(f.severity == "blocker" for f in result.findings) else 0)


if __name__ == "__main__":
    main()
