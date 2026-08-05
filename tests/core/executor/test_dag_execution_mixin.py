import os
import tempfile
import threading
import time
import unittest

from data_juicer.core.executor.dag_execution_mixin import DAGExecutionMixin
from data_juicer.core.executor.dag_execution_strategies import (
    NonPartitionedDAGStrategy,
    PartitionedDAGStrategy,
)
from data_juicer.core.executor.pipeline_dag import DAGNodeStatus, PipelineDAG
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


# ==================== Fake/Helper Classes ====================


class FakeOperation:
    """Fake operation with _name attribute for testing."""

    def __init__(self, name):
        self._name = name


class FakeConfig:
    """Fake configuration object for testing."""

    def __init__(self, work_dir=None, process=None, use_dag=None):
        self.work_dir = work_dir or tempfile.mkdtemp()
        self.process = process or []
        if use_dag is not None:
            self.use_dag = use_dag


class ConcreteDAGExecutor(DAGExecutionMixin):
    """Concrete class inheriting from DAGExecutionMixin for testing."""

    def __init__(self, executor_type="default", num_partitions=None):
        DAGExecutionMixin.__init__(self)
        self.executor_type = executor_type
        if num_partitions is not None:
            self.num_partitions = num_partitions


# ==================== Test Classes ====================


class DAGExecutionMixinInitTest(DataJuicerTestCaseBase):
    """Tests for DAGExecutionMixin.__init__()."""

    def test_state_lock_is_reentrant(self):
        """Verify the lock is reentrant — concurrent mark calls depend on this."""
        executor = ConcreteDAGExecutor()
        executor._dag_state_lock.acquire()
        executor._dag_state_lock.acquire()
        executor._dag_state_lock.release()
        executor._dag_state_lock.release()

    def test_fresh_executor_not_initialized(self):
        """A fresh executor must report dag_initialized=False so that
        _initialize_dag_execution runs on first call."""
        executor = ConcreteDAGExecutor()
        self.assertFalse(executor.dag_initialized)
        self.assertIsNone(executor.pipeline_dag)


class CurrentDagNodePropertyTest(DataJuicerTestCaseBase):
    """Tests for current_dag_node thread-local property."""

    def test_initial_value_is_none(self):
        """Test that current_dag_node is initially None."""
        executor = ConcreteDAGExecutor()
        self.assertIsNone(executor.current_dag_node)

    def test_set_and_get(self):
        """Test setting and getting current_dag_node."""
        executor = ConcreteDAGExecutor()
        executor.current_dag_node = "op_001_filter"
        self.assertEqual(executor.current_dag_node, "op_001_filter")

    def test_set_to_none(self):
        """Test setting current_dag_node back to None."""
        executor = ConcreteDAGExecutor()
        executor.current_dag_node = "op_001_filter"
        executor.current_dag_node = None
        self.assertIsNone(executor.current_dag_node)

    def test_thread_local_isolation(self):
        """Test that current_dag_node is thread-local."""
        executor = ConcreteDAGExecutor()
        results = {}

        def set_in_thread(name, value):
            executor.current_dag_node = value
            time.sleep(0.05)  # Allow other thread to run
            results[name] = executor.current_dag_node

        t1 = threading.Thread(target=set_in_thread, args=("thread1", "node_A"))
        t2 = threading.Thread(target=set_in_thread, args=("thread2", "node_B"))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Each thread should see its own value
        self.assertEqual(results["thread1"], "node_A")
        self.assertEqual(results["thread2"], "node_B")

    def test_main_thread_not_affected_by_other_threads(self):
        """Test that main thread value is not affected by other threads."""
        executor = ConcreteDAGExecutor()
        executor.current_dag_node = "main_node"

        def set_in_thread():
            executor.current_dag_node = "other_node"

        t = threading.Thread(target=set_in_thread)
        t.start()
        t.join()

        # Main thread should still see its own value
        self.assertEqual(executor.current_dag_node, "main_node")


class IsPartitionedExecutorTest(DataJuicerTestCaseBase):
    """Tests for _is_partitioned_executor()."""

    def test_returns_true_for_ray_partitioned(self):
        """Test returns True when executor_type is ray_partitioned."""
        executor = ConcreteDAGExecutor(executor_type="ray_partitioned")
        self.assertTrue(executor._is_partitioned_executor())

    def test_returns_false_for_default(self):
        """Test returns False when executor_type is default."""
        executor = ConcreteDAGExecutor(executor_type="default")
        self.assertFalse(executor._is_partitioned_executor())

    def test_returns_false_for_ray(self):
        """Test returns False when executor_type is ray (non-partitioned)."""
        executor = ConcreteDAGExecutor(executor_type="ray")
        self.assertFalse(executor._is_partitioned_executor())

    def test_returns_false_when_no_executor_type(self):
        """Test returns False when executor_type attribute is missing."""
        executor = DAGExecutionMixin()
        DAGExecutionMixin.__init__(executor)
        self.assertFalse(executor._is_partitioned_executor())


class CreateExecutionStrategyTest(DataJuicerTestCaseBase):
    """Tests for _create_execution_strategy()."""

    def test_creates_non_partitioned_strategy_for_default(self):
        """Test creates NonPartitionedDAGStrategy for default executor."""
        executor = ConcreteDAGExecutor(executor_type="default")
        cfg = FakeConfig()
        strategy = executor._create_execution_strategy(cfg)
        self.assertIsInstance(strategy, NonPartitionedDAGStrategy)

    def test_creates_non_partitioned_strategy_for_ray(self):
        """Test creates NonPartitionedDAGStrategy for ray executor."""
        executor = ConcreteDAGExecutor(executor_type="ray")
        cfg = FakeConfig()
        strategy = executor._create_execution_strategy(cfg)
        self.assertIsInstance(strategy, NonPartitionedDAGStrategy)

    def test_creates_partitioned_strategy_for_ray_partitioned(self):
        """Test creates PartitionedDAGStrategy for ray_partitioned executor."""
        executor = ConcreteDAGExecutor(
            executor_type="ray_partitioned", num_partitions=4
        )
        cfg = FakeConfig()
        strategy = executor._create_execution_strategy(cfg)
        self.assertIsInstance(strategy, PartitionedDAGStrategy)

    def test_partitioned_strategy_raises_without_num_partitions(self):
        """Test that creating partitioned strategy without num_partitions raises."""
        executor = ConcreteDAGExecutor(executor_type="ray_partitioned")
        # Remove num_partitions attribute
        if hasattr(executor, "num_partitions"):
            delattr(executor, "num_partitions")
        cfg = FakeConfig()
        with self.assertRaises(ValueError):
            executor._create_execution_strategy(cfg)


class InitializeDAGExecutionTest(DataJuicerTestCaseBase):
    """Tests for _initialize_dag_execution()."""

    def test_skips_if_already_initialized(self):
        """Test that initialization is skipped if dag_initialized is True."""
        executor = ConcreteDAGExecutor()
        executor.dag_initialized = True
        executor._initialize_dag_execution(FakeConfig(), [])
        # Should not change anything
        self.assertIsNone(executor.pipeline_dag)

    def test_disables_dag_for_standalone_mode(self):
        """Test DAG disabled when use_dag=False."""
        executor = ConcreteDAGExecutor(executor_type="default")
        cfg = FakeConfig(use_dag=False)
        executor._initialize_dag_execution(cfg, [])
        self.assertTrue(executor.dag_initialized)
        self.assertIsNone(executor.pipeline_dag)

    def test_default_executor_disables_dag_by_default(self):
        """Test that default executor disables DAG unless explicitly enabled."""
        executor = ConcreteDAGExecutor(executor_type="default")
        cfg = FakeConfig()  # No use_dag set
        executor._initialize_dag_execution(cfg, [])
        self.assertTrue(executor.dag_initialized)
        # For default executor with no explicit use_dag, DAG should be disabled
        self.assertIsNone(executor.pipeline_dag)

    def test_initializes_with_ops(self):
        """Test that initialization works with provided ops."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("text_filter"), FakeOperation("clean_mapper")]
        cfg = FakeConfig(work_dir=work_dir, use_dag=True)

        executor._initialize_dag_execution(cfg, ops)

        self.assertTrue(executor.dag_initialized)
        self.assertIsNotNone(executor.pipeline_dag)
        self.assertIsNotNone(executor.dag_execution_strategy)
        self.assertIsNotNone(executor.dag_execution_start_time)

    def test_stores_ops_for_reuse(self):
        """Test that ops are stored in _dag_ops for reuse."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("filter_op")]
        cfg = FakeConfig(work_dir=work_dir, use_dag=True)

        executor._initialize_dag_execution(cfg, ops)

        self.assertEqual(executor._dag_ops, ops)

    def test_initializes_pipeline_dag_with_correct_nodes(self):
        """Test that pipeline_dag has correct number of nodes."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("op_a"), FakeOperation("op_b"), FakeOperation("op_c")]
        cfg = FakeConfig(work_dir=work_dir, use_dag=True)

        executor._initialize_dag_execution(cfg, ops)

        self.assertEqual(len(executor.pipeline_dag.nodes), 3)


class GetOperationsFromConfigTest(DataJuicerTestCaseBase):
    """Tests for _get_operations_from_config()."""

    def test_returns_cached_ops(self):
        """Test returns cached _dag_ops when available."""
        executor = ConcreteDAGExecutor()
        cached_ops = [FakeOperation("cached_op")]
        executor._dag_ops = cached_ops
        cfg = FakeConfig()

        result = executor._get_operations_from_config(cfg)
        self.assertEqual(result, cached_ops)

    def test_returns_cached_ops_not_config(self):
        """Test that cached ops take priority over config."""
        executor = ConcreteDAGExecutor()
        cached_ops = [FakeOperation("cached_op")]
        executor._dag_ops = cached_ops
        cfg = FakeConfig(process=[{"some_op": {}}])

        result = executor._get_operations_from_config(cfg)
        self.assertEqual(result, cached_ops)
        self.assertEqual(result[0]._name, "cached_op")


class GenerateDAGWithStrategyTest(DataJuicerTestCaseBase):
    """Tests for _generate_dag_with_strategy()."""

    def test_generates_sequential_dag_for_non_partitioned(self):
        """Test DAG generation for non-partitioned executor."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("filter"), FakeOperation("mapper")]
        executor._dag_ops = ops
        executor.dag_execution_strategy = NonPartitionedDAGStrategy()

        cfg = FakeConfig(work_dir=work_dir)
        executor._generate_dag_with_strategy(cfg)

        self.assertIsNotNone(executor.pipeline_dag)
        self.assertEqual(len(executor.pipeline_dag.nodes), 2)

        # Verify sequential dependency
        second_node_id = "op_002_mapper"
        self.assertIn(second_node_id, executor.pipeline_dag.nodes)
        node = executor.pipeline_dag.nodes[second_node_id]
        self.assertEqual(node["dependencies"], ["op_001_filter"])

    def test_generates_partitioned_dag(self):
        """Test DAG generation for partitioned executor."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(
            executor_type="ray_partitioned", num_partitions=2
        )
        ops = [FakeOperation("filter"), FakeOperation("mapper")]
        executor._dag_ops = ops
        executor.dag_execution_strategy = PartitionedDAGStrategy(num_partitions=2)

        cfg = FakeConfig(work_dir=work_dir)
        executor._generate_dag_with_strategy(cfg)

        self.assertIsNotNone(executor.pipeline_dag)
        # 2 ops * 2 partitions = 4 nodes
        self.assertEqual(len(executor.pipeline_dag.nodes), 4)

    def test_saves_execution_plan_file(self):
        """Test that execution plan is saved to disk."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("filter")]
        executor._dag_ops = ops
        executor.dag_execution_strategy = NonPartitionedDAGStrategy()

        cfg = FakeConfig(work_dir=work_dir)
        executor._generate_dag_with_strategy(cfg)

        plan_path = os.path.join(work_dir, "dag_execution_plan.json")
        self.assertTrue(os.path.exists(plan_path))


class MarkDAGNodeStartedTest(DataJuicerTestCaseBase):
    """Tests for _mark_dag_node_started()."""

    def _create_executor_with_dag(self):
        """Helper to create executor with an initialized DAG."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("filter"), FakeOperation("mapper")]
        executor._dag_ops = ops
        executor.dag_execution_strategy = NonPartitionedDAGStrategy()
        cfg = FakeConfig(work_dir=work_dir)
        executor._generate_dag_with_strategy(cfg)
        return executor

    def test_marks_node_as_running(self):
        """Test that node status is set to running."""
        executor = self._create_executor_with_dag()
        node_id = "op_001_filter"

        executor._mark_dag_node_started(node_id)

        node = executor.pipeline_dag.nodes[node_id]
        self.assertEqual(node["status"], DAGNodeStatus.RUNNING.value)

    def test_sets_current_dag_node(self):
        """Test that current_dag_node is set."""
        executor = self._create_executor_with_dag()
        node_id = "op_001_filter"

        executor._mark_dag_node_started(node_id)

        self.assertEqual(executor.current_dag_node, node_id)

    def test_updates_current_dag_nodes_dict(self):
        """Test that current_dag_nodes dict is updated."""
        executor = self._create_executor_with_dag()
        node_id = "op_001_filter"

        executor._mark_dag_node_started(node_id)

        # Node has partition_id=None for non-partitioned
        self.assertIn(None, executor.current_dag_nodes)
        self.assertEqual(executor.current_dag_nodes[None], node_id)

    def test_ignores_nonexistent_node(self):
        """Test that marking nonexistent node does nothing."""
        executor = self._create_executor_with_dag()
        # Should not raise
        executor._mark_dag_node_started("nonexistent_node")

    def test_ignores_when_pipeline_dag_is_none(self):
        """Test that method does nothing when pipeline_dag is None."""
        executor = ConcreteDAGExecutor()
        # Should not raise
        executor._mark_dag_node_started("op_001_filter")

    def test_sets_start_time(self):
        """Test that start_time is set on the node."""
        executor = self._create_executor_with_dag()
        node_id = "op_001_filter"

        before = time.time()
        executor._mark_dag_node_started(node_id)
        after = time.time()

        node = executor.pipeline_dag.nodes[node_id]
        self.assertIsNotNone(node.get("start_time"))
        self.assertGreaterEqual(node["start_time"], before)
        self.assertLessEqual(node["start_time"], after)


class MarkDAGNodeCompletedTest(DataJuicerTestCaseBase):
    """Tests for _mark_dag_node_completed()."""

    def _create_executor_with_running_node(self):
        """Helper to create executor with a running node."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("filter"), FakeOperation("mapper")]
        executor._dag_ops = ops
        executor.dag_execution_strategy = NonPartitionedDAGStrategy()
        cfg = FakeConfig(work_dir=work_dir)
        executor._generate_dag_with_strategy(cfg)
        executor._mark_dag_node_started("op_001_filter")
        return executor

    def test_marks_node_as_completed(self):
        """Test that node status is set to completed."""
        executor = self._create_executor_with_running_node()
        node_id = "op_001_filter"

        executor._mark_dag_node_completed(node_id, duration=1.5)

        node = executor.pipeline_dag.nodes[node_id]
        self.assertEqual(node["status"], DAGNodeStatus.COMPLETED.value)

    def test_clears_current_dag_node(self):
        """Test that current_dag_node is cleared after completion."""
        executor = self._create_executor_with_running_node()
        node_id = "op_001_filter"

        executor._mark_dag_node_completed(node_id, duration=1.0)

        self.assertIsNone(executor.current_dag_node)

    def test_removes_from_current_dag_nodes_dict(self):
        """Test that node is removed from current_dag_nodes dict."""
        executor = self._create_executor_with_running_node()
        node_id = "op_001_filter"

        executor._mark_dag_node_completed(node_id, duration=1.0)

        self.assertNotIn(None, executor.current_dag_nodes)

    def test_records_duration(self):
        """Test that duration is recorded on the node."""
        executor = self._create_executor_with_running_node()
        node_id = "op_001_filter"

        executor._mark_dag_node_completed(node_id, duration=2.5)

        node = executor.pipeline_dag.nodes[node_id]
        self.assertEqual(node["actual_duration"], 2.5)

    def test_ignores_nonexistent_node(self):
        """Test that marking nonexistent node does nothing."""
        executor = self._create_executor_with_running_node()
        # Should not raise
        executor._mark_dag_node_completed("nonexistent_node", duration=1.0)

    def test_ignores_when_pipeline_dag_is_none(self):
        """Test that method does nothing when pipeline_dag is None."""
        executor = ConcreteDAGExecutor()
        # Should not raise
        executor._mark_dag_node_completed("op_001_filter", duration=1.0)


class MarkDAGNodeFailedTest(DataJuicerTestCaseBase):
    """Tests for _mark_dag_node_failed()."""

    def _create_executor_with_running_node(self):
        """Helper to create executor with a running node."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("filter"), FakeOperation("mapper")]
        executor._dag_ops = ops
        executor.dag_execution_strategy = NonPartitionedDAGStrategy()
        cfg = FakeConfig(work_dir=work_dir)
        executor._generate_dag_with_strategy(cfg)
        executor._mark_dag_node_started("op_001_filter")
        return executor

    def test_marks_node_as_failed(self):
        """Test that node status is set to failed."""
        executor = self._create_executor_with_running_node()
        node_id = "op_001_filter"

        executor._mark_dag_node_failed(node_id, "Some error", duration=0.5)

        node = executor.pipeline_dag.nodes[node_id]
        self.assertEqual(node["status"], DAGNodeStatus.FAILED.value)

    def test_records_error_message(self):
        """Test that error_message is recorded."""
        executor = self._create_executor_with_running_node()
        node_id = "op_001_filter"

        executor._mark_dag_node_failed(node_id, "OutOfMemory error", duration=0.5)

        node = executor.pipeline_dag.nodes[node_id]
        self.assertEqual(node["error_message"], "OutOfMemory error")

    def test_clears_current_dag_node(self):
        """Test that current_dag_node is cleared after failure."""
        executor = self._create_executor_with_running_node()
        node_id = "op_001_filter"

        executor._mark_dag_node_failed(node_id, "error", duration=0.5)

        self.assertIsNone(executor.current_dag_node)

    def test_removes_from_current_dag_nodes_dict(self):
        """Test that node is removed from current_dag_nodes dict."""
        executor = self._create_executor_with_running_node()
        node_id = "op_001_filter"

        executor._mark_dag_node_failed(node_id, "error", duration=0.5)

        self.assertNotIn(None, executor.current_dag_nodes)

    def test_ignores_nonexistent_node(self):
        """Test that marking nonexistent node does nothing."""
        executor = self._create_executor_with_running_node()
        # Should not raise
        executor._mark_dag_node_failed("nonexistent_node", "error", duration=0.5)

    def test_ignores_when_pipeline_dag_is_none(self):
        """Test that method does nothing when pipeline_dag is None."""
        executor = ConcreteDAGExecutor()
        # Should not raise
        executor._mark_dag_node_failed("op_001_filter", "error", duration=0.5)


class ExtractOperationTypesTest(DataJuicerTestCaseBase):
    """Tests for _extract_operation_types_from_ops()."""

    def test_detects_all_suffix_types_and_deduplicates(self):
        executor = ConcreteDAGExecutor()
        ops = [
            FakeOperation("text_length_filter"),
            FakeOperation("language_filter"),
            FakeOperation("clean_mapper"),
            FakeOperation("minhash_deduplicator"),
            FakeOperation("topk_selector"),
            FakeOperation("key_value_grouper"),
            FakeOperation("nested_aggregator"),
        ]
        types = executor._extract_operation_types_from_ops(ops)
        for expected in ("filter", "mapper", "deduplicator", "selector", "grouper", "aggregator"):
            self.assertIn(expected, types)
        self.assertEqual(types.count("filter"), 1)

    def test_empty_ops_returns_empty(self):
        executor = ConcreteDAGExecutor()
        self.assertEqual(executor._extract_operation_types_from_ops([]), [])

    def test_unrecognized_suffix_excluded(self):
        executor = ConcreteDAGExecutor()
        ops = [FakeOperation("unknown_op")]
        self.assertEqual(len(executor._extract_operation_types_from_ops(ops)), 0)



class GetDAGExecutionStatusTest(DataJuicerTestCaseBase):
    """Tests for get_dag_execution_status()."""

    def test_returns_not_initialized_when_no_dag(self):
        """Test returns not_initialized status when pipeline_dag is None."""
        executor = ConcreteDAGExecutor()
        status = executor.get_dag_execution_status()
        self.assertEqual(status["status"], "not_initialized")

    def test_returns_running_when_pending_nodes_exist(self):
        """Test returns running status when there are pending nodes."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("filter"), FakeOperation("mapper")]
        executor._dag_ops = ops
        executor.dag_execution_strategy = NonPartitionedDAGStrategy()
        cfg = FakeConfig(work_dir=work_dir)
        executor._generate_dag_with_strategy(cfg)
        executor.dag_execution_start_time = time.time()

        status = executor.get_dag_execution_status()

        self.assertEqual(status["status"], "running")
        self.assertIn("summary", status)
        self.assertIn("execution_plan_length", status)

    def test_returns_completed_when_all_nodes_done(self):
        """Test returns completed status when no pending nodes."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("filter")]
        executor._dag_ops = ops
        executor.dag_execution_strategy = NonPartitionedDAGStrategy()
        cfg = FakeConfig(work_dir=work_dir)
        executor._generate_dag_with_strategy(cfg)

        # Mark all nodes completed
        executor._mark_dag_node_started("op_001_filter")
        executor._mark_dag_node_completed("op_001_filter", duration=1.0)

        status = executor.get_dag_execution_status()
        self.assertEqual(status["status"], "completed")

    def test_includes_dag_execution_start_time(self):
        """Test that dag_execution_start_time is included in status."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("filter")]
        executor._dag_ops = ops
        executor.dag_execution_strategy = NonPartitionedDAGStrategy()
        cfg = FakeConfig(work_dir=work_dir)
        executor._generate_dag_with_strategy(cfg)
        executor.dag_execution_start_time = 1234567890.0

        status = executor.get_dag_execution_status()
        self.assertEqual(status["dag_execution_start_time"], 1234567890.0)


class CalculateDAGStatisticsTest(DataJuicerTestCaseBase):
    """Tests for _calculate_dag_statistics()."""

    def test_empty_node_states(self):
        executor = ConcreteDAGExecutor()
        stats = executor._calculate_dag_statistics({})
        self.assertEqual(stats["total_nodes"], 0)
        self.assertEqual(stats["completion_percentage"], 0)

    def test_mixed_statuses(self):
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {"status": DAGNodeStatus.COMPLETED.value},
            "node_2": {"status": DAGNodeStatus.RUNNING.value},
            "node_3": {"status": DAGNodeStatus.FAILED.value},
            "node_4": {"status": DAGNodeStatus.PENDING.value},
            "node_5": {"status": DAGNodeStatus.PENDING.value},
        }

        stats = executor._calculate_dag_statistics(node_states)

        self.assertEqual(stats["total_nodes"], 5)
        self.assertEqual(stats["completed_nodes"], 1)
        self.assertEqual(stats["running_nodes"], 1)
        self.assertEqual(stats["failed_nodes"], 1)
        self.assertEqual(stats["pending_nodes"], 2)
        self.assertAlmostEqual(stats["completion_percentage"], 20.0)
        self.assertEqual(stats["ready_nodes"], 0)


class FindReadyNodesTest(DataJuicerTestCaseBase):
    """Tests for _find_ready_nodes()."""

    def test_empty_node_states(self):
        executor = ConcreteDAGExecutor()
        self.assertEqual(executor._find_ready_nodes({}), [])

    def test_pending_no_deps_is_ready(self):
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {"status": DAGNodeStatus.PENDING.value, "dependencies": []},
        }
        self.assertEqual(executor._find_ready_nodes(node_states), ["node_1"])

    def test_non_pending_statuses_excluded(self):
        """Running, completed, and failed nodes are never 'ready'."""
        executor = ConcreteDAGExecutor()
        node_states = {
            "a": {"status": DAGNodeStatus.RUNNING.value, "dependencies": []},
            "b": {"status": DAGNodeStatus.COMPLETED.value, "dependencies": []},
            "c": {"status": DAGNodeStatus.FAILED.value, "dependencies": []},
        }
        self.assertEqual(executor._find_ready_nodes(node_states), [])

    def test_incomplete_deps_blocks_node(self):
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {"status": DAGNodeStatus.PENDING.value, "dependencies": []},
            "node_2": {"status": DAGNodeStatus.PENDING.value, "dependencies": ["node_1"]},
        }
        self.assertEqual(executor._find_ready_nodes(node_states), ["node_1"])

    def test_diamond_dag_topology(self):
        """Diamond: A→B,C→D. D ready only after both B and C complete."""
        executor = ConcreteDAGExecutor()
        node_states = {
            "A": {"status": DAGNodeStatus.COMPLETED.value, "dependencies": []},
            "B": {"status": DAGNodeStatus.COMPLETED.value, "dependencies": ["A"]},
            "C": {"status": DAGNodeStatus.COMPLETED.value, "dependencies": ["A"]},
            "D": {"status": DAGNodeStatus.PENDING.value, "dependencies": ["B", "C"]},
        }
        self.assertEqual(executor._find_ready_nodes(node_states), ["D"])

    def test_missing_dep_treated_as_satisfied(self):
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_2": {"status": DAGNodeStatus.PENDING.value, "dependencies": ["missing"]},
        }
        self.assertEqual(executor._find_ready_nodes(node_states), ["node_2"])


class DetermineResumptionStrategyTest(DataJuicerTestCaseBase):
    """Tests for _determine_resumption_strategy()."""

    def test_priority_1_resume_from_failed_node(self):
        """Test that failed nodes have highest priority for resumption."""
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {
                "status": DAGNodeStatus.COMPLETED.value,
                "execution_order": 1,
            },
            "node_2": {
                "status": DAGNodeStatus.FAILED.value,
                "execution_order": 2,
            },
            "node_3": {
                "status": DAGNodeStatus.PENDING.value,
                "execution_order": 3,
            },
        }
        ready_nodes = ["node_3"]
        statistics = {
            "total_nodes": 3,
            "completed_nodes": 1,
            "failed_nodes": 1,
            "running_nodes": 0,
            "pending_nodes": 1,
        }

        result = executor._determine_resumption_strategy(
            node_states, ready_nodes, statistics
        )

        self.assertTrue(result["can_resume"])
        self.assertEqual(result["resume_from_node"], "node_2")
        self.assertIn("node_2", result["failed_nodes"])

    def test_priority_1_picks_earliest_failed_node(self):
        """Test that earliest (by execution_order) failed node is chosen."""
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {
                "status": DAGNodeStatus.FAILED.value,
                "execution_order": 3,
            },
            "node_2": {
                "status": DAGNodeStatus.FAILED.value,
                "execution_order": 1,
            },
            "node_3": {
                "status": DAGNodeStatus.FAILED.value,
                "execution_order": 2,
            },
        }
        ready_nodes = []
        statistics = {
            "total_nodes": 3,
            "completed_nodes": 0,
            "failed_nodes": 3,
            "running_nodes": 0,
            "pending_nodes": 0,
        }

        result = executor._determine_resumption_strategy(
            node_states, ready_nodes, statistics
        )

        self.assertTrue(result["can_resume"])
        self.assertEqual(result["resume_from_node"], "node_2")

    def test_priority_2_resume_from_running_node(self):
        """Test that running nodes are chosen when no failed nodes."""
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {
                "status": DAGNodeStatus.COMPLETED.value,
                "execution_order": 1,
            },
            "node_2": {
                "status": DAGNodeStatus.RUNNING.value,
                "execution_order": 2,
            },
            "node_3": {
                "status": DAGNodeStatus.PENDING.value,
                "execution_order": 3,
            },
        }
        ready_nodes = ["node_3"]
        statistics = {
            "total_nodes": 3,
            "completed_nodes": 1,
            "failed_nodes": 0,
            "running_nodes": 1,
            "pending_nodes": 1,
        }

        result = executor._determine_resumption_strategy(
            node_states, ready_nodes, statistics
        )

        self.assertTrue(result["can_resume"])
        self.assertEqual(result["resume_from_node"], "node_2")
        self.assertIn("node_2", result["running_nodes"])

    def test_priority_2_picks_earliest_running_node(self):
        """Test that earliest (by execution_order) running node is chosen."""
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {
                "status": DAGNodeStatus.RUNNING.value,
                "execution_order": 5,
            },
            "node_2": {
                "status": DAGNodeStatus.RUNNING.value,
                "execution_order": 2,
            },
        }
        ready_nodes = []
        statistics = {
            "total_nodes": 2,
            "completed_nodes": 0,
            "failed_nodes": 0,
            "running_nodes": 2,
            "pending_nodes": 0,
        }

        result = executor._determine_resumption_strategy(
            node_states, ready_nodes, statistics
        )

        self.assertTrue(result["can_resume"])
        self.assertEqual(result["resume_from_node"], "node_2")

    def test_priority_3_start_from_ready_nodes(self):
        """Test that ready nodes are chosen when no failed or running nodes."""
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {
                "status": DAGNodeStatus.COMPLETED.value,
                "execution_order": 1,
            },
            "node_2": {
                "status": DAGNodeStatus.PENDING.value,
                "execution_order": 2,
            },
            "node_3": {
                "status": DAGNodeStatus.PENDING.value,
                "execution_order": 3,
            },
        }
        ready_nodes = ["node_2", "node_3"]
        statistics = {
            "total_nodes": 3,
            "completed_nodes": 1,
            "failed_nodes": 0,
            "running_nodes": 0,
            "pending_nodes": 2,
        }

        result = executor._determine_resumption_strategy(
            node_states, ready_nodes, statistics
        )

        self.assertTrue(result["can_resume"])
        self.assertEqual(result["resume_from_node"], "node_2")
        self.assertEqual(sorted(result["ready_nodes"]), ["node_2", "node_3"])

    def test_priority_3_picks_earliest_ready_node(self):
        """Test that earliest (by execution_order) ready node is chosen."""
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {
                "status": DAGNodeStatus.PENDING.value,
                "execution_order": 10,
            },
            "node_2": {
                "status": DAGNodeStatus.PENDING.value,
                "execution_order": 3,
            },
            "node_3": {
                "status": DAGNodeStatus.PENDING.value,
                "execution_order": 7,
            },
        }
        ready_nodes = ["node_1", "node_2", "node_3"]
        statistics = {
            "total_nodes": 3,
            "completed_nodes": 0,
            "failed_nodes": 0,
            "running_nodes": 0,
            "pending_nodes": 3,
        }

        result = executor._determine_resumption_strategy(
            node_states, ready_nodes, statistics
        )

        self.assertTrue(result["can_resume"])
        self.assertEqual(result["resume_from_node"], "node_2")

    def test_all_completed_cannot_resume(self):
        """Test that can_resume is False when all nodes are completed."""
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {
                "status": DAGNodeStatus.COMPLETED.value,
                "execution_order": 1,
            },
            "node_2": {
                "status": DAGNodeStatus.COMPLETED.value,
                "execution_order": 2,
            },
        }
        ready_nodes = []
        statistics = {
            "total_nodes": 2,
            "completed_nodes": 2,
            "failed_nodes": 0,
            "running_nodes": 0,
            "pending_nodes": 0,
        }

        result = executor._determine_resumption_strategy(
            node_states, ready_nodes, statistics
        )

        self.assertFalse(result["can_resume"])
        self.assertIsNone(result["resume_from_node"])

    def test_failed_nodes_take_priority_over_running(self):
        """Test that failed nodes have priority over running nodes."""
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {
                "status": DAGNodeStatus.RUNNING.value,
                "execution_order": 1,
            },
            "node_2": {
                "status": DAGNodeStatus.FAILED.value,
                "execution_order": 2,
            },
        }
        ready_nodes = []
        statistics = {
            "total_nodes": 2,
            "completed_nodes": 0,
            "failed_nodes": 1,
            "running_nodes": 1,
            "pending_nodes": 0,
        }

        result = executor._determine_resumption_strategy(
            node_states, ready_nodes, statistics
        )

        self.assertTrue(result["can_resume"])
        # Failed nodes have priority (Priority 1) over running (Priority 2)
        self.assertEqual(result["resume_from_node"], "node_2")

    def test_result_contains_all_expected_keys(self):
        """Test that result dictionary contains all expected keys."""
        executor = ConcreteDAGExecutor()
        node_states = {
            "node_1": {
                "status": DAGNodeStatus.PENDING.value,
                "execution_order": 1,
            },
        }
        ready_nodes = ["node_1"]
        statistics = {
            "total_nodes": 1,
            "completed_nodes": 0,
            "failed_nodes": 0,
            "running_nodes": 0,
            "pending_nodes": 1,
        }

        result = executor._determine_resumption_strategy(
            node_states, ready_nodes, statistics
        )

        self.assertIn("can_resume", result)
        self.assertIn("resume_from_node", result)
        self.assertIn("ready_nodes", result)
        self.assertIn("failed_nodes", result)
        self.assertIn("running_nodes", result)


class InitializeNodeStatesFromPlanTest(DataJuicerTestCaseBase):
    """Tests for _initialize_node_states_from_plan()."""

    def test_empty_plan(self):
        """Test with empty plan (no nodes)."""
        executor = ConcreteDAGExecutor()
        dag_plan = {"nodes": {}}

        result = executor._initialize_node_states_from_plan(dag_plan)
        self.assertEqual(result, {})

    def test_initializes_nodes_with_pending_status(self):
        """Test that all nodes start with pending status."""
        executor = ConcreteDAGExecutor()
        dag_plan = {
            "nodes": {
                "op_001_filter": {
                    "op_name": "filter",
                    "op_type": "filter",
                    "execution_order": 1,
                    "dependencies": [],
                    "dependents": [],
                },
                "op_002_mapper": {
                    "op_name": "mapper",
                    "op_type": "mapper",
                    "execution_order": 2,
                    "dependencies": ["op_001_filter"],
                    "dependents": [],
                },
            }
        }

        result = executor._initialize_node_states_from_plan(dag_plan)

        self.assertEqual(len(result), 2)
        self.assertEqual(result["op_001_filter"]["status"], DAGNodeStatus.PENDING.value)
        self.assertEqual(result["op_002_mapper"]["status"], DAGNodeStatus.PENDING.value)

    def test_preserves_dependencies(self):
        """Test that dependencies are preserved from plan."""
        executor = ConcreteDAGExecutor()
        dag_plan = {
            "nodes": {
                "op_001_filter": {
                    "op_name": "filter",
                    "op_type": "filter",
                    "execution_order": 1,
                    "dependencies": [],
                    "dependents": ["op_002_mapper"],
                },
                "op_002_mapper": {
                    "op_name": "mapper",
                    "op_type": "mapper",
                    "execution_order": 2,
                    "dependencies": ["op_001_filter"],
                    "dependents": [],
                },
            }
        }

        result = executor._initialize_node_states_from_plan(dag_plan)

        self.assertEqual(result["op_001_filter"]["dependencies"], [])
        self.assertEqual(result["op_002_mapper"]["dependencies"], ["op_001_filter"])

    def test_initializes_timing_fields_to_none(self):
        """Test that timing fields are initialized to None/0."""
        executor = ConcreteDAGExecutor()
        dag_plan = {
            "nodes": {
                "op_001_filter": {
                    "op_name": "filter",
                    "op_type": "filter",
                    "execution_order": 1,
                    "dependencies": [],
                    "dependents": [],
                },
            }
        }

        result = executor._initialize_node_states_from_plan(dag_plan)

        self.assertIsNone(result["op_001_filter"]["start_time"])
        self.assertIsNone(result["op_001_filter"]["end_time"])
        self.assertEqual(result["op_001_filter"]["actual_duration"], 0.0)
        self.assertIsNone(result["op_001_filter"]["error_message"])


class GetDAGNodeForOperationTest(DataJuicerTestCaseBase):
    """Tests for _get_dag_node_for_operation()."""

    def test_returns_none_when_no_strategy(self):
        """Test returns None when dag_execution_strategy is None."""
        executor = ConcreteDAGExecutor()
        result = executor._get_dag_node_for_operation("filter", 0)
        self.assertIsNone(result)

    def test_returns_node_id_for_non_partitioned(self):
        """Test returns correct node ID for non-partitioned strategy."""
        executor = ConcreteDAGExecutor()
        executor.dag_execution_strategy = NonPartitionedDAGStrategy()

        result = executor._get_dag_node_for_operation("filter", 0)
        self.assertEqual(result, "op_001_filter")

    def test_returns_node_id_with_partition(self):
        """Test returns correct node ID with partition_id for partitioned strategy."""
        executor = ConcreteDAGExecutor(
            executor_type="ray_partitioned", num_partitions=3
        )
        executor.dag_execution_strategy = PartitionedDAGStrategy(num_partitions=3)

        result = executor._get_dag_node_for_operation(
            "filter", 0, partition_id=2
        )
        self.assertEqual(result, "op_001_filter_partition_2")


class DAGExecutionMixinIntegrationTest(DataJuicerTestCaseBase):
    """Integration tests for DAGExecutionMixin workflow."""

    def test_full_lifecycle_non_partitioned(self):
        """Test complete lifecycle: init -> start -> complete for all nodes."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [
            FakeOperation("text_filter"),
            FakeOperation("clean_mapper"),
            FakeOperation("length_filter"),
        ]
        cfg = FakeConfig(work_dir=work_dir, use_dag=True)

        # Initialize
        executor._initialize_dag_execution(cfg, ops)
        self.assertTrue(executor.dag_initialized)
        self.assertEqual(len(executor.pipeline_dag.nodes), 3)

        # Execute each node
        for i, op in enumerate(ops):
            node_id = f"op_{i+1:03d}_{op._name}"
            executor._mark_dag_node_started(node_id)
            self.assertEqual(executor.current_dag_node, node_id)
            executor._mark_dag_node_completed(node_id, duration=float(i + 1))

        # Verify final status
        status = executor.get_dag_execution_status()
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["summary"]["completed_nodes"], 3)

    def test_failure_mid_pipeline(self):
        """Test failure in the middle of pipeline execution."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [
            FakeOperation("filter"),
            FakeOperation("mapper"),
            FakeOperation("selector"),
        ]
        cfg = FakeConfig(work_dir=work_dir, use_dag=True)

        executor._initialize_dag_execution(cfg, ops)

        # Complete first node
        executor._mark_dag_node_started("op_001_filter")
        executor._mark_dag_node_completed("op_001_filter", duration=1.0)

        # Fail second node
        executor._mark_dag_node_started("op_002_mapper")
        executor._mark_dag_node_failed("op_002_mapper", "OOM error", duration=0.5)

        # Verify status
        status = executor.get_dag_execution_status()
        self.assertEqual(status["status"], "running")  # Still has pending nodes
        self.assertEqual(status["summary"]["completed_nodes"], 1)
        self.assertEqual(status["summary"]["failed_nodes"], 1)
        self.assertEqual(status["summary"]["pending_nodes"], 1)

    def test_multiple_initializations_only_first_takes_effect(self):
        """Test that calling _initialize_dag_execution multiple times only initializes once."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops1 = [FakeOperation("filter")]
        ops2 = [FakeOperation("mapper"), FakeOperation("selector")]
        cfg = FakeConfig(work_dir=work_dir, use_dag=True)

        executor._initialize_dag_execution(cfg, ops1)
        first_dag = executor.pipeline_dag

        # Second call should be a no-op
        executor._initialize_dag_execution(cfg, ops2)
        self.assertIs(executor.pipeline_dag, first_dag)
        self.assertEqual(len(executor.pipeline_dag.nodes), 1)

    def test_thread_safety_mark_operations(self):
        """Test that marking operations is thread-safe."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation(f"op_{i}") for i in range(10)]
        cfg = FakeConfig(work_dir=work_dir, use_dag=True)
        executor._initialize_dag_execution(cfg, ops)

        errors = []

        def mark_node(idx):
            try:
                node_id = f"op_{idx+1:03d}_op_{idx}"
                executor._mark_dag_node_started(node_id)
                time.sleep(0.01)
                executor._mark_dag_node_completed(node_id, duration=0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=mark_node, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        # All nodes should be completed
        status = executor.get_dag_execution_status()
        self.assertEqual(status["summary"]["completed_nodes"], 10)


class VisualizeDAGExecutionPlanTest(DataJuicerTestCaseBase):
    """Tests for visualize_dag_execution_plan()."""

    def test_returns_message_when_no_dag(self):
        """Test returns message when pipeline_dag is not initialized."""
        executor = ConcreteDAGExecutor()
        result = executor.visualize_dag_execution_plan()
        self.assertEqual(result, "Pipeline DAG not initialized")

    def test_returns_visualization_string(self):
        """Test returns non-empty visualization when DAG exists."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("filter"), FakeOperation("mapper")]
        executor._dag_ops = ops
        executor.dag_execution_strategy = NonPartitionedDAGStrategy()
        cfg = FakeConfig(work_dir=work_dir)
        executor._generate_dag_with_strategy(cfg)

        result = executor.visualize_dag_execution_plan()

        self.assertIn("DAG Execution Plan", result)
        self.assertIn("filter", result)
        self.assertIn("mapper", result)


class GetDAGExecutionPlanPathTest(DataJuicerTestCaseBase):
    """Tests for get_dag_execution_plan_path()."""

    def test_returns_empty_string_when_no_dag_and_no_cfg(self):
        """Test returns empty string when no DAG and no cfg."""
        executor = ConcreteDAGExecutor()
        result = executor.get_dag_execution_plan_path()
        self.assertEqual(result, "")

    def test_returns_path_from_cfg_work_dir(self):
        """Test returns path constructed from cfg.work_dir when no DAG."""
        executor = ConcreteDAGExecutor()
        executor.cfg = FakeConfig(work_dir="/tmp/test_work_dir")
        result = executor.get_dag_execution_plan_path()
        self.assertEqual(result, "/tmp/test_work_dir/dag_execution_plan.json")

    def test_returns_path_from_pipeline_dag(self):
        """Test returns path from pipeline_dag.dag_dir when DAG exists."""
        work_dir = tempfile.mkdtemp()
        executor = ConcreteDAGExecutor(executor_type="ray")
        ops = [FakeOperation("filter")]
        executor._dag_ops = ops
        executor.dag_execution_strategy = NonPartitionedDAGStrategy()
        cfg = FakeConfig(work_dir=work_dir)
        executor._generate_dag_with_strategy(cfg)

        result = executor.get_dag_execution_plan_path()
        expected = os.path.join(work_dir, "dag_execution_plan.json")
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
