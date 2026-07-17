import json
import os
import tempfile
import unittest

from data_juicer.core.executor.dag_execution_mixin import DAGExecutionMixin
from data_juicer.core.executor.pipeline_dag import DAGNodeStatus, PipelineDAG
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


def _make_mixin(**attrs):
    """Create a DAGExecutionMixin instance with optional attributes."""
    m = DAGExecutionMixin.__new__(DAGExecutionMixin)
    DAGExecutionMixin.__init__(m)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def _make_dag(work_dir, nodes=None):
    """Create a PipelineDAG with optional preset nodes."""
    dag = PipelineDAG(work_dir)
    if nodes:
        dag.nodes = nodes
    return dag


def _node(node_id, op_name='op', status='pending', deps=None, order=0,
          op_type='operation', **extra):
    """Create a standard DAG node dict."""
    n = {
        'node_id': node_id,
        'op_name': op_name,
        'operation_name': op_name,
        'op_type': op_type,
        'node_type': op_type,
        'status': status,
        'execution_order': order,
        'dependencies': deps or [],
        'dependents': [],
        'start_time': None,
        'end_time': None,
        'actual_duration': 0.0,
        'error_message': None,
    }
    n.update(extra)
    return n


class IsPartitionedExecutorTest(DataJuicerTestCaseBase):

    def test_default_not_partitioned(self):
        m = _make_mixin()
        self.assertFalse(m._is_partitioned_executor())

    def test_ray_partitioned(self):
        m = _make_mixin(executor_type='ray_partitioned')
        self.assertTrue(m._is_partitioned_executor())

    def test_other_type(self):
        m = _make_mixin(executor_type='default')
        self.assertFalse(m._is_partitioned_executor())


class ExtractOperationTypesTest(DataJuicerTestCaseBase):

    def _op(self, name):
        class FakeOp:
            pass
        o = FakeOp()
        o._name = name
        return o

    def test_classifies_by_suffix(self):
        ops = [
            self._op('text_length_filter'),
            self._op('clean_email_mapper'),
            self._op('document_deduplicator'),
            self._op('frequency_selector'),
            self._op('key_value_grouper'),
            self._op('meta_aggregator'),
        ]
        m = _make_mixin()
        types = m._extract_operation_types_from_ops(ops)
        for t in ['filter', 'mapper', 'deduplicator', 'selector',
                   'grouper', 'aggregator']:
            self.assertIn(t, types)

    def test_empty_ops(self):
        m = _make_mixin()
        self.assertEqual(m._extract_operation_types_from_ops([]), [])

    def test_unknown_suffix_uses_isinstance(self):
        from data_juicer.ops.base_op import Filter
        from data_juicer.ops.filter import AverageLineLengthFilter
        op = AverageLineLengthFilter()
        m = _make_mixin()
        types = m._extract_operation_types_from_ops([op])
        self.assertIn('filter', types)


class GetDagExecutionStatusTest(DataJuicerTestCaseBase):

    def test_not_initialized(self):
        m = _make_mixin()
        status = m.get_dag_execution_status()
        self.assertEqual(status['status'], 'not_initialized')

    def test_with_dag(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp, {
            'n1': _node('n1', status='completed'),
            'n2': _node('n2', status='completed'),
        })
        m = _make_mixin(pipeline_dag=dag, dag_execution_start_time=1000.0)
        status = m.get_dag_execution_status()
        self.assertEqual(status['status'], 'completed')
        self.assertEqual(status['summary']['completed_nodes'], 2)
        self.assertEqual(status['dag_execution_start_time'], 1000.0)

    def test_pending_means_running(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp, {
            'n1': _node('n1', status='completed'),
            'n2': _node('n2', status='pending'),
        })
        m = _make_mixin(pipeline_dag=dag, dag_execution_start_time=None)
        status = m.get_dag_execution_status()
        self.assertEqual(status['status'], 'running')


class VisualizeDagTest(DataJuicerTestCaseBase):

    def test_not_initialized(self):
        m = _make_mixin()
        self.assertEqual(m.visualize_dag_execution_plan(),
                         'Pipeline DAG not initialized')

    def test_with_dag(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp, {'n1': _node('n1')})
        m = _make_mixin(pipeline_dag=dag)
        result = m.visualize_dag_execution_plan()
        self.assertIsInstance(result, str)


class GetDagExecutionPlanPathTest(DataJuicerTestCaseBase):

    def test_with_dag(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp)
        m = _make_mixin(pipeline_dag=dag)
        path = m.get_dag_execution_plan_path()
        self.assertTrue(path.endswith('dag_execution_plan.json'))

    def test_without_dag_with_cfg(self):
        class FakeCfg:
            work_dir = '/tmp/test_work'
        m = _make_mixin(cfg=FakeCfg())
        path = m.get_dag_execution_plan_path()
        self.assertIn('dag_execution_plan.json', path)
        self.assertIn('/tmp/test_work', path)

    def test_without_dag_without_cfg(self):
        m = _make_mixin()
        path = m.get_dag_execution_plan_path()
        self.assertEqual(path, '')


class MarkDagNodeStartedTest(DataJuicerTestCaseBase):

    def test_marks_node_started(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp, {'n1': _node('n1')})
        m = _make_mixin(pipeline_dag=dag)
        m._mark_dag_node_started('n1')
        self.assertEqual(dag.nodes['n1']['status'], DAGNodeStatus.RUNNING.value)
        self.assertEqual(m.current_dag_node, 'n1')

    def test_nonexistent_node_no_error(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp, {'n1': _node('n1')})
        m = _make_mixin(pipeline_dag=dag)
        m._mark_dag_node_started('nonexistent')

    def test_no_dag_no_error(self):
        m = _make_mixin()
        m._mark_dag_node_started('n1')


class MarkDagNodeCompletedTest(DataJuicerTestCaseBase):

    def test_marks_completed(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp, {'n1': _node('n1', status='running')})
        m = _make_mixin(pipeline_dag=dag, current_dag_node='n1')
        m._mark_dag_node_completed('n1', duration=5.0)
        self.assertEqual(dag.nodes['n1']['status'],
                         DAGNodeStatus.COMPLETED.value)
        self.assertIsNone(m.current_dag_node)

    def test_nonexistent_node_no_error(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp)
        m = _make_mixin(pipeline_dag=dag)
        m._mark_dag_node_completed('nope')

    def test_no_dag_no_error(self):
        m = _make_mixin()
        m._mark_dag_node_completed('n1')


class MarkDagNodeFailedTest(DataJuicerTestCaseBase):

    def test_marks_failed(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp, {'n1': _node('n1', status='running')})
        m = _make_mixin(pipeline_dag=dag, current_dag_node='n1')
        m._mark_dag_node_failed('n1', 'boom')
        self.assertEqual(dag.nodes['n1']['status'],
                         DAGNodeStatus.FAILED.value)
        self.assertIsNone(m.current_dag_node)

    def test_nonexistent_node_no_error(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp)
        m = _make_mixin(pipeline_dag=dag)
        m._mark_dag_node_failed('nope', 'err')

    def test_no_dag_no_error(self):
        m = _make_mixin()
        m._mark_dag_node_failed('n1', 'err')


class InitializeNodeStatesFromPlanTest(DataJuicerTestCaseBase):

    def test_initializes_from_plan(self):
        plan = {
            'nodes': {
                'n1': {
                    'op_name': 'filter_a',
                    'op_type': 'filter',
                    'execution_order': 0,
                    'dependencies': [],
                    'dependents': ['n2'],
                },
                'n2': {
                    'op_name': 'mapper_b',
                    'op_type': 'mapper',
                    'execution_order': 1,
                    'dependencies': ['n1'],
                    'dependents': [],
                },
            }
        }
        m = _make_mixin()
        states = m._initialize_node_states_from_plan(plan)
        self.assertEqual(len(states), 2)
        self.assertEqual(states['n1']['status'], 'pending')
        self.assertEqual(states['n1']['op_name'], 'filter_a')
        self.assertEqual(states['n2']['dependencies'], ['n1'])
        self.assertIsNone(states['n1']['start_time'])

    def test_empty_plan(self):
        m = _make_mixin()
        states = m._initialize_node_states_from_plan({'nodes': {}})
        self.assertEqual(states, {})

    def test_missing_optional_fields(self):
        plan = {'nodes': {'n1': {}}}
        m = _make_mixin()
        states = m._initialize_node_states_from_plan(plan)
        self.assertIsNone(states['n1']['op_name'])
        self.assertEqual(states['n1']['execution_order'], -1)
        self.assertEqual(states['n1']['dependencies'], [])


class HandleDagNodeStartEventTest(DataJuicerTestCaseBase):

    def test_updates_status(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'pending', 'start_time': None},
        }
        event = {
            'metadata': {'dag_node_id': 'n1'},
            'timestamp': 100.0,
        }
        m._handle_dag_node_start_event(event, states)
        self.assertEqual(states['n1']['status'], DAGNodeStatus.RUNNING.value)
        self.assertEqual(states['n1']['start_time'], 100.0)

    def test_unknown_node_ignored(self):
        m = _make_mixin()
        states = {'n1': {'status': 'pending', 'start_time': None}}
        event = {'metadata': {'dag_node_id': 'unknown'}, 'timestamp': 0}
        m._handle_dag_node_start_event(event, states)
        self.assertEqual(states['n1']['status'], 'pending')

    def test_no_node_id_ignored(self):
        m = _make_mixin()
        states = {'n1': {'status': 'pending', 'start_time': None}}
        m._handle_dag_node_start_event({'metadata': {}}, states)
        self.assertEqual(states['n1']['status'], 'pending')


class HandleDagNodeCompleteEventTest(DataJuicerTestCaseBase):

    def test_updates_status(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'running', 'end_time': None,
                    'actual_duration': 0.0},
        }
        event = {
            'metadata': {'dag_node_id': 'n1'},
            'timestamp': 200.0,
            'duration': 5.5,
        }
        m._handle_dag_node_complete_event(event, states)
        self.assertEqual(states['n1']['status'],
                         DAGNodeStatus.COMPLETED.value)
        self.assertEqual(states['n1']['end_time'], 200.0)
        self.assertEqual(states['n1']['actual_duration'], 5.5)


class HandleDagNodeFailedEventTest(DataJuicerTestCaseBase):

    def test_updates_status_and_error(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'running', 'end_time': None,
                    'actual_duration': 0.0, 'error_message': None},
        }
        event = {
            'metadata': {'dag_node_id': 'n1'},
            'timestamp': 300.0,
            'duration': 1.0,
            'error_message': 'OOM',
        }
        m._handle_dag_node_failed_event(event, states)
        self.assertEqual(states['n1']['status'], DAGNodeStatus.FAILED.value)
        self.assertEqual(states['n1']['error_message'], 'OOM')


class HandleOperationEventTest(DataJuicerTestCaseBase):

    def test_op_start(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'pending', 'start_time': None,
                    'end_time': None, 'actual_duration': 0.0,
                    'error_message': None},
        }
        from data_juicer.core.executor.event_logging_mixin import EventType
        event = {
            'event_type': EventType.OP_START.value,
            'metadata': {'dag_context': {'dag_node_id': 'n1'}},
            'timestamp': 10.0,
        }
        m._handle_operation_event(event, states)
        self.assertEqual(states['n1']['status'], DAGNodeStatus.RUNNING.value)

    def test_op_complete(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'running', 'start_time': 10.0,
                    'end_time': None, 'actual_duration': 0.0,
                    'error_message': None},
        }
        from data_juicer.core.executor.event_logging_mixin import EventType
        event = {
            'event_type': EventType.OP_COMPLETE.value,
            'metadata': {'dag_context': {'dag_node_id': 'n1'}},
            'timestamp': 20.0,
            'duration': 10.0,
        }
        m._handle_operation_event(event, states)
        self.assertEqual(states['n1']['status'],
                         DAGNodeStatus.COMPLETED.value)
        self.assertEqual(states['n1']['actual_duration'], 10.0)

    def test_op_failed(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'running', 'start_time': 10.0,
                    'end_time': None, 'actual_duration': 0.0,
                    'error_message': None},
        }
        from data_juicer.core.executor.event_logging_mixin import EventType
        event = {
            'event_type': EventType.OP_FAILED.value,
            'metadata': {'dag_context': {'dag_node_id': 'n1'}},
            'timestamp': 15.0,
            'duration': 5.0,
            'error_message': 'fail',
        }
        m._handle_operation_event(event, states)
        self.assertEqual(states['n1']['status'], DAGNodeStatus.FAILED.value)
        self.assertEqual(states['n1']['error_message'], 'fail')

    def test_no_dag_context_ignored(self):
        m = _make_mixin()
        states = {'n1': {'status': 'pending'}}
        from data_juicer.core.executor.event_logging_mixin import EventType
        event = {
            'event_type': EventType.OP_START.value,
            'metadata': {},
        }
        m._handle_operation_event(event, states)
        self.assertEqual(states['n1']['status'], 'pending')


class UpdateNodeStatesFromEventsTest(DataJuicerTestCaseBase):

    def test_processes_multiple_events(self):
        m = _make_mixin()
        from data_juicer.core.executor.event_logging_mixin import EventType
        states = {
            'n1': {'status': 'pending', 'start_time': None,
                    'end_time': None, 'actual_duration': 0.0,
                    'error_message': None},
            'n2': {'status': 'pending', 'start_time': None,
                    'end_time': None, 'actual_duration': 0.0,
                    'error_message': None},
        }
        events = [
            {'event_type': EventType.DAG_NODE_START.value,
             'metadata': {'dag_node_id': 'n1'}, 'timestamp': 1.0},
            {'event_type': EventType.DAG_NODE_COMPLETE.value,
             'metadata': {'dag_node_id': 'n1'}, 'timestamp': 2.0,
             'duration': 1.0},
            {'event_type': EventType.DAG_NODE_START.value,
             'metadata': {'dag_node_id': 'n2'}, 'timestamp': 2.0},
        ]
        m._update_node_states_from_events(states, events)
        self.assertEqual(states['n1']['status'], 'completed')
        self.assertEqual(states['n2']['status'], 'running')


class CalculateDagStatisticsTest(DataJuicerTestCaseBase):

    def test_mixed_states(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'completed'},
            'n2': {'status': 'completed'},
            'n3': {'status': 'failed'},
            'n4': {'status': 'running'},
            'n5': {'status': 'pending'},
        }
        stats = m._calculate_dag_statistics(states)
        self.assertEqual(stats['total_nodes'], 5)
        self.assertEqual(stats['completed_nodes'], 2)
        self.assertEqual(stats['failed_nodes'], 1)
        self.assertEqual(stats['running_nodes'], 1)
        self.assertEqual(stats['pending_nodes'], 1)
        self.assertAlmostEqual(stats['completion_percentage'], 40.0)

    def test_empty(self):
        m = _make_mixin()
        stats = m._calculate_dag_statistics({})
        self.assertEqual(stats['total_nodes'], 0)
        self.assertEqual(stats['completion_percentage'], 0)

    def test_all_completed(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'completed'},
            'n2': {'status': 'completed'},
        }
        stats = m._calculate_dag_statistics(states)
        self.assertAlmostEqual(stats['completion_percentage'], 100.0)


class FindReadyNodesTest(DataJuicerTestCaseBase):

    def test_no_deps_all_ready(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'pending', 'dependencies': []},
            'n2': {'status': 'pending', 'dependencies': []},
        }
        ready = m._find_ready_nodes(states)
        self.assertEqual(set(ready), {'n1', 'n2'})

    def test_deps_not_met(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'pending', 'dependencies': []},
            'n2': {'status': 'pending', 'dependencies': ['n1']},
        }
        ready = m._find_ready_nodes(states)
        self.assertEqual(ready, ['n1'])

    def test_deps_completed(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'completed', 'dependencies': []},
            'n2': {'status': 'pending', 'dependencies': ['n1']},
        }
        ready = m._find_ready_nodes(states)
        self.assertEqual(ready, ['n2'])

    def test_completed_nodes_excluded(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'completed', 'dependencies': []},
        }
        ready = m._find_ready_nodes(states)
        self.assertEqual(ready, [])

    def test_chain_only_first_ready(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'pending', 'dependencies': []},
            'n2': {'status': 'pending', 'dependencies': ['n1']},
            'n3': {'status': 'pending', 'dependencies': ['n2']},
        }
        ready = m._find_ready_nodes(states)
        self.assertEqual(ready, ['n1'])


class DetermineResumptionStrategyTest(DataJuicerTestCaseBase):

    def test_resume_from_failed(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'completed', 'execution_order': 0},
            'n2': {'status': 'failed', 'execution_order': 1},
            'n3': {'status': 'pending', 'execution_order': 2},
        }
        stats = {'failed_nodes': 1, 'running_nodes': 0,
                 'completed_nodes': 1, 'total_nodes': 3}
        result = m._determine_resumption_strategy(states, ['n3'], stats)
        self.assertTrue(result['can_resume'])
        self.assertEqual(result['resume_from_node'], 'n2')

    def test_resume_from_running(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'completed', 'execution_order': 0},
            'n2': {'status': 'running', 'execution_order': 1},
        }
        stats = {'failed_nodes': 0, 'running_nodes': 1,
                 'completed_nodes': 1, 'total_nodes': 2}
        result = m._determine_resumption_strategy(states, [], stats)
        self.assertTrue(result['can_resume'])
        self.assertEqual(result['resume_from_node'], 'n2')

    def test_resume_from_ready(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'completed', 'execution_order': 0},
            'n2': {'status': 'pending', 'execution_order': 1},
            'n3': {'status': 'pending', 'execution_order': 2},
        }
        stats = {'failed_nodes': 0, 'running_nodes': 0,
                 'completed_nodes': 1, 'total_nodes': 3}
        result = m._determine_resumption_strategy(
            states, ['n2', 'n3'], stats)
        self.assertTrue(result['can_resume'])
        self.assertEqual(result['resume_from_node'], 'n2')

    def test_all_completed_cannot_resume(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'completed', 'execution_order': 0},
            'n2': {'status': 'completed', 'execution_order': 1},
        }
        stats = {'failed_nodes': 0, 'running_nodes': 0,
                 'completed_nodes': 2, 'total_nodes': 2}
        result = m._determine_resumption_strategy(states, [], stats)
        self.assertFalse(result['can_resume'])

    def test_failed_priority_over_running(self):
        m = _make_mixin()
        states = {
            'n1': {'status': 'running', 'execution_order': 0},
            'n2': {'status': 'failed', 'execution_order': 1},
        }
        stats = {'failed_nodes': 1, 'running_nodes': 1,
                 'completed_nodes': 0, 'total_nodes': 2}
        result = m._determine_resumption_strategy(states, [], stats)
        self.assertEqual(result['resume_from_node'], 'n2')


class LoadDagExecutionPlanTest(DataJuicerTestCaseBase):

    def test_valid_plan(self):
        tmp = tempfile.mkdtemp()
        plan = {'nodes': {'n1': {'op_name': 'test'}}}
        plan_path = os.path.join(tmp, 'dag_execution_plan.json')
        with open(plan_path, 'w') as f:
            json.dump(plan, f)

        dag = _make_dag(tmp)
        m = _make_mixin(pipeline_dag=dag)
        result = m._load_dag_execution_plan()
        self.assertEqual(result, plan)

    def test_missing_plan(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp)
        m = _make_mixin(pipeline_dag=dag)
        result = m._load_dag_execution_plan()
        self.assertIsNone(result)

    def test_corrupt_json(self):
        tmp = tempfile.mkdtemp()
        plan_path = os.path.join(tmp, 'dag_execution_plan.json')
        with open(plan_path, 'w') as f:
            f.write('{invalid json')

        dag = _make_dag(tmp)
        m = _make_mixin(pipeline_dag=dag)
        result = m._load_dag_execution_plan()
        self.assertIsNone(result)


class LogOperationWithDagContextTest(DataJuicerTestCaseBase):

    def test_op_start_dispatches(self):
        calls = []

        def fake_log_op_start(pid, name, idx, meta):
            calls.append(('start', pid, name, idx, meta))

        m = _make_mixin(dag_execution_strategy=None)
        m.log_op_start = fake_log_op_start
        m._log_operation_with_dag_context('test_op', 0, 'op_start',
                                          partition_id=1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 'start')
        self.assertEqual(calls[0][1], 1)
        self.assertEqual(calls[0][2], 'test_op')

    def test_op_complete_dispatches(self):
        calls = []

        def fake_log_op_complete(pid, name, idx, dur, cp, inp, out):
            calls.append(('complete', dur))

        m = _make_mixin(dag_execution_strategy=None)
        m.log_op_complete = fake_log_op_complete
        m._log_operation_with_dag_context('op', 0, 'op_complete',
                                          duration=3.0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], 3.0)

    def test_op_failed_dispatches(self):
        calls = []

        def fake_log_op_failed(pid, name, idx, err, retry):
            calls.append(('failed', err))

        m = _make_mixin(dag_execution_strategy=None)
        m.log_op_failed = fake_log_op_failed
        m._log_operation_with_dag_context('op', 0, 'op_failed',
                                          error='boom')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], 'boom')


class ReconstructDagStateTest(DataJuicerTestCaseBase):

    def test_no_event_logger(self):
        m = _make_mixin()
        result = m.reconstruct_dag_state_from_events('job1')
        self.assertIsNone(result)

    def test_no_plan_file(self):
        tmp = tempfile.mkdtemp()
        dag = _make_dag(tmp)

        class FakeEventLogger:
            def get_events(self, event_type=None):
                return []

        m = _make_mixin(pipeline_dag=dag, event_logger=FakeEventLogger())
        result = m.reconstruct_dag_state_from_events('job1')
        self.assertIsNone(result)

    def test_full_reconstruction(self):
        tmp = tempfile.mkdtemp()
        plan = {
            'nodes': {
                'n1': {
                    'op_name': 'filter_a', 'op_type': 'filter',
                    'execution_order': 0, 'dependencies': [],
                    'dependents': ['n2'],
                },
                'n2': {
                    'op_name': 'mapper_b', 'op_type': 'mapper',
                    'execution_order': 1, 'dependencies': ['n1'],
                    'dependents': [],
                },
            },
            'execution_plan': ['n1', 'n2'],
            'parallel_groups': [],
        }
        plan_path = os.path.join(tmp, 'dag_execution_plan.json')
        with open(plan_path, 'w') as f:
            json.dump(plan, f)

        from data_juicer.core.executor.event_logging_mixin import EventType
        dag = _make_dag(tmp)

        class FakeEventLogger:
            def get_events(self, event_type=None):
                return [
                    {'event_type': EventType.DAG_NODE_START.value,
                     'metadata': {'dag_node_id': 'n1'}, 'timestamp': 1.0},
                    {'event_type': EventType.DAG_NODE_COMPLETE.value,
                     'metadata': {'dag_node_id': 'n1'}, 'timestamp': 2.0,
                     'duration': 1.0},
                ]

        m = _make_mixin(pipeline_dag=dag, event_logger=FakeEventLogger())
        result = m.reconstruct_dag_state_from_events('job1')

        self.assertIsNotNone(result)
        self.assertEqual(result['job_id'], 'job1')
        self.assertEqual(result['node_states']['n1']['status'], 'completed')
        self.assertEqual(result['node_states']['n2']['status'], 'pending')
        self.assertTrue(result['resumption']['can_resume'])
        self.assertEqual(result['resumption']['resume_from_node'], 'n2')
        self.assertEqual(result['statistics']['completed_nodes'], 1)
        self.assertIn('n2', result['resumption']['ready_nodes'])


class CreateExecutionStrategyTest(DataJuicerTestCaseBase):

    def test_non_partitioned(self):
        from data_juicer.core.executor.dag_execution_strategies import (
            NonPartitionedDAGStrategy,
        )
        m = _make_mixin()

        class FakeCfg:
            pass

        strategy = m._create_execution_strategy(FakeCfg())
        self.assertIsInstance(strategy, NonPartitionedDAGStrategy)

    def test_partitioned_needs_num_partitions(self):
        m = _make_mixin(executor_type='ray_partitioned')

        class FakeCfg:
            pass

        with self.assertRaises(ValueError):
            m._create_execution_strategy(FakeCfg())

    def test_partitioned_with_num(self):
        from data_juicer.core.executor.dag_execution_strategies import (
            PartitionedDAGStrategy,
        )
        m = _make_mixin(executor_type='ray_partitioned', num_partitions=4)

        class FakeCfg:
            pass

        strategy = m._create_execution_strategy(FakeCfg())
        self.assertIsInstance(strategy, PartitionedDAGStrategy)


class PrePostExecuteMonitoringTest(DataJuicerTestCaseBase):

    def test_pre_execute_no_dag_noop(self):
        m = _make_mixin()
        m._pre_execute_operations_with_dag_monitoring([])

    def test_post_execute_no_dag_noop(self):
        m = _make_mixin()
        m._post_execute_operations_with_dag_monitoring([])


if __name__ == '__main__':
    unittest.main()
