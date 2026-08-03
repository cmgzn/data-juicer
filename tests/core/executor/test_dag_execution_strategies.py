import unittest

from data_juicer.core.executor.dag_execution_strategies import (
    DAGNodeStatusTransition,
    DAGNodeType,
    NodeID,
    NonPartitionedDAGStrategy,
    PartitionedDAGStrategy,
    ScatterGatherNode,
    is_global_operation,
)
from data_juicer.core.executor.pipeline_dag import DAGNodeStatus
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, TEST_TAG


class FakeOp:
    def __init__(self, name):
        self._name = name


@TEST_TAG("standalone")
class DAGNodeStatusTransitionTest(DataJuicerTestCaseBase):

    def test_pending_to_running(self):
        self.assertTrue(DAGNodeStatusTransition.is_valid(
            DAGNodeStatus.PENDING, DAGNodeStatus.RUNNING))

    def test_pending_to_completed(self):
        self.assertTrue(DAGNodeStatusTransition.is_valid(
            DAGNodeStatus.PENDING, DAGNodeStatus.COMPLETED))

    def test_running_to_completed(self):
        self.assertTrue(DAGNodeStatusTransition.is_valid(
            DAGNodeStatus.RUNNING, DAGNodeStatus.COMPLETED))

    def test_running_to_failed(self):
        self.assertTrue(DAGNodeStatusTransition.is_valid(
            DAGNodeStatus.RUNNING, DAGNodeStatus.FAILED))

    def test_failed_to_running_retry(self):
        self.assertTrue(DAGNodeStatusTransition.is_valid(
            DAGNodeStatus.FAILED, DAGNodeStatus.RUNNING))

    def test_completed_is_terminal(self):
        self.assertFalse(DAGNodeStatusTransition.is_valid(
            DAGNodeStatus.COMPLETED, DAGNodeStatus.RUNNING))
        self.assertFalse(DAGNodeStatusTransition.is_valid(
            DAGNodeStatus.COMPLETED, DAGNodeStatus.FAILED))

    def test_invalid_pending_to_failed(self):
        self.assertFalse(DAGNodeStatusTransition.is_valid(
            DAGNodeStatus.PENDING, DAGNodeStatus.FAILED))

    def test_string_inputs(self):
        self.assertTrue(DAGNodeStatusTransition.is_valid("pending", "running"))
        self.assertFalse(DAGNodeStatusTransition.is_valid("completed", "running"))

    def test_validate_and_log_valid(self):
        self.assertTrue(DAGNodeStatusTransition.validate_and_log(
            "node_1", DAGNodeStatus.PENDING, DAGNodeStatus.RUNNING))

    def test_validate_and_log_invalid(self):
        self.assertFalse(DAGNodeStatusTransition.validate_and_log(
            "node_1", DAGNodeStatus.COMPLETED, DAGNodeStatus.RUNNING))


@TEST_TAG("standalone")
class ScatterGatherNodeTest(DataJuicerTestCaseBase):

    def test_node_id(self):
        node = ScatterGatherNode(
            operation_index=5,
            operation_name="dedup",
            input_partitions=[0, 1, 2],
            output_partitions=[0, 1, 2],
        )
        self.assertEqual(node.node_id, "sg_005_dedup")

    def test_node_id_zero_index(self):
        node = ScatterGatherNode(
            operation_index=0,
            operation_name="sort",
            input_partitions=[0],
            output_partitions=[0],
        )
        self.assertEqual(node.node_id, "sg_000_sort")


@TEST_TAG("standalone")
class NodeIDTest(DataJuicerTestCaseBase):

    def test_for_operation(self):
        self.assertEqual(NodeID.for_operation(0, "filter"), "op_001_filter")
        self.assertEqual(NodeID.for_operation(9, "mapper"), "op_010_mapper")

    def test_for_partition_operation(self):
        self.assertEqual(
            NodeID.for_partition_operation(2, 0, "filter"),
            "op_001_filter_partition_2")

    def test_for_scatter_gather(self):
        self.assertEqual(NodeID.for_scatter_gather(3, "dedup"), "sg_003_dedup")

    def test_parse_operation(self):
        result = NodeID.parse("op_001_mapper")
        self.assertEqual(result["type"], DAGNodeType.OPERATION)
        self.assertEqual(result["operation_index"], 0)
        self.assertEqual(result["operation_name"], "mapper")

    def test_parse_partition_operation(self):
        result = NodeID.parse("op_002_filter_partition_3")
        self.assertEqual(result["type"], DAGNodeType.PARTITION_OPERATION)
        self.assertEqual(result["operation_index"], 1)
        self.assertEqual(result["operation_name"], "filter")
        self.assertEqual(result["partition_id"], 3)

    def test_parse_scatter_gather(self):
        result = NodeID.parse("sg_005_deduplicator")
        self.assertEqual(result["type"], DAGNodeType.SCATTER_GATHER)
        self.assertEqual(result["operation_index"], 5)
        self.assertEqual(result["operation_name"], "deduplicator")

    def test_parse_invalid(self):
        self.assertIsNone(NodeID.parse("invalid_format"))

    def test_parse_complex_op_name(self):
        result = NodeID.parse("op_001_text_length_filter_partition_0")
        self.assertEqual(result["type"], DAGNodeType.PARTITION_OPERATION)
        self.assertEqual(result["operation_name"], "text_length_filter")
        self.assertEqual(result["partition_id"], 0)


@TEST_TAG("standalone")
class NonPartitionedDAGStrategyTest(DataJuicerTestCaseBase):

    def setUp(self):
        self.strategy = NonPartitionedDAGStrategy()
        self.ops = [FakeOp("filter"), FakeOp("mapper"), FakeOp("dedup")]

    def test_generate_dag_nodes(self):
        nodes = self.strategy.generate_dag_nodes(self.ops)
        self.assertEqual(len(nodes), 3)
        self.assertIn("op_001_filter", nodes)
        self.assertIn("op_002_mapper", nodes)
        self.assertIn("op_003_dedup", nodes)

    def test_node_structure(self):
        nodes = self.strategy.generate_dag_nodes(self.ops)
        node = nodes["op_001_filter"]
        self.assertEqual(node["operation_name"], "filter")
        self.assertEqual(node["execution_order"], 1)
        self.assertEqual(node["node_type"], DAGNodeType.OPERATION.value)
        self.assertIsNone(node["partition_id"])
        self.assertEqual(node["status"], "pending")

    def test_build_dependencies(self):
        nodes = self.strategy.generate_dag_nodes(self.ops)
        self.strategy.build_dependencies(nodes, self.ops)
        self.assertEqual(nodes["op_001_filter"]["dependencies"], [])
        self.assertEqual(nodes["op_002_mapper"]["dependencies"], ["op_001_filter"])
        self.assertEqual(nodes["op_003_dedup"]["dependencies"], ["op_002_mapper"])

    def test_can_execute_node_no_deps(self):
        nodes = self.strategy.generate_dag_nodes(self.ops)
        self.strategy.build_dependencies(nodes, self.ops)
        self.assertTrue(self.strategy.can_execute_node("op_001_filter", nodes, set()))

    def test_can_execute_node_deps_met(self):
        nodes = self.strategy.generate_dag_nodes(self.ops)
        self.strategy.build_dependencies(nodes, self.ops)
        self.assertTrue(self.strategy.can_execute_node(
            "op_002_mapper", nodes, {"op_001_filter"}))

    def test_can_execute_node_deps_not_met(self):
        nodes = self.strategy.generate_dag_nodes(self.ops)
        self.strategy.build_dependencies(nodes, self.ops)
        self.assertFalse(self.strategy.can_execute_node(
            "op_002_mapper", nodes, set()))

    def test_can_execute_nonexistent_node(self):
        nodes = self.strategy.generate_dag_nodes(self.ops)
        self.assertFalse(self.strategy.can_execute_node("fake", nodes, set()))

    def test_get_dag_node_id(self):
        self.assertEqual(self.strategy.get_dag_node_id("x", 0), "op_001_x")

    def test_validate_dag_no_cycles(self):
        nodes = self.strategy.generate_dag_nodes(self.ops)
        self.strategy.build_dependencies(nodes, self.ops)
        self.assertTrue(self.strategy.validate_dag(nodes))

    def test_validate_dag_with_cycle(self):
        nodes = self.strategy.generate_dag_nodes(self.ops)
        self.strategy.build_dependencies(nodes, self.ops)
        nodes["op_001_filter"]["dependencies"].append("op_003_dedup")
        self.assertFalse(self.strategy.validate_dag(nodes))


@TEST_TAG("standalone")
class PartitionedDAGStrategyTest(DataJuicerTestCaseBase):

    def setUp(self):
        self.strategy = PartitionedDAGStrategy(num_partitions=2)
        self.ops = [FakeOp("filter"), FakeOp("dedup"), FakeOp("mapper")]

    def test_generate_nodes_partition_count(self):
        nodes = self.strategy.generate_dag_nodes(self.ops)
        partition_nodes = [n for n in nodes if "partition" in n]
        self.assertEqual(len(partition_nodes), 6)  # 3 ops x 2 partitions

    def test_generate_with_convergence_points(self):
        nodes = self.strategy.generate_dag_nodes(
            self.ops, convergence_points=[1])
        sg_nodes = [n for n in nodes if n.startswith("sg_")]
        self.assertEqual(len(sg_nodes), 1)
        self.assertIn("sg_001_dedup", nodes)

    def test_scatter_gather_node_structure(self):
        nodes = self.strategy.generate_dag_nodes(
            self.ops, convergence_points=[1])
        sg = nodes["sg_001_dedup"]
        self.assertEqual(sg["node_type"], DAGNodeType.SCATTER_GATHER.value)
        self.assertEqual(sg["input_partitions"], [0, 1])
        self.assertEqual(sg["output_partitions"], [0, 1])

    def test_get_dag_node_id_with_partition(self):
        self.assertEqual(
            self.strategy.get_dag_node_id("f", 0, partition_id=1),
            "op_001_f_partition_1")

    def test_get_dag_node_id_without_partition(self):
        self.assertEqual(self.strategy.get_dag_node_id("f", 0), "op_001_f")

    def test_build_dependencies_sequential(self):
        nodes = self.strategy.generate_dag_nodes(self.ops)
        self.strategy.build_dependencies(nodes, self.ops)
        node = nodes["op_002_dedup_partition_0"]
        self.assertIn("op_001_filter_partition_0", node["dependencies"])

    def test_build_dependencies_with_scatter_gather(self):
        nodes = self.strategy.generate_dag_nodes(
            self.ops, convergence_points=[1])
        self.strategy.build_dependencies(
            nodes, self.ops, convergence_points=[1])
        sg = nodes["sg_001_dedup"]
        self.assertIn("op_001_filter_partition_0", sg["dependencies"])
        self.assertIn("op_001_filter_partition_1", sg["dependencies"])

    def test_can_execute_scatter_gather(self):
        nodes = self.strategy.generate_dag_nodes(
            self.ops, convergence_points=[1])
        self.strategy.build_dependencies(
            nodes, self.ops, convergence_points=[1])
        completed = {"op_001_filter_partition_0", "op_001_filter_partition_1"}
        self.assertTrue(self.strategy.can_execute_node(
            "sg_001_dedup", nodes, completed))


@TEST_TAG("standalone")
class IsGlobalOperationTest(DataJuicerTestCaseBase):

    def test_explicit_flag(self):
        class Op:
            is_global_operation = True
            _name = "custom_op"
        self.assertTrue(is_global_operation(Op()))

    def test_no_flag(self):
        class Op:
            _name = "filter"
        self.assertFalse(is_global_operation(Op()))

    def test_name_pattern_deduplicator(self):
        class Op:
            _name = "ray_deduplicator"
        self.assertTrue(is_global_operation(Op()))

    def test_name_pattern_global_prefix(self):
        class Op:
            _name = "global_sort"
        self.assertTrue(is_global_operation(Op()))

    def test_name_pattern_full_dataset_prefix(self):
        class Op:
            _name = "full_dataset_stats"
        self.assertTrue(is_global_operation(Op()))


if __name__ == "__main__":
    unittest.main()
