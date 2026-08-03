import json
import os
import tempfile
import unittest

from data_juicer.core.executor.pipeline_dag import DAGNodeStatus, PipelineDAG
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, TEST_TAG


@TEST_TAG("standalone")
class DAGNodeStatusTest(DataJuicerTestCaseBase):

    def test_values(self):
        self.assertEqual(DAGNodeStatus.PENDING.value, "pending")
        self.assertEqual(DAGNodeStatus.RUNNING.value, "running")
        self.assertEqual(DAGNodeStatus.COMPLETED.value, "completed")
        self.assertEqual(DAGNodeStatus.FAILED.value, "failed")

    def test_from_string(self):
        self.assertEqual(DAGNodeStatus("pending"), DAGNodeStatus.PENDING)
        self.assertEqual(DAGNodeStatus("failed"), DAGNodeStatus.FAILED)


@TEST_TAG("standalone")
class PipelineDAGTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.tmp_dir = tempfile.mkdtemp()
        self.dag = PipelineDAG(self.tmp_dir)

    def _add_nodes(self):
        self.dag.nodes = {
            "op_001_filter": {
                "node_id": "op_001_filter",
                "operation_name": "filter",
                "node_type": "operation",
                "partition_id": None,
                "dependencies": [],
                "execution_order": 1,
                "status": "pending",
                "start_time": None,
                "end_time": None,
                "actual_duration": None,
                "error_message": None,
            },
            "op_002_mapper": {
                "node_id": "op_002_mapper",
                "operation_name": "mapper",
                "node_type": "operation",
                "partition_id": None,
                "dependencies": ["op_001_filter"],
                "execution_order": 2,
                "status": "pending",
                "start_time": None,
                "end_time": None,
                "actual_duration": None,
                "error_message": None,
            },
            "op_003_dedup": {
                "node_id": "op_003_dedup",
                "operation_name": "dedup",
                "node_type": "operation",
                "partition_id": None,
                "dependencies": ["op_002_mapper"],
                "execution_order": 3,
                "status": "pending",
                "start_time": None,
                "end_time": None,
                "actual_duration": None,
                "error_message": None,
            },
        }

    def test_init(self):
        self.assertEqual(self.dag.nodes, {})
        self.assertEqual(self.dag.edges, [])

    def test_save_execution_plan(self):
        self._add_nodes()
        path = self.dag.save_execution_plan()
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(len(data["nodes"]), 3)
        self.assertIn("op_001_filter", data["nodes"])

    def test_load_execution_plan(self):
        self._add_nodes()
        self.dag.save_execution_plan()
        new_dag = PipelineDAG(self.tmp_dir)
        result = new_dag.load_execution_plan()
        self.assertTrue(result)
        self.assertEqual(len(new_dag.nodes), 3)
        self.assertEqual(new_dag.nodes["op_001_filter"]["status"], "pending")

    def test_load_execution_plan_not_found(self):
        result = self.dag.load_execution_plan("nonexistent.json")
        self.assertFalse(result)

    def test_load_execution_plan_invalid_json(self):
        bad_path = os.path.join(self.tmp_dir, "dag_execution_plan.json")
        with open(bad_path, "w") as f:
            f.write("not json")
        result = self.dag.load_execution_plan()
        self.assertFalse(result)

    def test_mark_node_started(self):
        self._add_nodes()
        self.dag.mark_node_started("op_001_filter")
        node = self.dag.nodes["op_001_filter"]
        self.assertEqual(node["status"], DAGNodeStatus.RUNNING.value)
        self.assertIsNotNone(node["start_time"])

    def test_mark_node_started_idempotent(self):
        self._add_nodes()
        self.dag.mark_node_started("op_001_filter")
        start_time = self.dag.nodes["op_001_filter"]["start_time"]
        self.dag.mark_node_started("op_001_filter")
        self.assertEqual(self.dag.nodes["op_001_filter"]["start_time"], start_time)

    def test_mark_node_started_nonexistent(self):
        self._add_nodes()
        self.dag.mark_node_started("nonexistent")  # should not raise

    def test_mark_node_completed(self):
        self._add_nodes()
        self.dag.mark_node_started("op_001_filter")
        self.dag.mark_node_completed("op_001_filter", duration=1.5)
        node = self.dag.nodes["op_001_filter"]
        self.assertEqual(node["status"], DAGNodeStatus.COMPLETED.value)
        self.assertEqual(node["actual_duration"], 1.5)
        self.assertIsNotNone(node["end_time"])

    def test_mark_node_completed_auto_duration(self):
        self._add_nodes()
        self.dag.mark_node_started("op_001_filter")
        self.dag.mark_node_completed("op_001_filter")
        node = self.dag.nodes["op_001_filter"]
        self.assertIsNotNone(node["actual_duration"])
        self.assertGreaterEqual(node["actual_duration"], 0)

    def test_mark_node_failed(self):
        self._add_nodes()
        self.dag.mark_node_started("op_002_mapper")
        self.dag.mark_node_failed("op_002_mapper", "OOM error")
        node = self.dag.nodes["op_002_mapper"]
        self.assertEqual(node["status"], DAGNodeStatus.FAILED.value)
        self.assertEqual(node["error_message"], "OOM error")
        self.assertIsNotNone(node["actual_duration"])

    def test_get_node_status(self):
        self._add_nodes()
        self.assertEqual(self.dag.get_node_status("op_001_filter"),
                         DAGNodeStatus.PENDING)
        self.dag.mark_node_started("op_001_filter")
        self.assertEqual(self.dag.get_node_status("op_001_filter"),
                         DAGNodeStatus.RUNNING)

    def test_get_node_status_nonexistent(self):
        self.assertEqual(self.dag.get_node_status("fake"),
                         DAGNodeStatus.PENDING)

    def test_get_ready_nodes_initial(self):
        self._add_nodes()
        ready = self.dag.get_ready_nodes()
        self.assertEqual(ready, ["op_001_filter"])

    def test_get_ready_nodes_after_completion(self):
        self._add_nodes()
        self.dag.mark_node_started("op_001_filter")
        self.dag.mark_node_completed("op_001_filter")
        ready = self.dag.get_ready_nodes()
        self.assertEqual(ready, ["op_002_mapper"])

    def test_get_ready_nodes_none_ready(self):
        self._add_nodes()
        self.dag.mark_node_started("op_001_filter")
        ready = self.dag.get_ready_nodes()
        self.assertEqual(ready, [])

    def test_get_execution_summary(self):
        self._add_nodes()
        self.dag.mark_node_started("op_001_filter")
        self.dag.mark_node_completed("op_001_filter", duration=2.0)
        self.dag.mark_node_started("op_002_mapper")
        self.dag.mark_node_failed("op_002_mapper", "error")

        summary = self.dag.get_execution_summary()
        self.assertEqual(summary["total_nodes"], 3)
        self.assertEqual(summary["completed_nodes"], 1)
        self.assertEqual(summary["failed_nodes"], 1)
        self.assertEqual(summary["pending_nodes"], 1)
        self.assertAlmostEqual(summary["completion_percentage"], 100 / 3, places=1)

    def test_get_execution_summary_empty(self):
        summary = self.dag.get_execution_summary()
        self.assertEqual(summary["total_nodes"], 0)
        self.assertEqual(summary["completion_percentage"], 0)

    def test_visualize_empty(self):
        result = self.dag.visualize()
        self.assertEqual(result, "Empty DAG")

    def test_visualize_with_nodes(self):
        self._add_nodes()
        result = self.dag.visualize()
        self.assertIn("DAG Execution Plan", result)
        self.assertIn("filter", result)


if __name__ == "__main__":
    unittest.main()
