"""
Tests for data_juicer.utils.custom_op

These tests exercise the persistent custom-op registry end-to-end:
register, unregister, reset, list, load, stale-entry cleanup,
and the CLI sub-commands.

Each test uses a private temp directory for the registry JSON and a
throwaway custom-op source file so that nothing leaks between tests.
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

from data_juicer.ops.base_op import OPERATORS
from data_juicer.utils.custom_op import (
    _read_registry,
    _write_registry,
    get_registry_path,
    list_registered,
    load_persistent_custom_ops,
    main as custom_op_main,
    register_persistent,
    reset_registry,
    unregister_ops,
)
from data_juicer.utils.registry import Registry
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase

def _make_custom_op_file(tmp_dir: str, op_name: str = "my_test_mapper") -> str:
    """Create a minimal custom mapper .py file and return its path."""
    code = textwrap.dedent(f"""\
        from data_juicer.ops.base_op import OPERATORS, Mapper

        @OPERATORS.register_module('{op_name}')
        class MyTestMapper(Mapper):
            \"\"\"A test custom mapper.\"\"\"
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            def process_single(self, sample):
                return sample
    """)
    path = os.path.join(tmp_dir, f"{op_name}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return path

# ---------------------------------------------------------------------------
# Unit tests for low-level API
# ---------------------------------------------------------------------------

class RegistryUnregisterTest(DataJuicerTestCaseBase):
    """Test Registry.unregister_module (new method)."""

    def test_unregister_existing(self):
        reg = Registry("test_unreg")

        class Dummy:
            pass

        reg.register_module("dummy_op", Dummy)
        self.assertIn("dummy_op", reg.modules)
        result = reg.unregister_module("dummy_op")
        self.assertTrue(result)
        self.assertNotIn("dummy_op", reg.modules)

    def test_unregister_nonexistent(self):
        reg = Registry("test_unreg2")
        result = reg.unregister_module("no_such_op")
        self.assertFalse(result)

class RegistryPathTest(DataJuicerTestCaseBase):
    """Test get_registry_path with and without env override."""

    def test_default_path(self):
        env_backup = os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        try:
            path = get_registry_path()
            self.assertTrue(str(path).endswith("custom_op.json"))
            self.assertIn(".data_juicer", str(path))
        finally:
            if env_backup is not None:
                os.environ["DJ_CUSTOM_OP_REGISTRY"] = env_backup

    def test_env_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom_path = os.path.join(tmp, "custom_reg.json")
            os.environ["DJ_CUSTOM_OP_REGISTRY"] = custom_path
            try:
                self.assertEqual(str(get_registry_path()), custom_path)
            finally:
                del os.environ["DJ_CUSTOM_OP_REGISTRY"]

class ReadWriteRegistryTest(DataJuicerTestCaseBase):
    """Test _read_registry / _write_registry helpers."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._reg_path = os.path.join(self._tmp.name, "custom_op.json")
        os.environ["DJ_CUSTOM_OP_REGISTRY"] = self._reg_path

    def tearDown(self):
        os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        self._tmp.cleanup()

    def test_read_empty(self):
        data = _read_registry()
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["custom_operators"], {})

    def test_write_and_read(self):
        payload = {
            "version": 1,
            "custom_operators": {
                "foo": {"source_path": "/tmp/foo.py", "registered_at": "2026-01-01T00:00:00"}
            },
        }
        _write_registry(payload)
        data = _read_registry()
        self.assertEqual(data, payload)

    def test_read_malformed(self):
        with open(self._reg_path, "w") as f:
            f.write("not json")
        data = _read_registry()
        self.assertEqual(data["custom_operators"], {})

class RegisterPersistentTest(DataJuicerTestCaseBase):
    """Test register_persistent end-to-end."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._reg_path = os.path.join(self._tmp.name, "custom_op.json")
        os.environ["DJ_CUSTOM_OP_REGISTRY"] = self._reg_path
        self._op_name = "test_reg_mapper"
        self._op_file = _make_custom_op_file(self._tmp.name, self._op_name)

    def tearDown(self):
        OPERATORS.unregister_module(self._op_name)
        sys.modules.pop(self._op_name, None)
        os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        self._tmp.cleanup()

    def test_register_and_json(self):
        result = register_persistent([self._op_file])
        self.assertIn(self._op_name, result["registered"])
        self.assertIn(self._op_name, OPERATORS.modules)

        data = _read_registry()
        self.assertIn(self._op_name, data["custom_operators"])
        self.assertEqual(
            data["custom_operators"][self._op_name]["source_path"],
            os.path.abspath(self._op_file),
        )

    def test_register_nonexistent_path(self):
        result = register_persistent(["/no/such/path.py"])
        self.assertEqual(result["registered"], [])
        self.assertGreater(len(result["warnings"]), 0)

class UnregisterOpsTest(DataJuicerTestCaseBase):
    """Test unregister_ops."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._reg_path = os.path.join(self._tmp.name, "custom_op.json")
        os.environ["DJ_CUSTOM_OP_REGISTRY"] = self._reg_path
        self._op_name = "test_unreg_mapper"
        self._op_file = _make_custom_op_file(self._tmp.name, self._op_name)
        register_persistent([self._op_file])

    def tearDown(self):
        OPERATORS.unregister_module(self._op_name)
        sys.modules.pop(self._op_name, None)
        os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        self._tmp.cleanup()

    def test_unregister_existing(self):
        result = unregister_ops([self._op_name])
        self.assertIn(self._op_name, result["removed"])
        self.assertEqual(result["not_found"], [])
        self.assertNotIn(self._op_name, OPERATORS.modules)

        data = _read_registry()
        self.assertNotIn(self._op_name, data["custom_operators"])

    def test_unregister_nonexistent(self):
        result = unregister_ops(["no_such_op"])
        self.assertEqual(result["removed"], [])
        self.assertIn("no_such_op", result["not_found"])

class ResetRegistryTest(DataJuicerTestCaseBase):
    """Test reset_registry."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._reg_path = os.path.join(self._tmp.name, "custom_op.json")
        os.environ["DJ_CUSTOM_OP_REGISTRY"] = self._reg_path
        self._op_name = "test_reset_mapper"
        self._op_file = _make_custom_op_file(self._tmp.name, self._op_name)
        register_persistent([self._op_file])

    def tearDown(self):
        OPERATORS.unregister_module(self._op_name)
        sys.modules.pop(self._op_name, None)
        os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        self._tmp.cleanup()

    def test_reset_clears_all(self):
        result = reset_registry()
        self.assertIn(self._op_name, result["removed"])
        self.assertNotIn(self._op_name, OPERATORS.modules)

        data = _read_registry()
        self.assertEqual(data["custom_operators"], {})

class ListRegisteredTest(DataJuicerTestCaseBase):
    """Test list_registered."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._reg_path = os.path.join(self._tmp.name, "custom_op.json")
        os.environ["DJ_CUSTOM_OP_REGISTRY"] = self._reg_path

    def tearDown(self):
        os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        self._tmp.cleanup()

    def test_list_empty(self):
        result = list_registered()
        self.assertEqual(result["custom_operators"], {})

    def test_list_after_register(self):
        op_name = "test_list_mapper"
        op_file = _make_custom_op_file(self._tmp.name, op_name)
        register_persistent([op_file])
        try:
            result = list_registered()
            self.assertIn(op_name, result["custom_operators"])
        finally:
            OPERATORS.unregister_module(op_name)
            sys.modules.pop(op_name, None)

class LoadPersistentCustomOpsTest(DataJuicerTestCaseBase):
    """Test load_persistent_custom_ops including stale-entry cleanup."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._reg_path = os.path.join(self._tmp.name, "custom_op.json")
        os.environ["DJ_CUSTOM_OP_REGISTRY"] = self._reg_path

    def tearDown(self):
        os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        self._tmp.cleanup()

    def test_load_valid(self):
        op_name = "test_load_mapper"
        op_file = _make_custom_op_file(self._tmp.name, op_name)
        register_persistent([op_file])

        OPERATORS.unregister_module(op_name)
        sys.modules.pop(op_name, None)
        self.assertNotIn(op_name, OPERATORS.modules)

        result = load_persistent_custom_ops()
        self.assertIn(op_name, result["loaded"])
        self.assertIn(op_name, OPERATORS.modules)

        OPERATORS.unregister_module(op_name)
        sys.modules.pop(op_name, None)

    def test_load_cleans_stale(self):
        payload = {
            "version": 1,
            "custom_operators": {
                "stale_op": {
                    "source_path": "/no/such/file.py",
                    "registered_at": "2026-01-01T00:00:00",
                }
            },
        }
        _write_registry(payload)

        result = load_persistent_custom_ops()
        self.assertIn("stale_op", result["cleaned"])
        self.assertGreater(len(result["warnings"]), 0)

        data = _read_registry()
        self.assertNotIn("stale_op", data["custom_operators"])

class CrossProcessVisibilityTest(DataJuicerTestCaseBase):
    """Test that a custom op registered in one process is visible in another."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._reg_path = os.path.join(self._tmp.name, "custom_op.json")
        os.environ["DJ_CUSTOM_OP_REGISTRY"] = self._reg_path
        self._op_name = "test_xproc_mapper"
        self._op_file = _make_custom_op_file(self._tmp.name, self._op_name)
        register_persistent([self._op_file])

    def tearDown(self):
        OPERATORS.unregister_module(self._op_name)
        sys.modules.pop(self._op_name, None)
        os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        self._tmp.cleanup()

    def test_cross_process(self):
        """Spawn a subprocess that loads the registry and checks the op."""
        script = textwrap.dedent(f"""\
            import os, sys, json
            os.environ["DJ_CUSTOM_OP_REGISTRY"] = "{self._reg_path}"
            from data_juicer.utils.custom_op import load_persistent_custom_ops
            from data_juicer.ops.base_op import OPERATORS
            result = load_persistent_custom_ops()
            if "{self._op_name}" in OPERATORS.modules:
                print("OK")
            else:
                print("FAIL")
                sys.exit(1)
        """)
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, f"stderr: {proc.stderr}")
        self.assertIn("OK", proc.stdout)

# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class CustomOpCLIListTest(DataJuicerTestCaseBase):
    """Test the 'list' CLI sub-command."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._reg_path = os.path.join(self._tmp.name, "custom_op.json")
        os.environ["DJ_CUSTOM_OP_REGISTRY"] = self._reg_path

    def tearDown(self):
        os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        self._tmp.cleanup()

    def test_list_empty(self):
        rc = custom_op_main(["list"])
        self.assertEqual(rc, 0)

class CustomOpCLIRegisterTest(DataJuicerTestCaseBase):
    """Test the 'register' CLI sub-command."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._reg_path = os.path.join(self._tmp.name, "custom_op.json")
        os.environ["DJ_CUSTOM_OP_REGISTRY"] = self._reg_path
        self._op_name = "cli_reg_mapper"
        self._op_file = _make_custom_op_file(self._tmp.name, self._op_name)

    def tearDown(self):
        OPERATORS.unregister_module(self._op_name)
        sys.modules.pop(self._op_name, None)
        os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        self._tmp.cleanup()

    def test_register(self):
        rc = custom_op_main(["register", self._op_file])
        self.assertEqual(rc, 0)
        self.assertIn(self._op_name, OPERATORS.modules)

class CustomOpCLIUnregisterTest(DataJuicerTestCaseBase):
    """Test the 'unregister' CLI sub-command."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._reg_path = os.path.join(self._tmp.name, "custom_op.json")
        os.environ["DJ_CUSTOM_OP_REGISTRY"] = self._reg_path
        self._op_name = "cli_unreg_mapper"
        self._op_file = _make_custom_op_file(self._tmp.name, self._op_name)
        register_persistent([self._op_file])

    def tearDown(self):
        OPERATORS.unregister_module(self._op_name)
        sys.modules.pop(self._op_name, None)
        os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        self._tmp.cleanup()

    def test_unregister(self):
        rc = custom_op_main(["unregister", self._op_name])
        self.assertEqual(rc, 0)
        self.assertNotIn(self._op_name, OPERATORS.modules)

class CustomOpCLIResetTest(DataJuicerTestCaseBase):
    """Test the 'reset' CLI sub-command."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._reg_path = os.path.join(self._tmp.name, "custom_op.json")
        os.environ["DJ_CUSTOM_OP_REGISTRY"] = self._reg_path
        self._op_name = "cli_reset_mapper"
        self._op_file = _make_custom_op_file(self._tmp.name, self._op_name)
        register_persistent([self._op_file])

    def tearDown(self):
        OPERATORS.unregister_module(self._op_name)
        sys.modules.pop(self._op_name, None)
        os.environ.pop("DJ_CUSTOM_OP_REGISTRY", None)
        self._tmp.cleanup()

    def test_reset(self):
        rc = custom_op_main(["reset"])
        self.assertEqual(rc, 0)
        self.assertNotIn(self._op_name, OPERATORS.modules)

class CustomOpCLINoCommandTest(DataJuicerTestCaseBase):
    """Test calling custom_op CLI with no command."""

    def test_no_command(self):
        rc = custom_op_main([])
        self.assertEqual(rc, 1)

if __name__ == "__main__":
    unittest.main()
