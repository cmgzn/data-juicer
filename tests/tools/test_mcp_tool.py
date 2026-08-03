import os
import unittest

from data_juicer.tools.mcp_tool import (
    DEFAULT_OUTPUT_DIR,
    add_extra_cfg,
    execute_analyze,
    execute_op,
)
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class AddExtraCfgTest(DataJuicerTestCaseBase):

    def setUp(self):
        self._orig_server_transport = os.environ.get("SERVER_TRANSPORT")

    def tearDown(self):
        if self._orig_server_transport is None:
            os.environ.pop("SERVER_TRANSPORT", None)
        else:
            os.environ["SERVER_TRANSPORT"] = self._orig_server_transport

    def test_export_path_generated_when_missing(self):
        cfg = {}
        result = add_extra_cfg(cfg)
        self.assertIn("export_path", result)
        self.assertTrue(result["export_path"].startswith(DEFAULT_OUTPUT_DIR))
        self.assertTrue(result["export_path"].endswith("processed_data.jsonl"))

    def test_export_path_preserved_when_set(self):
        cfg = {"export_path": "/my/custom/path.jsonl"}
        result = add_extra_cfg(cfg)
        self.assertEqual(result["export_path"], "/my/custom/path.jsonl")

    def test_np_defaults_to_1_when_not_set(self):
        os.environ.pop("SERVER_TRANSPORT", None)
        cfg = {}
        result = add_extra_cfg(cfg)
        self.assertEqual(result["np"], 1)

    def test_np_preserved_when_set_and_transport_not_stdio(self):
        os.environ["SERVER_TRANSPORT"] = "sse"
        cfg = {"np": 4}
        result = add_extra_cfg(cfg)
        self.assertEqual(result["np"], 4)

    def test_np_forced_to_1_when_transport_is_stdio(self):
        os.environ["SERVER_TRANSPORT"] = "stdio"
        cfg = {"np": 8}
        result = add_extra_cfg(cfg)
        self.assertEqual(result["np"], 1)

    def test_open_monitor_always_false(self):
        cfg = {"open_monitor": True}
        result = add_extra_cfg(cfg)
        self.assertFalse(result["open_monitor"])

    def test_returns_modified_dict(self):
        cfg = {"export_path": "/tmp/out.jsonl", "np": 2}
        os.environ["SERVER_TRANSPORT"] = "sse"
        result = add_extra_cfg(cfg)
        self.assertIs(result, cfg)
        self.assertIn("open_monitor", result)


class ExecuteOpTest(DataJuicerTestCaseBase):

    def test_invalid_config_returns_error_string(self):
        # Pass a config that will cause an exception during execution
        cfg = {}
        result = execute_op(cfg)
        self.assertIsInstance(result, str)
        self.assertTrue(
            result.startswith("Occur error when executing Data-Juicer:")
        )


class ExecuteAnalyzeTest(DataJuicerTestCaseBase):

    def test_invalid_config_returns_error_string(self):
        # Pass a config that will cause an exception during analysis
        cfg = {}
        result = execute_analyze(cfg)
        self.assertIsInstance(result, str)
        self.assertTrue(
            result.startswith(
                "Occur error when executing Data-Juicer Analyzer:"
            )
        )


if __name__ == "__main__":
    unittest.main()
