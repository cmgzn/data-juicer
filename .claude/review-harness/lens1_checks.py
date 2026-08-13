#!/usr/bin/env python3
"""
Lens 1: Mechanical Convention Checker for data-juicer PRs.

This script performs deterministic AST-based checks on changed files.
It does NOT require LLM judgment — all checks are machine-decidable.

Usage:
    python lens1_checks.py <base_ref> [<head_ref>]
    python lens1_checks.py main              # diff against main
    python lens1_checks.py main feature/x    # explicit range
    python lens1_checks.py --files a.py b.py # check specific files
"""

import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Known core dependencies (importable names, not pip names)
CORE_IMPORT_NAMES = {
    "datasets", "fsspec", "pandas", "numpy", "np", "loguru", "tqdm",
    "jsonargparse", "jsonlines", "zstandard", "lz4", "multiprocess",
    "dill", "psutil", "pydantic", "uv", "httpx", "emoji", "tabulate",
    "bs4", "beautifulsoup4", "requests", "wget", "streamlit", "PIL",
    "Pillow", "mwparserfromhell", "regex", "tomli", "tomli_w",
    "gitpython", "git", "dep_logic",
    # stdlib (never flag these)
    "os", "sys", "re", "ast", "json", "math", "copy", "io", "abc",
    "collections", "itertools", "functools", "operator", "pathlib",
    "typing", "dataclasses", "enum", "contextlib", "threading",
    "multiprocessing", "subprocess", "tempfile", "shutil", "glob",
    "hashlib", "uuid", "time", "datetime", "traceback", "warnings",
    "inspect", "importlib", "pkgutil", "types", "struct", "string",
    "textwrap", "logging", "unittest", "argparse", "configparser",
    "csv", "pickle", "shelve", "sqlite3", "socket", "http", "urllib",
    "email", "html", "xml", "zipfile", "tarfile", "gzip", "bz2",
    "signal", "platform", "ctypes", "queue", "heapq", "bisect",
    "array", "weakref", "secrets", "statistics", "fractions",
    "decimal", "random", "base64", "binascii", "codecs",
    "concurrent", "asyncio", "selectors", "mmap", "gc", "glob",
    "pickle", "pprint", "locale", "getpass", "fnmatch",
    "difflib", "fileinput", "linecache", "tokenize", "token",
    "keyword", "dis", "code", "codeop", "compileall",
    "numbers", "cmath", "atexit", "resource", "syslog",
}

# Internal project imports (never flag)
INTERNAL_PREFIXES = {"data_juicer", ".", ".."}


@dataclass
class Finding:
    file: str
    line: int
    lens: str
    severity: str  # "blocker", "warning", "suggestion"
    convention_id: str
    message: str
    context: str = ""


@dataclass
class CheckResult:
    findings: list = field(default_factory=list)

    def add(self, finding: Finding):
        self.findings.append(finding)

    @property
    def blockers(self):
        return [f for f in self.findings if f.severity == "blocker"]

    @property
    def warnings(self):
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def suggestions(self):
        return [f for f in self.findings if f.severity == "suggestion"]


def get_diff_files(base_ref: str, head_ref: Optional[str] = None) -> list[str]:
    """Get list of changed Python files in the diff."""
    if head_ref:
        cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR",
               f"{base_ref}...{head_ref}"]
    else:
        cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR", base_ref]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    files = [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]
    return files


def is_op_file(filepath: str) -> bool:
    """Check if file is an operator file (under data_juicer/ops/)."""
    return filepath.startswith("data_juicer/ops/") and not filepath.endswith("__init__.py")


def is_test_file(filepath: str) -> bool:
    """Check if file is a test file."""
    return filepath.startswith("tests/")


def get_top_level_imports(tree: ast.AST) -> list[tuple[int, str]]:
    """Extract top-level import names and their line numbers."""
    imports = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:  # absolute import
                imports.append((node.lineno, node.module.split(".")[0]))
    return imports


def is_package_file(filepath: str) -> bool:
    """Check if file is part of the main package (data_juicer/)."""
    return filepath.startswith("data_juicer/")


def check_lazy_loader_discipline(filepath: str, tree: ast.AST, result: CheckResult):
    """Convention 1: Non-core deps must use LazyLoader at top level."""
    if not is_package_file(filepath):
        return
    if is_test_file(filepath):
        return

    imports = get_top_level_imports(tree)
    for lineno, module_name in imports:
        if module_name in CORE_IMPORT_NAMES:
            continue
        if any(module_name.startswith(p) for p in INTERNAL_PREFIXES):
            continue
        # Check if it's a LazyLoader assignment instead
        # LazyLoader pattern: `torch = LazyLoader("torch")`
        # These appear as assignments, not imports, so they won't be caught here
        result.add(Finding(
            file=filepath,
            line=lineno,
            lens="convention",
            severity="blocker",
            convention_id="dep-001",
            message=f"Top-level import of '{module_name}' — not in core dependencies. "
                    f"Use LazyLoader or move to function body.",
            context=f"import {module_name}"
        ))


def check_init_signature(filepath: str, tree: ast.AST, result: CheckResult):
    """Convention 11: __init__ must accept *args, **kwargs and forward to super."""
    if not is_op_file(filepath):
        return

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        # Look for __init__ method
        for item in node.body:
            if not isinstance(item, ast.FunctionDef) or item.name != "__init__":
                continue
            args = item.args
            has_vararg = args.vararg is not None
            has_kwarg = args.kwarg is not None

            if not has_vararg or not has_kwarg:
                result.add(Finding(
                    file=filepath,
                    line=item.lineno,
                    lens="convention",
                    severity="blocker",
                    convention_id="init-001",
                    message=f"Class '{node.name}.__init__' missing "
                            f"{'*args' if not has_vararg else '**kwargs'}. "
                            f"Base OP class requires forwarding for global param injection.",
                    context=f"class {node.name}"
                ))

            # Check super().__init__ call exists
            has_super_init = False
            for stmt in ast.walk(item):
                if isinstance(stmt, ast.Call):
                    func = stmt.func
                    if (isinstance(func, ast.Attribute) and
                            func.attr == "__init__" and
                            isinstance(func.value, ast.Call) and
                            isinstance(func.value.func, ast.Name) and
                            func.value.func.id == "super"):
                        has_super_init = True
                        break
            if not has_super_init:
                result.add(Finding(
                    file=filepath,
                    line=item.lineno,
                    lens="convention",
                    severity="blocker",
                    convention_id="init-002",
                    message=f"Class '{node.name}.__init__' does not call "
                            f"super().__init__(*args, **kwargs).",
                    context=f"class {node.name}"
                ))


def check_registration_name(filepath: str, source: str, result: CheckResult):
    """Convention 8: Registration name must match filename."""
    if not is_op_file(filepath):
        return
    # Skip base files
    basename = os.path.basename(filepath)
    if basename in ("base_op.py", "load.py", "op_fusion.py", "op_env.py",
                    "mixins.py", "fused_batch_executor.py",
                    "fused_sequential_batch_op.py"):
        return

    expected_name = basename.replace(".py", "")
    # Find @OPERATORS.register_module('name') or ("name") or (OP_NAME)
    pattern_literal = r"@OPERATORS\.register_module\(['\"]([^'\"]+)['\"]\)"
    pattern_var = r"@OPERATORS\.register_module\((\w+)\)"
    literal_matches = re.findall(pattern_literal, source)
    var_matches = re.findall(pattern_var, source)

    has_registration = bool(literal_matches) or bool(var_matches)

    if not has_registration:
        # Might be a utility file in ops/common/ etc
        if "/common/" in filepath:
            return
        result.add(Finding(
            file=filepath,
            line=1,
            lens="convention",
            severity="warning",
            convention_id="reg-001",
            message=f"No @OPERATORS.register_module() found. "
                    f"If this is an operator, it must be registered.",
            context=basename
        ))
    else:
        # Check literal name matches filename
        for name in literal_matches:
            if name != expected_name:
                result.add(Finding(
                    file=filepath,
                    line=1,
                    lens="convention",
                    severity="suggestion",
                    convention_id="reg-002",
                    message=f"Registration name '{name}' differs from filename "
                            f"'{expected_name}'. Convention: they should match.",
                    context=f"@OPERATORS.register_module('{name}')"
                ))
        # If using a variable, try to resolve it
        for var_name in var_matches:
            # Look for OP_NAME = 'xxx' pattern
            name_pattern = rf"{var_name}\s*=\s*['\"]([^'\"]+)['\"]"
            name_match = re.search(name_pattern, source)
            if name_match:
                resolved_name = name_match.group(1)
                if resolved_name != expected_name:
                    result.add(Finding(
                        file=filepath,
                        line=1,
                        lens="convention",
                        severity="suggestion",
                        convention_id="reg-002",
                        message=f"Registration name '{resolved_name}' (via {var_name}) "
                                f"differs from filename '{expected_name}'.",
                        context=f"{var_name} = '{resolved_name}'"
                    ))


def check_mutable_class_attributes(filepath: str, tree: ast.AST, result: CheckResult):
    """Convention 7: Mutable class attributes shared across instances."""
    if not is_op_file(filepath):
        return

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            # Check if value is a mutable literal: [], {}, set()
            val = item.value
            is_mutable = False
            if isinstance(val, ast.List) and len(val.elts) == 0:
                is_mutable = True
            elif isinstance(val, ast.Dict) and len(val.keys) == 0:
                is_mutable = True
            elif (isinstance(val, ast.Call) and
                  isinstance(val.func, ast.Name) and
                  val.func.id in ("set", "dict", "list", "defaultdict")):
                is_mutable = True

            if is_mutable:
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Skip known safe patterns
                        if target.id.startswith("_") and target.id in (
                            "_batched_op", "_accelerator", "_requirements",
                            "_default_kwargs"
                        ):
                            continue
                        result.add(Finding(
                            file=filepath,
                            line=item.lineno,
                            lens="convention",
                            severity="warning",
                            convention_id="mut-001",
                            message=f"Mutable class attribute '{target.id}' in "
                                    f"'{node.name}' — will be shared across all "
                                    f"instances. Move to __init__ if used as "
                                    f"instance state.",
                            context=f"class {node.name}: {target.id} = ..."
                        ))


def check_test_file_exists(filepath: str, result: CheckResult):
    """Convention 10: Every op must have a test file."""
    if not is_op_file(filepath):
        return
    basename = os.path.basename(filepath)
    if basename in ("base_op.py", "load.py", "op_fusion.py", "op_env.py",
                    "__init__.py", "mixins.py", "fused_batch_executor.py",
                    "fused_sequential_batch_op.py"):
        return
    if "/common/" in filepath:
        return

    # Determine expected test path
    # data_juicer/ops/mapper/clean_email_mapper.py ->
    # tests/ops/mapper/test_clean_email_mapper.py
    parts = filepath.split("/")
    if len(parts) >= 4:
        op_type = parts[2]  # mapper, filter, etc.
        op_file = parts[-1]
        test_path = PROJECT_ROOT / "tests" / "ops" / op_type / f"test_{op_file}"
        if not test_path.exists():
            result.add(Finding(
                file=filepath,
                line=1,
                lens="convention",
                severity="blocker",
                convention_id="test-001",
                message=f"No test file found at 'tests/ops/{op_type}/test_{op_file}'. "
                        f"Every operator must have corresponding tests.",
                context=f"Expected: tests/ops/{op_type}/test_{op_file}"
            ))


def check_filter_two_phase(filepath: str, tree: ast.AST, source: str, result: CheckResult):
    """Convention 9: Filters must implement two-phase design."""
    if not is_op_file(filepath):
        return
    if "/filter/" not in filepath:
        return

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        # Check if it inherits from Filter
        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.append(base.attr)

        if "Filter" not in base_names:
            continue

        method_names = {item.name for item in node.body
                       if isinstance(item, ast.FunctionDef)}

        has_compute = ("compute_stats_single" in method_names or
                       "compute_stats_batched" in method_names)
        has_process = ("process_single" in method_names or
                      "process_batched" in method_names)

        if not has_compute:
            result.add(Finding(
                file=filepath,
                line=node.lineno,
                lens="convention",
                severity="blocker",
                convention_id="filter-001",
                message=f"Filter '{node.name}' missing compute_stats_single/batched. "
                        f"Filters must separate stat computation from decision logic.",
                context=f"class {node.name}(Filter)"
            ))


def format_report(result: CheckResult) -> str:
    """Format findings as a readable report."""
    lines = []
    lines.append("=" * 60)
    lines.append("LENS 1: MECHANICAL CONVENTION CHECK REPORT")
    lines.append("=" * 60)
    lines.append("")

    if not result.findings:
        lines.append("All checks passed. No mechanical issues found.")
        return "\n".join(lines)

    if result.blockers:
        lines.append(f"## BLOCKERS ({len(result.blockers)})")
        lines.append("")
        for f in result.blockers:
            lines.append(f"  [{f.convention_id}] {f.file}:{f.line}")
            lines.append(f"    {f.message}")
            if f.context:
                lines.append(f"    > {f.context}")
            lines.append("")

    if result.warnings:
        lines.append(f"## WARNINGS ({len(result.warnings)})")
        lines.append("")
        for f in result.warnings:
            lines.append(f"  [{f.convention_id}] {f.file}:{f.line}")
            lines.append(f"    {f.message}")
            if f.context:
                lines.append(f"    > {f.context}")
            lines.append("")

    if result.suggestions:
        lines.append(f"## SUGGESTIONS ({len(result.suggestions)})")
        lines.append("")
        for f in result.suggestions:
            lines.append(f"  [{f.convention_id}] {f.file}:{f.line}")
            lines.append(f"    {f.message}")
            if f.context:
                lines.append(f"    > {f.context}")
            lines.append("")

    lines.append("=" * 60)
    lines.append(f"SUMMARY: {len(result.blockers)} blockers, "
                 f"{len(result.warnings)} warnings, "
                 f"{len(result.suggestions)} suggestions")
    lines.append("=" * 60)
    return "\n".join(lines)


def get_file_content(filepath: str, commit: Optional[str] = None) -> Optional[str]:
    """Get file content, optionally from a specific git commit."""
    if commit:
        cmd = ["git", "show", f"{commit}:{filepath}"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        if result.returncode != 0:
            return None
        return result.stdout
    else:
        full_path = PROJECT_ROOT / filepath
        if not full_path.exists():
            return None
        return full_path.read_text(encoding="utf-8")


def main():
    os.chdir(PROJECT_ROOT)

    if len(sys.argv) < 2:
        print("Usage: python lens1_checks.py <base_ref> [<head_ref>]")
        print("       python lens1_checks.py --files file1.py file2.py")
        print("       python lens1_checks.py --commit <sha> --files file1.py ...")
        sys.exit(1)

    commit = None
    if "--commit" in sys.argv:
        idx = sys.argv.index("--commit")
        commit = sys.argv[idx + 1]
        sys.argv = sys.argv[:idx] + sys.argv[idx + 2:]

    if sys.argv[1] == "--files":
        files = sys.argv[2:]
    else:
        base_ref = sys.argv[1]
        head_ref = sys.argv[2] if len(sys.argv) > 2 else None
        files = get_diff_files(base_ref, head_ref)

    if not files:
        print("No Python files changed.")
        sys.exit(0)

    print(f"Checking {len(files)} changed files"
          f"{f' at commit {commit[:8]}' if commit else ''}...")
    print()

    result = CheckResult()

    for filepath in files:
        source = get_file_content(filepath, commit)
        if source is None:
            continue

        try:
            tree = ast.parse(source)
        except SyntaxError:
            result.add(Finding(
                file=filepath, line=1, lens="convention",
                severity="blocker", convention_id="syntax-001",
                message="File has syntax errors — cannot parse.",
                context=""
            ))
            continue

        # Run all checks
        check_lazy_loader_discipline(filepath, tree, result)
        check_init_signature(filepath, tree, result)
        check_registration_name(filepath, source, result)
        check_mutable_class_attributes(filepath, tree, result)
        check_test_file_exists(filepath, result)
        check_filter_two_phase(filepath, tree, source, result)

    print(format_report(result))
    sys.exit(1 if result.blockers else 0)


if __name__ == "__main__":
    main()
